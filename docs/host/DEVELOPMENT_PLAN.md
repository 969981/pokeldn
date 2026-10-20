# 实机 Switch 房主联机 RaidPoint 奖励追加开发规划（N0–N7）

- 建立日期：2026-10-20
- 工作分支：`969981/pokeldn:host`，起点 `main@93bb74833d411537703f8a203dc3eb46c518c213`
- 实机基线：先锁定《宝可梦 紫》4.0.0 和其 Build ID；《朱》、其他版本、BCAT 活动与官方互联网另行验收。
- 优先目标：真正的房主 Switch，以只读观测证明 `生产者 RaidPoint → 复制/序列化 → 发出的 Bootstrap`，再开发防越界、幂等追加 `subject=5`。
- 文档性质：研发任务／验收规范，**不是已经实现、测试通过的 Hook**。

## 1. 已证实、推导和未证实的分界

| 断言 | 证据 | 状态 |
|---|---|---|
| 团体战 `0x3380/0x2F` 消息，内部 `0x012F`，LZ4 解压后 `0xAA0` 字节；其中 `0x6B8..0xA9F` 为 `0x3E8` RaidPoint | `main/docs/sv_raid.md`，`main/pokeldn/sv/raid.py` | 公开逆向与实现/测试支持 |
| 当前 `main` 定义 `RaidPoint+0xE4` 为 45 条连续 16 字节记录，结构按 `<IIII` 为 `item, quantity, rare, subject` | `main/pokeldn/sv/raid.py`、`main/tests/test_sv_raid.py` 中原版 3/6 星对照 | 当前模型已由测试支持；须在目标实机再次验证 |
| `subject=5` 由接收端原版 Lua 奖励过滤处理，检查背包道具 `2481`（晶耀护符） | `main/docs/sv_raid.md` 的 `F316609DEA110601D`；`research` 4.0.0 离线模型 | 代码/模拟证据，待硬件闭环 |
| PokéLDN 模拟房主，向正版参与者发送自定义奖励，例如先机球 ×500 并在正版设备发放 | `research/docs/research/sv/references/SV_RAID_BOOTSTRAP_ENCODER.md` | 模拟房主 → 正版参与者的替换方案已验证 |
| 原生 `0x012F` 发送器复制已生成的 RaidPoint，而不是在复制时生成奖励 | `main/docs/sv_raid.md`、`research` Ghidra 记录 | 强定位线索，不代表已找到可写的运行时点 |
| 实机正版 Switch 房主原奖励不减，追加一行、二十行且参与者持晶耀护符才拿到 | **尚无此路径硬件日志** | 未验证 |
| 官方互联网对局与本地 LDN 使用完全相同的房主可信奖励数据链 | **无闭环证据** | 未验证；不能从本地实验外推 |

**历史材料冲突必须显式检查：**归档旧 Encoder 的早期结构说明写成 `condition_or_source, item_id, quantity, reserved`，而当前 `main` 的 `raid_point()` 与原版对照测试使用 `item, quantity, rare, subject`；**禁止把旧文档中的四字值直接套入当前运行时结构。** N0 要用指定版本原始解压字节、`main` fixture、逐行索引与接收端结果校验字段的实际偏移与语义。不同代实验记录不能混作同一版证据。

## 2. 正确的切入时间：并非进入战斗后才发奖励

`房主点击开始 → 参与者回复就绪/开始确认 0x0D → 原生奖励生成 → 房主 RaidPoint 形成 → 只读快照 → （容量、版本、身份校验）→ 尾部追加 → RaidPoint 被序列化 → 0x2F/0x012F Bootstrap 发出 → 客户端按原版 Lua 资格过滤 → 战斗胜利 → 发奖 → 保存重启验证`。

- 对房主而言，修改必须**发生在目标 Bootstrap 的最终序列化/发出前**；参与者「已经开打」通常太晚，不应在战斗中反复补写。
- 房主生成的是候选奖励集合；晶耀护符资格由**参与者自身**的接收端原版逻辑筛选。不要要求房主替参与者读取背包，也不要修改接收端 Lua 过滤。
- `0x2F` 是网络消息 kind，`0x012F` 是内部应用消息类型，避免日志里混淆。外层可靠传输可能分片、按标志套 zlib；内部 RaidPoint 数据先组成固定长明文，再由 LZ4 压缩。**先观测内存原始对象，不要先改压缩后的密文/字节流。**
- 原生模块、动态 Hook、进程内 Patch 或独立调试入口需要目标 Switch 上有相应可用权限/环境；普通 PC 软件仅通过网络无法保证改到真实房主进程。规划不预设必须替换 `sys-botbase`。

## 3. 关键数据约束与状态保护

