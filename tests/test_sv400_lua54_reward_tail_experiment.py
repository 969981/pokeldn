"""Regression checks for the Lua 5.4 tail-graft experiment.

Tests compile/load/execute synthetic chunks in an actual Lua 5.4 VM.
They do NOT assert that Violet 4.0.0 main.blua has been modified or loaded.
"""
import ctypes
import ctypes.util
import importlib.util
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sv400_lua54_reward_tail_experiment",
    ROOT / "scripts" / "research" / "sv400_lua54_reward_tail_experiment.py",
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)

LIB = ctypes.util.find_library("lua5.4")
if not LIB:
    pytest.skip("Lua 5.4 runtime not installed on test runner", allow_module_level=True)
L = ctypes.CDLL(LIB)
L.luaL_newstate.restype = ctypes.c_void_p
L.lua_close.argtypes = [ctypes.c_void_p]
L.luaL_openlibs.argtypes = [ctypes.c_void_p]
L.luaL_loadbufferx.argtypes = [
    ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t,
    ctypes.c_char_p, ctypes.c_char_p,
]
L.luaL_loadbufferx.restype = ctypes.c_int
L.lua_pcallk.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_longlong, ctypes.c_void_p,
]
L.lua_pcallk.restype = ctypes.c_int
L.lua_type.argtypes = [ctypes.c_void_p, ctypes.c_int]
L.lua_type.restype = ctypes.c_int
L.lua_tointegerx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
L.lua_tointegerx.restype = ctypes.c_longlong
L.lua_rawgeti.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]
L.lua_rawgeti.restype = ctypes.c_int
L.lua_getfield.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
L.lua_getfield.restype = ctypes.c_int
L.lua_settop.argtypes = [ctypes.c_void_p, ctypes.c_int]
L.lua_tolstring.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t),
]
L.lua_tolstring.restype = ctypes.c_void_p
WRITER = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    ctypes.c_void_p,
)
L.lua_dump.argtypes = [ctypes.c_void_p, WRITER, ctypes.c_void_p, ctypes.c_int]
L.lua_dump.restype = ctypes.c_int


def error_message(state):
    size = ctypes.c_size_t()
    ptr = L.lua_tolstring(state, -1, ctypes.byref(size))
    return ctypes.string_at(ptr, size.value) if ptr else b"<no message>"


def compile_lua(source):
    state = L.luaL_newstate()
    try:
        code = source.encode("utf-8")
        status = L.luaL_loadbufferx(state, code, len(code), b"=test", b"t")
        assert status == 0, error_message(state)
        chunks = []

        def collect(s, ptr, size, user):
            chunks.append(ctypes.string_at(ptr, size))
            return 0

        callback = WRITER(collect)
        assert L.lua_dump(state, callback, None, 0) == 0
        return b"".join(chunks)
    finally:
        L.lua_close(state)


def execute_lua(chunk):
    state = L.luaL_newstate()
    try:
        L.luaL_openlibs(state)
        status = L.luaL_loadbufferx(state, chunk, len(chunk), b"=test", b"b")
        assert status == 0, error_message(state)
        status = L.lua_pcallk(state, 0, 1, 0, 0, None)
        assert status == 0, error_message(state)
        assert L.lua_type(state, -1) == 6  # outer returns function
        status = L.lua_pcallk(state, 0, 1, 0, 0, None)
        assert status == 0, error_message(state)
        assert L.lua_type(state, -1) == 5  # returned reward object
        L.lua_rawgeti(state, -1, 3)
        assert L.lua_type(state, -1) == 5  # BattleRewardData[3] mock
        L.lua_getfield(state, -1, b"length")
        total = L.lua_tointegerx(state, -1, None)
        L.lua_settop(state, -2)
        added_item = None
        if total:
            L.lua_rawgeti(state, -1, 1)
            if L.lua_type(state, -1) == 5:
                L.lua_getfield(state, -1, b"ItemNo")
                added_item = L.lua_tointegerx(state, -1, None)
        return total, added_item
    finally:
        L.lua_close(state)


SYNTHETIC = """return function()
  local reward = {[3]={length=0}}
  reward[3].push = function(self,item)
    self.length=self.length+1
    self[self.length] = item
  end
  return reward
end"""


def last_return(chunk):
    target = mod.get_proto(mod.parse(chunk), "root/0")
    pcs = [i for i in range(target.code_count)
           if mod.word(chunk, target, i) & 127 == mod.OP_RETURN1]
    assert pcs, "fixture did not compile a RETURN1"
    return target, pcs[-1]


def helper():
    return compile_lua(mod.DEFAULT_HELPER_SOURCE)


def test_compiled_chunk_repacked_and_executes_added_reward():
    chunk = compile_lua(SYNTHETIC)
    assert execute_lua(chunk) == (0, None)
    target, pc = last_return(chunk)
    altered, report = mod.graft_tail(
        chunk, "root/0", pc, helper(),
        expected_code_start=target.code_start,
    )
    assert execute_lua(altered) == (1, 492)
    assert report["original_instructions_other_than_redirect_identical"]
    assert len(mod.get_proto(mod.parse(altered), "root/0").children) == len(target.children) + 1


def test_nonreturn_pc_rejected():
    chunk = compile_lua(SYNTHETIC)
    with pytest.raises(ValueError, match="expected RETURN1"):
        mod.graft_tail(chunk, "root/0", 0, helper())


def test_wrong_sha_and_code_offset_rejected():
    chunk = compile_lua(SYNTHETIC)
    target, pc = last_return(chunk)
    with pytest.raises(ValueError, match="identity check FAILED"):
        mod.graft_tail(chunk, "root/0", pc, helper(), guard_sha="0" * 64)
    with pytest.raises(ValueError, match="Prototype code_start"):
        mod.graft_tail(chunk, "root/0", pc, helper(),
                       expected_code_start=target.code_start + 1)


def test_all_untouched_original_instructions_are_identical():
    chunk = compile_lua(SYNTHETIC)
    target, pc = last_return(chunk)
    amended, _ = mod.graft_tail(chunk, "root/0", pc, helper())
    changed = mod.get_proto(mod.parse(amended), "root/0")
    for original_pc in range(target.code_count):
        if original_pc != pc:
            assert mod.word(chunk, target, original_pc) == mod.word(amended, changed, original_pc)


def test_original_violet_sha_rejects_synthetic_sample():
    chunk = compile_lua(SYNTHETIC)
    _, pc = last_return(chunk)
    with pytest.raises(ValueError, match="identity check FAILED"):
        mod.graft_tail(chunk, "root/0", pc, helper(), guard_sha=mod.ORIGINAL_SHA)


def test_existing_reward_is_not_removed():
    source = """return function()
      local rows={length=1,[0]={ItemNo=1862,ItemNum=12,subjectType=5,rareType=0}}
      rows.push=function(self,item) self[self.length]=item; self.length=self.length+1 end
      return {[3]=rows}
    end"""
    chunk = compile_lua(source)
    _, pc = last_return(chunk)
    amended, _ = mod.graft_tail(chunk, "root/0", pc, helper())
    assert execute_lua(chunk)[0] == 1
    assert execute_lua(amended) == (2, 492)


def test_full_45_slots_stays_unchanged():
    source = """return function()
      local rows={length=45}
      rows.push=function(self,item) self[self.length]=item; self.length=self.length+1 end
      return {[3]=rows}
    end"""
    chunk = compile_lua(source)
    _, pc = last_return(chunk)
    amended, _ = mod.graft_tail(chunk, "root/0", pc, helper())
    assert execute_lua(chunk)[0] == 45
    assert execute_lua(amended)[0] == 45
