---
title: SV Lua 奖励资格与晶耀护符交叉核对
parent: 朱／紫（SV）
nav_order: 3
---

# SV BattleRewardData / Bag：晶耀护符 ID 2481 的公开 Lua 源码交叉核对

- **研究日期**：2026-10-19
- **研究状态**：**3.0.1 时代公开 Lua 反编译证据已实际核对；4.0.0 原始 Lua / RomFS 仍待独立验证**
- **目标**：核对上游对 `subjectType=5` 的描述；追踪“背包有没有晶耀护符”的数据查询，而不从 ELF 的结构序列化函数猜测 Lua 判断。
- **资料来源**：[`Martmists-GH/SV-Script-RE`](https://github.com/Martmists-GH/SV-Script-RE) `master`，仓库 README 声明覆盖的游戏版本为 **3.0.1（在当时）**；本次直接读取该仓库反编译文本与名称表，**不是当前用户自己的《紫》4.0.0 RomFS**。
- **相关本地实证**：[《紫》4.0.0 ELF bootstrap 审计](violet400-elf-raid-bootstrap-audit.md)；[晶耀护符、联网奖励假说](glimmering-charm-raid-rewards.md)。
- **公开文件 SHA**：`decompiled/C07C34FC3B976E5A7.lua` Git blob `3a8bfe88242a238b8aa3ab93837dc712384d6212`；`split/C07C34FC3B976E5A7.lua` Git blob `506b547a726b30eeb08e884023de88ed09865196`。可复核版本宜额外固定 repo commit，以免 `master` 移动。
- **原始文件规则**：不将 4.0.0 ELF、RomFS 或第三方反编译全文件复制进本仓库；仅记录链接、少量局部代码语义和验证结论。

## 1. 发现的真实类与方法（不是推测）

| 标识 / 路径 | 已定位名称 | 来源 |
|---|---|---|
| `C07C34FC3B976E5A7` | `main.battle.BattleRewardData` | [名称映射](https://github.com/Martmists-GH/SV-Script-RE/blob/master/data/lua_names.h) |
| `F316609DEA110601D` | `BattleRewardData` 的奖励资格过滤方法（名称仍为 hash） | [代码 182–321](https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C07C34FC3B976E5A7.lua#L182-L321) |
| `C14A8D35D72F56FE9` | `main.management.bag.Bag` | [名称映射](https://github.com/Martmists-GH/SV-Script-RE/blob/master/data/lua_names.h) |
| `S90D73F1D715BCBF4` | `Bag.GetInctance`（名称表中的原拼写） | [Bag 定义](https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C14A8D35D72F56FE9.lua) |
| `F547A7E84715631C6` | `Bag.GetNumItem` | [Bag.GetNumItem](https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C14A8D35D72F56FE9.lua#L2820-L2835) |
| `F13D72EF77582090D` | `Bag.FindItemById` | [Bag.FindItemById](https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C14A8D35D72F56FE9.lua#L2771-L2790) |

`be21e65463b9a98f` 是上游 [SV Raid 文档](../../sv_raid.md) 给出的 **Lua 代码块标识**，不能擅自断言存在名为 `be21e65463b9a98f.lua` 的独立 RomFS 文件。真正找到的可读类文件是 **`C07C34FC3B976E5A7.lua`**。没有做代码块标识与外部仓库文件字节的 SHA 等价证明。

## 2. 脚本内实际背包读取链

[BattleRewardData 183–196 行](https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C07C34FC3B976E5A7.lua#L183-L196) 的语义可直译为：

```text
bag = C14A8D35D72F56FE9.S90D73F1D715BCBF4()
count = bag.F547A7E84715631C6(2481)
hasGlimmeringCharm = (count > 0)
```

`Bag.GetNumItem(id)` 不是固定 true：内部调用 `Bag.FindItemById(id)`，遍历背包记录 `self[6][index].itemID`，未找到 ID 返回 `-1`；找到后返回 `self[6][index].num`。因此 `count > 0` **表示背包中确实有大于零的持有数量**，没有独立的 `isDlcPurchased` 或 `getExpansionPassEntitlement` 条件出现在这段函数。

[BattleRewardData 240–299 行](https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C07C34FC3B976E5A7.lua#L240-L299) 的 `subjectType` 条件语义为：

```text
subject 0：允许每位玩家
subject 1：A1_2 为 host 时允许
subject 2：A1_2 为 guest 时允许
subject 3：A4_2 为 true 时允许
subject 4：匹配 boss Tera 类型的 Raid Power Lv.N，按出现顺序保留前 N 条
subject 5：hasGlimmeringCharm 为 true 时允许
```

**判断逻辑（重写后的等价示意，不是逐字反编译）**：

```lua
local hasCharm = bag:GetNumItem(2481) > 0
if reward.subjectType == 5 and hasCharm then
    keep = true
end
```

若 `subjectType=5` 且 `bag:GetNumItem(2481)<=0`，此条件本身不会让奖励行入选。值得注意的是 `subjectType=3` 的资格参数与 `subjectType=4` 的料理团战力**属于不同条件**，不能混为护符判定。

## 3. 与 4.0.0 原生 ELF / PokéLDN 的证据分层

| 结论 | 证据级别 |
|---|---|
| 3.0.1 时代公开 Lua 代码直接读取 `Bag.GetNumItem(2481)`，`>0` 后接受 `subjectType=5` | **本轮独立公开源码核对** |
| 《紫》4.0.0 ELF 中 `RaidPoint` 整块进入 `0xAA0` 的 bootstrap；序列化地址与上游匹配 | **前次 Library ELF 机器码实证** |
| 《朱》4.0.0 Lua 的同名 hash 函数由上游记录为同样的 `subjectType=5` / ID 2481 判定 | **上游 4.0.0 逆向与既有测试**，本轮没有 4.0.0 Lua 实体重新运行 |
| 某视频的联网 999 道具必然使用 `subjectType=5` | **不能证实**：也可能是奖励行 `subjectType=0` + 商家额外前置要求 |
| “必须购买 DLC”的判定在这段 Lua 过滤函数内实现 | **无证据**；目前这段只检查接收端背包数量，不代表整个联网/入场链完全不验 DLC |

### 与商品“必须有晶耀护符”的关系

可以得到**可检验假说**：商业主持方把部分或全部自定义奖励行标记为 `subjectType=5`，使没有 2481 的玩家收不到这些行。它解释了为何商家强调护符，但**不是商业协议实现的证明**。公开 `pokeldn/sv/raid.py` 的自选 `rewards` 使用 `subjectType=0`，因此官方开源参数本身没有这个资格门槛。

## 3.1 追加：奖励 Lua 原始调用链的中文逻辑拆解

已固定公开脚本版本为 [SV-Script-RE commit 1f843bd](https://github.com/Martmists-GH/SV-Script-RE/tree/1f843bd2517c707fbb47491dad58856eaa2c2cc7)，并追踪 `BattleRewardData` 的调用方以及团体战结算入包。用户确认奖励 Lua 行为与 4.0.0 完全一致；**本次没有原始 4.0.0 RomFS 字节供逐字 hash 对比**。

**源码入口**：
- [`GameEventNetworkBattleRaid` 1512–1549 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C849FF496D0E93636.lua#L1512-L1549)：传入 `raidBattleRewardData`，封装为 `[92]`，随后调用奖励过滤函数；
- [`BattleRewardData.F316609DEA110601D` 183–321 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C07C34FC3B976E5A7.lua#L183-L321)：实际资格过滤代码，先通过 `Bag.GetNumItem(2481)>0` 得到护符布尔值，再按 `subjectType` 逐行筛选，过滤后的奖励行放回 `self[3]`；
- [`Bag.FindItemById` 2771–2790 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C14A8D35D72F56FE9.lua#L2771-L2790)：按 `itemID` 找背包数组位置；[GetNumItem 2820–2835 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C14A8D35D72F56FE9.lua#L2820-L2835) 返回 `num` 或缺失时 `-1`；
- [`GameEventBattleResult.RaidResultAddItem` 1625–1697 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C889F6553EDFCD011.lua#L1625-L1697)：获胜后逐行执行 `Bag.AddItem`；有 `SlotMaxNum` 容量调整；
- [`SaveLoadManager.RequestAutoSave`](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C073521D193106184.lua#L92-L105)：团体战结算分支申请自动保存。

下面代码是**对公开 Lua 反编译逻辑的等价语义重写**，用可读英文变量代替哈希、临时变量；不是完整零售 Lua bytecode：

```lua
-- Phase 1: receiving-side eligibility
local hasCharm = bag:GetNumItem(2481) > 0
local eligible = {}
local powerRow = 0
for _, r in ipairs(raidRewards) do
    local ok = (r.subjectType == 0)
        or (r.subjectType == 1 and isHost)
        or (r.subjectType == 2 and not isHost)
        or (r.subjectType == 3 and onceEligible)
        or (r.subjectType == 4 and powerRow < matchingRaidPowerLv)
        or (r.subjectType == 5 and hasCharm)
    if r.subjectType == 4 then powerRow = powerRow + 1 end
    if ok then eligible[#eligible+1] = r end
end

-- Phase 2: victory settlement; independent of display/eligibility
for _, r in ipairs(eligible) do
    local n = r.ItemNum
    if bag:WouldExceedExistingSlotLimit(r.ItemNo, n) then
        n = bag:RemainingCapacity(r.ItemNo)
    end
    if n > 0 then bag:AddItem(r.ItemNo, n) end
end
saveLoadManager:RequestAutoSave(0)  -- this is a request, not confirmed completion
```

**注意准确性**：`WouldExceedExistingSlotLimit` 和 `RemainingCapacity` 是对未命名的 `F2001F41E6B757BB1`/`F6C18EEC27ED4BA1E` 的解释性命名，原始接口不是这些名称；还需要核对奖励分支条件 `type=2` / `result[1]=1`。完整代码分析、首次获得与已有道具不同的限制处理、2137 特例和存档阶段证据，见 [《太晶坑奖励入包与自动保存调用链》](raid-reward-to-bag-save-chain.md)。


## 4. 本轮材料搜寻结果与下一步

本轮查了用户 Library 的 ELF 文件、Lua 扩展名和 RomFS 相关文档，也检索了 `be21e65463b9a98f`；已有 `Violet4.0.0.elf` 和历史分析文档，但**未定位到 4.0.0 的原始 RomFS Lua 资源文件**。Library 中的 `dir.txt` 出现的本地硬盘路径只是目录清单，不能视为其提及文件已实际上传到 Library。

下一步：由用户自己合法获取的《紫》4.0.0 RomFS 找到对应原始 Lua 资源（可能是在捆绑/压缩容器内部，不一定是独立的 `.lua`）；记下文件大小、哈希、容器及解包工具。再对比此处公开的 3.0.1 反编译函数、上游 4.0.0 字节码行 78707–78765，并在可重复环境验证 `GetNumItem(2481)`。**任何从完整 ELF 到 Lua bytecode 的关联必须凭实际容器/资源加载链给出，不能只靠哈希名或 4.0.0 ELF 指令推断**。

## 参考

- [SV-Script-RE 项目](https://github.com/Martmists-GH/SV-Script-RE)
- [BattleRewardData](https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C07C34FC3B976E5A7.lua)
- [Bag](https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C14A8D35D72F56FE9.lua)
- [上游 PokéLDN 的 4.0.0 Lua 实验记录](../../sv_raid.md)
