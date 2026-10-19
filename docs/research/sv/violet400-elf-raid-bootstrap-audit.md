---
title: 紫 4.0.0 ELF 太晶坑初始化原生指令复核
parent: 朱／紫（SV）
nav_order: 2
---

# 《紫》4.0.0 ELF：RaidPoint → bootstrap 的原生指令复核

- **日期**：2026-10-19
- **证据等级**：**本轮原始 ELF 实际检验 / DISASM_EXACT**（不同于引用上游 Lua 研究）
- **来源**：用户个人 Library 中 `Violet4.0.0.elf`（**不纳入 Git 仓库**）
- **大小**：74,362,480 字节（70.92 MiB）
- **文件类型**：ELF64、AArch64、little endian、PIE（ET_DYN）、stripped
- **Build ID**：`709bfd66115298640155fcc4979dba151c7cc79a`
- **SHA-256**：`d17403eaa9d844db82f647fd2f1518806b10c0518d53602fc0ac1766298fdba0`
- **工具**：Linux `file`、`readelf`、`llvm-objdump`、Python 标准库 `hashlib`/`struct`
- **配套推论文档**：[晶耀护符与 999 奖励案例](glimmering-charm-raid-rewards.md)
- **源码对照**：上游 [SV Raid](../../sv_raid.md)；本仓库 [raid.py](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py)

## 1. ELF 身份核验

```sh
file Violet4.0.0.elf
sha256sum Violet4.0.0.elf
readelf -h Violet4.0.0.elf
readelf -n Violet4.0.0.elf
readelf -SW Violet4.0.0.elf
```

实际输出的关键值：`e_machine=AArch64`、`e_type=DYN`、.text 的虚拟地址从 `0x0` 开始、文件偏移 `0x8D8`、大小 `0x343FC90`。因此下列 `main+0x...` 地址在此 ELF 的 .text 中可按 `file_offset=RVA+0x8D8` 验证原始 opcode；此映射只适用于当前已校验 ELF 的 .text，不推广到所有 ELF 节区。绝对运行时地址还需要 ASLR 基址。

**特别注意**：下面使用真实游戏《紫》4.0.0 自有 ELF 实际反汇编，不再只是“上游认为《朱》《紫》偏移相同”；本轮确证了以下《紫》的具体函数入口与指令。但这不等于验证最新游戏版本，也不等于持有 Lua 奖励过滤模块或商家改版。

## 2. Native serializer：`main+0xE327FC`（精确机器码证据）

```sh
llvm-objdump -d --start-address=0xE327FC --stop-address=0xE329B4 Violet4.0.0.elf
```

已核对的原始机器码与含义：

| RVA | Opcode（32-bit） | ARM64 指令 | 直接证据 |
|---|---|---|---|
| `0xE32828` | `52815416` | `mov w22, #0xaa0` | 申请 `0xAA0=2720` 字节 bootstrap |
| `0xE32844` | `52802B18` | `mov w24, #0x158` | 每只宝可梦队伍记录 `0x158=344` 字节 |
| `0xE3294C` | `911582E0` | `add x0, x23, #0x560` | 第五份记录（首领）的目的位置 |
| `0xE32960` | `911B62E0` | `add x0, x23, #0x6d8` | RaidPoint 后段的目的位置 |
| `0xE32968` | `9101E281` | `add x1, x20, #0x78` | RaidPoint 后段来自消息对象 `+0x78` |
| `0xE3296C` | `52807902` | `mov w2, #0x3c8` | 后段复制 `0x3C8=968` 字节 |
| `0xE32970` | `F9035EEB` | `str x11, [x23, #0x6b8]` | RaidPoint 的前 8 字节写入 `+0x6B8` |
| `0xE32980` | `94982624` | `bl 0x343C210` | 调用 `memcpy@plt` 复制后段 |
| `0xE329B0` | `141D8073` | `b 0x1592B7C` | 进入上游所述消息序列化/压缩链 |

