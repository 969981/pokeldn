---
title: SV 4.0.0 自动保存原生边界与道具数量上限
parent: 朱／紫（SV）
nav_order: 5
---

# 《朱／紫》太晶坑 P0：StartSaveProcess → SaveProcess → 完成轮询，以及 SlotMaxNum

- **日期**：2026-10-19
- **代码源**：[`SV-Script-RE` 固定提交](https://github.com/Martmists-GH/SV-Script-RE/tree/1f843bd2517c707fbb47491dad58856eaa2c2cc7) 的公开旧版 Lua（约 3.0.1）；用户确认其奖励行为与《紫》4.0.0 一致，**未独立比较 4.0.0 原始 RomFS 字节**。
- **独立 ELF 基线**：[用户 Library《紫》4.0.0 ELF 原生指令核对](violet400-elf-raid-bootstrap-audit.md)。本次保存流程审计基于 Lua，不声称已完成对保存原生接口的 ELF AArch64 RVA 定位。
- **范围**：验证保存代码究竟走到哪一层；用真实道具 ID 对照 PKHeX Gen9 SV 的容量规则，并制作可从用户自己的 RomFS 原始表读取每一项 `SlotMaxNum` 的只读工具。**不包含游戏 RomFS / ELF 原件。**
- **状态**：Lua 保存协程及原生轮询入口 **已定位**；写盘结果和官方在线模式持久性 **未实机验证**；原版 `itemdata_array.bin` **未在 Library 定位**，不能把 PKHeX 的 999 当成逐项 ROM 表实测值。

## 1. 保存调用链：目前证据能追踪到哪里

```text
GameEventBattleResult (胜利 type=2, result[1]=1)
  ├─ RaidResultAddItem → Bag.AddItem
  │    ├─ BagSaveAccessor.SaveNewGetItem(id, num, category)   // 首次获得
  │    └─ BagSaveAccessor.SAB9A64F8881E7F45(id, finalNum) // 已有
  └─ SaveLoadManager.RequestAutoSave(0)
      → CAE5B15F66F86E1FD.RequestAutoSave
           self[4] = requestType（待处理请求）
           → RunAutoSaveRequest（条件满足时）
                → StartSaveProcess
                    ├─ 若 FSYS_REPORT_DISABLE / DisableReport 有效：拒绝
                    ├─ 如果 self[2] 仍有执行中的 process：拒绝
                    ├─ C02B3E6571816B75E.S988D7D0A4EEF693D(mode)
                    └─ 注册 SaveProcess 到 coroutine scheduler
                         → SaveProcess.mainCoroutineFunc
                              ├─ c639BAEBC.fAA5A90DA(mode)
                              └─ while NOT c639BAEBC.f6F7C8191():
                                    C1DB14DCC9D7634FA.S760DAE4C5371A78E(nil)
  回调/系统真实写盘与成功标志：待 ELF/native hook + 可控存档实验
```

### 1.1 StartSaveProcess：不是“完成保存”

[CAE5B15F66F86E1FD.StartSaveProcess 第 232–283 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/CAE5B15F66F86E1FD.lua#L232-L283)：

- `A2_2` 默认为 `false`；
- 检查 `DisableReport` 和 `FSYS_REPORT_DISABLE`；若禁止上报/保存流程，则返回 `false`；
- 如果 `self[2]` 已持有一个进程对象，返回 `false`，防止重复任务；
- 把 `not A2_2` 写入 `self[5]`，创建 `C02B3E6571816B75E.S988D7D0A4EEF693D(A1_2)`（命名 `SaveProcess_mode_<mode>`），存入 `self[2]` 并将对象加入 `self[1]` 调度器；
- 最终返回 `true` 的含义是**接受并安排一次保存工作**，不是磁盘结果。

**不要误把 `DisableReport` 变量名解释成一定禁止磁盘写入**：上述确实用其作为拒绝此流程的条件，但原生副作用未分析。

### 1.2 SaveProcess 的主协程：原生启动 + 完成等待

[SaveProcess（`C02B3E6571816B75E`）的 mainCoroutineFunc](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C02B3E6571816B75E.lua#L1-L80)：

```lua
-- 只保留控制流的等价伪代码，native 函数名保持源文件 hash
function mainCoroutineFunc(mode)
    if not c639BAEBC.fAA5A90DA(mode) then
        return
    end
    while not c639BAEBC.f6F7C8191() do
        C1DB14DCC9D7634FA.S760DAE4C5371A78E(nil) -- coroutine yield
    end
end
```

**重要区分**：`fAA5A90DA` 返回值是“是否启动/接受”层；`f6F7C8191` 是**循环退出条件**，从其被用作布尔条件本身不能推断“成功提交且已刷盘”，除非独立定位并反汇编原生实现、获得错误码与明确成功回调。

### 1.3 请求消费、完成通知及读回

[RunAutoSaveRequest 第 395–433 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/CAE5B15F66F86E1FD.lua#L395-L433) 读取 `self[4]` 的待请求类型，在条件满足时 `StartSaveProcess(...)`，随后清理待请求；如果启动失败会调整相应状态。对 `requestType=0` 不可一概当成手动保存或直接 save call。

[Initialize 第 80–206 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/CAE5B15F66F86E1FD.lua#L80-L206) 注册来自 `c37452BA0` 的两个回调：
- **保存相关回调**：`c37452BA0.fB469A33A(function ...)` 中有对监听器 `FA7B9750360BF2368` 的通知调用，及报告/状态处理；
- **读取/加载相关回调**：`c37452BA0.fC7A7FCA3(function ...)` 遍历注册的 `BagSaveAccessor.Load` 等加载器，触发系统加载与重建。

**此处回调是否以存储系统真正成功写盘为触发条件，仍未凭原生语义验证**。源代码中还存在 `SetReportData`，但不应将它误认作无条件的保存成功标志。

### 1.4 BagSaveAccessor 已证实的字段更新 / 读回

[BagSaveAccessor.SaveNewGetItem 第 89–123 行](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C985427E5D92698CE.lua#L89-L123) 的新记录设置了数量、类别、`isGet` 和 `newFlag`。已有记录的 `SAB9A64F8881E7F45` 通过 `cACA3F5A6` 写入最终数量。[BagSaveAccessor.Load 第 124 行以后](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C985427E5D92698CE.lua#L124-L170) 会使用 `cACA3F5A6.f6A1EF75F` 逐 ID 读取存储项，获取 `num/category` 和标记，最后传给 `Bag.SetLoadDataEx` 重建运行时背包。

所以**既能找到写数据访问器，也能找到加载重建入口**；但 `cACA3F5A6` 的底层保存缓冲格式、加密/校验和与 fs commit 尚未独立确认。

## 2. `SlotMaxNum` 不是单独的通用常量

[ItemDataManager.GetSlotMaxNum](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C6BC8418E8E071EE6.lua#L471-L479) 会根据 ID 从道具数据表中读取字段 `SlotMaxNum`。对应真实的 RomFS 路径是：

```text
world/data/item/itemdata/itemdata_array.bin
```

路径来自 [KM-Editor 的 SV 文件路径定义](https://github.com/KotMatrosk1n/KM-Editor/blob/4b0d1c6dee20be7d77bad2435476da67a1ae30e8/src/KM.SV/Data/SvDataPaths.cs)，格式是 `ItemDataArray` FlatBuffers；`Id` 为 schema 字段索引 0，`SlotMaxNum` 为 **字段索引 24（0-based）**，参考 [pkNX FlatBuffers schema](https://github.com/kwsch/pkNX/blob/d191cd0e5c05f2af81d9a41c1f1d82e6621b351a/FlatBuffers/SV/Item/Schemas/ItemDataArray.fbs)。

**Library 查询结果**：有《紫》4.0.0 ELF，但没有发现 `itemdata_array.bin` 的独立文件或完整对应 RomFS，因此下表把 PKHeX 的公开 SV 背包实现列为**交叉参照容量**，原游戏 4.0.0 的 `SlotMaxNum` 一栏明确标为“待 RomFS 核实”，不伪造实测值。

## 3. 截图涉及的道具：ID 与已知背包上限对照

下表中**“PKHeX 规则”均为 999**，其来源是 [PKHeX.Core ItemStorage9SV.GetMax](https://github.com/kwsch/PKHeX/blob/master/PKHeX.Core/Items/ItemStorage9SV.cs) 的对应口袋，以及 [PlayerBag9.GetMaxCount](https://github.com/kwsch/PKHeX/blob/master/PKHeX.Core/Items/Bags/PlayerBag9.cs)。它们是存档编辑规则的强交叉参照，**不是《紫》4.0.0 RomFS 中的逐项 SlotMaxNum 读取结果**。

道具 ID 与简体名称来自 [PMSV 原始名称表](https://github.com/Ruimusume/PMSV/blob/master/Item%20Names.txt)（同名“沉重球”另有非 SV 本体球 ID，应使用当前 SV 道具 ID `495`）。

| 道具 | SV 道具 ID | PKHeX 允许数量（一般背包规则） | 《紫》4.0.0 原始 `SlotMaxNum` |
|---|---:|---:|---|
| 大师球 | 1 | 999 | 待原表读取 |
| 金色王冠 | 796 | 999 | 待原表读取 |
| 神奇糖果 | 50 | 999 | 待原表读取 |
| 经验糖果 XL | 1128 | 999 | 待原表读取 |
| 巨大金珠 | 581 | 999 | 待原表读取 |
| 特性膏药 | 1606 | 999 | 待原表读取 |
| 速度球、等级球、诱饵球、沉重球、甜蜜球、友友球、月亮球、竞赛球 | 492–499 | 999 | 待原表读取 |
| 究极球 | 851 | 999 | 待原表读取 |
| 秘传：甜/咸/酸/苦/辣味料 | 1904–1908 | 999 | 待原表读取 |

注：PKHeX 明确有**某些野餐配件上限 1**的例外，说明“任何道具都统一 999”不成立。大师球、金色王冠、经验糖果和上述常规道具均不属于这类附件例外。

## 4. 照片中 999 的含义：严格区分奖励值和净增

对于已有道具 `current`、新奖励 `reward`，且假设本体表给出的 `SlotMaxNum=999`：

```text
remaining = max(0, 999 - current)
awardedToBag = min(reward, remaining)
finalCount = current + awardedToBag
```

`RaidResultAddItem` 会在超出数量上限时先替换为剩余容量再调用 `Bag.AddItem`，因此如果已有 200 个大师球，结算显示 ×999，实际背包最多增加 799 个，最后达到 999。**这只是基于旧版 Lua 和假设的 SlotMaxNum=999 的代码推演**，不是同一台机器的前后背包差分结果。

值得复核的边界：原旧版 Lua 的 `Bag.AddItem` 新物品分支没有与已有物品分支完全一样的显式 min cap，遇到没有记录且传入极大数量时可能出现不同的初始写入路径；这**不意味着游戏最终能稳定保存超过上限的数据**。

## 5. 可重复核实工具与实际待办

已准备**只读**脚本 [`scripts/research/sv_item_slotmax.py`](../../../scripts/research/sv_item_slotmax.py)，无需安装第三方依赖，直接解析用户本人提供的原始 FlatBuffers 道具表：

```bash
python scripts/research/sv_item_slotmax.py --self-test
python scripts/research/sv_item_slotmax.py /path/to/RomFS
python scripts/research/sv_item_slotmax.py /path/to/RomFS/world/data/item/itemdata/itemdata_array.bin --all > all_item_slotmax.csv
```

输出含 ID、名称、`SlotMaxNum`、原始表大小及 SHA-256（哈希输出到 stderr），从而能将上表最后一列替换成真正 4.0.0 RomFS 值。脚本只读，不覆盖游戏文件、不提取或发布版权资源。**本次没有实际原表，因此脚本的解析功能以自合成 FlatBuffers 测试验证，不冒充原表实测**。

### 仍待完成的 P0

1. **原生保存入口**：在已校验 Build ID 的 4.0.0 ELF 内定位 `c639BAEBC.fAA5A90DA`、`f6F7C8191`、`cACA3F5A6` 的桥接和真实 `SaveProcess` completion/error codes；优先只读反汇编和本地可控测试。
2. **存储完成条件**：确认 SaveProcess 协程退出之后系统回调的状态分类，记录错误/中断和读回成功的区别；不要把“polling 结束”宣称为成功。
3. **真实道具表**：在自己有权访问的《紫》4.0.0 RomFS 文件中提供 `itemdata_array.bin`；运行脚本，记录 SHA-256、每项 ID+SlotMaxNum 以及游戏 Build ID / ROMFS 版本。
4. **存档前后差分**：先小额普通道具，分别对已有条目/新条目、护符有/无、联网/离线做控制实验；只有“保存完成、重启读回、再次联网仍有”才称稳定入库。

## 参考

- [前一阶段奖励到背包 Lua 调用链](raid-reward-to-bag-save-chain.md)
- [SV 4.0.0 ELF 已验证发送端](violet400-elf-raid-bootstrap-audit.md)
- [PokéLDN 原版 SV Raid 技术文档](../../sv_raid.md)
- [反编译固定版本](https://github.com/Martmists-GH/SV-Script-RE/tree/1f843bd2517c707fbb47491dad58856eaa2c2cc7)
- [PKHeX Gen9 SV 容量定义](https://github.com/kwsch/PKHeX/blob/master/PKHeX.Core/Items/ItemStorage9SV.cs)
