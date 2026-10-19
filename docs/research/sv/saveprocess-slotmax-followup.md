---
title: 太晶坑奖励保存回调与 SlotMaxNum 研究
parent: 朱／紫（SV）
nav_order: 6
---

# 《朱／紫》团体战奖励：SaveProcess 异步链与道具容量

日期：2026-10-19。证据取自固定版本 [SV-Script-RE@1f843bd](https://github.com/Martmists-GH/SV-Script-RE/tree/1f843bd2517c707fbb47491dad58856eaa2c2cc7) 的公开旧版 Lua 反编译，以及 [KM-Editor ItemData.cs](https://github.com/KotMatrosk1n/KM-Editor/blob/main/src/KM.Formats/SV/Generated/GameData/ItemData.cs) 的 FlatBuffers 定义。当前 Library 的 `Violet4.0.0.elf` 并不包含需要的完整 RomFS 物品表；本文不把 3.0.1 时代 Lua 反编译伪装成从 4.0.0 ELF 新恢复的代码。

## 1. StartSaveProcess 后面确实存在异步任务

```text
GameEventBattleResult.RaidResultAddItem
  → Bag.AddItem → BagSaveAccessor
  → SaveLoadManager.RequestAutoSave(0)
  → CAE5B15F66F86E1FD.RequestAutoSave: self[4] = mode
  → CAE5B15F66F86E1FD.RunAutoSaveRequest
  → StartSaveProcess
      检查禁止标志与 self[2] 是否已有活动任务
      self[2] = C02B3E6571816B75E.S988D7D0A4EEF693D(mode)
      self[1].f47BAE49D(...) 交给调度器
  → main.savedata.system.SaveProcess.mainCoroutineFunc
      c639BAEBC.fAA5A90DA(mode) -> 启动结果
      while not c639BAEBC.f6F7C8191():
          ti.Coroutine.yield(nil)
  → 后处理回调 / 原生完成状态 / 文件提交 / 重启保留
      最后三项仍然 PENDING
```

### 1.1 精确源码锚点

| 文件和行 | 可直接看见的代码事实 | 证据边界 |
|---|---|---|
| [CAE5... RequestAutoSave 310–388](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/CAE5B15F66F86E1FD.lua#L310-L388) | `self[4]` 存待处理模式 | 只是排队 |
| [RunAutoSaveRequest 395–432](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/CAE5B15F66F86E1FD.lua#L395-L432) | 消费请求；特定条件下 mode 1/3 转 mode 4；清 pending | 不是刷盘确认 |
| [StartSaveProcess 232–283](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/CAE5B15F66F86E1FD.lua#L232-L283) | 已有 `self[2]` 会拒绝；构建 SaveProcess 并派给调度器 | 返回 true 只表示启动任务 |
| [SaveProcess.mainCoroutineFunc 54–75](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C02B3E6571816B75E.lua#L54-L75) | 先调用原生启动、再轮询、每次未完成则 yield | `f6F7C8191()` 的 true 不足以断言成功写入 |
| [管理器 Initialize 117–165](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/CAE5B15F66F86E1FD.lua#L117-L165) | `c37452BA0.fB469A33A` 注册回调，更新标志并通知子模块 | 尚未证明事件与系统完成写入的对应关系 |
| [native/c639BAEBC.lua](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/native/c639BAEBC.lua) | 声明了 `fAA5A90DA` / `f6F7C8191` | Native 实现文件标记 TODO |

**P0 下钻要求**：找到上述 Native binding 在当前 Build ID 中的函数地址、底层序列化/写入/校验及返回错误路径；证实 `self[2]` 是何时释放的，并以授权测试存档的 T0 收奖前、T1 AddItem、T2 自动保存启动、T3 写入结果、T4 重启读回做独立对照。游戏内弹出奖励画面不能代替 T4。

## 2. 真实 SlotMaxNum 来源已经确定，具体数值尚待资源

[ItemDataManager.GetSlotMaxNum 471–479](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C6BC8418E8E071EE6.lua#L471-L479) 根据道具 ID 按字段字符串 `"SlotMaxNum"` 从物品资源读取。对应的游戏 RomFS 路径：

```text
world/data/item/itemdata/itemdata_array.bin
```

[KM-Editor ItemDataArray.cs](https://github.com/KotMatrosk1n/KM-Editor/blob/main/src/KM.Formats/SV/Generated/GameData/ItemDataArray.cs) 明确 root 的 `Values` 为 field #0；[ItemData.cs](https://github.com/KotMatrosk1n/KM-Editor/blob/main/src/KM.Formats/SV/Generated/GameData/ItemData.cs) 明确 `Id` 为 field #0，`SlotMaxNum` 为 field #24 / **vtable offset 52**、类型 int32。这里的 52 **不是在每条记录中固定的字节偏移**，解析时必须通过各条记录的 FlatBuffers vtable 定位。

### 2.1 已新增离线只读提取工具

[`scripts/slot_max_num.py`](scripts/slot_max_num.py) 不修改资源、不依赖额外 pip 库，读取官方原始 FlatBuffer，输出文件 SHA-256、ID→SlotMaxNum 和缺失项；若物品表字节损坏或结构不符则报错。

```bash
python docs/research/sv/scripts/slot_max_num.py \
  /path/to/world/data/item/itemdata/itemdata_array.bin \
  --ids 1,15,50,795,796,1606,2481 --csv sv_item_caps.csv

# 全量物品清单
python docs/research/sv/scripts/slot_max_num.py /path/to/itemdata_array.bin \
  --ids all --csv sv_item_caps_full.csv
```

配套 [`tests/test_sv_slot_max.py`](../../../../tests/test_sv_slot_max.py) 使用**自行生成的非游戏测试 FlatBuffer**做字段读取、默认零值、非法 buffer 拒绝等回归测试；本轮已提交测试代码，**尚未取得实际运行测试日志**。

### 2.2 物品调查清单（不要用 999 填充未核实数据）

| ID | 道具 | 实际 SlotMaxNum |
|---|---|---|
| `1` | 大师球 | **PENDING 资源读取** |
| `15` | 先机球 | **PENDING 资源读取** |
| `50` | 神奇糖果 | **PENDING 资源读取** |
| `795` | 银色王冠 | **PENDING 资源读取** |
| `796` | 金色王冠 | **PENDING 资源读取** |
| `1606` | 经验糖果 XL | **PENDING 资源读取** |
| `2481` | 晶耀护符（Key Item） | **PENDING 资源读取；非普通自定义奖励** |

本轮已经能从旧版 Lua 证明**已有道具数量**通过 `Bag.F2001F41E6B757BB1` 检测 `current + delta` 是否超 `SlotMaxNum`，再用 `F6C18EEC27ED4BA1E` 算剩余容量；**首次新建物品记录**走不同分支。`--raid-reward` 数量最大 999 只是 PokéLDN CLI 的输入约束，不是所有道具的实时持有上限，也不等于增加了 999。

目前 Library 有 `Violet4.0.0.elf`，但没有上述 RomFS `itemdata_array.bin` 实际字节。下一次取得用户自有游戏提取的表后，可在不传播原始版权素材的前提下只发布 `item_id/slot_max_num` 与 SHA-256 的研究元数据。**没有原件不报告精确 cap 数字**。

## 3. 本轮 subject=0/5 开发及测试状态

`research` 已增加每行“所有玩家 / 仅持有晶耀护符”的下拉控件、`--raid-reward ITEM:QUANTITY:5` 扩展解析和二元组旧数据兼容。相关测试已加入 `tests/test_sv_raid.py`、`tests/test_gui_rewards.py` 和 `tests/test_gui_catalog.py`，另有上述 FlatBuffers 解析器回归。具体通过与否以实际 pytest/Actions 测试日志为准，禁止将“新增测试”误写成“测试全部通过”。

参考：[原先奖励入包与自动保存链](raid-reward-to-bag-save-chain.md) · [自定义奖励结构与 ELF](custom-raid-rewards-host-elf.md) · [Lua subject 过滤](battle-reward-lua-cross-version.md)。
