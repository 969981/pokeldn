# 《宝可梦 朱／紫》太晶团体战 Bootstrap 发送时序与自定义奖励技术研究

> 研究日期：2026-10-20  
> 目标仓库：[`969981/pokeldn`](https://github.com/969981/pokeldn)，分支：`research`  
> 基线：上游 [`Decryptu/pokeldn` 的 `docs/sv_raid.md`](https://github.com/Decryptu/pokeldn/blob/main/docs/sv_raid.md) 与本分支 `pokeldn/sv/raid.py`、`pokeldn/sv/raid_reward_trace.py`。  
> 版本边界：上游给出的 Nintendo Switch 零售机、反汇编偏移主要针对 **Scarlet/Violet 4.0.0**；不要自动套用到其他版本。  
> 文档性质：已核验的源码/文档事实 + 逻辑推论 + 未验证事项；本文**没有新增实体 Switch 实验**。

## 0. TL;DR：回答“玩家刚进队列就发，还是开始战斗时发？”

**Bootstrap（游戏消息 `kind=0x2F`，组合 ID `0x012F`）是在大厅准备流程结束、房主发出开始信号 `0x0C` 并收到参与者 `0x0D` 确认以后发送，且先于加载完成/正式战斗开始。不是玩家一加入房间就发送。**

加入大厅时会先交换 **Raid 描述符 `0x2C`、玩家状态 `0x2D`、宝可梦记录 `0x2E`、倒计时 `0x30`**；这些不是包含奖励数组的完整 Bootstrap。上游记录的原版 `Raid_Start_Go`（Lua `0.27140`）反复发 `0x0C` 等待所有 `0x0D`，然后发送 `0x2F`。

因此：
- **最稳妥的房主改奖时机：源 RaidPoint 完成奖励生成之后、被复制到 Bootstrap 并序列化之前。**
- 可以在按下“开始战斗”前修改奖励，但**按按钮本身不是精确的代码锚点**；要沿 `Raid_Start_Go → RaidPoint 复制 → 0x2F 序列化` 定位。
- 一旦 Bootstrap 已经发出，接收方有自己那份 RaidPoint 副本；**仅改房主原对象无法推定接收方也会改变**。

## 1. 证据分级

| 级别 | 内容 | 状态 |
| --- | --- | --- |
| A：上游实机/逆向记录 | 开始握手、Bootstrap 位置、Lua 接收/奖励筛选、Quick Ball ×500 的零售版领取 | 文档明确记录；不是本次重测 |
| B：本分支源码 | `RaidGroup.started`、`RaidHost._next`、`bootstrap`、`raid_point`、`raid_reward_trace` 的具体实现 | 本次已检查 |
| C：推论 | 房主源内存需要在 Bootstrap 快照生成前更新，才能影响接收方 | 由复制/网络序列化链推导 |
| D：待验证 | 真实 Switch 房主 ARM64 Hook 的最佳入口、所有玩家完整接收及入包、其他版本偏移 | **未验证，禁止称已完成** |

## 2. 本地团体战消息、方向、阶段

通信通道：游戏消息承载于 `0x80 port 0`；大厅处理 key `0x3380`。

| 消息 | 方向/含义 | 阶段 |
| --- | --- | --- |
| `0x2C` | 房主提供 Raid 描述符：物种/形态/星级/太晶属性等 | 入房、展示大厅 |
| `0x2D:0x18` | 参与者进入大厅的状态 | 入房 |
| `0x2E` | 参与者的 344 字节加密 party 宝可梦记录 | 入房、队伍同步 |
| `0x30` | 大厅剩余秒数 | 大厅 |
| `0x2D:0x01` | 参与者 Ready | 准备 |
| `0x2D:0x0C` | 房主请求开始战斗 | 开始握手 |
| `0x2D:0x0D` | 参与者确认收到开始请求 | 开始握手 |
| **`0x2F`** | **房主发送 Boss + RaidPoint + 4 玩家记录** | **进入战斗之前** |
| `0x6E/0x73`（key `0x0132`） | 接收方加载/已加载通知 | 加载 |
| `0x93`（key `0x3480`） | 正式战斗开始消息 | 战斗 |
| key `0x007B` 的后续帧 | 战斗启动所需消息 | 战斗 |

**状态机（高层）：**

```text
JOIN / LOBBY
  ├─ 0x2C Raid descriptor
  ├─ 0x18 player entering + 0x2E party record
  ├─ 0x30 countdown ...
  └─ 0x01 Ready
         │ 房主满足启动条件（所有指定成员 Ready，或大厅倒计时触发）
         ▼
  HOST: 0x0C Start
         │
  GUEST(S): 0x0D Start acknowledged
         │
  HOST: 完成必要会话 ACK/状态同步
         │
         ├─ raid_point() 构造源 RaidPoint (可含自定义奖励)
         ├─ bootstrap() 整合玩家、Boss 和 RaidPoint
         └─ bootstrap_message() → LZ4 → kind 0x2F
                    │
                    ▼
  RECEIVER: 0x2F / Bootstrap 接收、解压、建立战斗数据
                    │
        0x6E / 0x73 Loading / Loaded
                    │
            0x93 Battle begins
                    │
       Battle / Reward filter / Save
```

### 2.1 上游实机顺序（不是固定耗时）

上游 `docs/sv_raid.md` 的**一台参与 Switch、5 秒内 Ready 的样例**中，主机消息序号：

| seq | 内容 | 触发 |
| --- | --- | --- |
| 1 | Raid 描述符 | 参与者大厅的 `0x2E` |
| 2–3 | `0x18`、房主宝可梦记录 | 大厅同步 |
| 4–6 | 倒计时 | 大厅进行 |
| 7 | `0x01` Ready | 示例约 3.19s |
| 8–9 | 倒计时 | 示例约 3.76s、4.79s |
| **10** | **`0x0C` Start** | **样例约 5.39s，非固定时间** |
| — | Net `0x50`、Session station list | 参与者确认及网络状态同步 |
| **11–12** | **`0x2F` Bootstrap，分两段** | **开始握手及会话同步完成** |
| 13 | 已加载通知 | `0x6E` 或 `0x73` |
| 14 | `0x93` 战斗开始 | `0x73` |
| 15–20 | 战斗启动消息 | 战斗状态 |

说明：
1. 多人情况下需等待各已在场成员的开始确认；不是固定加入 5.39 秒后发送。
2. 原版房主以 `Raid_Start_Go` 的 `0.27140` 逻辑等待 `0x0D`；`research` 分支通过 `all("guest_start" in m.seen for m in self.group.present())` 和 `session_ack` 约束发送。
3. 可靠消息可能重传；上表是**阶段/逻辑顺序**，不是断言网络只会出现一次物理包。
4. 参与者不 Ready 时也存在倒计时触发的路径；不能把“必须手动全员点 Ready”当作所有情况下的硬规则。

**上游证据：** [大厅与时序](https://github.com/Decryptu/pokeldn/blob/main/docs/sv_raid.md#the-lobby)；[本分支 `raid.py` 的 `RaidGroup.started`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py#L295-L311)、[`RaidHost._next`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py#L545-L567)。

## 3. Bootstrap 与 RaidPoint 的二进制布局

`0x2F` 消息的**未压缩 payload 为 `0xAA0 = 2720` 字节**，经 LZ4 压缩；消息内含序列化头（key、kind、counter、compression、明文长度等）。以下偏移均针对**解压后的 Bootstrap payload**，**不是 Switch 进程虚拟地址**。

| Bootstrap 偏移 | 大小 | 数据 |
| --- | --- | --- |
| `0x000` | `4 * 0x158 = 0x560` | 4 个参与者的 party 记录 |
| `0x560` | `0x158` | Boss party 记录 |
| `0x6B8` | `0x3E8` | RaidPoint 整体 |
| 总长 | `0xAA0` | 不含传输 framing |

其中 RaidPoint：

| RaidPoint 偏移 | 长度 | 内容 |
| --- | --- | --- |
| `0x000` | `0x18` | 名称 `RaidPoint_...` |
| `0x020` | `4 * u32` | 星级、水晶类别、捕获率、捕获等级 |
| `0x030` | `7 * u32` | 战斗限时等 |
| `0x04C` | `37 * u32` | Boss 行为数据 |
| **`0x0E4`** | **`45 * 16 = 0x2D0`** | **奖励数组（720 字节）** |
| `0x3B4` | 1 字节 | 水晶标志 |
| `0x3B8` | `7 * u32` | Raid 摘要 |
| `0x3D8` | `u64` | NPC/战斗随机种子 |
| `0x3E0` | `u32` | NPC 组进度 |

奖励行是小端序 `<IIII`：

```c
struct RaidRewardRow {
    uint32_t item_id;   // +0x00
    uint32_t quantity;  // +0x04
    uint32_t rare_flag; // +0x08
    uint32_t subject;   // +0x0C
};
```

每一行在解压 Bootstrap 中的偏移：

```text
reward_region = 0x6B8 + 0xE4 = 0x79C
row[i] offset = 0x79C + 16 * i,  i ∈ [0,44]
end (exclusive) = 0x79C + 0x2D0 = 0xA6C
```

注意 `POINT_SUMMARY` 是 `0x3B8`，不是 `0x3B4`；`0x3B4` 存在一个单独的标志字节。不要把 720 字节奖励区覆盖进摘要。

**原版结构证据：** [上游 Bootstrap 结构与反汇编](https://github.com/Decryptu/pokeldn/blob/main/docs/sv_raid.md#the-battle-bootstrap)；[本分支 `raid.py`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py)。

## 4. 固定奖励、随机奖励、最终 45 行与 Subject

**原始掉落表层：**
- 固定奖励：按 Raid 对应的固定奖励表选择道具/数量/领取对象；适用行无需抽选。
- 随机奖励：根据 Lottery 配置进行 RNG 抽选，其权重 `Rate` 参与“抽到哪一条”，但**不是最终 RaidPoint 奖励行的字段**。
- 原版 RaidPoint 的最终数组会综合固定行、随机抽取、料理额外行及晶耀护符额外行。数组**总共至多 45 行**，不是每种 Subject 各 45 行。

**最终数组 Subject 含义（原版 4.0.0 逆向记录）：**

| 值 | 最终领取筛选 |
| --- | --- |
| `0` | 所有人可领取 |
| `1` | 房主 |
| `2` | 参与者 |
| `3` | 满足一次性奖励资格 |
| `4` | 与太晶属性匹配的 Raid Power，可保留前 N 条额外奖励（N 受等级影响） |
| `5` | 接收者持有 Glimmering Charm（晶耀护符） |

`Subject=4/5` 在**最终 RaidPoint 奖励行**可见，不代表游戏固定奖励表枚举也有 4、5 这两个值。带 `rare_flag` 的记录在上游观测中有靠前显示现象；不可直接解释为加权概率。

**本仓库 `research` 分支与上游 `main` 要区别：**

- `research` 的 `raid_point()` 能接收内部元组 `(item, quantity, subject)`，但**当前只允许 Subject 0 和 5**，不是已支持任意 Subject 0–5 的编辑器。
- 命令行 `--raid-reward ITEM:QUANTITY[:SUBJECT]` 数量允许 1–999；无 Subject 默认 0；有 Subject 只能 0/5。
- 覆盖奖励时会重建最终奖励行，而不是自动“固定 + 随机”叠加；默认 `rare_flag=0`，其余位置零填充。
- 注意自定义奖励模式与未经覆盖时的原始奖励生成路径不同；后者可保留 seed 推导的常规/额外奖励。

**源码证据：** [本分支 `raid_point()`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py#L171-L215)、[`bin/sv_host.py` CLI 解析](https://github.com/969981/pokeldn/blob/research/bin/sv_host.py#L209-L223)。

## 5. “先机球 ×500” 原始实验：验证了什么，没验证什么

上游文档记载（意译）：“零售版 Switch 对一个被重写为 Quick Ball ×500 的奖励行进行了发放；其他奖励行清空，保留一条额外奖励行，实际按设置领取。”

这是**上游已记录的特定实机观测**，不是本次现场测试，也不等于提供了可精确复现当年实验的完整命令/内存日志。

以 `ItemID=15`（先机球）、`quantity=500`、`rare=0`、`subject=0` 作为**示意的第一行**：

```text
Relative RaidPoint +0xE4 / plain Bootstrap +0x79C:
0F 00 00 00  F4 01 00 00  00 00 00 00  00 00 00 00
   item=15        qty=500       rare=0           all=0
```

**强调：** 文档只写明“重写一行、其余清空、仍留一条 bonus”，**并没有给出那一行的原始行号、完整 45 行十六进制快照或执行命令**。上面“一行在首槽，Subject=0，Rare=0”是便于解释的**构造示例**，不得冒充原始实验的原样 dump。

验证结论：
1. 至少在记录的 4.0.0 本地房主发送场景中，**零售端能够使用收到的自定义 RaidPoint 奖励数据发奖**。
2. 某条奖励成功以 **500** 数量发放，不等于所有物品都能发 999、不等于房主和三名客机同时通过验证。
3. 没有证据证明对任意官方互联网团体战也可照搬；本报告聚焦本地 LDN 路线。
4. 上游采用 **PokéLDN 构造/发送自定义 Bootstrap 的模拟房主**，不是在真实 Switch 房主进程里植入 ARM64 Hook。

**实验原始出处：** [`docs/sv_raid.md` 的 Reward rows 章节](https://github.com/Decryptu/pokeldn/blob/main/docs/sv_raid.md#the-battle-bootstrap)。

## 6. 真实房主的“源 RaidPoint → Bootstrap”复制链

上游给出的 Scarlet/Violet 4.0.0 反汇编链：

```text
Raid_Start_Go (Lua proto 0.27140)
    └── send start 0x0C / await 0x0D
          └── 0x1BAE670
                 └── 0x1BAE760
                        └── reflected-field getter 0x1BAFF98
                              └── copy 0x1BB0018 → message object +0x78
                                    └── serializer 0xE327FC
                                          └── LZ4 encode / 0x2F
```

上游文档明确说：“RaidPoint is copied whole”。其中首 `0x20` 字节及后 `0x3C8` 字节在消息对象中有不同持有方式；不要把 `message+0x78` 与“RaidPoint 原始头部起点”混同。

**Hook 设计推论：**
- 源头（奖励生成后）：可影响随后复制；可能被后续奖励生成逻辑重写，需记录快照。
- 复制/消息对象阶段：只在确认对应字段与完整长度时替换，避免错误覆盖 Boss/成员数据。
- 序列化之前：最终对外 payload 的最直接观察点；改得太迟将无法影响已经分发的副本。
- 接收方独立内存：作为**验证点**，不能仅凭房主包内哈希推导对方筛选/背包保存成功。

上述反汇编偏移是**解压游戏 main 的相对偏移，绑定 4.0.0 版本**，不是任意版本可直接 patch 的运行时绝对地址；未做 4.0.0 以外符号迁移。

## 7. research 分支已经具备的 S1/S2 观测能力

已存在：[`pokeldn/sv/raid_reward_trace.py`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid_reward_trace.py)。

开启方式：

```bash
export POKELDN_SV_REWARD_TRACE=/tmp/pokeldn_rewards.jsonl
# 按现有工程文档启动 sv_host.py；这里只展示诊断开关
```

每个 RaidGroup 有独立 `run_id`，输出 JSONL；日志至少包含以下事件：

| 事件 | 捕获内容 | 判定 |
| --- | --- | --- |
| `S1_SOURCE` | `raid_point()` 最终 0x3E8 的奖励区 | 源 45 行及 SHA-256 |
| `S2_HOST_BOOTSTRAP` | 发送前的明文 `0xAA0` Bootstrap | 完整 RaidPoint 与 S1 对比 |
| `S2_WIRE_LOOPBACK` | 对房主自己已封装消息进行独立本地解码 | 回解结果与 S2 对比 |

判定字段例如 `MATCH_S1`、`MATCH_S2_HOST`、`COPY_MISMATCH`、`TRANSPORT_OR_PARSE_MISMATCH`。计算哈希**必须包括全部 45 行（720 字节，含全零行）**，不能只比对非零项目、数量总和或字符串显示。

采样点已经写在 `research` 分支：
- `bootstrap(..., on_point=...)`：构造最终源 RaidPoint 后立即采样。
- `RaidGroup.bootstrap()`：把源对象组入房主使用的完整 Bootstrap。
- `RaidHost._next()` 的 `boot1` 路径：在 `bootstrap_message` 后 `capture_host(...)`，随后做分片发送。

**注意：这套日志是房主本地自检，不是接收者抓包。** 还需独立从受控/授权的 Switch 或隔离测试客户端提取 `S3_RECEIVER`。

## 8. 下一阶段：三点一致性验证与验收矩阵

### 8.1 最小三点闭环

```text
S1_SOURCE:      最终生成的源 RaidPoint 奖励区
     ||    SHA-256(all 720 bytes)
S2_HOST:        房主发送前 Bootstrap +0x79C 奖励区
     ||    SHA-256(all 720 bytes)
S2_LOOPBACK:    主机本地完整解包的奖励区
     ?     接收方独立采样，不能由主机假装
S3_RECEIVER:    真实接收者解压/反序列化后的 RaidPoint 奖励区
     ↓
S4_REWARD:      胜利奖励画面、背包实际变化、存档再读取
```

| 用例 | 操作 | 必须验证 |
| --- | --- | --- |
| TC-01 | 参与者刚加入大厅，未开始 | 只有描述符/玩家/计时相关消息，**无 0x2F** |
| TC-02 | 参与者 Ready，但房主未发开始 | 不应发送 0x2F |
| TC-03 | 房主触发开始 | 先 0x0C，再观测所有在场参与者回 0x0D |
| TC-04 | 开始确认及 session ACK 完成 | 此后可见 0x2F 的分片；位置符合状态机 |
| TC-05 | S1 与 S2 的所有 720 字节比较 | 必须相等，否则定位覆盖/复制问题 |
| TC-06 | S2 与 S2_LOOPBACK 比较 | 必须相等，否则定位 framing/压缩问题 |
| TC-07 | 受控接收方解码 S3 | 与 S2 对应奖励区哈希相等 |
| TC-08 | Subject=0 自定义小数量道具 | 胜利奖励画面、背包增量、保存重进一致 |
| TC-09 | Quick Ball ×500 或更高数量 | 分道具、分版本检查上限及实际入包，**不由 CLI 999 上限推定成功** |
| TC-10 | 多人本地联机 | 每名参与者分别记录 S3/S4，不以单机样例替代 |

日志建议增加 `run_id`、`station_index`、游戏版本/TitleID、`start_0x0c`、`guest_start_0x0d`、`bootstrap_start`、`bootstrap_last_fragment`、`loaded` 时间戳（同一端使用单调时钟，跨机需校时或记录相对序列）；切勿输出玩家敏感信息/完整存档。

### 8.2 明确不在本次提交范围

- 未编译、未部署、未进行零售 Switch 或 NSP 的新增实测。
- 未添加 ARM64 Hook，未对 sys-botbase、游戏 main 或线上通信做修改。
- 未证明 Nintendo 官方在线团体战也接受房主随意指定奖励。
- 未将 `Subject=1/2/3/4` 开放为本分支 CLI 自定义奖励参数。
- 未证明物品数量 999 在所有道具类别上的保存行为。

## 9. 下一步工程建议（按优先级）

1. **P0：拿下 TC-01～TC-07**，在真实“加入 → Ready → Start → 0x2F → Loaded”周期中获得时间序列及 S3 接收方独立数据。
2. **P1：定位真实 Switch 房主 4.0.0 上奖励生成结束及 Bootstrap 复制入口**；使用 S1/S2 数据作回归基线，再考虑 Hook。
3. **P1：按物品类别、Subject 与持有上限验证 S4**，区别显示、入包、保存和二次加载四个阶段。
4. **P2：迁移至其他游戏版本时重新定位函数/结构，不使用 4.0.0 偏移硬编码。**

## 10. 代码与文档索引

- [上游 Tera Raids 技术文档](https://github.com/Decryptu/pokeldn/blob/main/docs/sv_raid.md)：`The lobby`、`The battle bootstrap` 与奖励发放验证。
- [上游 `raid.py`](https://github.com/Decryptu/pokeldn/blob/main/pokeldn/sv/raid.py)：消息构造、Bootstrap、`RaidHost` 时序实现。
- [本分支 `raid.py`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py)：`RaidGroup`、`raid_point`、`bootstrap`、`RaidHost._next`。
- [本分支 `raid_reward_trace.py`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid_reward_trace.py)：S1/S2/S2_LOOPBACK 原始奖励区哈希诊断。
- [本分支 `bin/sv_host.py`](https://github.com/969981/pokeldn/blob/research/bin/sv_host.py)：`--raid-reward ITEM:QUANTITY[:SUBJECT]` 输入、数量/Subject 校验。
