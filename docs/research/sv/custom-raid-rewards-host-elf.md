---
title: SV 自定义太晶坑奖励：PokéLDN 源码与《紫》4.0.0 ELF 复核
parent: 朱／紫（SV）
nav_order: 5
---

# PokéLDN 自定义太晶坑奖励：主机生成、RaidPoint 字段、客户端发奖

- **日期**：2026-10-19
- **研究分支**：`969981/pokeldn@research`；仅提交技术笔记，不修改游戏 ELF、网络协议或现有项目代码。
- **结论**：PokéLDN 原版已有 `--raid-reward ITEM:QUANTITY`。它**替换整个种子默认奖励列表**，支持二元组 `(item,quantity)` 自动采用 `subject=0`，也支持三元组 `(item,quantity,subject=5)` 按晶耀护符过滤；不同设置仍只改 RaidPoint 数据行，不需要游戏 ELF 补丁。修改资格的位置是**主持端 RaidPoint 奖励行的第四个 u32：subject**，并非修改 ELF。
- **验证级别**：实际读取用户 Library 中的 `Violet4.0.0.elf`，校验 SHA、Build ID、15 条相关机器指令 **15/15 PASS**；仓库源码与现有自动化测试证明生成逻辑；**未在本轮运行真实 Switch 团体战、自动保存或互联网房间测试**。
- **避免混淆**：ELF 已验证「传入 RaidPoint 的原生序列化」，`subject` 资格判定来自上游 4.0.0 Lua 实验及固定版本公开 Lua 反编译；二者不是同一层面的指令证据。

## 1. 从 GUI/CLI 到游戏的完整数据路径

```text
GUI Tera Raid (Host) → RewardPicker {item_id, quantity, optional subject}
                         ↓ 命令构造
bin/sv_host.py: --raid-reward ITEM:QUANTITY[:SUBJECT] (可重复)
  raid_reward() → (item, quantity[, subject])
  prepare_raid() → 验证数量、45 行上限、是否属于 SV bag
                         ↓
RaidGroup(..., rewards=...)
  raid_point(raid, rewards=...)                 [pokeldn/sv/raid.py]
    rewards 非 None → (item, quantity, rare=0, subject=0/5)
    pack_into("<IIII", RaidPoint, 0xE4 + i*0x10, ...)
                         ↓
bootstrap() = 4×0x158 参与者 + 0x158 boss + 0x3E8 RaidPoint
bootstrap_message() → LZ4 → 0x3380 / kind 0x2F
                         ↓
游戏客户端接收/解码 → raidBattleRewardData
  BattleRewardData.F316609DEA110601D → 按 subject 过滤
                         ↓（仅获胜）
GameEventBattleResult.RaidResultAddItem
  → Bag 容量核验 → Bag.AddItem → BagSaveAccessor
  → SaveLoadManager.RequestAutoSave → StartSaveProcess (更下层未闭合)
```

**源码锚点（本轮实际读取）**：

