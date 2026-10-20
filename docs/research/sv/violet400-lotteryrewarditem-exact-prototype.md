---
title: 《紫》4.0.0 LotteryRewardItem 精确定位和单条晶耀奖励追加
parent: 朱／紫（SV）
nav_order: 13
---

# Violet 4.0.0：LotteryRewardItem 静态锚点与单条 subject=5 追加门槛

- 记录日期：2026-10-20。
- 游戏：Pokemon Violet 4.0.0。
- 状态：**历史静态分析已记录精确绑定；本轮尚无完整原始 main.blua，未重新执行对应原始字节码核验，也未安装实机 Hook。**
- 对应工作：[后置追加 P1](sv400-lua-post-lottery-append-hook.md)、[生成端](fieldraidjewelry-lotteryrewarditem-glimmering.md)、[接收端](battle-reward-lua-cross-version.md)。

## 1. 原版 Lua 字节码标识

从此前保存的 Violet 4.0.0 静态字节码验证报告整理出[可机器读取的锚点](references/violet400-reward-prototype-anchors.json)：

- 原始 main.blua 长度 12,912,264 字节，SHA-256 = c1a4f4e2625912cf0b739a642a79ba3357df0557a544b92da22a6cb139de2815。
- Lua 5.4 root code count = 429,034；root children = 30,829；总 Prototype 数 = 37,743。
- 游戏内路径：romfs/script/lua/bin/release/main/main.blua。

| 方法 | Prototype | 指令区文件偏移 | 指令数 |
|---|---|---|---|
| FieldRaidJewelry.LotteryRewardItem（FE77BCB620AB2EDCA） | root/2899 | 0x377501 | 477 |
| BattleRewardData.F316609DEA110601D（护符过滤） | root/4870 | 0x410673 | 137 |
| GameEventBattleResult.RaidResultAddItem | root/3756 | 0x3B1E39 | 69 |
| RaidMatchingView.FCE48462FE20C26A7（45 槽写入） | root/27146 | 0xAA084E | 91 |

LotteryRewardItem 的提前返回候选 PC：27、33、39、53；原版生成完成后附近**候选** PC：475。

~~~text
Lua instruction file offset at PC 475:
0x377501 + 475 * 4 = 0x377C6D
~~~

**注意**：这些位置是 Lua binary chunk 的 file offset / PC，不是 Switch 运行时地址，不是 ARM64 RVA。PC475 的准确控制流和 opcode 需要持有原版 main.blua 后逐条核验；不可直接将此处当作已经可安全插入 Hook 的地址。

## 2. 本轮新增工具

- [sv400_exact_reward_gate.py](../../../scripts/research/sv400_exact_reward_gate.py)：只读、严格校验 SHA-256、文件长度、root shape、四个 Prototype 路径与 code offset、指令数量；导出 PC 对应的原始指令字段。
- [test_sv400_exact_reward_gate.py](../../../tests/test_sv400_exact_reward_gate.py)：使用人工合成的 Prototype 检查错误版本、错位、越界 PC 的 fail-closed 行为，并沿用原有 reward append 模型验证原始前缀及护符条件。
- 原有 [sv_lua_reward_append_prototype.py](../../../scripts/research/sv_lua_reward_append_prototype.py)：仅模拟 BattleRewardData[3] 的末尾追加和客户端筛选，不改真实 Lua、不直接发奖。

在从用户自己的 4.0.0 游戏资源提取文件后，可运行：

~~~powershell
python scripts/research/sv400_exact_reward_gate.py "D:\SV\romfs\script\lua\bin\release\main\main.blua" --output violet400_reward_gate.json
pytest -q tests/test_sv400_exact_reward_gate.py tests/test_sv_lua_reward_append_prototype.py
~~~

门槛通过仅输出 EXACT_VIOLET_400_STATIC_ANCHORS_RECHECKED，**不是 Mod 或实机闭环**。

## 3. 单条 subject=5 无损追加：当前的验证边界

预期语义：

~~~text
Original = 零售版固定、随机、料理、晶耀奖励行
Extra = [492, 1, 0, 5]   (仅供测试的一条道具记录)
if len(Original) + 1 > 45: FAIL CLOSED
else: BattleRewardData[3] = Original + [Extra]
~~~

- 原版奖励列表必须完整保留，顺序、ItemNo、ItemNum、rareType、subjectType 均不变。
- 新增行应放在 LotteryRewardItem **完成原版奖励生成之后**、45 槽序列化之前，避免更早初始化流程清除 subject=5。
- 持有晶耀护符（背包道具 ID 2481）时，F316 奖励过滤逻辑允许 subject=5；没有护符时不允许。多个 subject=5 行在已知 Lua 循环中逐行判断，但仍需真实入包验证。
- **现有自动化只验证模拟器/模型语义**，没有证明 4.0.0 的零售版在 Switch 实际读取了新增奖励或永久保存。
- 追加总数大于 45 的情况下必须不修改原版数据；禁止覆盖或截断任何一条原版奖励。

## 4. 必须闭环的实机证据（尚未执行）

1. S0：同一局 seed 的原版奖励、背包和星级记录。
2. S1：生成后 BattleRewardData[3] 原版行原样保留，额外恰好一条 subject=5。
3. S2：当前房主源 RaidPoint 与本地 LDN 0x2F 发送对象都含该行，所有原版行仍在。
4. S3：客户端 F316 根据是否持有 2481 保留/过滤新增行。
5. S4：获胜后背包道具数量实际按游戏 SlotMaxNum 增加。
6. S5/S6：保存完成并彻底重启游戏，额外道具仍存在。

**当前阻塞**：完整原版 main.blua 尚未在可访问文件中；未完成可重编译/重打包的 Lua 4.0.0 改写，也没有实际 Hook 位置和运行时对象证据。原始游戏文件不提交到公开仓库。
