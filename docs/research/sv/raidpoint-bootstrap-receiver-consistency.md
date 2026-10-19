---
title: SV 本地太晶坑奖励三点数据一致性验证
parent: 朱／紫（SV）
nav_order: 7
---

# 《朱／紫》本地 LDN：源 RaidPoint → Bootstrap → 接收端筛选列表一致性验证方案

- **日期**：2026-10-19
- **项目 / 目标分支**：`969981/pokeldn@research`
- **状态**：**研究方案 / 待执行（P0）**；非实机验证报告
- **研究范围**：本地 LDN（PokéLDN 充当主持端）→ 零售或受控接收端；先只读记录和比较，**不实施官方互联网奖励注入**
- **目标游戏基线**：《宝可梦 紫》4.0.0；先前研究也指出《朱》4.0.0 可参考同偏移，但本报告以已核验的《紫》ELF 为准
- **原始 ELF**：`Violet4.0.0.elf`，74,362,480 字节，SHA-256 `d17403eaa9d844db82f647fd2f1518806b10c0518d53602fc0ac1766298fdba0`，Build ID `709bfd66115298640155fcc4979dba151c7cc79a`（**不提交原件**）
- **证据等级**：PokéLDN 主持端源码和 ELF 序列化机器指令已核实；接收端过滤语义来自上游 4.0.0 测试及 [SV-Script-RE](https://github.com/Martmists-GH/SV-Script-RE/tree/1f843bd2517c707fbb47491dad58856eaa2c2cc7) 约 3.0.1 反编译；**接收端完整实例链、实机观测、4.0.0 RomFS Lua 逐字校验尚缺**

## 0. 核心问题与成功定义

本阶段不问“奖励界面显示什么就是发放成功”，而是闭合三个实际数据观测点：

```text
S1 主持端源 RaidPoint（0x3E8）
    │ 0xE4..0x3B3 = 45 × 16 字节奖励行
    ▼
S2 本地团体战 Bootstrap（解压明文 0xAA0）
    │ 0x6B8 为 RaidPoint；0x79C..0xA6B 为相同奖励区
    │ kind 0x2F → 接收 / 解码
    ▼
S3 接收端 BattleRewardData：资格过滤后的列表
    │ subject 0/1/2/3/4/5 根据本机身份/条件筛选
    ▼
（非本阶段通关条件）获胜后 Bag.AddItem → SaveLoadManager → nn::fs::Commit
```

**数据一致性不是 S1/S2/S3 三个二进制 SHA 全都相等**：S1 和 S2 的 720 字节奖励区应按字节相等；S3 则应与“以 S2 的奖励行作为输入，结合接收端实际资格条件计算出的**期望过滤结果**”一致。因为 S3 已经过过滤，其记录数、序列化格式都可能变化。

三点闭环的合格证据为：同一个 `run_id`/`raid_session_id` 下，(1) S1 生成的行与 S2 解压得到的行逐字节一致；(2) S2 经接收端真正加载后能确认传给 `raidBattleRewardData` 的原始行集合；(3) S3 过滤后的 `ItemNo, ItemNum, rareType, subjectType` 与相同身份、护符和团战力条件的预期集合逐行一致。**没有（2）时，只算“主持端发送 + Lua 行为推断”，不能称为接收端全链路闭环。**

## 1. 已知数据布局（固定版本，禁止当成通用动态地址）

| 数据对象 | 大小 | 奖励区 | 45 行索引和边界 |
|---|---:|---|---|
| `RaidPoint` | `0x3E8` | `+0x0E4..+0x3B3` | 行 `i` 位于 `+0xE4+i×0x10`，`0≤i<45` |
| `Bootstrap` 解压明文 | `0xAA0` | `+0x79C..+0xA6B` | 由 `+0x6B8 + 0xE4` 得出 |
| 保留/其他字段 | — | `RaidPoint+0x3B4..+0x3B7` | 4 字节不是第 46 行；`+0x3B8` 开始是摘要 |

每行 `<IIII`（四个 little-endian u32）：`item_id`、`quantity`、`rare`、`subject`。实际自定义列表目前在 `research` 分支支持 `subject=0` 或 `subject=5`，且作为 **替换** 而不是追加种子的默认奖励。

**Native 发送端静态锚点**（《紫》4.0.0、`main+RVA`）：

| 地址/函数 | 已知作用 | 适合作什么 |
|---|---|---|
| `0xE327FC` | Bootstrap 序列化函数入口 | 确认当前序列化上下文 |
| `0xE32964` | 从 `x20+0x58` 读取 RaidPoint 前段 | 源对象定位依据 |
| `0xE32968` / `0xE3296C` | 从 `x20+0x78` 复制后 `0x3C8` 字节 | 数据复制证据 |
| `0xE32980` | `memcpy` | 拷贝前后边界 |
| **`0xE32984`** | `memcpy` 返回后的下一条指令 | **S2 明文快照的只读观测候选点** |
| `0xE329B0` | 转到下一层序列化 | 离开当前快照窗口 |

在该函数调用期间，源奖励第 0 行为 `x20+0x13C`，明文输出第 0 行为 `x23+0x79C`。**x20/x23 是动态寄存器值、非固定全局指针**；`0xE32984` 后要及时采集，函数结束后不可把寄存器当永久奖励位置。`0x79C` 也**不**是 LZ4 网络包/Pia 封装/存档中的固定偏移。

本轮撰写前重新只读验证个人 Library 原始 ELF：SHA 匹配，抽查 `0xE32828, 0xE32844, 0xE32968, 0xE3296C, 0xE32970, 0xE32980, 0xE329B0, 0x147F9A0` 共 **8/8 opcode PASS**；这证明静态字节，不是动态 Hook 成功。

## 2. S1：源 RaidPoint（主持端，P0）

**PokéLDN 控制路径**：

```text
bin/sv_host.py::prepare_raid
    ├─ raid_encounter.generate(seed, version, map, progress, content)
    ├─ --raid-reward ITEM:QUANTITY[:SUBJECT]（当前 0/5）
    └─ RaidGroup(..., rewards)
         ├─ __init__: raid_point(...) 做合法性预检查；未发送
         └─ RaidGroup.bootstrap(): 首次构造并缓存 self.plain
              └─ bootstrap() → raid_point() → pack_into("<IIII", ...)
```

源码位置：[`pokeldn/sv/raid.py`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py) `POINT_REWARDS` / `raid_point()` / `RaidGroup.bootstrap()`；[`bin/sv_host.py`](https://github.com/969981/pokeldn/blob/research/bin/sv_host.py) `raid_reward()`、`prepare_raid()`。

**采样要求**：将`最终一次` `bootstrap()` 内调用 `raid_point()` 所返回的完整 `0x3E8` 字节在拼接前直接作为 S1 记录；不能通过事后从 `self.plain` 切片来构造 S1，否则 `S1 == S2` 只是同一缓冲区与自身比较，失去独立性。`RaidGroup.__init__()` 中的 `raid_point()` 调用只用于预检查，必须区分它与最终发包版本。S2_host 则在 `RaidHost._next` 实际组包时从 `self.group.bootstrap()` 的 `0xAA0` 明文截取（如果 `self.plain` 已缓存，记录缓存生成时序和来源）。推荐再在压缩/分片链之后，用自己的**本地记录消息重组及解压回读**做 S2_wire_loopback，避免“同一数据对象重复切片”造成的假阳性。

最低记录字段：`seed`、`version`、`map`、`content`、`progress`、`source_kind`（seed/custom/event）、`configured_rows`、`parsed_rows_count`、完整 720 B 的 SHA-256、非空行 `(index,item,quantity,rare,subject)`、四字节保留区的十六进制、RaidPoint 身份与 `run_id`。自定义为空与 `None`（使用种子掉落）必须分开表达。

## 3. S2：Bootstrap（发包前以及接收后）

### S2a：主持端组包检查（可马上实施的测试）

[`pokeldn/sv/raid.py`](https://github.com/969981/pokeldn/blob/research/pokeldn/sv/raid.py) 中 `RaidHost._next` 调用 `bootstrap_message(self.group.bootstrap(), ...)`，`bootstrap_message` 对 `0xAA0` 明文进行 LZ4 处理，形成 `kind=0x2F` 的消息（另有可靠传输分片）。

逐字节断言（必须对**明文**执行）：

```python
import hashlib
import struct

def reward_snapshot(plain, offset):
    reward_bytes = plain[offset:offset + 45 * 16]
    assert len(reward_bytes) == 720
    rows = [struct.unpack_from("<IIII", reward_bytes, i * 16)
            for i in range(45)]
    return {"sha256": hashlib.sha256(reward_bytes).hexdigest(),
            "rows": rows, "raw": reward_bytes}

# s1: raid_point() 本次最终产物；s2: 独立实际组包/解压快照（非从同一对象回切）
assert len(s1) == 0x3E8
assert len(s2) == 0xAA0
assert s1 == s2[0x6B8:0xAA0]
a = reward_snapshot(s1, 0xE4)
b = reward_snapshot(s2, 0x79C)
assert a["raw"] == b["raw"], "S1/S2 reward bytes mismatch"
```

这里的 `s1/s2` 必须来自**同一个会话实际执行轨迹**。合成数据断言通过只可证明编码正确，不能代替本机运行时证据。

### S2b：客户端实收检查（完成三点闭环不可省略）

接收端须在本地授权、隔离测试中取得消息 `0x2F` **真正解压/反序列化后**的 RaidPoint（或等价的已解析结构），记录同一 45 行及 SHA-256，作为 `S2_receiver`。优先对照上游 [battle bootstrap](../../sv_raid.md#the-battle-bootstrap) 描述的接收器；具体接收端运行时 Native/Lua 对象转换仍需从可用 4.0.0 资源或调试日志下钻，不可杜撰 Hook RVA。

- `S1.raw == S2_host.raw` 仅说明源对象与实际组包快照一致；如补充 `S2_wire_loopback` 才能证明本地实际封装的消息解压回读不丢字段；`S2_wire_loopback.raw == S2_receiver.raw` 才能进一步证明接收端采用同一奖励字节。
- 如果只能看到发送端 `S2_host`，记录 `RECEIVER_UNOBSERVED`，**不得**将其标记为 `END_TO_END_PASS`。
- 记录 `kind`、解压长度、分片重组状态、异常/超时；不要把未解压的通信密文字节与明文偏移直接对比。
- 保持 `0x3B4..0x3B7` 和 Boss/摘要信息不变，可帮助区分写错偏移与接收端拒绝整个点。

## 4. S3：客户端奖励资格筛选后的列表（P0 难点）

既有参考：[`GameEventNetworkBattleRaid`](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C849FF496D0E93636.lua#L1512-L1549) 从 `self[17].raidBattleRewardData` 形成上下文 `[92]` 并调用 `F316609DEA110601D`；[`BattleRewardData`](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C07C34FC3B976E5A7.lua#L183-L321) 按资格条件生成 `self[3]` 过滤列表。这是约 3.0.1 的**公开反编译**，与上游 4.0.0 研究一致，但不等于已从当前 4.0.0 RomFS 捕获到同一函数实现。

**接收端最小日志必须有两份**：

1. 调用过滤**之前**的 `raidBattleRewardData` 行列表（证实 Native 解码对象确实进入 Lua）。
2. `F316609DEA110601D` **之后**的 `self[3]`（实际保留的 `ItemNo/ItemNum/rareType/subjectType`），同时记录本地资格输入：`is_host`、`once_eligible`、`raid_tera_type`、`raid_power_type`、`raid_power_level`、`has_glimmering_charm`（物品 ID 2481 数量是否大于 0）。

依据旧版 Lua 与 PokéLDN 上游 4.0.0 实验的预期筛选规则：

| `subject` | S3 应保留的条件 |
|---|---|
| 0 | 所有接收者 |
| 1 | 仅房主 |
| 2 | 仅加入者 |
| 3 | 一次性资格为真 |
| 4 | 团战力属性匹配且按顺序只保留前 N 行（N=0、1、2、3） |
| 5 | 本机 `Bag.GetNumItem(2481)>0` |

**不能单纯比较 S3 的哈希和 S2 的哈希**。生成 `expected_filtered_rows` 时先按 `subject` 与**实际资格输入**逐行筛选，再同 S3 以保留次序比较；不按 ItemID 排序，不把重复行默认合并。`BattleRewardData.F8975ECC0360F96CE` 存在按 `ItemNo+rareType` 合并同类项的帮助方法，尚未证明此路径必定调用；如果遇到顺序/数量不匹配，应记录是否触发合并，不能悄悄重排或相加后宣布通过。

如果无法观测原始 4.0.0 Lua 的 `[92]` 对象或它的功能等价接收端结构，记录 `FILTER_NOT_INSTRUMENTED`，保留上游实验和旧版脚本作为预期，**不能填“已实测一致”**。

## 5. 日志协议建议（开发阶段：不含用户标识/密钥）

采用逐行 JSONL，推荐只读采样，由 `run_id`、`station_index` 和 `event` 关联。以单调计时 `t_monotonic_ms` 保序（设备之间不可把独立单调时钟直接相减；跨设备需会话消息序号/同步基准）。

建议公共字段：`schema_version, run_id, game_build_id, pokeldn_commit, station_index, event, t_monotonic_ms, message_kind, source_kind, seed, row_count, rows_sha256, row_entries, data_len, stage_result, error`。仅 S3 增加 `eligibility`、`expected_rows` 与 `actual_rows`。所有哈希必须明确计算的是哪个**明文字节片段**；S3 采用稳定规范化 `[(ItemNo,ItemNum,rareType,subjectType), ...]`，不能混称“720 字节哈希”。

**示意 JSONL（完全合成，非实机日志）**：

```json
{"schema_version":1,"run_id":"local-001","event":"S1_SOURCE","data_len":1000,"row_count":2,"row_entries":[[0,15,5,0,0],[1,50,2,0,5]],"rows_sha256":"<720-byte-reward-region-SHA256>"}
{"schema_version":1,"run_id":"local-001","event":"S2_HOST_BOOTSTRAP","message_kind":"0x2f","data_len":2720,"row_count":2,"rows_sha256":"<same-720-byte-reward-region-SHA256>","stage_result":"MATCH_S1"}
{"schema_version":1,"run_id":"local-001","station_index":1,"event":"S2_RECEIVER_PRE_FILTER","row_entries":[[0,15,5,0,0],[1,50,2,0,5]],"stage_result":"MATCH_S2_HOST"}
{"schema_version":1,"run_id":"local-001","station_index":1,"event":"S3_FILTERED","eligibility":{"is_host":false,"has_glimmering_charm":false,"raid_power_level":0,"once_eligible":false},"actual_rows":[[15,5,0,0]],"expected_rows":[[15,5,0,0]],"stage_result":"MATCH_EXPECTED"}
```

`rows_sha256` 应由工具计算真实完整十六进制 SHA，不得将示意占位符用作真实日志。默认仅保存必要字段摘要，原始 720 B dump 需要显式调试开关、脱敏及有限保留期；不要记录 Nintendo Account、玩家识别码、连接密钥或未脱敏的完整网络帧。

## 6. 最小实验矩阵（按成本升序）

| 用例 | 源奖励配置 | 客户端资格 | 预期 S3 | 目的 |
|---|---|---|---|---|
| T00 | `subject=0`，普通道具 ×2 | 加入者，无护符 | 一行保留 | 基线、先验证三点采样 |
| T01 | `subject=0` 与 `subject=5` 各一行 | 加入者，无护符 | 仅 0 | 护符过滤阴性 |
| T02 | 同 T01 | 加入者，有护符 | 0 与 5 均保留 | 护符过滤阳性 |
| T03 | 由原版种子表生成 `subject=1/2` | 房主/加入者分别记录 | 各自对应行 | 分离房主/参与者 |
| T04 | 由原版种子生成 `subject=4` 多行 | 对应属性 Raid Power Lv.0/1/2/3 | 前 0/1/2/3 行 | 验证受料理和行序影响 |
| T05 | 原版 `subject=3` | once true/false 两种状态 | 对应资格决定 | 验证一次性条件 |
| T06 | 45 行、重复 item、末端第 44 行 | 常规加入者 | 不越界；如有合并需单独解释 | 边界与可选合并路径 |
| T07 | 同一会话两个客户端 | 不同护符/料理状态 | S2 相同、S3 可不同 | 证明独立接收端筛选 |
| T08 | 开房未开始/有人退出或重连 | 各种状态 | 不得把旧 `self.plain` 当新会话 | 缓存生命周期/失效规则 |

**推荐先做 T00 → T01 → T02 → T06**。自定义 GUI/CLI 当前仅支持 `subject 0/5`；T03/T04/T05 优先采用原生种子生成行，勿为测试而把现有功能错误描述成已经支持 `1/2/3/4` 自选编辑。每例至少采一次发包前后；同种子不同会话使用不同 `run_id`。先以很小的普通道具数量验证，暂不拿“×999 画面”做这条链的通关证据。

## 7. 自动化验收条件与失败分类

**严格验收**：

- `STRUCTURE_PASS`：`len(RaidPoint)=0x3E8`、`len(Bootstrap)=0xAA0`、全部 45 行在合法范围、保留 4 B 未被改写、Boss/摘要字段未意外变化。
- `HOST_COPY_PASS`：同一会话 `S1[0xE4:0x3B4] == S2_host[0x79C:0xA6C]`（精确 720 B）。
- `RECEIVE_PASS`：`S2_receiver` 的完整奖励行与 `S2_host` 行逐字节或逐字段一致；需明确 Native/Lua 转换会不会保留 padding。
- `FILTER_PASS`：`S3_actual == expected_filter(S2_receiver, observed_eligibility)`，保留原顺序、`rare/subject`、重复条目。
- **`END_TO_END_PASS`**：上述四项均通过，且具备接收端真实观测，不接受仅用合成向量或旧版本脚本模拟代替。

失败分类：`SOURCE_WRONG`（种子/自定义输入错误）、`COPY_MISMATCH`（S1→S2）、`TRANSPORT_OR_PARSE_MISMATCH`（S2 host→receiver）、`FILTER_MISMATCH`（eligibility/合并/版本语义）、`MISSING_OBSERVATION`（无法判定）、`SESSION_STALE`（缓存被上一局污染）、`BUFFER_LIFETIME_ERROR`（断点后指针失效）。记录首个不同的行号和字段、会话与版本；不要只输出“写入失败”。

已有仓库测试基础：[`tests/test_sv_raid.py`](https://github.com/969981/pokeldn/blob/research/tests/test_sv_raid.py) `test_custom_reward_subject_is_encoded_without_touching_other_row_fields`、`test_charm_and_all_player_rewards_reach_the_host_bootstrap`；[`tests/test_gui_rewards.py`](https://github.com/969981/pokeldn/blob/research/tests/test_gui_rewards.py) `test_reward_picker_subject_selection_persists_and_reaches_raidpoint`。它们验证主持端编码，不提供 `S2_receiver / S3` 的零售游戏日志。

## 8. 根据三点验证结果决定本地 Hook / 写入阶段

| 实测结果 | 根因优先判断 | 后续实现的优先方向 |
|---|---|---|
| S1 已错误 | 奖励选项/生成/配置映射有问题 | **生成阶段**：修复 `raid_point()` 或输入适配，不需要 Native Hook |
| S1 正确、S2_host 错 | 源对象复制/组包或拿错快照 | **数据复制/组包阶段**：查 `0xE327FC` 及缓存生命周期，先解决结构一致性 |
| S2_host 正确、S2_receiver 错 | 分片、传输、接收解析或版本差异 | **发送/接收边界**：先恢复正确数据，不贸然 Hook 战后保存 |
| S2_receiver 正确、S3 错 | `subject` / 护符 / 团战力 / once 或合并差异 | **接收方筛选阶段**：核对实际 Lua 资格输入与调用次序 |
| S1/S2/S3 全部正确，但入包数量不符 | `SlotMaxNum` / Bag 访问器 / 保存 | 已超出三点目标；另走 `Bag.AddItem → SaveProcess` 专项链 |
| 仅主机端可观测，接收端空白 | 缺证据 | 先补只读 S2_receiver/S3 日志，**不宣称已确定 Hook 最佳点** |

**阶段性推荐**：对 PokéLDN 本地主持端，最小、稳定且已具源码基础的做法仍是 **生成阶段 `raid_point()` 配置奖励**；对真实游戏本地房主需凭动态数据流判断，不能仅因 `main+0xE32984` 可读便断言它一定是最优写入点。先只读采集，只有完成 S1→S2_receiver→S3 的一致性证明后再选择写入候选窗口。

## 9. P0 执行顺序与交付清单

1. **P0-A（可自动化）**：为 `research` 主持端添加结构化只读 S1/S2_host 日志；做 45 行边界/保留字节/重复项/种子与自选两路径单测，避免修改网络报文及游戏二进制。
2. **P0-B（关键依赖）**：在合法的本地受控测试环境取得 `0x2F` 接收端 **解压后**的 RaidPoint 及 `raidBattleRewardData` 输入；补 `S2_receiver` 与 `S3` 采样并建立运行时会话关联。
3. **P0-C（验证）**：执行 T00、T01、T02、T06；输出每场 `S1/S2_host/S2_receiver/S3` 的字节/字段差分、SHA、角色和护符条件，保留异常案例最小复现。
4. **P1（决策）**：按第 8 节的结果输出 Hook 决策表；只有故障归因清晰才设计最小补丁/可撤销开关。官方互联网模式必须作为另一个独立研究课题，不可拿本地结论替代。

**交付判定**：`docs/research/sv/...` 实验报告附版本/证据、JSONL 脱敏样本、测试日志及是否闭环的判定；没有真实 S3 日志时状态维持 `PENDING_RECEIVER`。不得在文档中把文献证据、合成测试和实机测试混为一谈。

## 10. 参考与边界

- [本仓库自定义奖励动态指针与离线明文修改](sv400-custom-reward-pointer-patch.md)
- [本仓库《紫》4.0.0 ELF 序列化原生核验](violet400-elf-raid-bootstrap-audit.md)
- [本仓库奖励 → Bag → 保存链](raid-reward-to-bag-save-chain.md)
- [本仓库保存协程与 SlotMaxNum](sv400-autosave-and-item-slotmax.md)
- [PokéLDN 上游本地太晶团体战与 0x2F](../../sv_raid.md)
- [固定提交的公开 BattleRewardData Lua](https://github.com/Martmists-GH/SV-Script-RE/blob/1f843bd2517c707fbb47491dad58856eaa2c2cc7/decompiled/C07C34FC3B976E5A7.lua)

本方案不覆盖 Nintendo 官方互联网联机的服务端验证、未授权的第三方账号或存档操作。所有 ELF 指令地址只与上面绑定的《紫》4.0.0 Build ID 对应；更换版本需重新定位函数，不能套用地址差值。
