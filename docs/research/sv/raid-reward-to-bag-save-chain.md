---
title: SV 太晶坑奖励入包与自动保存调用链
parent: 朱／紫（SV）
nav_order: 4
---

# 《朱／紫》太晶坑奖励：RaidPoint → Lua 过滤 → 背包 AddItem → 自动保存请求

- **日期**：2026-10-19
- **范围**：研究公开逆向 Lua 中的结算到背包流程，交叉对照用户 Library《紫》4.0.0 ELF 及 PokéLDN；不修改存档、ELF、服务器或账号
- **源代码版本**：`Martmists-GH/SV-Script-RE` **固定 commit `1f843bd2517c707fbb47491dad58856eaa2c2cc7`**，公开反编译 README 基线约 **3.0.1**
- **用户确认**：用户表示该奖励 Lua 行为与 4.0.0 完全一致；本页按该确认继续研究，但**没有独立获取并逐字比对 4.0.0 RomFS Lua 原始模块**；源代码位置引自上述固定 commit
- **实证边界**：4.0.0 ELF 发送端机器码见 [独立审计](violet400-elf-raid-bootstrap-audit.md)；此处的 Lua 函数体证据是固定旧版公开源码；没有完成实机保存、联网新会话和服务器校验的端到端实验。

## 0. 一图看懂调用关系

```text
PokéLDN raid.py / 原生 main+0xE327FC
  RaidPoint (+0x0E4: item, quantity, rare, subject) → bootstrap 0x2F
                              │
                              ▼
GameEventNetworkBattleRaid
  C849FF496D0E93636.lua 1512–1549
  param.raidBattleRewardData → context[92] / BattleRewardData.F316609DEA110601D
                              │
                ┌─────────────┴──────────────┐
                ▼                            ▼
BattleRewardData                 Bag.GetNumItem(2481)
  subjectType 0..5                 >0 → subject 5
  形成 self[3] 过滤列表
                │
                ▼
GameEventBattleResult
  C889F6553EDFCD011.lua 352–357: result[1] == 1（获胜）调用 RaidResultAddItem
  C889F6553EDFCD011.lua 1625–1697: 读取 self[18][92][3][i]
                │
                ▼
Bag.F2001F41E6B757BB1(item, amount)
  如果当前持有该道具且 current + amount > SlotMaxNum → 限制新增数量
                │
                ▼
Bag.F6C18EEC27ED4BA1E(item) → remaining capacity
                │
                ▼
Bag.AddItem(item, allowedAmount)
  C14A8D35D72F56FE9.lua 2970–3064
                │
                ▼
GameEventBattleResult 获胜结算同一分支
  C889F6553EDFCD011.lua 530–535
  SaveLoadManager.RequestAutoSave(0)
                │
                ▼
实际 save 文件提交 / 刷盘 / 联网重连保留：本轮未闭合
```

注意：由消息反序列化到 `raidBattleRewardData` 对象的**接收端 native/Lua 桥接细节**仍需逐层核实；图中“传至 BattleRewardData”是程序数据结构与已有上下游代码的关联，并非本轮抓包逐步追踪的完整同一对象实例证明。

## 1. 发奖前：调用资格过滤的明确时机

