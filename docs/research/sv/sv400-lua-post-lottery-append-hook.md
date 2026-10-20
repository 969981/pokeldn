---
title: 《紫》4.0.0 太晶坑奖励：LotteryRewardItem 后置追加 Hook 的 P1 定位
parent: 朱／紫（SV）
nav_order: 8
---

# 《紫》4.0.0 太晶坑奖励：在原版奖励生成后追加，而不是替换

- **研究日期**：2026-10-20
- **目标**：把 P1 从“能构造自定义 RaidPoint”推进到“保留原版奖励 + 额外追加奖励”的可验证实现路径。
- **最终完成标准**：实机原版奖励不减少、额外道具到账、重新载入存档后仍保留。三项缺一不可。
- **公开 Lua 语义基线**：[Martmists-GH/SV-Script-RE@1f843bd](https://github.com/Martmists-GH/SV-Script-RE/tree/1f843bd2517c707fbb47491dad58856eaa2c2cc7)。其 README 明确写的是“3.0.1 at time of writing”，因此本页把它作为可读语义参考，而不是冒充 4.0.0 原始字节码。
- **本轮代码**：[sv_lua_reward_append_prototype.py](../../../scripts/research/sv_lua_reward_append_prototype.py) 与 [test_sv_lua_reward_append_prototype.py](../../../tests/test_sv_lua_reward_append_prototype.py)。

## 1. 本轮核心结论

P1 不应继续以“清空 45 行奖励区后重写”为主路径。更合适的语义 Hook 窗口是：

~~~text
FieldRaidJewelry.LotteryRewardItem
    先完整生成零售 BattleRewardData
                |
                v
[Hook window]
    只向 BattleRewardData[3] 尾部 append 自定义行
    原有行顺序、字段、数量一律不改
    若原有行 + 新行 > 45：拒绝追加，保持零售结果
                |
                v
RaidMatchingView.FCE48462FE20C26A7
    原版固定循环 45 槽
    将 BattleRewardData[3] 写进 RaidPoint
                |
                v
接收端 BattleRewardData.F316609DEA110601D
    原版按 subjectType 做资格过滤
                |
                v
胜利后 GameEventBattleResult.RaidResultAddItem
    原版 Bag.AddItem
                |
                v
RequestAutoSave
~~~

这样能够直接满足 P1 的第一原则：**新增功能不能以减少原版掉落为代价。**

## 2. 为什么 Hook 要放在 LotteryRewardItem 返回之后

公开反编译 [C81390F82EADEF632.lua](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C81390F82EADEF632.lua) 中，FieldRaidJewelry.LotteryRewardItem（FE77BCB620AB2EDCA，约 820 行起）会创建 C07C34FC3B976E5A7，也就是 BattleRewardData，并向 BattleRewardData[3] 逐行 push 四个字段：

- ItemNo
- ItemNum
- rareType
- subjectType

其调用方约在 476–492 行先执行 FE77BCB620AB2EDCA，返回对象赋给 L16_2；随后继续填充 boss / raid 元信息，并在约 701 行保存到 C79A8A2641CC135A3.SE9713F112CDA989C。

因此从数据生命周期看，**返回值 L16_2 已经是完整原版奖励对象**。在这之后 append，比修改奖励表初始化阶段更不容易破坏零售生成逻辑。

### 2.1 为什么不建议更早注入

[C80A12678D6ED31F7.lua](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C80A12678D6ED31F7.lua) 的 EncountRaidManager.InitializeLotteryRewardItem 在约 675 行存在 subjectType == 5 时 splice 的路径。

也就是说，至少在这一条初始化/准备流程里，subjectType=5 行会被主动删除。把自定义 subject=5 行放得太早，有可能在写入 RaidPoint 前再次被原版清掉。

当前推荐顺序是：**原版先生成 → 我们 append → 原版序列化 → 原版接收端过滤。**

## 3. 45 行写入点已经从 Lua 侧闭合

[C050DB411547B4BAC.lua 6256–6364](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C050DB411547B4BAC.lua#L6256-L6364) 的 RaidMatchingView.FCE48462FE20C26A7(A1_2, A2_2) 固定循环 45 次：

~~~text
for index = 0 .. 44:
    if index < A2_2[3].length:
        row = A2_2[3][index]
        item    = row.ItemNo
        num     = row.ItemNum
        rare    = row.rareType
        subject = row.subjectType
    else:
        四字段 = 0

    A1_2.fE74A2301(index, item, num, rare, subject)
~~~

因此：

- BattleRewardData[3] 就是序列化前奖励行数组；
- 原版代码已经提供 45 槽逐行写入；
- P1 不需要改 LZ4，也不需要替换整个 0xAA0；
- append 后只要总长度不超过 45，原版路径会自然把新增行带入 RaidPoint；
- 超过 45 行必须在 Hook 层 fail closed，不能覆盖尾部零售奖励。

## 4. 接收端继续让原版自己做资格过滤

[C07C34FC3B976E5A7.lua 182–321](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C07C34FC3B976E5A7.lua#L182-L321) 的 BattleRewardData.F316609DEA110601D 会重新建立过滤后的数组并写回 self[3]。

已核对语义：

| subject | 原版条件 |
|---:|---|
| 0 | 全体 |
| 1 | 房主 |
| 2 | 参与者 |
| 3 | 一次性资格参数为真 |
| 4 | 团体战力的序号/等级条件 |
| 5 | Bag.GetNumItem(2481) > 0 |

因此 P1 原型无需重写护符判定。新增 subject=5 行继续交给原版 F316... 过滤即可。

## 5. 真正入包和保存请求的位置没有变化

[C889F6553EDFCD011.lua 1624–1697](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C889F6553EDFCD011.lua#L1624-L1697) 的 GameEventBattleResult.RaidResultAddItem：

1. 遍历 self[18][92][3]；
2. 读取 ItemNo / ItemNum；
3. 做背包容量处理；
4. 数量大于 0 时调用 Bag.AddItem。

同一结算流程随后会请求 RequestAutoSave(0)。但是“请求自动保存”不等于“已经刷盘完成”，所以 P1 仍必须完全退出并重载存档后再次确认库存。

## 6. 4.0.0 的 main.blua 已有明确版本锚点

### 6.1 本账号已有的 TRPFD 研究

[969981/Ogre_Oustin 的 4.0.0 main Lua 研究](https://github.com/969981/Ogre_Oustin/blob/015717a751029fd3b8e204e645c6abed278873ea/docs/08-trpfd-4.0.0-main-lua.md) 已经从 Violet 4.0.0 arc/data.trpfd 实际确认：

| 项 | 值 |
|---|---|
| Pack index | 14659 |
| Pack name | arc/scriptluabinreleasemainmain.blua.trpak |
| Pack size | 2,255,432 bytes |
| FileCount | 1 |
| dynamic pack | arc/scriptluabinreleasemain_dynamicmain_dynamic.blua.trpak |
| dynamic size | 551,344 bytes |

[extract_trpak.py](https://github.com/969981/Ogre_Oustin/blob/015717a751029fd3b8e204e645c6abed278873ea/tools/extract_trpak.py) 已实现 data.trpfd + data.trpfs → FNV1a64(pack name) → FileSystem offset → 提取目标 trpak 的流程。

所以现在缺的不是“main Lua 在哪里”，而是匹配的 4.0.0 data.trpfs 或已经合法提取出的原始 main.blua 字节。

### 6.2 KM-Editor 给出字节级身份

[KM-Editor 的 sv-4.0.0.json](https://github.com/KotMatrosk1n/KM-Editor/blob/e108ec745488a0e38c28edf8585dd1d5c4bbfd96/native/km-native-settings/profiles/sv-4.0.0.json) 记录：

~~~text
path:
romfs/script/lua/bin/release/main/main.blua

Violet 4.0.0 base SHA-256:
C1A4F4E2625912CF0B739A642A79BA3357DF0557A544B92DA22A6CB139DE2815

Violet Build ID:
709BFD66115298640155FCC4979DBA151C7CC79A000000000000000000000000
~~~

这给 P1 下一阶段提供了严格入口：**只有 main.blua SHA-256 精确等于上述 base hash，才进入 4.0.0 Prototype / PC 定位。**

## 7. Martmists / Reisyukaku / Xzonn 的材料边界

### Martmists

SV-Script-RE 当前公开树中有 main.dumped.lua、split/、decompiled/，README 明确基线为 3.0.1；仓库树中未找到原始 main.blua。因此它适合做 Lua 语义和调用链定位，不适合直接给出 4.0.0 bytecode PC。

### Reisyukaku

GitHub 索引可找到 Reisyukaku/SVScripts 中相同类哈希的早期资料，可作为第二份反编译参考，但仍不替代 4.0.0 原始字节。

### Xzonn

本轮检查了 Xzonn 的公开仓库及 Xzonn/PokemonSV-pkNX。PokemonSV-pkNX 有大量《朱／紫》解包后的世界/表数据，但公开代码搜索没有找到 main.blua、blua 或本次团战 Lua 类。因此当前没有从 Xzonn 的公开 GitHub 索引中得到比 Ogre_Oustin + KM-Editor 更直接的 4.0.0 Lua 资源。

这只表示本轮公开 GitHub 索引检索结果，不表示 Xzonn 从未在其他位置持有或发布相关文件。

## 8. 本轮加入的离线 P1 原型

新增：

- [scripts/research/sv_lua_reward_append_prototype.py](../../../scripts/research/sv_lua_reward_append_prototype.py)
- [tests/test_sv_lua_reward_append_prototype.py](../../../tests/test_sv_lua_reward_append_prototype.py)

模型只做四件事：

1. 输入原版 original_rows；
2. 在尾部 append extra_rows；
3. 超过 45 行立即拒绝；
4. 用公开 F316... 语义模拟资格过滤。

刻意不做运行中游戏修改，也不伪造 4.0.0 Prototype PC，不把模拟过滤冒充实机入包，不把 RequestAutoSave 冒充持久化完成。

回归测试覆盖：

- 原版奖励前缀完全保持；
- subject=5 有/无护符差分；
- 45 行已满时 fail closed；
- append subject=5 不改变已有 subject=4 的序号；
- 报告中的实机入包、重载持久化保持 PENDING。

## 9. P1 实机验收矩阵

第一轮只追加一条低风险、容易观察、当前库存有足够空间的普通道具，数量保持很小。不要一开始用 999，否则会把 SlotMaxNum / 容量裁剪混进 Hook 正确性判断。

| 阶段 | 要比较的值 | PASS 条件 |
|---|---|---|
| S0 战前 | 原版预测奖励、目标道具库存 | 留底 |
| S1 生成后 | BattleRewardData[3] | 原版行逐行不变，尾部多 1 行 |
| S2 序列化前/后 | 45 行 RaidPoint | S1 原版前缀一致；新增行存在 |
| S3 接收端过滤后 | F316... 输出 | 原版应得行仍在；新增 subject 条件符合预期 |
| S4 战后入包 | Bag | 原版奖励净增不低于无 Hook 对照；新增道具净增正确 |
| S5 自动保存完成后 | save state | 无保存错误 |
| S6 完全退出再启动 | Bag | S4 新增的道具仍在 |

**最终 P1 PASS = S4 原版未减少 + S4 新增到账 + S6 重载后仍在。**

## 10. 下一步精确技术任务

1. 用已知 base SHA-256 获取/校验用户自己的 Violet 4.0.0 main.blua；
2. 解析 Lua 5.4 Prototype，定位：
   - C81390F82EADEF632 调用 FE77BCB620AB2EDCA 后的返回值落点；
   - 写入 SE9713F112CDA989C 前后的指令；
   - 或 C050...FCE484... 消费 A2_2[3] 前的稳定点；
3. 选择最小后置 append 实现；
4. 先做只读 trace，确认一次 raid 只追加一次；
5. 再开启实机一条奖励；
6. 按 S0→S6 完成持久化闭环。

在拿到与 C1A4F4E2625912CF0B739A642A79BA3357DF0557A544B92DA22A6CB139DE2815 完全一致的 4.0.0 main.blua 之前，**不把 3.0.1 的 Prototype index / PC 硬搬到 4.0.0。**


## 11. 补充：能否完全不改 main.blua，只做 ExeFS / ARM64 Hook

本轮对 KM-Editor 的 4.0.0 runtime module 做了时序复核。

[native/km-native-settings/src/sv_runtime.cpp](https://github.com/KotMatrosk1n/KM-Editor/blob/e108ec745488a0e38c28edf8585dd1d5c4bbfd96/native/km-native-settings/src/sv_runtime.cpp) 的 km_sv_registration_hook 先调用原版 registration trampoline，然后注册若干 C global，并通过 luaL_loadbufferx / pcall 执行 helper source。源码注释明确说明该回调发生在 **Lua VM construction，主 scripts/gameplay 消费设置之前**。

因此现成 registration hook 不能直接执行：

~~~text
C81390F82EADEF632_prototype.FE77BCB620AB2EDCA = wrapper
~~~

因为此时 main Lua 尚未建立该 class/prototype table。

这条纯 ExeFS 路线如果继续，需要额外解决一个“late trigger”：

1. 找到 main.blua 已执行完成后的 native 边界；或
2. hook main script 的 loader / protected-call 完成边界，只对目标主 chunk 的返回时刻执行一次 helper；或
3. 找到一个确定在 main 初始化后、首次团战生成前调用的原生生命周期函数，在同一 Lua state 线程内安装 wrapper。

不建议从后台线程直接调用 Lua state，因为 Lua VM 的线程/栈所有权需要由游戏原调用线程保证。

旧版 Violet 4.0.0 ELF 审计也支持这个边界判断：F316609DEA110601D 与 RaidResultAddItem 是 Lua closure，尚无独立 ARM64 RVA；f21AF1B35 / f66894ABE 等属于原生绑定/初始化候选，不能直接等同于上述 Lua closure。

所以当前两条实现路线的优先级是：

~~~text
A. main.blua 路线
   exact SHA -> Prototype locator -> 最小 bytecode append call
   优点：目标语义最直接，容易证明只改一个边界

B. pure ExeFS 路线
   Lua VM registration -> 再寻找 post-main late trigger -> runtime wrapper
   优点：可以不分发 main.blua 派生文件
   缺点：第二触发点尚未闭合，当前不能声称已可实机
~~~

本轮新增 [sv400_main_blua_locator.py](../../../scripts/research/sv400_main_blua_locator.py)，其默认硬校验 Violet 4.0.0 base SHA，并按 KM-Editor 已验证的 root shape 再检查：

- root code count = 429,034
- root child Prototype count = 30,829

随后按 LotteryRewardItem、45 行 serializer、F316 filter、RaidResultAddItem 的常量指纹枚举候选 Prototype，并可输出每条 Lua 指令的 file offset / PC / raw word 字段。它只读，不修改 main.blua。
