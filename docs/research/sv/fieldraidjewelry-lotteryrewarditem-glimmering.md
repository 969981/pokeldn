---
title: SV FieldRaidJewelry 晶耀奖励生成链与 subject=5
parent: 朱／紫（SV）
nav_order: 12
---

# 《宝可梦 朱／紫》晶耀护符奖励生成链逆向分析

研究日期：2026-10-20

> **证据边界**：本页结合公开的 3.0.1 时代 Lua 反编译、PokéLDN 4.0.0 零售版奖励研究及上传的 FlatBuffers 表进行交叉分析。没有宣称完成 4.0.0 Lua 重打包或实机新增奖励到账验证。
> **对应已有研究**：[Lua 后置追加 Hook](sv400-lua-post-lottery-append-hook.md) · [晶耀护符奖励资格](glimmering-charm-raid-rewards.md) · [接收端 Lua](battle-reward-lua-cross-version.md) · [三点一致性](raidpoint-bootstrap-receiver-consistency.md)。
> **参考公开脚本固定版本**：[SV-Script-RE@1f843bd](https://github.com/Martmists-GH/SV-Script-RE/tree/1f843bd2517c707fbb47491dad58856eaa2c2cc7)。


## 0. 核心结论与证据等级

1. **已从较旧版本 Lua 反编译源码确认：** `main.event.general.raid.FieldRaidJewelry.LotteryRewardItem`（`C81390F82EADEF632_prototype:FE77BCB620AB2EDCA`）生成固定奖励、随机奖励、料理奖励（`subject=4`）与晶耀奖励（`subject=5`）。它以 Boss 太晶属性索引 18 项道具 ID 表，以星级读取 `difficulty_%d` 数量，`>0` 时只追加一条 `subject=5`、`rareType=0` 的记录。
2. **已从 4.0.0 零售版样本及接收端 Lua 检查证实：** `RaidPoint +0x0e4` 是 45×16 字节奖励区，四个 u32 依次为 item、quantity、rareFlag、subject；接收端必须持有道具 2481 才保留 `subject=5` 奖励。原生 4.0.0 的普通晶耀奖励是一条对应 Boss 太晶属性的太晶碎块。
3. **用户上传的文件** `raid_gem_item_reward_boost/data.bin` 属于数量表；`data.bfbs` 描述根对象 `RaidGemItemRewardBoost`，每星级为 int32，数值为 0、0、2、5、10、12、0。只改此文件无法更换奖励种类。
4. **尚未验证：** 4.0.0 的 `main.blua` 能否不改变现有其他资源地被重新打包、改写并通过 LayeredFS 稳定加载；仅依据较旧版本反编译源码不能认定已有可安装的改奖励 Mod。

## 1. 源码定位

- 生成端 Lua（参考旧版，仓库 README 标注逆向基准为 3.0.1）：
  https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C81390F82EADEF632.lua
  - 类：`C81390F82EADEF632` = `main.event.general.raid.FieldRaidJewelry`
  - 函数：`FE77BCB620AB2EDCA` = `LotteryRewardItem`（文件中自第 820 行附近起）
- 静态资源读取入口：
  https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C4EE52E49562F8277.lua
  - `C4EE52E49562F8277.S9B76F2540C4CDC13()` → `EncountRaidManager.F9B76F2540C4CDC13()`
- 表加载包装层：
  https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C80A12678D6ED31F7.lua
  - `F9B76F2540C4CDC13()` 检查对象与表加载器，取出返回的字段对象。底层 native/trinity 数据载入逻辑尚需主程序交叉引用确认。
- 接收端奖励数据：
  https://github.com/Martmists-GH/SV-Script-RE/blob/master/decompiled/C07C34FC3B976E5A7.lua
  - 类：`C07C34FC3B976E5A7` = `main.battle.BattleRewardData`
  - `F316609DEA110601D`：按 subject 检查，5 要求晶耀护符 2481
  - `F8975ECC0360F96CE`：按 ItemNo+rareType 汇总相同道具数量（是否及何时调用，需对真实流程追踪）
- 4.0.0 样本、内存结构、消息传递：
  https://github.com/Decryptu/pokeldn/blob/main/docs/sv_raid.md
- PokéLDN 主机端可对照实现：
  https://github.com/969981/pokeldn/blob/main/pokeldn/sv/raid_encounter.py

## 2. 调用参数（通过上层 `mainBody` 调用与函数内使用交叉比对）

`LotteryRewardItem(self, A1, A2, A3, A4, A5, A6, A7)`：

- `A1=1`：由 `mainBody` 传入，本段计算中未发现直接使用。
- `A2`：Boss 的 `DevID`；对 category=1 掉落用于读取素材道具。
- `A3`：太晶坑星级，作为 `difficulty_%d` 字段后缀。
- `A4`：Boss 太晶属性的索引（0…17），对应太晶碎块数组。
- `A5`：固定掉落表键 `battle.dropTableFix`。
- `A6`：随机掉落表键 `battle.dropTableRandom`。
- `A7`：随机数生成器，决定掉落槽位与结果。

## 3. 奖励生成伪代码（非原游戏代码，不可直接当作补丁）

```python
# 类似于 Lua 的逻辑概要，省略实际 FlatBuffers 查找、固定/随机掉落细节
SHARD_ITEM_BY_TERA = [
    1862, 1868, 1871, 1869, 1870, 1874, 1873, 1875, 1878,
    1863, 1864, 1866, 1865, 1872, 1867, 1876, 1877, 1879,
]

def generate_reward_rows(stars, tera_index, fixed_rows, lottery_rows, boost_table, rng):
    result = list(fixed_rows)            # 保留 SubjectType 0/1/2/3
    base_draw_count = choose_base_lottery_count(stars, rng)
    for index in range(base_draw_count + 3):
        row = roll_lottery(lottery_rows, rng)
        row.subject = 4 if index >= base_draw_count else 0
        result.append(row)
    amount = boost_table[f'difficulty_{stars}']
    if amount > 0:
        result.append({
            'item': SHARD_ITEM_BY_TERA[tera_index],
            'quantity': amount,
            'rare_flag': 0,
            'subject': 5,
        })
    return result
```

注意：原函数还涉及固定表 category=1 依据 Boss 种类读取素材、category=2 按太晶属性映射碎块；随机表 category=1/2 采用同类替换逻辑。

### 道具确定的实际代码路径

- 读取所有星级数量的对象：`EncountManager.S9B76F2540C4CDC13()` → `EncountRaidManager.F9B76F2540C4CDC13()`。
- 读取星级数量：对数量表对象调用 `fCD31E312("difficulty_%d" % stars)`；若数量 `>0` 才追加晶耀行。
- 道具 ID：静态 18 项数组以 `A4`（太晶属性索引）取值，而不是从 `raid_gem_item_reward_boost/data.bin` 读出。
- 添加记录：对 `BattleRewardData` 的 `self[3]` 数组执行 `.push`；记录是 `ItemNo`、`ItemNum`、`rareType=0`、`subjectType=5`。
- 旧版 Lua 的晶耀奖励本身恰好只有 1 条，没有针对每个星级单独定义多种道具的 FlatBuffers 表。

## 4. 接收端为何能处理多个晶耀行

`BattleRewardData.F316609DEA110601D` 遍历奖励列表，每次遇到 `subjectType==5` 且本玩家持有道具 2481 时保留该行，并没有只能保留一条的计数限制。它对 `subject=4` 则使用料理对应等级计数。因此从筛选逻辑看，**发送多个独立的 subject=5 行原则上有机会全部通过**。

这只说明“筛选器支持逐行保留”，不保证 45 槽之外能扩容，也不保证任意道具在接收端都能入包，更不证明真实零售版房主会传送经过第三方修改的奖励。

`F8975ECC0360F96CE` 还有相同 `ItemNo`、相同 `rareType` 时汇总数量的逻辑，所以测试应使用彼此不同的道具 ID，避免相同道具汇总干扰结果。

## 5. RaidPoint / 0x2F 数据布局

4.0.0 本地太晶坑 bootstrap（解压后的 0xAA0 字节）：

- `[0x000, 0x6B8)`：4 个训练家记录 + Boss 记录
- `[0x6B8, 0xAA0)`：0x3E8 字节的 RaidPoint
- `RaidPoint +0x0E4`（相当于整个 0xAA0 对象的 `0x79C`）：奖励区，45 行 × 16 字节
- 每行四个 little-endian u32：item, quantity, rareFlag, subject

上限计算：源码中的固定表物理位置最多 15 行；6 星常规抽取最多 11 次；另外有 3 次 `subject=4` 和 1 次 `subject=5`。即**极端理论场景**如果 15 条固定都有效，则 15+11+3+1=30 行，剩余 15 行。实际有效固定行可能少得多，必须根据具体 seed/raid 实测；不能默认无损再加 20 行一定有空间。

## 6. 修改路线比较

### A. 静态 FlatBuffers Mod（只改数量）

编辑 `/world/data/raid/raid_gem_item_reward_boost/data.bin` → 修改 difficulty_1..difficulty_7。易于回退，不改变道具种类，也不能产生多行。

### B. Lua 函数 Mod（改种类或追加新行）

选择 4.0.0 `main.blua` 中对应函数（先比对 hash/行为）→ 更换晶耀行 `ItemNo`，或在现有晶耀行后 append 不同 ItemNo/ItemNum/rareType=0/subjectType=5 的记录 → 重新构建脚本容器 → 作为 RomFS Mod 部署 → 验证发送前 45 槽及接收方。

**重要：** 当前只有较旧版本 Lua 源码及 4.0.0 行为证据，还没有验证可稳定重编、重封 `main.blua` 的完整工具链；因此 B 是明确的代码修改点而不是已完成的 Mod。

### C. 房主原生/运行时 Hook

不修改 `main.blua` 时，在游戏完成奖励生成之后、`RaidPoint` 被序列化复制到 0x2F 之前，找到实际内存对象，原位替换或利用空奖励槽追加。读写必须约束在当前房主真实 RaidPoint 的 45 槽里，不能把静态 ELF 寄存器或存档 RaidBlock 指针误当成当前活跃 RaidPoint。

对 4.0.0，PokéLDN 记录 `0x1bae670 → 0x1bae760 → 0x1baff98 → 0x1bb0018` 将源 RaidPoint 复制到序列化消息对象；这些是 decompressed `main` 的版本相关偏移（不是运行时固定绝对地址）。`0xe327fc` 写序列化正文，后续 LZ4。对 Hook 调研应优先在**源 RaidPoint/复制入口**观察，而不是修改压缩数据。

## 7. 最小可证伪测试

1. `T0`：原版六星、晶耀护符、`subject=5` 只读捕获基线，校验物品为当前太晶属性碎块、数量 12。
2. `T1`：只将数量表六星改 12→13，以 RomFS Mod 载入，单机只读验证生成行变化。失败说明资源覆盖/缓存/版本未命中。
3. `T2`：在已证实能加载的 4.0.0 自定义脚本环境中，**仅更换晶耀奖励行的 ItemNo**，保留 amount 和 subject=5；验证战斗后实际道具领取。
4. `T3`：恢复原生碎块，并只追加 1 条 `subject=5`、独特且可入包的道具；比较原版所有奖励行不减少、追加行出现在源 RaidPoint 和 0x2F、接收方筛选输出及保存重启。
5. `T4`：如要追加 20 行，必须增加 45 槽空间预检、禁止覆盖任何原奖励；超容量时拒绝生成而非静默截断。

**完成标准**：同一局的源 RaidPoint、解压后的 `0x2F` 奖励区、接收方筛选和最终持久化清单彼此一致，原版奖励均保留、新增道具真实到账。测试优先在离线本地联机环境开展。

## 8. 未解决问题

- 4.0.0 `main.blua` 中 `C81390F82EADEF632/FE77BCB620AB2EDCA` 是否沿用相同字节码命名及调用关系，需要从该版本直接提取比对。
- 4.0.0 `main.blua` 可重编/打包为游戏接受的 Mod 吗？尚无已验证完整流水线。
- 是否在 source RaidPoint 已生成而发送前还有覆盖、归一化或过滤？需要抓包/断点闭环。
- 所有道具的数量限制（`SlotMaxNum`）与领取时的包容量/丢弃行为尚待验证。
- 在线团体战是否与已验证的离线本地 LDN 完全同链路，不能由现有证据推断。
## 9. 补充：修改位置与已有 P1 研究衔接

- [现有 P1 研究](sv400-lua-post-lottery-append-hook.md) 指出 `EncountRaidManager.InitializeLotteryRewardItem` 的初始化路径可能清掉已有的 `subjectType=5` 项，因此**不要在奖励表加载前或初始化阶段盲目塞入自定义晶耀行**。
- 研究目标若是**保留原版所有掉落并追加新道具**，优先在 `LotteryRewardItem` 返回完整 `BattleRewardData[3]` 后添加，而非修改 `RaidGemItemRewardBoost` 或替换所有原有 45 槽。
- `RaidMatchingView.FCE48462FE20C26A7`（旧版 Lua）固定循环 45 次将上述数组写入 RaidPoint；新增总数超过 45 时必须停止追加并保留原样，禁止静默截断原有奖励。
- 在获得**经 SHA 验证的 4.0.0 `main.blua`** 并完成版本一致性比对以前，本页函数名仅是可读语义锚点，不能将 3.0.1 的 Prototype/PC 或其他版本的 ARM64 偏移当成 4.0.0 可用补丁地址。

