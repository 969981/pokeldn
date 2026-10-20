---
title: 《紫》4.0.0 Bootstrap 发送副本 Hook 与 RaidCrawler/host 重构
parent: 朱／紫（SV）
---

# 《紫》4.0.0 真实房主：在 0x2F Bootstrap 明文副本无损追加 subject=5

> 2026-10-20；目标为 **969981/RaidCrawler 的 host 分支**，参考 **969981/pokeldn 的 research 分支**。本页是源码级实施与验收规格，**不是已在实机联机发奖成功的证明**。用户已确认数量表实验完成，因此 **不再重复改 `raid_gem_item_reward_boost/data.bin` 的 12→13 实验**。

## 1. 一句话技术路线

真实《紫》4.0.0 Switch 作为房主；在原生 `main+0xE32984` 的 post-memcpy、pre-LZ4 位置使用 **现有 exlaunch InlineHook** 只读观察或受控改写当前 `x23` 指向的 **0xAA0 字节明文发送副本**；在 `RaidPoint` 45×16B 的**首个连续全零槽**追加 1 条 `(ItemID, Quantity, RareFlag=0, Subject=5)`。原始奖励、源对象、Boss、存档及压缩后数据不改。之后由原版 `0x1592B7C` / LZ4 / Pia 链继续发送。

- **不是**寻找静态存档 `RaidBlockPointerBase`、全堆扫描、轮询 `x20/x23` 寄存器或 PC 主动通过 sys-botbase 发送 0x2F。
- sys-botbase 仅用于 C# 与 Native 邮箱之间的控制和取证；实时写入必须由 Switch **同步处于游戏调用路径**的 Native 执行。
- 非标准版本、不同 Build ID 或不匹配指令：fail closed，不安装/不执行写入。默认 CI 构建禁止 N2 写入。
- 当前证据为《紫》4.0.0 ELF，Title ID `01008F6008C5E000`、Build ID `709bfd66115298640155fcc4979dba151c7cc79a`；**朱版、官方 NSO** 不能直接套用。

## 2. 最重要的 ABI 勘误：E4 才是行首

此前 RaidCrawler/host 部分代码沿用已经被否定的 `+0xE0`、`[condition_or_source,item,quantity,reserved]` 解释。最新静态 ELF + PokéLDN donor 交叉验证为：

| 字段 | 值 |
|---|---|
| Bootstrap 明文长度 | `0xAA0` |
| RaidPoint 明文基址 | `x23 + 0x6B8` |
| RaidPoint 长度 | `0x3E8` |
| **45 槽奖励行起始** | **`RaidPoint+0xE4 = x23+0x79C`** |
| 源对象奖励起点 | **`x20 + 0x58 + 0xE4 = x20+0x13C`** |
| 单行 | `u32 ItemID, u32 Quantity, u32 RareFlag, u32 Subject`，Little Endian |
| 行数、总长度 | `45 * 0x10 = 0x2D0` |
| 奖励结束（exclusive） | `RaidPoint+0x3B4 = Bootstrap+0xA6C` |
| 摘要起始 | `RaidPoint+0x3B8`，不可触碰 |

不能将 `+0xE0` 开始解析得到的“marker=5, item=0”当作独立的特殊行：它是 **前一个 subject 字段与下一个空行错位**所致。在 donor 中可按 `+0xE4` 验证 21 条有效行，最后一条为 `(1862, 10, 0, 5)`，其余 24 个全零空行。

核对原始研究：[Violet 4.0.0 ELF 复核](violet400-elf-raid-bootstrap-audit.md)、[donor 解码勘误](sv400-reward-donor-bin-ghidra-audit.md)、[FieldRaidJewelry 生成链](fieldraidjewelry-lotteryrewarditem-glimmering.md)。

## 3. 原生运行链与 Hook 生命周期

```text
FieldRaidJewelry.LotteryRewardItem
   → host 当前房间的奖励列表
   → source RaidPoint / 45 行（main 运行态对象）
   → main+0xE3295C..0xE32980 将 RaidPoint 复制到 x23+0x6B8
   → main+0xE32984 [Native InlineHook：同步采样/受控修改]
       source rewards: x20+0x13C   (720B)
       outgoing rows:  x23+0x79C   (720B)
   → game native main+0x1592B7C 序列化 / raw LZ4
   → 实机 0x2F Bootstrap → 原版参与者接收
   → 每个接收端按背包 item 2481 过滤 subject=5
   → 战斗获胜奖励/背包写入/保存
```

上述 RVA 是匹配 ELF 的静态偏移，不是任何一台 Switch 上的固定绝对地址；仅可在安装了匹配模块的游戏本身调用 `Hook` 时经寄存器读取实时值。只读 N1 的 `source` 与 `outgoing` 的原版 720B 必须完全一致，才允许对下次会话启用 N2。

**应增加强约束：** 核查 `x22` 声明的明文长度（若运行时确认 `0xAA0`）、`x20+0x58` 与 `x23+0x6B8` 双端的 `RaidPoint_` 签名、45 槽连续性、可识别 subject、原版稀有标记的允许集合、外部请求版本与场次；检查失败时完全走原版序列化。

## 4. Host 分支重构入口与职责