已建立的结构（基于当前 `main`）：

| 偏移/长度 | 意义 | 检验 |
|---|---|---|
| Bootstrap `0x000..0x55F` | 四位参与者，各 `0x158` | 原样保留 |
| Bootstrap `0x560..0x6B7` | Boss `0x158` | 原样保留 |
| Bootstrap `0x6B8..0xA9F` | `RaidPoint` 共 `0x3E8` | 除奖励尾部外不得改变 |
| RaidPoint `+0xE4` | 45 × 16 字节，共 720 字节 | 逐行解出 4×u32 LE |
| RaidPoint `+0x3B4` 及之后 | 摘要/种子等非奖励字段 | 严禁覆盖 |
| 奖励行字段 | `item_id, quantity, rare_flag, subject` | 以 4.0.0 原始样本交叉校验 |
| 追加行 | `item_id, quantity, rare_flag=0, subject=5` | 首阶段限定低风险合法物品及小数量 |

**硬限制：**设房主原生有效奖励行数为 `N`，追加配置行数 `K`，只允许 `N + K <= 45`；配置整批 20 行要求 `N <= 25`。如果空间不足，默认**整批跳过**，不得覆盖、截断或挤掉任何一行原奖励；不能把「20 行上限」误认为所有 Raid 都至少剩 20 个槽。

**强制 fail-closed：**版本/Build ID 不符、RaidPoint 名称与大小异常、奖励区域不可读、行布局不符、尾部不是连续空槽、原生行计数异常、并发中发生变更、只存在部分可用槽位、重复调用无法确认幂等性、物品/数量超出配置白名单时，保持原内存字节不变，只记录诊断原因，原版照常运行。

**幂等：**不能仅按物品 ID 去重（与原生物品可能重合）。用战斗会话/房主生成批次身份、追加前原始奖励哈希、配置哈希记录状态；重传或重复进入发送路径不得再次追加。逐字节断言原生奖励完整且顺序不变，并保留其既有 `subject=4`（料理）及 `subject=5`（原生护符）行。不要改变 `rare_flag` 或客户端当前结算过滤器。

**数量和库存：**字段能表示数值、离线编码器支持 `1..999`，并不证明 999 个能显示、背包能容纳、加总或最终保存。必须检查实际 `SlotMaxNum` / 品类背包限制、相同物品行合并、显示截断和实际库存净增；首次实机只测 `1 × 1`，经验证才尝试 `127 / 128 / 500 / 999` 和 `20 × 999`。不可把「出现领奖文字」等同「持久到账」。

## 4. Hook 点如何选择：先三点一致性再改写

候选 A（首选）：**生产完毕的原生 RaidPoint 对象，且尚未被复制/序列化**。观察 `FieldRaidJewelry.LotteryRewardItem`（研究中的 Lua 生产者）、`BattleRewardData[3]` 和 `RaidPoint` 奖励区；如果确认存在唯一稳定生命周期，做一次受控尾部追加。

候选 B（备选）：**原生 RaidPoint 被复制到 Bootstrap 对象时的前后**。`main/docs/sv_raid.md` 给出 `0x1bae670 → 0x1bae760 → 0x1baff98 / 0x1bb0018`（反编译中也以 `0x7101…` 表示映射地址）。这些是待目标 Build ID 核实的**代码相对位置/历史 Ghidra 符号线索**，不可直接当成 ASLR 不变的实机绝对地址。追踪源指针、目的指针与拷贝时序。

候选 C（最后手段）：**Bootstrap 仍是未压缩 `0xAA0` 明文的发送前副本**。如果 A/B 无可持久的对象，才考虑严格范围内改写奖励区；不得盲改压缩包、可靠流片段或接收端保存流程。

任何候选必须收集同一战斗的四份证据：`P0` 原生生成完成的奖励数组 → `P1` RaidPoint 对象 → `P2` 序列化的 `0xAA0` 明文 → `P3` 最终发出/参与者加载后解出的 RaidPoint。保存原文哈希、时间顺序、原生行数、追加行数、包 ID、房主/参与者角色、版本/Build ID；在只读模式禁止修改游戏内存。用一场独特标识的战斗关联四份数据，避免跨场混淆。

## 5. 分阶段任务与交付物（按门禁顺序）