[`GameEventNetworkBattleRaid` 第 1512–1549 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C849FF496D0E93636.lua#L1512-L1549)：

- 从 `self[17].raidBattleRewardData` 取得传入的团体战奖励；
- 以 `L58_1` 封装后写入 `self[19][92]`；
- 在战斗开始/进入相应流程之前，调用 `self[19][92].F316609DEA110601D(...)`；
- 这一步依据角色、是否满足一次性条件、属性/料理效果和晶耀护符，过滤奖励对象内部 `[3]` 列表。

**与“获胜才发物品”的区别**：这个函数是**资格过滤阶段**，不等于背包已经收到 `ItemNum`。实际加背包发生在下面的 `GameEventBattleResult`。

### 1.1 晶耀护符判定的 Lua 等价伪代码

由 [BattleRewardData 183–196 和 240–299 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C07C34FC3B976E5A7.lua#L183-L299)、[Bag.GetNumItem 2820–2835 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C14A8D35D72F56FE9.lua#L2820-L2835) 还原（**不是原代码逐字粘贴**）：

```lua
local bag = Bag.GetInstance()
local hasCharm = (bag:GetNumItem(2481) > 0) -- 晶耀护符

for _, reward in ipairs(rewards) do
    local keep = false
    if reward.subjectType == 0 then
        keep = true
    elseif reward.subjectType == 1 and isHost then
        keep = true
    elseif reward.subjectType == 2 and not isHost then
        keep = true
    elseif reward.subjectType == 3 and onceEligible then
        keep = true
    elseif reward.subjectType == 4 then
        keep = matchingRaidPowerLevel > numberOfPreviousSubject4Rows
    elseif reward.subjectType == 5 then
        keep = hasCharm
    end
    if reward.subjectType == 4 then numberOfPreviousSubject4Rows =
        numberOfPreviousSubject4Rows + 1 end
    if keep then filtered[#filtered+1] = reward end
end
```

`isHost`、`onceEligible`、`matchingRaidPowerLevel` 是为解释而命名的逻辑变量；3.0.1 反编译函数实参依次为 `A1_2..A4_2`；具体角色和餐力参数由调用方传入，不能把此伪代码作为真实游戏的完整 Lua 运行环境。

### 1.2 代码中“同道具合并”的位置与边界

[`BattleRewardData.F8975ECC0360F96CE` 101–179 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C07C34FC3B976E5A7.lua#L101-L179) 提供**可选的同类奖励行汇总方法**：

```text
对每行奖励:
    如果已有行满足 ItemNo 相同 且 rareType 相同:
         已有 ItemNum += 当前 ItemNum
    否则:
         新建一行（保留 ItemNo/ItemNum/rareType/subjectType）
```

**重要陷阱**：匹配条件中**没有 subjectType**。因此若该方法在资格过滤之前使用，subject 不同的两行可能合并到第一行并继承其 subject；但搜索到的方法本身并不能证明其在此具体团体战路径的调用时机。本轮未找到确定的调用点，**不能断言所有奖励一定在入包前合并，也不能拿此方法解释商品图片中每项 ×999**。

## 2. 胜利后：真正向背包加道具的 Lua 函数

[`GameEventBattleResult` 第 305–357 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C889F6553EDFCD011.lua#L305-L357) 显示：事件类型 `self[17].type == 2`、结算结果 `self[19][1] == 1` 时调用 `self.FCBBD4D63B93E4C04()`；对应名称映射 **`RaidResultAddItem`**。

[`RaidResultAddItem` 第 1625–1697 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C889F6553EDFCD011.lua#L1625-L1697) 从 `self[18][92][3]` 遍历奖励，对每个 `ItemNo` 做三步：

1. 以原始 `ItemNum` 初始化想要发放的数量；
2. `Bag.F2001F41E6B757BB1(ItemNo, ItemNum)` 检查是否超过 `SlotMaxNum`；若超过则以 `Bag.F6C18EEC27ED4BA1E(ItemNo)` 取得剩余容量，并将应发数改为该值；
3. 如果调整后的数量大于零，才调用 **`Bag.FB01A9B29CD4CC6CB(ItemNo, adjustedAmount)`**，即 `Bag.AddItem`。

代码中特例是 **item ID 2137**：如超过背包数量上限，会把无法容纳的部分累计到名为 `WSYS_COIN_OVERFLOW_NUM` 的变量。这个特例**不能推广到大师球、经验糖果等所有道具**。

### 2.1 三个具体方法的源码意义

| 类 / 函数 | 证据链接 | 实际语义 |
|---|---|---|
| `Bag.F2001F41E6B757BB1` | [3089–3114](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C14A8D35D72F56FE9.lua#L3089-L3114) | **针对已有该道具记录**，判断 `existing + delta > max` |
| `Bag.F6C18EEC27ED4BA1E` | [3064–3088](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C14A8D35D72F56FE9.lua#L3064-L3088) | `max`（没已有记录）或 `max - current`（已有记录） |
| `Bag.FB01A9B29CD4CC6CB` | [2970–3064](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C14A8D35D72F56FE9.lua#L2970-L3064) | **AddItem**：先查 ID、类别；新道具分支建立记录并直接写数量；已有道具分支 `current += delta` 后按上限截断 |
| `ItemDataManager.F74042DD40BF93AB1` | [471–479](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C6BC8418E8E071EE6.lua#L471-L479) | 读取物品数据表的字段 **`SlotMaxNum`**，并非所有道具统一写死 999 |

**值得注意的源码差异**：在所研究的旧版代码里 `F2001` 初始总数为 0，只有 **ID 已存在**时才加上 `current + delta`。而 `Bag.AddItem` 的**新道具分支**把 `delta` 直接赋给新记录的 `num`，并不在同一分支重复执行显式 cap；已有道具分支才在加法后将数量 `min(num, SlotMaxNum)`。因此不能泛化为“所有首次领取都一定自动裁到 999”，也不能由此推出后续保存、UI 或其他游戏层不会检查数量。

### 2.2 可计算的数量示例（设此道具 SlotMaxNum=999）

| 收奖前 | 奖励行 | 流程推导的运行时入包 | 说明 |
|---:|---:|---:|---|
| 已有 100 | ×999 | 最多再加 899，结果 999 | `F2001` 超上限 → `F6C18` 返回 899 |
| 已有 999 | ×999 | 新增 0，保持 999 | 不调用 `Bag.AddItem` |
| 已有 0，记录已存在 | ×500 | 结果 500 | 原始增量未触及上限 |
| 未有该物品记录 | ×999 | 旧版 AddItem 新建 999 | `F2001` 对不存在项不以 delta 比较上限，若数据容器没有其他检查则直接写 |
| 未有该物品记录 | ×1500 | 旧版 AddItem 新建时可能写 1500 | **理论分支，不是实机验证，也不说明保存后合法或稳定** |

照片上看到“奖励 ×999”，不自动等于入包新增 999；需要用入包前数量、道具 `SlotMaxNum`、最终实际数量区分**奖励显示**与**真正库存净增**。

## 3. 下一层：何时发起自动保存？

[`GameEventBattleResult` 第 530–535 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C889F6553EDFCD011.lua#L530-L535) 在上述 `type == 2` 团体战处理分支中，调用：

```lua
-- 语义化示例：并非逐字截取
SaveLoadManager.RequestAutoSave(0)
```

[`SaveLoadManager.SEBD55FFD8EF97D80` 92–105 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C073521D193106184.lua#L92-L105) 将这一请求继续委托给其内部管理器 `FEBD55FFD8EF97D80`。

所以可以证明到：

**胜利的团体战结算 → `RaidResultAddItem` 写运行时 Bag → 此分支后段请求自动保存**。

**尚不能证明**：
- 自动保存请求是否立即执行、完成状态如何反馈、出现异常时是否回滚；
- 运行时 Bag 的 `num` 如何进入持久化 SaveData（对象序列化和 checksum）；
- 重启之后异常奖励是否保留，重新进入互联网模式会不会发生额外验证；
- 商业联网坑如何创建房间、如何传输、其自定义奖励是否都是 `subject=5`。

## 4. 与 PokéLDN 的对照、研究结论

| 环节 | 已有静态证据 | 当前结论 |
|---|---|---|
| 原始 `RaidPoint` 结构进入 bootstrap | 用户 Library 《紫》4.0.0 ELF 原始指令；PokéLDN `raid.py` | **独立 ELF 实证** |
| 资格过滤 `subjectType=5` → 背包 `2481` | 公开 Lua 3.0.1；上游 4.0.0 Lua 既有研究；用户确认行为一致 | **跨来源一致**，仍未逐字比对 4.0.0 RomFS |
| 把过滤后的奖励保留在 `[92][3]` 列表 | `GameEventNetworkBattleRaid` 和 `GameEventBattleResult` 文件 | **源码直接可读** |
| 获胜时调用 `RaidResultAddItem` | `GameEventBattleResult` 中 `type=2` 且 `result[1]=1` | **源码直接可读** |
| `SlotMaxNum` 截断 + `Bag.AddItem` | `GameEventBattleResult`、`Bag` 和 `ItemDataManager` | **源码直接可读** |
| 结算发起 `RequestAutoSave(0)` | `GameEventBattleResult`、`SaveLoadManager` | **源码直接可读（仅请求）** |
| 保存完成、重启稳定、官方互联网服务器校验 | 尚无存档变化差分、网络/系统写入日志 | **待验证** |

### P0/P1 后续路线

1. **P0**：追 `SaveLoadManager` 内部 `FEBD55FFD8EF97D80` 至背包存档序列化、写入和完成通知（目标：区分请求/开始/完成）。
2. **P0**：对实际道具表的 `SlotMaxNum` 和截图涉及的每种道具 ID 建立核对表；不假设所有道具统一为 999。
3. **P1**：在用户有权分析的《紫》4.0.0 Lua 实体和实机上重演一组小额奖品（0/5 subject）、对比运行时背包与保存后背包；避免直接以 999 大量异常物品作为基线。
4. **P1**：跟踪反序列化 `0x2F` → `raidBattleRewardData` 的实际对象转换调用链，并确认网络模式的输入来源。
5. **P2**：验证重复条目合并方法 `F8975ECC0360F96CE` 的实际可达路径与调用次序，排除合并跨 subject 资格影响。

## 参考（全部为可核对源码路径）

- [BattleRewardData Lua](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C07C34FC3B976E5A7.lua)
- [NetworkBattleRaid Lua](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C849FF496D0E93636.lua)
- [GameEventBattleResult Lua](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C889F6553EDFCD011.lua)
- [Bag Lua](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C14A8D35D72F56FE9.lua)
- [ItemDataManager Lua](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C6BC8418E8E071EE6.lua)
- [SaveLoadManager Lua](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C073521D193106184.lua)
- [PokéLDN SV Raid 原版文档](../../sv_raid.md)