`0xE32860`/`0xE32898`/`0xE328D0`/`0xE32908`/`0xE32940` 依次读取五个队伍记录来源，写入 `bootstrap` 的 `0x000/0x158/0x2B0/0x408/0x560`。随后 `0xE3295C` 读取消息对象的前 32 字节（`[x20+0x58..+0x77]`），`0xE32970..0xE3297C` 将其写入 `[x23+0x6B8..+0x6D7]`；`0xE32980` 再把对象 `+0x78` 开始的 `0x3C8` 字节复制至 `+0x6D8`。

**地址/长度算术的独立核对**：

```text
5 × 0x158 = 0x6B8  （四位参与者 + 一位首领）
0x20 + 0x3C8 = 0x3E8 （RaidPoint 整体）
0x6B8 + 0x3E8 = 0xAA0 （bootstrap 总长度）
0x6D8 + 0x3C8 = 0xAA0 （最后一次 memcpy 后的末尾）
```

在本轮《紫》ELF 上，这不是仅根据项目 Python 常量倒推出的结构，而是**机器指令实际实现的布局**。

## 3. Native RaidPoint object/getter/copy 链

```sh
llvm-objdump -d --start-address=0x1BAE670 --stop-address=0x1BAE7C8 Violet4.0.0.elf
llvm-objdump -d --start-address=0x1BAFF98 --stop-address=0x1BB0068 Violet4.0.0.elf
```

| RVA | Opcode | 事实 |
|---|---|---|
| `0x1BAE790` | `94000602` | `bl 0x1BAFF98`：调用结构 getter |
| `0x1BAE798` | `52807902` | `mov w2, #0x3c8`，给第一次 `memcpy` 长度 |
| `0x1BAE7B0` | `9400061A` | `bl 0x1BB0018`：再把得到的数据写入目标结构 |
| `0x1BAFFF4` | `52807902` | 无有效源指针时，备用静态结构清零长度 `0x3C8` |
| `0x1BB003C` | `52807908` | `0x1BB0018` 复制时再次使用 `0x3C8` 长度 |

细节：`0x1BAFF98` 中，状态符合条件且 `[source+0x8]` 有效时取结构指针，否则返回初始化清零的结构；`0x1BB0018` 按包装对象类型决定数据地址，最终 `memcpy` 仅复制 `0x3C8` 字节。原代码路径与上游文档的 getter/copy 描述吻合。

压缩链也可核实：`main+0x1592EA4` 的机器码 `97C62AA7` 是 `bl 0x71D940`，与上游标注的 LZ4 函数调用对应。**仅凭这个调用不足以证明整个在线或离线传输协议。**

## 4. 与 `subject=5`、晶耀护符的严格区分

本轮**原生 ELF 直接证实**：`RaidPoint` 的整块 `0x3E8` 数据被复制进 `0x2F` 初始化消息结构。对应项目源码 `pokeldn/sv/raid.py` 把 `RaidPoint+0xE4` 当成 45 条 16 字节奖励行，其中每行四个 `u32` 为 `item, quantity, rare, subject`。

但**本轮 ELF 尚未直接证实**客户端过滤 `subject=5` 的那几条 Lua 判断语句：上游把逻辑定位在 Lua 函数 `C07C34FC3B976E5A7.F316609DEA110601D`（字节码行 78707..78765；Lua 模块标识 `be21e65463b9a98f`）。这不是一个等价于 AArch64 RVA 的函数名，**不能从 ELF 的结构复制指令推出“它已在 ELF 汇编中读取重要物品 2481”**。

实际全文字节搜索在本 ELF 中未找到上述 Lua 函数文本标识（也不能因搜索不到就断言不存在相关运行时语义）。要进一步做**真正独立**的护符资格证明，需要相应 RomFS Lua 模块原始字节或可靠反编译结果，并跟踪其原生 getter 桥接到背包持有查询的路径。

