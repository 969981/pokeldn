---
title: SV 4.0.0 历史奖励 donor BIN / Ghidra 溯源与字段勘误
parent: 朱／紫（SV）
---

# Violet 4.0.0 — sv_raid_reward_donor.bin 实证解析与 Ghidra 逆向溯源

- 复核日期：2026-10-20
- 对象：**references/fixtures/sv_raid_reward_donor.bin**
- 上游固定提交：**8b2c19c480400a6805eeeff266e13ded20c97475**
- 文件 Git Blob SHA：**444b1babacd231a32eb6bda1e5ed5d3eeab6eed9**
- 方法：读取归档 BIN → 原生 raw LZ4 解码 → 明文小端字段扫描 → 与上游分析文档 / 当前 research 源码 / 已有独立 ELF 复核报告比较。
- 证据边界：**本次直接验证 BIN 数据内容；作者的 Ghidra 结论来自其公开笔记；本次没有运行其 Ghidra 工程，也没有重新读取或执行真实游戏 ELF、实机联机/发奖/存盘。**

## 一句话结论

这不是存档、通用道具奖励库、单独的 reward table、ELF 或网络捕获原始帧；它是 **Violet 4.0.0 / Avalugg / RaidPoint_13_1_1 的完整 0x012F 应用层 Bootstrap donor 样本**。BIN 共 **1707 字节**，前 **18 字节**应用消息封装，后 **1689 字节** raw LZ4；解压得到**严格 0xAA0 = 2720 字节**，与作者根据 Violet 4.0.0 主程序 Ghidra 反编译所得序列化长度及本 fork 已记录的独立机器码复核一致。

## 1. 作者 Ghidra 记录在哪里？

**分析文本（已在本仓库 references 归档）：**

- [SV_RAID_BOOTSTRAP_ENCODER.md](references/SV_RAID_BOOTSTRAP_ENCODER.md)：从消息对象和序列化函数到 LZ4，早期奖励重写实验与原始错误字段注释；参见 “Ghidra call chain”。
- [SV_RAIDPOINT_REVERSE_ENGINEERING.md](references/SV_RAIDPOINT_REVERSE_ENGINEERING.md)：Violet 4.0.0 原生函数、五个 PK9、RaidPoint 的 0x3E8、遇敌资产（700 个条目）、三份抓包对照，以及 Ghidra 工程说明；参见 “Ghidra project and scripts” / “Proven native layout”。
- [SV_RAID_REWARD_PROFILES.md](references/SV_RAID_REWARD_PROFILES.md)：旧 donor 限定 JSON 奖励编辑与实机实验（例如 Quick Ball ×500）。

**上游原始 Ghidra Java 脚本：**

