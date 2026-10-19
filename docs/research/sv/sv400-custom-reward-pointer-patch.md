---
title: 《紫》4.0.0 自定义太晶坑奖励：ELF 指针、字节布局与修改验证
parent: 朱／紫（SV）
nav_order: 6
---

# PokéLDN 自定义奖励：主持端实现 × 《紫》4.0.0 ELF 实际指针

- **更新**：2026-10-19。
- **项目基线**：`969981/pokeldn` 的 `research` 分支；实际阅读 `bin/sv_host.py`、`pokeldn/sv/raid.py`、`gui/views/rewards.py`、`tests/test_sv_raid.py`、`tests/test_gui_rewards.py`。
- **ELF 实证对象**：用户 Library `Violet4.0.0.elf`；ELF64 AArch64 PIE；SHA-256 `d17403eaa9d844db82f647fd2f1518806b10c0518d53602fc0ac1766298fdba0`；Build ID `709bfd66115298640155fcc4979dba151c7cc79a`。
- **独立复验结果**：原 ELF **13/13 条本页指令断言通过**；离线合成的 `RaidPoint` 及 bootstrap **2/2 修改测试通过**。验证脚本：[`sv_custom_raid_reward_offsets.py`](../../../scripts/research/sv_custom_raid_reward_offsets.py)。
- **证据边界**：本文证实了**HOST 自定义字段、原版 Native 拷贝路径、动态寄存器指针与明文字节位置**，不宣称商业互联网坑的实现/官方服务器校验/最终保存成功。原始 ELF 不提交。

## 1. 最新 research 源码已支持哪些功能？

**注意版本变化**：之前的 [主持端研究文档](custom-raid-rewards-host-elf.md) 写“只能 ITEM:QUANTITY、SUBJECT=5 是未来计划”，这是早期代码状态；**现在已经实现**：

