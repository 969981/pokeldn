---
title: 晶耀护符与太晶坑奖励资格（SV）
parent: 朱／紫（SV）
nav_order: 1
---

# 《朱／紫》晶耀护符、太晶坑奖励资格与 999 道具案例

- **项目**：969981/pokeldn · `research` 分支，SV/Pia6/RaidPoint
- **状态**：已有源码与上游 ELF 研究证据；商业联网案例、ELF 独立复核和 999 存档闭环 **待验证**
- **记录日期**：2026-10-19
- **研究游戏**：《朱／紫》；涉及的原生偏移来自上游**《朱》4.0.0 解压 main**（上游记载《紫》4.0.0 同偏移），不能外推其他游戏版本
- **研究基线**：research 初始参考 SHA `ce3ffd3a8dde324b001269e149fc88fc207afe14`（本次文档提交前）；具体文件请按下方路径查看；后续自动集成可能改变分支 HEAD
- **设备/材料**：此轮直接核对仓库 Python 源码、上游逆向文档及公开游戏资料；**没有取得《朱／紫》ELF 原件、IDA 数据库、联网抓包或商家改版可执行文件**。下方地址为**转录的上游逆向锚点**，不称作本轮重新完成的 ELF 反编译。

## 研究目标与范围

解释以下可分离的现象：①正常玩家如何获得晶耀护符；②奖励行的 `subject=5` 为什么能把道具奖励限定给持有护符的接收者；③原版 PokéLDN 在本地 LDN 已验证了什么；④视频/商品展示的联网 999 道具坑有哪些合理技术路径，以及还缺少哪些证据。