- [固定提交 scripts/ghidra 目录](https://github.com/Decryptu/pokeldn/tree/8b2c19c480400a6805eeeff266e13ded20c97475/tools/sv/ghidra)
- [DumpRaidFunctions.java](https://github.com/Decryptu/pokeldn/tree/8b2c19c480400a6805eeeff266e13ded20c97475/tools/sv/ghidra/DumpRaidFunctions.java)：调用者、被调用者、Ghidra 反编译 C 输出。
- [DumpInstructions.java](https://github.com/Decryptu/pokeldn/tree/8b2c19c480400a6805eeeff266e13ded20c97475/tools/sv/ghidra/DumpInstructions.java)：指定区间原生指令导出。
- [FindMultiScalarFunctions.java](https://github.com/Decryptu/pokeldn/tree/8b2c19c480400a6805eeeff266e13ded20c97475/tools/sv/ghidra/FindMultiScalarFunctions.java)：按多个标量值定位候选函数。
- [FindAsciiRefs.java](https://github.com/Decryptu/pokeldn/tree/8b2c19c480400a6805eeeff266e13ded20c97475/tools/sv/ghidra/FindAsciiRefs.java)：跟踪 ASCII 常量引用。
- [FindCallsWithNearbyScalar.java](https://github.com/Decryptu/pokeldn/tree/8b2c19c480400a6805eeeff266e13ded20c97475/tools/sv/ghidra/FindCallsWithNearbyScalar.java)：查找临近给定常量的调用。
- 此目录在历史提交内共 **13 个** Java 文件；本 fork 的 research 分支**没有 tools/sv/ghidra/**，这里提供的是上游固定提交链接，并不声称已复制这些脚本。

作者文档注明工程在个人机器上：**/home/ismail/violet_raidpoint.gpr** 与 **/home/ismail/violet_raidpoint.rep/**，headless 临时副本在 **/tmp/violet-ghidra-work**。这些是作者的*本机路径*，不代表 GitHub 已公开 Ghidra 工程文件或完整 Ghidra 执行日志；指定 Git 提交未包含 .gpr/.rep。作者使用的 Violet 4.0.0 main 载入基址 **0x7100000000**。

## 2. 实证：原始 18 字节头、LZ4、解压尺寸

原始文件前 18 字节：

~~~text
offset  bytes
0x00    80 33                  application prefix
0x02    2F 01                  message type 0x012F
0x04    13 00                  message/session-like value (0x0013; semantics unknown)
0x06    02 00 00 00            compression flag 2
0x0A    A0 0A 00 00            decoded size 0xAA0 = 2720
0x0E    00 00 28 3A            opaque tail; not always zero
0x12    ...                    raw LZ4 compressed payload (1689 bytes)
~~~

**独立解压结果**：1707 = 18 + 1689；raw LZ4 解码返回 2720 字节，末尾恰好位于 0xA9F（包含）。注意还有一个独立的*网络 reliable-fragment 可选 zlib* 外层，原始 BIN 已是重组的应用消息，不需要再把它当作 Pia 原始帧解码。

不能因为 0xAA0 正确就推出每个未知字节的语义正确；压缩仅保证结构可被解码。

## 3. Ghidra 核心结论：谁生成 0xAA0，如何压缩？

| Violet 4.0.0 Ghidra VA | main+RVA | 作者笔记中的作用 |
|---|---|---|
| FUN_71018BB5F8 | 0x18BB5F8 | 0x012F 大消息对象构造 |
| FUN_71018BB4FC | 0x18BB4FC | 创建消息对象，分配 0x460 字节 |
| **FUN_7100E327FC** | **0xE327FC** | **构造总长 0xAA0 的序列化明文** |
| FUN_7100E329B4 | 0xE329B4 | 将每个 PK9 子对象写成 0x158 字节 |
| FUN_7101E62FE4 | 0x1E62FE4 | 反向复制/加载路径 |
| FUN_7101592B7C | 0x1592B7C | 16 字节 serializer header、压缩分支 |
| FUN_7101592DAC | 0x1592DAC | 压缩缓冲区申请及调用 |
| FUN_7101592E50 | 0x1592E50 | LZ4_compressBound 计算 |
| FUN_7101592E80 | 0x1592E80 | fast LZ4 包装函数 |
| FUN_710071D940 | 0x71D940 | LZ4 fast 压缩核心 |

以上 VA 为历史作者设置的 0x7100000000 image base 加 RVA。运行时主模块基址可能随 ASLR 变化，**不可把上述 VA 当成通用固定内存指针**。

**生成布局：**

~~~c
struct RaidBootstrapRaw {
    uint8_t participant_pk9[4][0x158]; // 0x000..0x55F
    uint8_t boss_pk9[0x158];           // 0x560..0x6B7
    uint8_t raidpoint[0x3E8];          // 0x6B8..0xA9F
};                                      // 0xAA0
~~~

验证算术：5×0x158=0x6B8；0x20+0x3C8=0x3E8；0x6B8+0x3E8=0xAA0。

作者观察到 **FUN_7100E327FC 不负责“计算” RaidPoint**，而是将此前已生成的对象复制入消息。前部四个 qword 取自消息对象 **+0x58..+0x77**，另有 **0x3C8** 字节取自 **+0x78**。上游追溯的 getter / setter 链还涉及 **FUN_7101BAE670 / FUN_7101BAE760 / FUN_7101BAFF98 / FUN_7101BB0018**。因此“在序列化入口才生成 boss/奖励”的推断不成立。

现有独立 ELF 审计 [violet400-elf-raid-bootstrap-audit.md](violet400-elf-raid-bootstrap-audit.md) 记录了 0xE32828 的 MOV W22,#0xAA0、0xE32844 的 MOV W24,#0x158、0xE3296C 的 MOV W2,#0x3C8、0xE32980 的 memcpy 调用等 opcode 原始比对。**这是先前审计的结论，本次没有重做 ELF 静态校验。**

## 4. RaidPoint 解压样本所见

| 明文相对偏移 | 字段 | BIN 实测值 |
|---|---|---|
| 0x6B8 | RaidPoint 标识 | RaidPoint_13_1_1 |
| 0x6D8 (RaidPoint+0x20) | 星级 | 5 |
| 0x6E4 (RaidPoint+0x2C) | 等级 | 75 |
| 0x704 (RaidPoint+0x4C) | HP 系数 | 2000 |
| 0xA70 (RaidPoint+0x3B8) | 摘要星级 | 5 |
| 0xA74 (RaidPoint+0x3BC) | 物种内部索引 | 713（Avalugg） |
| 0xA7C (RaidPoint+0x3C4) | 性别 | 1 |
| 0xA80 (RaidPoint+0x3C8) | 摘要等级 | 75 |
| 0xA88 (RaidPoint+0x3D0) | 太晶属性编号 | 0 |

上游识别的源上下文为 Violet 4.0.0、**C72E1D7F** 种子、**五星彩色活动 Avalugg**。种子值来自历史抓包笔记与记录关联，**不是说该明文对象在固定偏移携带了该种子**。对于活动数据，只有种子不足以唯一重建：还需要游戏版本、地图、进度以及相应活动/BCAT 表。

## 5. 重要勘误：上游 donor 文档的奖励行整体向前错 4 字节

旧 [SV_RAID_BOOTSTRAP_ENCODER.md](references/SV_RAID_BOOTSTRAP_ENCODER.md) 把首条奖励设在**明文 0x798**，并解释为 marker/item/quantity/reserved；但研究分支当前 [pokeldn/sv/raid.py](../../../pokeldn/sv/raid.py) 定义：**POINT_REWARDS=0xE4，行格式为 little-endian 4×u32，即 item、quantity、rare、subject**。

正确布局：

| 项目 | 正确偏移及范围 |
|---|---|
| RaidPoint 大小 | 0x3E8 字节，明文从 0x6B8 开始 |
| 首条奖励 | **RaidPoint+0xE4 = Bootstrap+0x79C** |
| 第 i 条（从零计） | **0x79C + 0x10 × i** |
| 最大容量 | **45 行 × 16 字节 = 720 字节** |
| 奖励区 | 明文 0x79C..0xA6B |
| 其后 4 字节 | 0xA6C..0xA6F，**不是第 46 条** |
| 摘要开始 | 明文 0xA70（RaidPoint+0x3B8） |
| 每行 | item u32 / quantity u32 / rare u32 / subject u32 |

为什么旧表“道具与数量看上去正确”？它提前四字节读取，使得 **前一行的 subject** 成了当前行的 marker，而真正的 item/quantity 仍然落在其四字段窗口的后两列；把所有所谓 marker=0/1/2/4 直接作为同一条奖励的来源解释是错位的。

例如实际第 5 条从 **0x7DC** 读取：

~~~text
10 08 00 00 | 03 00 00 00 | 00 00 00 00 | 02 00 00 00
item=2064       qty=3          rare=0        subject=2
~~~

旧读法从 **0x7D8** 起始，会把该条的 subject=2 搬到**下一条**的 marker 列。这也说明旧文件在 **0x8D8** 标为 marker=4 的太晶碎块 x10，**实际记录位于 0x8DC，subject=5**（晶耀护符）。

这是一项**记录字段起点和解释的勘误**，不是说作者的 0xAA0、RaidPoint 0x3E8、LZ4 路径或实机收到指定奖励的历史结论都错误。

## 6. 实际 BIN：完整非空奖励清单

原始 RaidPoint 允许 45 个槽。本 BIN 按正确格式解析获得**21 条非空、24 条空**；所有非空条目的 rare=0。

| 行号 | Bootstrap 偏移 | Item ID | 数量 | Rare | Subject |
|---:|---|---:|---:|---:|---:|
| 1 | 0x79C | 1127 | 1 | 0 | 0 |
| 2 | 0x7AC | 1128 | 1 | 0 | 0 |
| 3 | 0x7BC | 2064 | 5 | 0 | 0 |
| 4 | 0x7CC | 567 | 3 | 0 | 0 |
| 5 | 0x7DC | 2064 | 3 | 0 | 2 |
| 6 | 0x7EC | 1862 | 2 | 0 | 0 |
| 7 | 0x7FC | 1862 | 2 | 0 | 1 |
| 8 | 0x80C | 2064 | 2 | 0 | 0 |
| 9 | 0x81C | 171 | 3 | 0 | 0 |
| 10 | 0x82C | 171 | 3 | 0 | 0 |
| 11 | 0x83C | 171 | 3 | 0 | 0 |
| 12 | 0x84C | 1235 | 1 | 0 | 0 |
| 13 | 0x85C | 171 | 3 | 0 | 0 |
| 14 | 0x86C | 171 | 3 | 0 | 0 |
| 15 | 0x87C | 171 | 3 | 0 | 0 |
| 16 | 0x88C | 171 | 3 | 0 | 0 |
| 17 | 0x89C | 171 | 3 | 0 | 0 |
| 18 | 0x8AC | 567 | 2 | 0 | 4 |
| 19 | 0x8BC | 89 | 1 | 0 | 4 |
| 20 | 0x8CC | 92 | 1 | 0 | 4 |
| 21 | 0x8DC | 1862 | 10 | 0 | 5 |

- Subject 分布：0=15 行，1=1 行，2=1 行，4=3 行，5=1 行。
- 按本文和目前源码的资格定义，普通参与者的可见基础奖励为 **15 条 subject=0 + 1 条 subject=2，数量合计 42**；房主的 subject=1 那条不是“客方必得”。
- Subject=4 三条是团战力/餐食相关的条件奖励，而非三条全体必得。
- **Subject=5 的 1862（一般太晶碎块）×10 是本文件中的原始样本，而不是后来造出来的测试数据。** 对其发奖资格的解释还需依赖相应客户端脚本/运行时语义，不是仅凭本 BIN 证明。
- 文件中 21 条数量之和为 58，但**58 不是任意一名玩家的实际奖励数量**，更不等于背包最终净增。

## 7. 可复现读取脚本（只读）

先安装第三方依赖：**python -m pip install lz4**，从仓库根目录执行：

~~~python
from pathlib import Path
from struct import unpack_from
import lz4.block

p = Path("docs/research/sv/references/fixtures/sv_raid_reward_donor.bin")
application = p.read_bytes()
assert len(application) == 1707
assert application[:4] == bytes.fromhex("80 33 2f 01")
assert unpack_from("<I", application, 0x06)[0] == 2
n = unpack_from("<I", application, 0x0A)[0]
assert n == 0xAA0

raw = lz4.block.decompress(application[0x12:], uncompressed_size=n)
assert len(raw) == 0xAA0
assert raw[0x6B8:0x6C8] == b"RaidPoint_13_1_1"

for i in range(45):
    off = 0x79C + 0x10 * i
    item, quantity, rare, subject = unpack_from("<IIII", raw, off)
    if item or quantity or rare or subject:
        print(f"{i+1:02d} @ 0x{off:03X}: "
              f"item={item}, qty={quantity}, rare={rare}, subject={subject}")
~~~

**禁止混淆三层偏移**：明文中的 0x79C ≠ LZ4 压缩文件偏移 ≠ Pia / reliable 分片内偏移 ≠ 游戏堆的固定地址。

## 8. 结论分类及对当前 Hook 研究的影响

| 命题 | 证据级别 |
|---|---|
| BIN 原始 1707、头部 18、raw LZ4 解至 0xAA0 | **本次独立解码验证** |
| 解压明文 4×PK9+Boss PK9+RaidPoint | **作者 Ghidra 记录 + 本次结构复核 + 已有 ELF opcode 审计** |
| 0xE327FC 构建；0x1592B7C / 0x71D940 参与压缩 | **作者 Ghidra 记录及 fork 已有 ELF 审计；本次未独立重跑 Ghidra** |
| 奖励从 0x79C 起，每行 4×u32，45 行 | **本 BIN 字节 + 当前源码 + fork 已有 ELF/脚本研究相互吻合** |
| 当前 BIN 含原生 subject 0/1/2/4/5 | **本次明文字节实测** |
| 具体 subject 筛选、奖励发放 / 背包写入 / Save 完成 | **涉及客户端执行流程，单凭 donor BIN 不足以证明** |
| 官方互联网团体战采用同一信任边界 | **未经本次验证** |

实际用途：历史样本可作为 Golden Fixture，回归检查**接收 / 解压 / RaidPoint 45 行解析**，尤其能避免错误的 **0x798 旧行结构**。后续仍应分别采集 S1 源 RaidPoint、S2 输出 Bootstrap 和 S3 接收端筛选结果；不能把“本地解压正确”直接等同于“后续发奖/保存全链闭环”。参见 [三点一致性研究](raidpoint-bootstrap-receiver-consistency.md)。

---

## 来源

1. [作者原始研究目录固定提交](https://github.com/Decryptu/pokeldn/tree/8b2c19c480400a6805eeeff266e13ded20c97475/docs/research/sv)
2. [上游 Ghidra scripts](https://github.com/Decryptu/pokeldn/tree/8b2c19c480400a6805eeeff266e13ded20c97475/tools/sv/ghidra)
3. [已有个人 ELF 机器码审计](violet400-elf-raid-bootstrap-audit.md)
4. [现有源码与奖励指针勘误](sv400-custom-reward-pointer-patch.md)