| 文件 | 重构职责 |
|---|---|
| `RaidCrawler.Core/Host/RaidPointLayout.cs` | 唯一 C# 常量源：`RewardsInRaidPoint=0xE4`、`RewardsInBootstrap=0x79C`、行序 `Item/Quantity/Rare/Subject` |
| `RaidCrawler.Core/Host/RewardAppendPlanner.cs` | 离线规划，45 槽容量检查、连续性、白名单、整体拒绝；不隐式删除原奖励 |
| `RaidCrawler.Core/Host/HostCaptureVerifier.cs` | 同一 generation 的 720B 比较，字段索引按 Item、Quantity、Rare、Subject |
| `RaidCrawler.Core/Host/Subject5AppendInspector.cs` | 逐字节确认只增加 1 条、原版前缀和其余尾部无变化 |
| `RaidCrawler.Core/Host/HostProbeMailbox.cs` | 使用现有 v2 共享邮箱与 sys-botbase 通道；请求参数邮箱顺序与发包实际行序区分 |
| `switch/host-probe/source/program/main.cpp` | 修正 SourceRows/WireRows 与 ABI；编译门控单行插入；增加运行态结构签名拒绝逻辑 |
| `RaidCrawler.WinForms/SubForms/HostProbeWindow.cs` | UI 默认只读；N1 证据与 N2 试验明确区分“已写入明文”和“真实发给接收者” |
| `RaidCrawler.Tests/Host/*` | 新 ABI、真实 donor 特征、原版稀有标志、45/46 行、空洞、错误版本、改动范围等回归 |

**不要**沿用现有的“自动查找候选 8 MiB/64 MiB 进程扫描”作为主流程；该扫描只能得到稳定内存拷贝，不能证明当前房主发出的 0x2F。推荐入口是已有 `HostProbeLocator` 按 Build 匹配的 Hook trampoline → callback → mailbox；未部署 Native 的情况下应该显示“无发送 Hook”，而不是无限扫描猜地址。

## 5. Native 原子修改要求

1. 采用当前 Hook 堆栈和寄存器提供的有效明文输出对象，先完成双端 720B 原样复制与版本化状态校验；只在同一原生同步回调里写出。
2. 根据真实 ABI 遍历 45 行 `(item,qty,rare,subject)`。全零为候选 padding；遇空洞后的非零行、未知 subject、非法道具或数量、未知保留位：拒绝。原版 `RareFlag=1` 不能误判为损坏（Bottle Cap 曾出现该值）。
3. 若 `used+extras>45`，整单拒绝，禁止裁剪原奖励；阶段 N2 只允许先机球 ID15、数量 1–10、RareFlag0、Subject5，单行。
4. 输出区目标确认为 `x23+0x79C+used*16`，单次最多改写 16B；**从不写回 `x20+0x13C` 源对象**。写前与写后保留原始 720B，C# 比对所有其他字节不得变化。
5. 请求“默认 off、按次 arm、用后/拒绝后清零”；单次 `generation` 绑定快照与结果，重复/重入/新房间不可沿用过期配置。可用时应加入真实 room/session nonce；现有邮箱 `session` 仍是保留字段，**不能标注已实现**。
6. 原版 LZ4 及 Pia 保持不变；PC 不能直接替代游戏发送端。发生错误时最安全的结果是 N2 不做修改，而不是回滚未知已发送内容。

**推荐增加全 `RaidPoint` 和 0xAA0 明文安全条件**，但 v2 邮箱只有 720B ×2 和固定头，若需要外部复核更多字段，需设计 v3 协议且同步更新 C++/C#；不应随意扩展现有结构破坏 v2 偏移。

## 6. 验收矩阵（已证与未证）

| 检查 | 通过条件 | 当前状态 |
|---|---|---|
| S0 静态 ELF + donor | +E4 行起点、45×16、原生复制序列 | 有静态证据 |
| S1 回归测试 | C# 和 Native 同一 ABI；原奖励不改；改写仅一行 | 需要 CI/构建确认 |
| N1 真机房主 Hook | Hook 回调命中并获取同局双端 720B、捕获次数变动 | 尚未验证 |
| N2 预览 | Next bootstrap 返回 10，无游戏内存修改 | 尚未实机验证 |
| N2 实机写入 | 返回 20，C# 确认新增 subject5 行、原内容逐字节保留 | 尚未实机验证 |
| N3 接收者与保存 | 持护符接收者见附加道具，无护符不见；到账并重载仍在 | 尚未验证 |
| 扩展 20×999 | 足够空槽、每种道具背包上限与实际保存经独立验证 | NOT SUPPORTED |
| 任天堂官方互联网 | 使用与本地 LDN 一致的信任路径及发奖规则 | 未证，独立门槛 |

外部证据：[PokéLDN Bootstrap 研究](../../sv_raid.md#the-battle-bootstrap)、[源码 raid_point 构造](https://github.com/969981/pokeldn/blob/host/pokeldn/sv/raid.py)、[RaidCrawler Native 现有实现](https://github.com/969981/RaidCrawler/blob/host/switch/host-probe/source/program/main.cpp)。

## 7. 本轮决策

**已完成的数量表关联研究不重复做。** 优先修复现有分支 ABI → N1 同步捕获 → 在保持默认只读前提下编译/单测 → 测试机显式 N2 编译与手动确认 → 房主发包与参与者存档闭环。不要扩大内存扫描范围，更不要宣称目前已能实时修改 NSO 或自动发奖。