- [`bin/sv_host.py:raid_reward`](https://github.com/969981/pokeldn/blob/research/bin/sv_host.py#L209-L223) 识别 `ITEM:QUANTITY[:SUBJECT]`，十进制和 `0x` 进制均可。数量 `1..999`、道具 ID `1..65535`、subject 只允许 `0/5`。接着 `prepare_raid` 校验最多 **45 条**及道具是否存在于 SV `bag` 名单。
- [`pokeldn/sv/raid.py:raid_point`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py#L171-L215) 解析二元组 `(item,quantity)` 为 `(item,quantity,rare=0,subject=0)`；三元组 `(item,quantity,subject)` 保留 `0/5` subject。每行以 `struct.pack_into("<IIII", out, 0xE4 + index*0x10, ...)` 写入。
- [`gui/views/rewards.py:RewardPicker`](https://github.com/969981/pokeldn/blob/research/gui/views/rewards.py) 已有**逐行 Eligibility 下拉框**，选项 “All players” (`0`) 和 “Glimmering Charm only” (`5`)，并能保存/恢复，传递到 CLI。
- [`tests/test_sv_raid.py`](https://github.com/969981/pokeldn/blob/research/tests/test_sv_raid.py#L1160-L1211) 含 subject 0/5、边界和最终 `0x2F` 明文包测试；[`tests/test_gui_rewards.py`](https://github.com/969981/pokeldn/blob/research/tests/test_gui_rewards.py) 含 GUI → CLI → `RaidPoint` subject 5 测试。**这些是已读取的测试源码，本轮未重新运行完整 pytest**。

**实际支持的参数示例**（仅展示构造，不表示已联网实测）：

```bash
python bin/sv_host.py --raid-seed 000F34C3 --raid-pokemon host.pk9 \
  --raid-reward 1:999:5   \
  --raid-reward 796:999:5 \
  --raid-reward 50:999:0
```

分别是大师球、金色王冠（subject 5、接收端需晶耀护符）及神奇糖果（subject 0）。**任何非空自定义列表替换种子全部原本奖励**，不是在原种子掉落之上追加。无需修改游戏 ELF；只要主持端构建自定义 `RaidPoint`。

与早期文档中的 ID 误记做勘误：**Quick Ball/先机球 ID = 15**，`492` 是 **Fast Ball/速度球**，请勿把 `492:500` 标成先机球。

## 2. 数据变更准确发生在哪个位置？

```text
GUI / CLI 选定 ITEM, QUANTITY, SUBJECT
  → sv_host.raid_reward()
  → prepare_raid() 检查 ID/数量/45行
  → RaidGroup.rewards
  → raid_point():
      RaidPoint = 0x3E8 字节
      [+0xE4 + i*0x10] 4 x u32 LE: item, count, rare, subject
  → bootstrap() = 4 x 0x158 participants + 0x158 boss + 0x3E8 RaidPoint
  → bootstrap_message(): plain 0xAA0，经 LZ4 压缩，
     channel key 0x3380 / kind 0x2F
  → 正版客户端：解压/取 RaidPoint → BattleRewardData subject filter
  → 团体战胜利 → GameEventBattleResult.RaidResultAddItem
  → Bag.AddItem + BagSaveAccessor → RequestAutoSave
```

- `RaidPoint` 内奖励区：**`0xE4..0x3B3`**，45 行，每行 0x10；**`0x3B4..0x3B7` 不属于第 46 行**，`0x3B8` 是摘要。
- `0xAA0` 明文 bootstrap 内奖励区：**`0x79C..0xA6B`**；`0xA6C..0xA6F` 不属于奖励行；`0xA70` 开始摘要。
- 单行字段：`+0x00 item u32 LE`；`+0x04 quantity u32 LE`；`+0x08 rare u32 LE`；`+0x0C subject u32 LE`。指定奖励使用 `rare=0`。
- 用户不能把明文 `0x79C` 直接加到 LZ4 压缩包、封装后的 Pia 帧或存档文件上；上述**仅是解压的 0xAA0**（或 0x3E8 原始 RaidPoint）的偏移。

### 示例：改一行大师球 ×999，仅护符玩家

```text
第一行位于 RaidPoint+0xE4 或 bootstrap+0x79C：
01 00 00 00 | E7 03 00 00 | 00 00 00 00 | 05 00 00 00
 item=1       quantity=999   rare=0         subject=5

同一行全体玩家版只改变最后 4 字节：
01 00 00 00 | E7 03 00 00 | 00 00 00 00 | 00 00 00 00
```

**不用改内核判断指令**即可触发已存在的 `subject=5` 条件；它在接收端 Lua 检查 `Bag.GetNumItem(2481)>0`。该条件是一个**奖励资格过滤**，并非 DLC entitlement 检查、保存完成证明或对官方互联网通信能力的证明。

## 3. ELF 原生序列化函数、寄存器和“指针地址”实证

### 3.1 ELF 身份、静态地址表达

本 ELF 的 `.text` 在虚拟地址 `0` 起、文件内偏移 `0x8D8`。表中 `main+RVA` 是**此 SHA/Build ID 的指令 RVA**，文件中仅 `.text` 的字节读取可按 `0x8D8 + RVA` 验证。Switch 内存 ASLR 后的指令地址需 **runtimeMainBase + RVA**；本文**没有捏造固定 runtimeMainBase**。

| main+RVA | 原始 opcode | ARM64 指令 | 实际含义 |
|---|---|---|---|
| `0xE327FC` | `A9BB7BFD` | `stp x29,x30,[sp,#-0x50]!` | 序列化函数入口 |
| `0xE32814` | `AA0003F4` | `mov x20,x0` | **x20 = 当前输入消息对象指针** |
| `0xE32828` | `52815416` | `mov w22,#0xAA0` | 明文总长 |
| `0xE3283C` | `AA0003F7` | `mov x23,x0` | **x23 = 分配后的明文输出缓冲区** |
| `0xE32844` | `52802B18` | `mov w24,#0x158` | 每份队伍记录长度 |
| `0xE3295C` | `A946A688` | `ldp x8,x9,[x20,#0x68]` | RaidPoint 首段的后两个 qword |
| `0xE32964` | `A945AA8B` | `ldp x11,x10,[x20,#0x58]` | RaidPoint 首段的前两个 qword |
| `0xE32968` | `9101E281` | `add x1,x20,#0x78` | RaidPoint 剩余字段的 memcpy 输入 |
| `0xE3296C` | `52807902` | `mov w2,#0x3C8` | 剩余拷贝长度 |
| `0xE32970` | `F9035EEB` | `str x11,[x23,#0x6B8]` | 先写 RaidPoint 的第一段 |
| `0xE32980` | `94982624` | `bl memcpy@plt` | 复制 `0x3C8` 到 `x23+0x6D8` |
| `0xE329B0` | `141D8073` | `b 0x1592B7C` | 进入下一层消息序列化 |

详见直接来自用户 ELF 的完整反汇编：[原生 ELF 审计](violet400-elf-raid-bootstrap-audit.md)。本次再次比对以下 **13 个**精确 opcode（完整列表在脚本 `OPCODES` 中），全部通过；没有仅通过 Python 的 `raid.py` 常量反推。

### 3.2 源对象和目的缓冲区的运行时地址

由 `main+0xE3295C..0xE32980` 的实际 ARM64 数据流可推出：

| 相对位置 | 公式 | 第 0 行 | 第 44 行 |
|---|---|---|---|
| 源对象 RaidPoint 基址 | `x20 + 0x58` | — | — |
| **源奖励行** | `x20 + 0x58 + 0xE4 + 0x10*i` | **`x20+0x13C`** | **`x20+0x3FC`** |
| 输出 RaidPoint 基址 | `x23 + 0x6B8` | — | — |
| **输出奖励行** | `x23 + 0x6B8 + 0xE4 + 0x10*i` | **`x23+0x79C`** | **`x23+0xA5C`** |
| 源 quantity 字段 | 行指针 `+0x04` | `x20+0x140` | `x20+0x400` |
| 源 subject 字段 | 行指针 `+0x0C` | `x20+0x148` | `x20+0x408` |
| 输出 quantity 字段 | 行指针 `+0x04` | `x23+0x7A0` | `x23+0xA60` |
| 输出 subject 字段 | 行指针 `+0x0C` | `x23+0x7A8` | `x23+0xA68` |

这里的 `x20` 指向**本函数传入的序列化对象**，并不代表任何全局固定地址；`x23` 指向**本次动态分配的明文 buffer**。没有足够证据把它们写成一个跨重启通用的 Cheat Engine 静态 pointer chain。实际断点时需读取寄存器的真实值。

**精确时机**：在 `main+0xE32984`（`memcpy` 已返回、下一条 `mov x8,x21`）暂停时，`x23` 尚未在函数尾部恢复，此时 `[x23+0x79C]` 是完整第 0 行明文数据；`x20` 仍是输入对象。**到 `0xE329A8`，函数会恢复保存的 `x23`，不能在函数返回后直接继续用该寄存器。**

另一个可用的函数关系：`main+0x1BAE790 → 0x1BAFF98` 为 RaidPoint getter 路径；`main+0x1BAE7B0 → 0x1BB0018` 为包装类型相关的 `0x3C8` 复制。getter 按类型标志和指针有效性选择数据，**不能因看到 `[x0+8]` 就断言“这里是固定永久奖励指针”**；这些地址是代码执行锚点而非总会有效的数据指针。

## 4. 几种“修改”方式的真正区别

| 方式 | 修改目标 | 已有证明 / 风险 |
|---|---|---|
| **当前支持：CLI/GUI 设置奖励** | 主持端 `RaidGroup.rewards → raid_point()` | **最稳妥**，不用改 ELF、存档或正版客户端 |
| 修改生成的原始 `RaidPoint` | 0x3E8 中的 `+0xE4+i*16`，重组整体消息 | **可离线复核**，必须保持数据结构长度和余下字段 |
| 修改**解压后的** bootstrap | 0xAA0 中 `+0x79C+i*16` | **可离线复核**；完成后须重新按正确协议压缩/封装 |
| 在真实进程断点改 `x20` 源对象字段 | `x20+0x13C+i*16` | 仅当前调用有效；必须在复制前改，不能假定静态全局地址 |
| 在真实进程断点改 `x23` 输出字段 | `x23+0x79C+i*16` | 仅当前调用有效；`0xE32984` 之后、buffer 被后续序列化之前才是准确窗口 |
| 直接改 ELF 指令字节 | 代码页 ARM64 指令 | **不推荐也不需要**。改 `memcpy` 长度/目标偏移有破坏结构的风险；本轮未创建游戏 ELF patch |

**提示**：如果研究真实内存，应先用只读断点观测正确的 `x20/x23` 与待传数据。直接修改内存有导致联机状态异常、断线或数据丢失的风险。此文档只说明已经证实的字段和调用边界，不把它当作官方互联网模式注入方案。

## 5. 可重复脚本：验证 ELF + 解析或离线修改明文

仓库脚本：[`scripts/research/sv_custom_raid_reward_offsets.py`](../../../scripts/research/sv_custom_raid_reward_offsets.py)。

```bash
# 只读：核验指定 Build ID 的原始 ELF（SHA-256 + 13/13 opcode）
python scripts/research/sv_custom_raid_reward_offsets.py verify-elf Violet4.0.0.elf

# 不打开游戏：查看行的精确源/目标相对地址
python scripts/research/sv_custom_raid_reward_offsets.py layout 0
python scripts/research/sv_custom_raid_reward_offsets.py layout 44

# 从自己已获得的、解压后的 0xAA0 明文读取奖励行
python scripts/research/sv_custom_raid_reward_offsets.py inspect bootstrap.bin

# 离线构造：输出新文件而不覆盖输入；仅支持 0x3E8 / 0xAA0 原始明文
python scripts/research/sv_custom_raid_reward_offsets.py patch bootstrap.bin \
  --reward 1:999:5 --reward 796:999:5 --reward 50:7:0 \
  --output bootstrap_custom.bin
```

`patch` 会**清空旧的 45 行奖励区并放入替换行**，完整保留奖励行范围之外的字节（包括 `+0x3B4..+0x3B7` 的 4 字节间隙、boss、partner、摘要）；拒绝覆盖原输入，限制 `1..45` 行和 subject 0/5，并要求 `RaidPoint_` 魔数与正确大小。它**不包含道具是否在零售 bag 名单的验证**，这一项仍由正式 CLI 的 `prepare_raid` 做；离线成品本身也不是可直接网络发送的压缩数据包。

自测记录：
- 用户 Library 的 `Violet4.0.0.elf`：SHA-256 匹配，**13/13 AArch64 opcode PASS**。
- 合成 `0x3E8` RaidPoint：修改行及其后间隙/前部未更改检查 **PASS**。
- 合成 `0xAA0` bootstrap：相同断言 **PASS**。
- **未进行**实机、商业联网样本、游戏内真正背包增量、存盘重启和官方服务器校验测试。

## 6. 结算与 999 的限制，下一步优先验证

**奖励屏幕 999 ≠ 每次背包净增 999**。客户端 `BattleRewardData` 根据 subject 过滤；胜利时 `GameEventBattleResult.RaidResultAddItem` 依据 `ItemDataManager.GetSlotMaxNum` 先算可增加数量、之后调用 `Bag.AddItem`，进而访问 `BagSaveAccessor` 并发起自动保存。由旧版 Lua + 上游 4.0.0 研究可证明调用机制；真实 `SlotMaxNum` 必须从 [`itemdata_array.bin` 原表](sv400-autosave-and-item-slotmax.md) 读取。若当前库存为 900、上限为 999，单条奖励显示 999，计算上最多增加 99。首次新建记录的限制分支也需单独实测。

**后续 P0**：1）`0x2F` 接收与 Lua `raidBattleRewardData` 的映射；2）实际的 `itemdata_array.bin`；3）原生 `SaveProcess` 完成/失败码及刷盘闭环；4）分离本地 LDN、远程 LDN 中继、Nintendo 官方互联网模式，不能从当前 ELF memcpy 推断第三者已开放任意奖励。

## 参考

- [主持端代码旧版分析（附更正）](custom-raid-rewards-host-elf.md)
- [原版 SV Raid 逆向](../../sv_raid.md)
- [4.0.0 ELF 原生发送路径](violet400-elf-raid-bootstrap-audit.md)
- [Lua 奖励资格及 Bag 入包](raid-reward-to-bag-save-chain.md)
- [SaveProcess / SlotMaxNum](sv400-autosave-and-item-slotmax.md)