用户提供的案例：2026-10-18 视频作者称要求购买 DLC 且持有晶耀护符；截图显示太晶坑结算数种奖励 ×999、背包中多个道具达到 999，用户确认案例属于远程联网。**这些是用户提供的截图/说明，不是本仓库重现实验，也不是任天堂官方互联网模式的抓包证明。**参考视频：[B站 BV1TAn36YEya](https://www.bilibili.com/video/BV1TAn36YEya)。

> **核心判断**：`subject=5` 的客户端资格判断是已有逆向证据；把 999 道具行改为 `subject=5` 是高度可检验的解释，**但没有证据证明商家的具体实现就是如此**。持有护符本身不会在正常游戏里把大师球等道具变为 ×999。

## 1. 游戏规则：晶耀护符不是闪耀护符

| 条目 | 内容 | 证据 |
|---|---|---|
| 中文 / 英文 | 晶耀护符 / Glimmering Charm；区别于提高异色遭遇概率的闪耀护符 / Shiny Charm | [Bulbapedia](https://bulbapedia.bulbagarden.net/wiki/Glimmering_Charm) |
| 类型 | 重要物品（Key Item），游戏内不能作为普通道具交换 | [Bulbapedia](https://bulbapedia.bulbagarden.net/wiki/Glimmering_Charm) |
| 常规获取 | 《碧之假面》北上图鉴登记全部 200 种后，在起舞山道（Reveler's Road）找吉尼亚（Jacq）老师领取；图鉴 200 种的阶段奖励另有月亮球，不能混淆 | [北上图鉴](https://bulbapedia.bulbagarden.net/wiki/Kitakami_Dex) |
| 正常效果 | 太晶坑额外太晶碎块：3★ +2、4★ +5、5★ +10、6★ +12；1、2、7★ 无此奖励 | [道具效果](https://bulbapedia.bulbagarden.net/wiki/Glimmering_Charm) |
| 代码检查对象 | 物品 ID **2481**；这是客户端奖励筛选用的背包拥有条件，不是 DLC 所有权凭据 | [上游 SV Raid 逆向](../../sv_raid.md#the-battle-bootstrap) |

**无 DLC 的边界**：通过交换或集友圈的某些活动获得 DLC 物种，与**获得北上图鉴/进入北上乡/找吉尼亚领重要物品**是不同条件。未购买 DLC 的玩家可获得部分新增物种，并不等于正常条件下能够获得晶耀护符；重要物品不能经普通交换转让。需要分别验证目标账号的 DLC 访问权、北上图鉴和重要物品背包。不能将“集友圈能抓 DLC 宝可梦”写成“没买 DLC 也能领取护符”。参见 [Nintendo Life](https://www.nintendolife.com/guides/pokemon-scarlet-and-violet-kitakami-pokedex-all-pokemon-locations-in-the-teal-mask-dlc)、[Nintendo 官方集友圈操作](https://www.nintendo.com/en-gb/Support/Purchases-Subscriptions/Games/How-to-Set-Up-a-Local-or-Online-Multiplayer-Game-Pokemon-Scarlet-Pokemon-Violet--2843740.html)。

## 2. 代码已证实：RaidPoint 奖励行结构

来源：[`pokeldn/sv/raid.py`](../../../pokeldn/sv/raid.py) 的 `raid_point`、`bootstrap`，及[`pokeldn/sv/raid_encounter.py`](../../../pokeldn/sv/raid_encounter.py) 的 `reward_rows`。

> 下面两个源码链接使用仓库根目录的相对定位时：[`pokeldn/sv/raid.py`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py)、[`pokeldn/sv/raid_encounter.py`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid_encounter.py)。

`0x2F` 战斗 bootstrap（解压后）固定 `0xAA0` 字节：

| 偏移（bootstrap） | 长度 | 内容 |
|---|---:|---|
| `0x000` | `4 × 0x158` | 四名玩家的加密队伍记录 |
| `0x560` | `0x158` | 首领的队伍记录 |
| `0x6B8` | `0x3E8` | `RaidPoint` |

`RaidPoint` 中从 **`+0x0E4`** 开始是 **最多 45 行 × 16 字节**的奖励行，每行都是小端 4 × `u32`：

| 行内偏移 | 解释 |
|---|---|
| `+0x00` | `item`：道具 ID |
| `+0x04` | `quantity`：数量 |
| `+0x08` | `rare`：稀有道具标记 |
| `+0x0C` | `subject`：领取资格类别 |

其中最后一行结束于 `0x3B4`，`0x3B4` 位置还有单独字节/保留区；`0x3B8` 是首领的摘要信息起点。实际长度由源码 `POINT_REWARDS=0x0E4`、`POINT_SUMMARY=0x3B8`、`REWARD_ROWS=(POINT_SUMMARY-POINT_REWARDS)//16` 导出，不能误写为“所有 0x0E4..0x3B8 都是完整奖励行”。

### 奖励 `subject` 的真实客户端语义

| `subject` | 接收端规则 | 验证程度 |
|---|---|---|
| 0 | 所有人 | 上游 Lua 过滤函数、项目生成代码 |
| 1 | 房主 | 上游 Lua 过滤函数 |
| 2 | 加入方 | 上游 Lua 过滤函数 |
| 3 | 满足一次性奖励资格 | 上游 Lua 过滤函数，依赖外部 eligibility 参数 |
| 4 | 与首领太晶属性匹配的“团战力”，最多保留前 N 条，N 为最高匹配等级（0–3） | 上游 Lua 与模拟客户端实验 |
| **5** | **接收者背包中拥有重要物品 ID 2481（晶耀护符）** | **上游 Lua 与实机加入方验证** |

重要区别：游戏的 `RaidRewardItemSubjectType` 枚举本身只包含 0–3，4/5 是奖励处理流程额外解释的取值。它们不是“4=道具价值高、5=999 专用”的格式说明。

正常零售奖励：固定奖励按表保留 `SubjectType`，普通抽奖按 0，额外的三个抽奖位置按 4，追加晶耀护符太晶碎块按 5；`SHARD_BOOST=(0,0,2,5,10,12,0)`。项目的 `raid_encounter.reward_rows` 明确按此组装。

**与商家现象最有关的差别**：

- 公开版 `raid.raid_point(raid, rewards=...)` 将所有自选 `--raid-reward ITEM:QUANTITY` 编为 `(item,quantity,0,subject=0)`，**不要求护符**。
- 若商业改版把同一奖励行的 `subject` 改为 5，现有 Lua 过滤规则意味着“只对持有护符者显示该行”。这个逻辑**不能推出**互联网房间如何建立、所有道具是否都被允许、能否永久保存。
- 由此，**卖家要求护符 ≠ 上游 `--raid-reward` 自带护符校验**。也可能只是人为设置门槛，需以报文或对照实验排除其他解释。

## 3. ELF / Lua 逆向锚点（上游已有证据；本轮未复核 ELF）

上游文档 [`docs/sv_raid.md`](../../sv_raid.md) 记载的《朱》4.0.0 解压 `main` 地址：

| 入口/偏移 | 上游记录的用途 |
|---|---|
| `0xE327FC`、`0xE329B4` | `0x2F` bootstrap 序列化与宝可梦记录写入 |
| `0x1BAE670 → 0x1BAE760 → 0x1BAFF98` | `RaidPoint` 反射 getter/数据取出 |
| `0x1BB0018` | 将 `RaidPoint` 内容拷贝到消息对象 |
| `0x1592B7C`、`0x1592DAC`、`0x1592E80`、`0x71D940` | 序列化头及 LZ4 压缩路径 |
| Lua 函数 `C07C34FC3B976E5A7.F316609DEA110601D` | 奖励行资格过滤，源 bytecode 行 78707–78765 |
| Lua 模块 `be21e65463b9a98f` | 奖励过滤函数所在块；上游记录 SHA-256 `c1a4f4e2625912cf0b739a642a79ba3357df0557a544b92da22a6cb139de2815` |

这里的 `0x...` 是**原版 4.0.0 对应 main 的偏移**，不是全版本通用绝对内存地址；Lua 函数名是字节码标识，不应虚构一个与其对应的 ARM64 入口。上游报告通过执行**未修改的 Lua 过滤函数**（提供环境 getter 的测试框架）验证 `subject=5` 读取 ID 2481 的背包存在性，并实测有护符的正版《朱》加入方取得相应太晶碎块。

**本轮 ELF 仍需补齐的链**：`bootstrap receiver → RaidPoint fields → Lua filter → per-player reward list → UI/result inventory → save persistence`。上游证明了中间部分，但未提供本轮独立 ELF 操作日志。下次应保存目标版本的 Build ID/ELF SHA-256、每个交叉引用与可重复命中的反汇编/伪代码；不要把 4.0.0 的 RVA 直接复制到其他版本。也不能把“未发现服务器校验”误写为“服务器绝对不校验”。

## 4. 999 道具截图的三种解释：不混淆“互联网”

| 可能路径 | 玩家看到的通信方式 | 本轮证据 |
|---|---|---|
| A. 本地 LDN：PokéLDN 模拟房主 + ESP32 | 游戏内离线搜索，现场/近距离参与 | **公开源码已支持本地太晶坑**；有自定义先机球 ×500 的实机记录 |
| B. 远程 LDN 中继 | 双端仍通过本地 LDN 连各自模拟器，中间走互联网 | **在线交换**已用 Nostr 中继验证；**太晶坑**套用此机制仍未在公开源码中证实 |
| C. 游戏原生“互联网连接”太晶坑 | 正版 Switch 通过官方互联网模式加入 | 视频/用户确认是远程联网，但**未获得足够可独立核验的会话/报文证据**证明此商用改版具体如何建立 C |

参考 [公开版 Online Trade](../../online.md)：两端各自面对本地交易，Nostr 中继跨公网传递数据；**在线交换≠官方互联网太晶坑**。参考 [公开版 SV Raid](../../sv_raid.md)：明确用离线搜索加入。视频若可见按 L 后“互联网连接”及原生联机大厅，应单独归类 C，不能由原版 LDN 文档否定，也不能据此称上游已实现 C。

**可证伪假说**：
- **H1（优先验证）**：商家构造可联网传递的 `RaidPoint`，将奖励行标为 `subject=5`，接收方按背包拥有 ID 2481 决定是否领取。
- **H2**：奖励行是 `subject=0`，商家对护符的要求只是服务前置约束；护符并非实际奖励资格条件。
- **H3**：远程 LDN 中继被称作“联网”；其实现不涉及原生 Nintendo 在线太晶坑房间。
- **H4**：实现走了不同奖励数据通道、额外客户端补丁或其他未披露机制；必须抓取报文才能排除。

从画面看到 `×999` 只说明当次 UI 显示的数量；**还不能直接证明每个道具在正常背包上限内以 999 永久入库，更不能据此断言服务器有或没有校验**。需对比领取前、领取后、保存、重启及重新联网后的数量。

## 5. 可复现测试计划与验收条件（均未在本轮执行）

只在自己控制的测试环境和授权账户中收集必要数据；保留原始报文哈希、游戏版本、ELF Build ID、源 commit、设备类型、账号护符状态；屏蔽 NNID、会话凭据、完整通信密钥。**先做离线/本地验证，不以未知商业网络为生产测试对象。**

1. **静态断言**：从 `pokeldn.sv.raid.raid_point` 得到 `0x3E8` 长度；验证 `bootstrap` 长 `0xAA0`、第一行从 `0x0E4` 起且 16 字节小端；`rewards=...` 时 `subject=0`；普通 `reward_rows` 随星级追加 `subject=5` 太晶碎块。
2. **护符差分**：构造等价的少量、普通且安全奖励，分别为 `subject=0` 与 `subject=5`；同版同种子同角色分别测试有/无 2481。H1 的最小预期：`subject=5` 仅有护符者显示，`subject=0` 两组均显示。
3. **奖励量差分**：用 3/4/5/6 星的原始护符碎块奖励做参照，记录 `2/5/10/12` 的观察；同时控制 `Raid Power` 避免把 `subject=4` 的额外条目误归因护符。
4. **容量和持久化**：分别用小数量及接近可持有上限的数量，比较 UI 单次显示、进入背包的实际增量及保存重启后的值；**未做之前不宣称任意 ×999 的稳定性**。
5. **联网传输证据**：记录是否在游戏内按 L 切“互联网连接”、Nintendo 匹配房间样式、联机码、host/guest 接收的 bootstrap 摘要及匿名化握手时间线（**不上传密钥**）。据此区分 A/B/C，而不是仅凭远程地理位置。
6. **ELF 复核**：在实际游戏版本中定位 `0x2F` 消息接收分发、字段 getter、Lua `subject 5` 判断、物品加入背包以及保存写入函数；每条结论附具体 RVA、调用链和证据截图/反汇编文本。禁止把上游 4.0.0 位置当成新版有效地址。

### 最小对照矩阵（预期，并非实测）

| 接收者 | 奖励的 subject | 预期显示 | 注意 |
|---|---:|---|---|
| 无护符 | 0 | 显示 | 受普通道具可用性限制 |
| 有护符 | 0 | 显示 | 与护符无关 |
| 无护符 | 5 | 过滤 | 需实机核对 |
| 有护符 | 5 | 显示 | 仅证明资格过滤，不证明联机/存档 |
| 任意护符状态，团战力不匹配 | 4 | 过滤 | 区分餐力条件 |
| 团战力匹配 Lv.1/2/3 | 4 | 保留前 1/2/3 行 | 上游 Lua 测试已验证 |

## 2026-10-19 Lua 交叉验证进展

已从独立公开仓库 [SV-Script-RE](https://github.com/Martmists-GH/SV-Script-RE) 找到游戏 3.0.1 时代的 `main.battle.BattleRewardData` 的实际反编译 `F316609DEA110601D`，并跨文件追到 `main.management.bag.Bag.GetNumItem(2481)` 及 `FindItemById`：结果数量大于零时才允许 `subjectType=5` 行。参见 [完整研究笔记](battle-reward-lua-cross-version.md)。**这不是 4.0.0 的原始 RomFS 文件，不是商业改版直接证据**。

## 6. 结论与后续建议

**已证实（源码 / 上游验证）**：公开 `raid_point` 自选奖励默认为 `subject=0`；正常种子构造 `subject=5` 护符碎块；客户端 4.0.0 Lua 过滤函数按照是否拥有 ID 2481 保留 `subject=5` 行；原版已实现本地 LDN 自定义奖励。

**推断**：商业案例强调晶耀护符，高度吻合“对自定义道具行使用 `subject=5`”的门槛设计，但并非唯一解释。

**待验证**：商家具体传输技术、是否原生 NSO 模式、其 `subject` 字段和奖励对象、所有 ×999 奖励是否存档持久化、游戏最新版本的 ELF 路径。后续如获得合法可研究的目标版本 ELF / 脱敏样本，按第 5 节更新证据，而不是直接将推断升级为已证实。


## 2026-10-19 后续 ELF 实证补充

已从 Library 取得真正的《紫》4.0.0 `Violet4.0.0.elf` 并独立验证 AArch64 指令、Build ID、SHA-256；`main+0xE327FC` 的 `0xAA0` bootstrap、`+0x6B8` RaidPoint、`0x3C8` 后段复制，以及 `0x1BAE790` getter 链均有本轮真实 ELF 机器码证据，15/15 opcode 断言通过。详见 [《紫》4.0.0 ELF 原生指令审计](violet400-elf-raid-bootstrap-audit.md)。**Lua subject=5 过滤、官方互联网房间与商业奖励存档仍未由这次 ELF 分析独立验证。** 本文页首“没有取得 ELF”描述的是第一次撰稿的材料状态，现已由此补充更新。

## 参考资料

- [上游 SV Raid 原版逆向](../../sv_raid.md)；[汉化版](../../zh-Hans/sv_raid.md)
- [SV 应用/协议基线](../../sv.md)；[Online Trade](../../online.md)
- [源码 raid.py](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py)；[raid_encounter.py](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid_encounter.py)；[sv_host.py](https://github.com/969981/pokeldn/blob/research/bin/sv_host.py)
- [晶耀护符](https://bulbapedia.bulbagarden.net/wiki/Glimmering_Charm)；[北上图鉴](https://bulbapedia.bulbagarden.net/wiki/Kitakami_Dex)
- [B站案例](https://www.bilibili.com/video/BV1TAn36YEya)（外部展示，尚无可独立验证的报文）