| 阶段 | 工作和提交内容 | 完成门禁 |
|---|---|---|
| **N0 证据对齐 / 基线** | 清单固定 `main` 与 `research` 参考版本；记录游戏 Title ID/Build ID、目标 ELF 指纹；核对 45×16、Lua 行格式、原版奖励示例；复用而非整分支合并离线追加模型及测试 | 原始/解码/重编码往返不改变字节语义；离线原版回归通过；差异/矛盾都有解释 |
| **N1 只读房主观测** | 在真实房主的开始流程捕获生成后 RaidPoint、`0x2F` 发送路径、接收端加载快照；记录四点数据的生命周期和稳定性 | **真实房主现场命中**，同场 P0–P3 奖励原版行一一对应，零改写、可反复复现 |
| **N2 Hook 可达性和稳定性** | 为确认的唯一入口建立 Build ID 匹配、只读/关闭开关、重复进入保护、异常回退；优先前序对象、再复制口 | 无奖励修改也可反复正常开坑/结束/回到大厅；不劫持无关业务 |
| **N3 追加器纯函数** | 将 `research/scripts/research/sv_lua_reward_append_prototype.py` 的语义性回归择需迁入 `host`；实现显式 45 行、字节保留、尾槽检查、整批拒绝、幂等；测试生成现有 `RaidPoint` 而不是专用 donor | 原奖励前缀/其他区完全相同；正/反资格过滤；满 45/空洞/重复调用均安全失败 |
| **N4 单行联机闭环** | 先本地受控测试，房主实机追加一条 `subject=5` 且数量 `1`，参与者两套账户分别持/不持护符；不修改接收端 | 有护符者原奖励不减且额外道具到账，无护符者拿不到额外行；退出游戏重进仍保留 |
| **N5 多行容量与数量验证** | `1 / 5 / 20` 行；数量 `1 / 127 / 128 / 500 / 999`；原生 `N=24/25/26/44/45` 等边界的模拟/可复现实机样本；多人、重发、二次开坑、满背包 | `N+K<=45` 才整批追加；所有原版项保留，净增与库存上限匹配，不溢出、不重复、不崩溃 |
| **N6 官方互联网兼容性** | **独立探索门禁**：先只读判别网络/房主信任与奖励加载路径是否与本地一致；涉及联网测试需合法授权、备份与风险评估 | 只有真实官方公网环境 P0–P3 链路及保存均实测成功，才宣称兼容；未验证则只支持本地 |
| **N7 配置和发布** | 给 RaidCrawler 或单独工具设计 `host reward append` 配置；只允许诊断、off、受控启用；对照 Build ID 选择模块，提供回滚与原生自检。Rust `format.rs` 集成必须先确认其实际仓库版本 | 构建可复现，测试/运行日志可审计，关闭功能与原版行为等价，版本不匹配自动停用 |

**最先开发的不是 N4 的 20×999 写入，而是 N0/N1。** N1 未通过以前，所有 Hook 入口都只是候选，不能把 PC 的模拟发包成功当成真实房主 Hook 成功。

## 6. 最小采样和验收矩阵

| 测试 | 房主/参与者 | 预期 |
|---|---|---|
| Baseline | 房主实机＋参与者实机，功能关闭 | 记录原版 `0x2F`、原生奖励、背包变化、保存 |
| Observe-only | 同样设备，启用诊断 | 内存/传输前后同源数据相等；绝不修改 |
| `subject=5, 1×1` | 参与者有晶耀护符 | 额外显示、净增 1，重启保留；原奖励不减 |
| `subject=5, 1×1` | 参与者没有晶耀护符 | 额外奖励不可见、不得到账，原奖励照常 |
| 普通奖励回归 | 同一战斗配置，`subject=0/1/2/4` | 房主/参与者角色条件、料理加成、原生护符加成全部保留 |
| 容量恰好和超出 | 例如 N=25/K=20；N=26/K=20 | 前者允许，后者**整批不追加**，无覆盖 |
| 幂等和重传 | 同一局序列化/重传命中两次 | 仅追加一次，永不重复结算 |
| 边界数量 | `1, 127, 128, 500, 999`；背包将满 | 不依赖 UI 文字判断；以结算前后背包净增和重载保留为准 |
| 版本/上下文差异 | 4.0.0 紫基线后，朱/活动/其他版本 | 必须重做指纹与结构判别，不默认适用 |
| 官方互联网 | 与本地 LDN 分开记录 | 未经现场验证一律标记 UNKNOWN |

每次运行输出结构化日志：`session_id, game/version/build_id, raid_context, hook_stage, point_fingerprint, original_rows, appended_rows, skipped_reason, p0/p1/p2/p3_hash, receiver_has_charm, pre_bag, post_bag, reload_bag, test_result`。日志要避免泄漏与任务无关的个人、联机身份和密钥数据。

## 7. 故障处置和版本风险

