#!/usr/bin/env python3
"""Conservative Lua 5.4 post-return reward-append bytecode experiment.

Proof-of-concept for synthetic Lua 5.4 chunks. For Violet 4.0.0, input must
match the exact retail main.blua SHA-256, the prototype path and code offset,
and the chosen PC must return exactly one value (RETURN B=2 or RETURN1). No game deployment is
claimed. Always run only on your own legally extracted game file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import argparse
import hashlib
import json
from pathlib import Path
import struct

ORIGINAL_SHA = 'c1a4f4e2625912cf0b739a642a79ba3357df0557a544b92da22a6cb139de2815'
LUA_HEADER = bytes.fromhex('1b4c7561540019930d0a1a0a040808') + struct.pack('<q', 0x5678) + struct.pack('<d', 370.5)
OP_MOVE, OP_GETTABUP, OP_CALL, OP_RETURN, OP_RETURN1, OP_CLOSURE, OP_JMP = 0, 11, 68, 70, 72, 79, 56
MAX_ARG_BX = (1 << 17) - 1
OFFSET_SJ = ((1 << 25) - 1) // 2
MAX_SIZE = 64 * 1024 * 1024

# Independent upvalue-free Lua 5.4 helper. Gameplay ABI requires device verification.
DEFAULT_HELPER_SOURCE = '''return function(reward)
  if reward == nil then return end
  local rows = reward[3]
  if rows == nil or rows.length == nil or rows.length >= 45 then return end
  local names = { ItemNo=true, ItemNum=true, rareType=true, subjectType=true }
  local item = { ItemNo=492, ItemNum=1, rareType=0, subjectType=5, __fields__=names }
  rows:push(item)
end'''


def encvar(n: int) -> bytes:
    if not isinstance(n, int) or n < 0 or n > 0x7FFFFFFFFFFFFFFF:
        raise ValueError('invalid Lua varuint')
    parts = [n & 127]
    n >>= 7
    while n:
        parts.append(n & 127)
        n >>= 7
    parts.reverse()
    parts[-1] |= 0x80
    return bytes(parts)


@dataclass
class Proto:
    path: str
    start: int
    code_len_pos: int
    code_len_end: int
    code_start: int
    code_end: int
    code_count: int
    maxstack_pos: int
    maxstack: int
    children_len_pos: int
    children_len_end: int
    children_insert_pos: int
    line_len_pos: int
    line_len_end: int
    line_data_end: int
    line_count: int
    end: int = 0
    children: list['Proto'] = field(default_factory=list)


class Reader:
    def __init__(self, raw: bytes):
        if not raw or len(raw) > MAX_SIZE: raise ValueError('invalid chunk size')
        self.raw = raw
        self.pos = 0
        self.proto_count = 0
    def read(self, n):
        if n < 0 or self.pos + n > len(self.raw): raise ValueError(f'truncated chunk 0x{self.pos:x}')
        out = self.raw[self.pos:self.pos+n]
        self.pos += n
        return out
    def u8(self): return self.read(1)[0]
    def var(self):
        v = 0
        for _ in range(10):
            b = self.u8()
            v = (v << 7) | (b & 127)
            if b & 128: return v
        raise ValueError('overlong varuint')
    def strings(self):
        n = self.var()
        if n: self.read(n-1)
    def proto(self, path='root', depth=0):
        if depth > 512 or self.proto_count > 1_000_000: raise ValueError('Prototype nesting too large')
        self.proto_count += 1
        start = self.pos
        self.strings()
        self.var(); self.var()
        self.u8(); self.u8()
        maxstack_pos = self.pos
        maxstack = self.u8()
        code_len_pos = self.pos
        code_count = self.var()
        code_len_end = self.pos
        code_start = self.pos
        if code_count > (len(self.raw) - self.pos)//4: raise ValueError('truncated instruction array')
        self.read(code_count * 4)
        code_end = self.pos
        for _ in range(self.var()):
            tag = self.u8()
            if tag in (0,1,17): continue
            if tag in (3,19): self.read(8); continue
            if tag in (4,20): self.strings(); continue
            raise ValueError(f'unknown constant tag {tag}')
        upvalue_count = self.var()
        self.read(upvalue_count * 3)
        children_len_pos = self.pos
        nchildren = self.var()
        children_len_end = self.pos
        children = [self.proto(path + '/' + str(i), depth+1) for i in range(nchildren)]
        children_insert_pos = self.pos
        line_len_pos = self.pos
        line_count = self.var()
        line_len_end = self.pos
        self.read(line_count)
        line_data_end = self.pos
        for _ in range(self.var()): self.var(); self.var()
        for _ in range(self.var()): self.strings(); self.var(); self.var()
        for _ in range(self.var()): self.strings()
        return Proto(path,start,code_len_pos,code_len_end,code_start,code_end,
                     code_count,maxstack_pos,maxstack,children_len_pos,children_len_end,
                     children_insert_pos,line_len_pos,line_len_end,line_data_end,
                     line_count,self.pos,children)


def parse(raw: bytes) -> Proto:
    r = Reader(raw)
    header = r.read(len(LUA_HEADER))
    if header != LUA_HEADER: raise ValueError('requires standard little-endian Lua 5.4 chunk')
    r.u8()
    tree = r.proto()
    if r.pos != len(raw): raise ValueError('trailing bytes')
    return tree


def get_proto(root: Proto, path: str) -> Proto:
    parts = path.split('/')
    if parts[0] != 'root': raise ValueError('Prototype path must start at root')
    cur = root
    for part in parts[1:]:
        if not part.isdecimal() or int(part) >= len(cur.children):
            raise ValueError(f'Prototype path missing: {path}')
        cur = cur.children[int(part)]
    return cur


def word(raw, node, pc):
    if pc < 0 or pc >= node.code_count: raise ValueError('PC out of bounds')
    return struct.unpack_from('<I', raw, node.code_start+4*pc)[0]


def code_abc(op, a=0, b=0, c=0, k=0):
    if any(not 0 <= v <= 255 for v in (a,b,c)) or k not in (0,1):
        raise ValueError('invalid register/opcode operands')
    return op | (a << 7) | (k << 15) | (b << 16) | (c << 24)


def code_abx(op, a, bx):
    if not 0 <= a <= 255 or not 0 <= bx <= MAX_ARG_BX:
        raise ValueError('invalid ABx operands')
    return op | (a << 7) | (bx << 15)


def code_jmp(delta):
    if not -OFFSET_SJ <= delta <= OFFSET_SJ:
        raise ValueError('Lua JMP relative displacement out of range')
    return OP_JMP | ((delta + OFFSET_SJ) << 7)


def splices(raw: bytes, edits: list[tuple[int,int,bytes]]) -> bytes:
    out = bytearray(raw)
    nonempty = sorted((start,end) for start,end,_ in edits if end>start)
    for (a,b),(c,d) in zip(nonempty,nonempty[1:]):
        if b>c: raise ValueError('overlapping repack replacements')
    for start,end,value in sorted(edits, key=lambda e:(e[0],e[1]), reverse=True):
        if start < 0 or end < start or end > len(raw):
            raise ValueError('invalid repack splice')
        out[start:end] = value
    return bytes(out)


def graft_tail(raw: bytes, path: str, return_pc: int, helper_chunk: bytes,
               *, guard_sha: str | None = None,
               expected_code_start: int | None = None) -> tuple[bytes, dict]:
    if guard_sha and hashlib.sha256(raw).hexdigest() != guard_sha.lower():
        raise ValueError('main.blua SHA-256 identity check FAILED')
    root = parse(raw)
    target = get_proto(root, path)
    if expected_code_start is not None and target.code_start != expected_code_start:
        raise ValueError('Prototype code_start differs from pinned 4.0.0 anchor')
    candidate = word(raw,target,return_pc)
    opcode = candidate & 127
    is_single_return = opcode == OP_RETURN1 or (
        opcode == OP_RETURN and ((candidate >> 16) & 255) == 2
    )
    if not is_single_return:
        raise ValueError(
            f'expected single-result RETURN (B=2) or RETURN1 at PC {return_pc}, '
            f'found opcode {opcode}; refusing patch'
        )
    if target.maxstack > 253:
        raise ValueError('not enough free Lua registers for safe appended call')
    if target.line_count not in (0,target.code_count):
        raise ValueError('unexpected debug lineinfo size; refusing patch')
    extra_root = parse(helper_chunk)
    if len(extra_root.children) != 1:
        raise ValueError('helper chunk must be: return function(reward) ... end')
    helper = extra_root.children[0]
    if helper_upvalues(helper_chunk,helper) != 0:
        raise ValueError('helper must contain no upvalues')
    old_child_count = len(target.children)
    if old_child_count > MAX_ARG_BX: raise ValueError('too many nested Proto children')
    new_stack = target.maxstack + 2
    scratch = target.maxstack
    result_reg = (candidate >> 7) & 255
    appendix = [
        code_abx(OP_CLOSURE,scratch,old_child_count),
        code_abc(OP_MOVE,scratch+1,result_reg),
        code_abc(OP_CALL,scratch,2,1),
        candidate,
    ]
    tail_pc = target.code_count
    jump = code_jmp(tail_pc - (return_pc+1))
    edits = [
        (target.maxstack_pos,target.maxstack_pos+1,bytes([new_stack])),
        (target.code_len_pos,target.code_len_end,encvar(target.code_count+len(appendix))),
        (target.code_start+4*return_pc,target.code_start+4*return_pc+4,struct.pack('<I',jump)),
        (target.code_end,target.code_end,struct.pack('<'+'I'*len(appendix),*appendix)),
        (target.children_len_pos,target.children_len_end,encvar(old_child_count+1)),
        (target.children_insert_pos,target.children_insert_pos,helper_chunk[helper.start:helper.end]),
    ]
    if target.line_count:
        edits.extend([
            (target.line_len_pos,target.line_len_end,encvar(target.line_count+len(appendix))),
            (target.line_data_end,target.line_data_end,b'\x00'*len(appendix)),
        ])
    patched = splices(raw,edits)
    patched_root = parse(patched)
    actual = get_proto(patched_root,path)
    if actual.code_count != target.code_count+len(appendix) or len(actual.children)!= old_child_count+1:
        raise AssertionError('post-repack structure did not validate')
    if word(patched,actual,return_pc) != jump:
        raise AssertionError('return trampoline was not repacked correctly')
    for pc in range(target.code_count):
        if pc != return_pc and word(raw,target,pc)!=word(patched,actual,pc):
            raise AssertionError('original Lua instruction unexpectedly modified')
    return patched, {
        'result':'SYNTHETIC_REPACK_OR_PENDING_RETAIL_HARDWARE',
        'input_sha256': hashlib.sha256(raw).hexdigest(),
        'patched_sha256':hashlib.sha256(patched).hexdigest(),
        'target':path, 'return_pc':return_pc,
        'old_instruction_hex':f'{candidate:08X}',
        'original_return_opcode':opcode, 'return_register':result_reg,
        'jump_instruction_hex':f'{jump:08X}',
        'append_tail_pc':tail_pc,'helper_proto_child_index':old_child_count,
        'original_code_count':target.code_count,'patched_code_count':actual.code_count,
        'original_child_count':old_child_count,'patched_child_count':len(actual.children),
        'original_instructions_other_than_redirect_identical':True,
        'actual_violet_reward_test':'NOT_RUN',
        'switch_test':'NOT_RUN',
    }


def helper_upvalues(raw:bytes,node:Proto)->int:
    r=Reader(raw)
    r.pos=node.code_end
    nconst=r.var()
    for _ in range(nconst):
        tag=r.u8()
        if tag in (0,1,17):continue
        if tag in (3,19):r.read(8);continue
        if tag in (4,20):r.strings();continue
        raise ValueError('unknown helper constant tag')
    return r.var()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('main_blua',type=Path)
    p.add_argument('helper_luac',type=Path,help='Lua 5.4 chunk: return function(reward) ... end')
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--report',type=Path)
    p.add_argument('--target',default='root/2899')
    p.add_argument('--pc',type=int,default=475)
    p.add_argument('--allow-synthetic',action='store_true',help='testing only; suppress retail SHA check')
    args=p.parse_args(argv)
    raw=args.main_blua.read_bytes()
    guard=None if args.allow_synthetic else ORIGINAL_SHA
    expected=None if args.allow_synthetic else 0x377501
    try:
        result,info=graft_tail(raw,args.target,args.pc,args.helper_luac.read_bytes(),
                                guard_sha=guard,expected_code_start=expected)
    except (ValueError, AssertionError) as exc:
        p.exit(2,'Patch refused: '+str(exc)+'\n')
    args.output.write_bytes(result)
    report=json.dumps(info,ensure_ascii=False,indent=2)+'\n'
    if args.report:args.report.write_text(report,encoding='utf-8')
    else:print(report)


if __name__=='__main__':main()