1. [`bin/sv_host.py`](https://github.com/969981/pokeldn/blob/research/bin/sv_host.py)：`raid_reward()` 原始 209–223 行、`--raid-reward` 参数约 395–397 行、`prepare_raid()` 原始 436–451 和 495 行。
2. [`pokeldn/sv/raid.py`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py)：`POINT_REWARDS=0xE4`、`REWARD_ROWS=45`；`raid_point()` 原始 170–200 行；`bootstrap()` 203–211；`bootstrap_message()` 214–218；`RaidGroup.bootstrap()` 原始 284–290 行。
3. [`pokeldn/sv/raid_encounter.py`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid_encounter.py)：`reward_rows()` 254–291 行。它生成**原版种子奖励**：固定表保留 subject，普通抽奖 subject=0，额外料理抽奖 subject=4，晶耀护符太晶碎块 subject=5。和自定义奖励路径不同。
4. [`gui/views/rewards.py`](https://github.com/969981/pokeldn/blob/research/gui/views/rewards.py) 的 `RewardPicker`：能编辑道具/数量，预设包括训练、太晶碎块、秘传调味料、财宝、球；当前支持每行 subject 0/5 编辑。
5. [`tests/test_gui_rewards.py`](https://github.com/969981/pokeldn/blob/research/tests/test_gui_rewards.py) 的 `test_a_bundle_survives_saving_and_reaches_the_scripted_console`：解析最终 bootstrap 的 45 行，**断言模板默认 subject=0 时自定义奖励为 `(item_id, 999, 0, 0)`；当前另有 subject=5 的单测**，剩余行全零。该项是仓库已有测试代码；本轮检查了断言内容，**没有重新运行 pytest**。

### 1.1 当前分支如何自定义奖励

命令行可重复传入：

```bash
./.venv/bin/python bin/sv_host.py \
  --raid-seed 000F34C3 \
  --raid-pokemon host.pk9 \
  --raid-reward 15:500
```

`15:500` 是先机球（Quick Ball）×500 的演示；实际运行需有正常的主持端网络/宝可梦文件/设备准备。整数解析使用 `int(value, 0)`，可以给道具 ID/数量写十进制或 `0x` 前缀。当前 `raid_reward` 限制道具 ID 为 `1..65535`，数量为 `1..999`；`prepare_raid` 还要求道具 ID 在 `pokemon_service.SERVICE.names("sv", "bag")` 中，拒绝超过 **45 行**。**关键物品和不在可用 bag 列表中的道具不属于本功能接受的奖励。**

- 未指定 `--raid-reward`：`RaidGroup` 得到 `None`，沿用随机种子/活动配置生成的零售奖励（含原生 subject 1、3、4、5）。
- 指定一行或多行：`raid_point` 把每条自定义行重建成 `(item, quantity, 0, subject)`，缺省 subject=0；当前支持显式 5；**不是「额外追加」到固定掉落之后**。
- GUI RewardPicker 当前已经可选择 All players（subject=0）或 Glimmering Charm only（subject=5），并正确传递到 CLI。
- `999` 是现有 CLI/GUI 对**请求数量**的限制；它**不证明**某件物品的真实 `SlotMaxNum` 一定等于 999，也不能证明库存增加 999。

## 2. 0xAA0 bootstrap / RaidPoint 奖励字段的精确布局

上游 4.0.0 团体战 `0x3380` 消息的 `0x2F` battle bootstrap 解压后为 `0xAA0` 字节：

| bootstrap 偏移 | 字节数 | 内容 |
|---|---:|---|
| `0x000..0x6B7` | `5×0x158` | 4 个参与者队伍记录 + 1 个首领记录 |
| `0x6B8..0xA9F` | `0x3E8` | RaidPoint，含身份、时间、首领配置、奖励、摘要等 |
| `0x79C` | `0x10` | 第一条奖励行：`0x6B8 + 0xE4` |
| `0xA5C` | `0x10` | 第 45 条奖励行（从 0 开始索引 44） |
| `0xA6C..0xA6F` | `4` | 奖励区与摘要之间的非完整行间隙，不要写入第 46 行 |
| `0xA70` | `0x1C` | RaidPoint `+0x3B8` 起的 7 个 u32 摘要字段 |

奖励记录 16 字节，小端序：

| 行内偏移 | 类型 | 含义 |
|---|---|---|
| `+0x00` | u32 LE | `ItemNo` / 道具编号 |
| `+0x04` | u32 LE | `ItemNum` / 请求数量 |
| `+0x08` | u32 LE | `rare` / 稀有标记 |
| `+0x0C` | u32 LE | `subject` / 资格条件 |

绝对的明文 bootstrap 行地址为 `0x79C + 16*i`（`0 ≤ i < 45`）；**不能将这个偏移直接当作加密/LZ4 网络包偏移**。`raid_point` 实际使用 `struct.pack_into("<IIII", out, 0xE4+i*16, *row)`，而 `bootstrap_message` 才对整个 `0xAA0` 明文应用 LZ4。

例如**第 0 行**设置 ID `15`（先机球）、数量 `500`，`subject=0`：

```text
0F 00 00 00 | F4 01 00 00 | 00 00 00 00 | 00 00 00 00
 item=15      quantity=500     rare=0         subject=0
```

若只把**同一行**最后一个 u32 改成 5，则变为：

```text
0F 00 00 00 | F4 01 00 00 | 00 00 00 00 | 05 00 00 00
```

**解释**：这是离线计算的结构示例，展示服务器/主持端如何编码数据。它不代表已在本轮实机验证修改后的 `subject=5` 发放/保存成功。

## 3. Library 《紫》4.0.0 ELF：本轮再次执行的独立静态核验

**实际输入**：用户 Library 的 `Violet4.0.0.elf`，74,362,480 字节，ELF64 AArch64 little-endian, ET_DYN/PIE, stripped。

- SHA-256：`d17403eaa9d844db82f647fd2f1518806b10c0518d53602fc0ac1766298fdba0`
- Build ID：`709bfd66115298640155fcc4979dba151c7cc79a`
- `.text` 文件偏移：`0x8D8`；在本文件的 `.text` 段核对 `RVA + 0x8D8`。
- 使用 `file`、`readelf -n`、Python `struct.unpack_from("<I", ...)`、`llvm-objdump`；原研究 [机器码审计](violet400-elf-raid-bootstrap-audit.md) 中的 **15 个 opcode 本轮独立重跑 15/15 通过**。

| RVA（main+） | 机器码 | 直接观察 |
|---|---|---|
| `0xE32828` | `52815416` | 初始化消息总长 `0xAA0` |
| `0xE32844` | `52802B18` | 参与者/首领队伍记录长度 `0x158` |
| `0xE32960` | `911B62E0` | `RaidPoint+0x20` 复制到明文 `0x6D8` |
| `0xE32968` | `9101E281` | 数据源为对象 `+0x78` |
| `0xE3296C` | `52807902` | 后段复制长度 `0x3C8` |
| `0xE32970` | `F9035EEB` | 把 RaidPoint 前 8 字节放至 `+0x6B8` |
| `0xE32980` | `94982624` | 调用 `memcpy@plt` |
| `0xE329B0` | `141D8073` | 跳向 `0x1592B7C` 的序列化链 |
| `0x1592EA4` | `97C62AA7` | 调用 `0x71D940`（上游确认的 LZ4 路径） |

此外再次核对 `0xE3294C`、`0x1BAE790`、`0x1BAE798`、`0x1BAE7B0`、`0x1BB003C`、`0x1BAFFF4` 等完整 15 项。它们证明原生代码会将**整块** RaidPoint 放入 bootstrap，**不能单凭 memcpy 证明游戏没有继续过滤字段、道具合法性或保存容量**。当前只适用于这个固定 Build ID。

## 4. subject 0–5：自定义发奖必须区分接收者资格

| subject | 真实语义 | 证据/实现含义 |
|---|---|---|
| `0` | **所有玩家** | 二元组自定义奖励默认选择；无需晶耀护符 |
| `1` | 房主 | 依角色标志过滤 |
| `2` | 加入方 | 依角色标志过滤 |
| `3` | 一次性奖励满足资格时 | 容易漏掉：它确实存在；依外部 once-eligible 参数 |
| `4` | 与首领太晶属性匹配的团战力 | 按顺序只保留前 N 行（N 为相符 Raid Power 最高等级 0–3）；不等价于全体加奖 |
| `5` | 持有 **晶耀护符 Glimmering Charm，item ID 2481** | 接收方 `Bag.GetNumItem(2481)>0` 时保留该行 |

原版的 `RaidRewardItemSubjectType` 表枚举一般列 0–3，但结算 Lua 额外识别 4/5。**护符 ≠ 闪耀护符；资格判断不是「是否购买 DLC」这个布尔值**。正常获取晶耀护符涉及《碧之假面》DLC 的进度，不能由该代码段推出实际有没有其他 DLC 前置检验。

Lua 证据：上游 [`docs/sv_raid.md`](https://github.com/Decryptu/pokeldn/blob/main/docs/sv_raid.md) 给出 4.0.0 `C07C34FC3B976E5A7.F316609DEA110601D` 的实验；[固定 commit 的公开旧版 BattleRewardData 183–321 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C07C34FC3B976E5A7.lua#L183-L321) 与 [Bag](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C14A8D35D72F56FE9.lua#L2820-L2835) 的公开反编译可交叉核对 `2481` 查询；参见 [原有交叉研究](battle-reward-lua-cross-version.md)。

**关键边界**：此 ELF 是原生 ARM64，不是 4.0.0 原始 RomFS Lua blob。公开 Lua 的历史基线约 3.0.1，上游拥有 4.0.0 的 Lua 测试证据，但本轮没有重新获得并字节匹配 4.0.0 Lua。切勿写成「4.0.0 ELF 中直接查到了 GetNumItem(2481) 汇编判断」。

## 5. 当前 research 已经正式支持 subject 5（2026-10-19 勘误）

**原本“subject 5 只是未来建议、CLI 仅支持二元组”的描述已经过时。** 当前 `bin/sv_host.py:raid_reward()` 正式接受 `ITEM:QUANTITY[:SUBJECT]`，限 `subject=0/5`；`raid_point` 接受 `(item,quantity)` 或 `(item,quantity,subject)`，将第四个 `u32` 写成所选 subject。GUI 的 RewardPicker 已有资格条件下拉框，测试覆盖 GUI→CLI→bootstrap 及第三字段正确保留。

**具体用法与更精确的原生 x20/x23 运行时字段地址，见 [新的指针与修改技术文档](sv400-custom-reward-pointer-patch.md)。** 旧二元组仍自动填 `subject=0`；非空自定义奖励依然**替换**所有种子原奖励。游戏的 `subject=5` 过滤不是购买 DLC 检查，真正加入背包还要看胜利/容量/保存。

```bash
python bin/sv_host.py --raid-seed 000F34C3 --raid-pokemon host.pk9 \
  --raid-reward 1:999:5 --raid-reward 796:999:5 --raid-reward 50:7:0
```

**道具 ID 勘误**：Quick Ball（先机球）= `15`；Fast Ball（速度球）= `492`，不要把 `492` 当先机球。


## 6. 接收端结算、数量上限与保存的边界

实际发奖**不等于**收到 bootstrap：

```text
GameEventNetworkBattleRaid.raidBattleRewardData
 → BattleRewardData 过滤 subject
 → 团体战获胜 (type=2, result[1]=1)
 → GameEventBattleResult.RaidResultAddItem
 → 对每个 ItemNo/ItemNum 检查 Bag / ItemDataManager.SlotMaxNum
 → Bag.AddItem
   → runtime Bag + BagSaveAccessor（已知访问器调用）
 → SaveLoadManager.RequestAutoSave(0)
 → RunAutoSaveRequest
 → StartSaveProcess
 → 实际文件序列化 / 写入完成 / 重启保留（本轮未证明）
```

公开 Lua 源文件、行号及此前实证见 [奖励到背包与自动保存链](raid-reward-to-bag-save-chain.md)。若道具原有 900，实际 `SlotMaxNum` 为 999，显示的奖励 ×500 并不意味着能再增加 500：按旧版 `RaidResultAddItem` 的已观察分支，容量至多容纳 99。**首次创建新道具记录**和**已有道具加量**在旧版 `Bag.AddItem` 中还有不同路径，不能武断认为所有异常值都绝对被自动截断、或一定永久保留。

上游报告“正版 Switch 实收自定义先机球 ×500”，是在其描述的**本地 LDN 主持场景**中实现；**不能**据此推断商业“联网 999 奖励坑”通过 Nintendo 官方互联网匹配使用同一种传输/授权实现，也不能推断官方服务器完全不复核。该商业案例是否采用 `subject=5` 仍是待测假说，不能当作逆向结论。

## 7. 可复现的验收与下一步

| 任务 | 本轮状态 | 后续验收 |
|---|---|---|
| 4.0.0 ELF 身份、15 条 bootstrap/serializing opcode | **本轮实跑：15/15 PASS** | 其他版本须另建 Build ID / RVA 表 |
| GUI → CLI → 序列化为 `(item,999,0,subject)` | **仓库源码及 subject=0/5 的既有测试证据** | 本次未运行 pytest；可重跑 `tests/test_gui_rewards.py` |
| 自选奖励 45 行、替换语义、bag 白名单、数量 1..999 | **源码明确** | 加入边界单测、重复 item 的例子 |
| `subject=0`/`5` 静态编码差异 | **当前源码已实现并有单测** | 继续核对多行组合、资格和真实客户端 |
| 实机有/无晶耀护符对照 | **未运行** | 持同一奖励包的小额物品试验 |
| `StartSaveProcess` → 完成回调、断电重启后数据 | **P0 未闭合** | 不要把排队/调用访问器等同成功刷盘 |
| 每种道具 `SlotMaxNum`，含大师球、金色王冠、经验糖果 | **P0 未核实具体数值** | 从实物表/游戏资源取字段并交叉验证 |
| 官方互联网模式与远程 LDN 桥接的区别 | **未测** | 仅以经过授权的匿名化报文、环境对照验证 |

### 参考与项目已有记录

- [PokéLDN 官方 Tera Raids](https://github.com/Decryptu/pokeldn/blob/main/docs/sv_raid.md)（上游 4.0.0 结构、Lua、实机先机球 ×500）。
- [本仓库 `pokeldn/sv/raid.py`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py)；[`bin/sv_host.py`](https://github.com/969981/pokeldn/blob/research/bin/sv_host.py)；[GUI test](https://github.com/969981/pokeldn/blob/research/tests/test_gui_rewards.py)。
- [ELF 机器码审计](violet400-elf-raid-bootstrap-audit.md)、[Lua 奖励资格](battle-reward-lua-cross-version.md)、[晶耀护符假说](glimmering-charm-raid-rewards.md)、[奖励入包/自动保存](raid-reward-to-bag-save-chain.md)。

> 不提交 ELF、固件、提取的加密游戏文件、私有密钥或完整反编译游戏资源。本页只保存源码指针、少量机器码与离线演示，严格区分“上游实机验证”“当前原始 ELF 静态实证”“公开历史 Lua”和“待验证假说”。