- 按「不可破坏原版流程」设计：只读探针异常、类型不确定、写入校验失败、写后即被引擎重建、满 45、保存未完成都应恢复原字节或在写入前放弃。**只有在安全地确定前置条件时才进行一次尾部写入**。
- 不应直接从 `research` 合并全部资料进 `host`，尤其不要把 3.0.1 的公开 Lua 反编译当成 4.0.0 精确字节码 PC。`research` 对 4.0.0 的 `main.blua` SHA/Build ID 门禁仍注明原文件输入缺失，需实物验证。
- 目标版本样本、备份与快照齐备之前，不对正式存档做高数量实验。在线实验可能受服务条款、完整性校验与账号安全影响，不能承诺官方服务器接受。
- 如果拿不到原生 Hook 所需的权限，仍可完成离线模型、只读串联验证（在可访问的合法测试环境）与架构文档；不声称仅凭 PC 程序即可实现实时房主内存改写。

## 8. 当前状态与下一交付优先级

截至本规划提交：**N0 有现成 `main` 回归与 `research` 离线原型参考；N1（真实房主 P0–P3 的只读捕获）未提供完成证据；N2–N7 未启动**。曾经的模拟房主发奖励测试不改变这个状态。

建议下一提交：`test(host): port guarded append model and byte-layout regression`；再下一提交：`feat(host): read-only on-device RaidPoint/0x2F trace`。没有 P0–P3 现场一致性，就不开展可写 Hook。

## 9. 依据链接（固定责任边界）

- [main: docs/sv_raid.md](https://github.com/969981/pokeldn/blob/main/docs/sv_raid.md) — 0x2F/0x012F、原生 45 行、Lua subject 过滤、开始时序
- [main: pokeldn/sv/raid.py](https://github.com/969981/pokeldn/blob/main/pokeldn/sv/raid.py) — 0xAA0、RaidPoint、生成/序列化与结构定义
- [main: tests/test_sv_raid.py](https://github.com/969981/pokeldn/blob/main/tests/test_sv_raid.py) — 对照原版 RaidPoint 的 byte-exact / row 顺序测试
- [research: historical bootstrap encoder](https://github.com/969981/pokeldn/blob/research/docs/research/sv/references/SV_RAID_BOOTSTRAP_ENCODER.md) — 模拟房主 → 正版参加者的改奖励实机证据；**非**原生房主追加成功证据
- [research: reverse-engineered RaidPoint](https://github.com/969981/pokeldn/blob/research/docs/research/sv/references/SV_RAIDPOINT_REVERSE_ENGINEERING.md) — Ghidra 生成/复制链
- [research: 4.0.0 readiness](https://github.com/969981/pokeldn/blob/research/docs/research/sv/references/Violet400_P1_solo_readiness.json) — 离线追加测试、未知项及版本门禁
- [research: append prototype](https://github.com/969981/pokeldn/blob/research/scripts/research/sv_lua_reward_append_prototype.py) / [tests](https://github.com/969981/pokeldn/blob/research/tests/test_sv_lua_reward_append_prototype.py) — 可挑选移植的非实机模型
- [Martmists-GH/SV-Script-RE](https://github.com/Martmists-GH/SV-Script-RE) — 用于语义交叉核对；**不能取代**目标 4.0.0 二进制校验


## 10. N0/N1 已落地的独立基础（2026-10-20 更新）

在 `host` 新增 `pokeldn/sv/host_trace.py`、`tests/test_sv_host_trace.py` 和 `docs/host/RESEARCH_MIGRATION.md`，对应能力是：

- N0：依据当前 `main` 的 `0xE4 / 45 × 16` 布局，离线解析三类二进制输入；对错误大小、异常 subject、空槽后继续出现非空行给出错误/警告；
- N0：建立 8 项隔离单元测试（含实际仓库 LZ4 算法的本地等价实现），已通过；**并非整仓测试/实机通过**；
- N1 准备：以 `P0 rows JSON`、`P1 原生 RaidPoint`、`P2 0xAA0 明文`、`P3 0x012F 完整应用消息` 为固定输入合同，对同场数据进行行内容及原始 RaidPoint 哈希比对；
- N1 未完成：尚未编写或部署房主 Switch 实机采集 Adapter，也无来自该实机的 `P0–P3` 同场原始输入。
- 注：`SNAPSHOTS_MATCH_NOT_HARDWARE_PROVEN` 只能表明所输入的离线快照互相一致，不证明原始来源真实性，也不代表官方网络、发奖、背包及保存验证通过。

具体用法和证据迁移决策见 [RESEARCH_MIGRATION.md](RESEARCH_MIGRATION.md)。下一步为**只读原生 Adapter**，先由目标 Build ID/文件 SHA 校验，再在完成生成、RaidPoint 成形、复制、发送前分别快照。不能在 N1 通过前打开写入 Hook。