| 命题 | 当前状态 |
|---|---|
| 《紫》4.0.0 中 bootstrap 大小 `0xAA0`，五份队伍记录后带 `0x3E8` RaidPoint | **本轮 ELF 实证** |
| `0x1BAE790 → 0x1BAFF98`、`0x1BAE7B0 → 0x1BB0018` 与文档一致 | **本轮 ELF 实证** |
| 奖励行 `+0xE4`，格式 `4×u32`，最多 45 行 | **项目源码 + 上游协议实验已证实**，本轮未单独复现处理端解析 |
| `subject=5` 读取物品 ID 2481（晶耀护符） | **上游 Lua 逆向 + 既有实机**；本轮 ELF **未独立闭环** |
| 自选奖励 `subject=0`、常规碎块补偿 `subject=5` | **项目 Python 源码已证实** |
| 商业远程 999 道具坑是否通过任天堂原生在线模式、是否依赖 `subject=5` | **待该案例实际报文/实现验证** |
| 999 奖励保存、重启、重新联网后是否持久化 | **待实机闭环** |

**重要负面判断**：不能把同一 ELF 的 opcode 命中当作“已破解互联网房间验证”；这次没有 Nintendo 官方会话抓包，没有解出商家软件，更没有验证服务器是否复算奖励。

## 5. 机器码验收脚本（只需用户本地原始 ELF）

将下列脚本粘贴本地保存为 `verify_raid_elf.py`，与 `Violet4.0.0.elf` 放在同一目录执行；仅只读。建议先比对文首 SHA-256 和 Build ID。

```python
import struct
from pathlib import Path

p = Path("Violet4.0.0.elf")
data = p.read_bytes()
elf_text_offset = 0x8D8
checks = {
    0xE32828: 0x52815416, 0xE32844: 0x52802B18,
    0xE3294C: 0x911582E0, 0xE32960: 0x911B62E0,
    0xE32968: 0x9101E281, 0xE3296C: 0x52807902,
    0xE32970: 0xF9035EEB, 0xE32980: 0x94982624,
    0xE329B0: 0x141D8073, 0x1BAE790: 0x94000602,
    0x1BAE798: 0x52807902, 0x1BAE7B0: 0x9400061A,
    0x1BB003C: 0x52807908, 0x1BAFFF4: 0x52807902,
    0x1592EA4: 0x97C62AA7,
}
for rva, expected in checks.items():
    actual = struct.unpack_from("<I", data, elf_text_offset + rva)[0]
    assert actual == expected, f"{rva:#x}: {actual:#x} != {expected:#x}"
print(f"{len(checks)}/{len(checks)} opcode assertions passed")
```

**本次实跑结果：15/15 exact opcode assertions PASS**。这是验证原始二进制指令的静态断言，不是游戏功能端到端测试。

> **2026-10-19 追加**：已在第三方公开的旧版 Lua 反编译中找到类 `main.battle.BattleRewardData`、方法 `F316609DEA110601D`，以及 `Bag.GetNumItem(2481)` 的真实调用；详见 [Lua 交叉研究](battle-reward-lua-cross-version.md)。但本轮仍没有 4.0.0 RomFS 的原始 Lua blob，因此不把旧版反编译误称作原版 4.0.0 的字节码实测。

## 6. 后续分析优先级

1. **P0：Lua 资源**：找 `be21e65463b9a98f` 模块（RomFS / Lua blob）以及 ID 2481 / `subject=5` 条件的真实指令级证据，做有护符/无护符输入差分。
2. **P1：接收方**：从 `0x2F` 反序列化入口下钻 `RaidPoint+0xE4` 奖励行读取，再闭合 UI 与道具添加函数调用链；本次确证的是**发送端 serializer**。
3. **P1：联网差异**：区分官方在线房间和 Nostr 远程 LDN 中继；采集用户授权的最小化匿名化报文/会话状态。
4. **P2：持久化与数量上限**：对正常存档中实际入包数量、溢出处理、重启/联网恢复做分步对照。
5. **P2：版本迁移**：先用 SHA-256 与 Build ID 绑定 4.0.0，再用代码锚点查其他版本，禁止地址机械加 delta。

## 参考

- [现有 SV Raid 文档](../../sv_raid.md)、[汉化](../../zh-Hans/sv_raid.md)
- [晶耀护符与 999 道具研究](glimmering-charm-raid-rewards.md)
- [项目 SV 代码](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py)
