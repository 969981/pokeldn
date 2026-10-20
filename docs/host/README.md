# host — 实机房主联机奖励追加研究

> 状态：N0 离线只读工具与测试已提交；N1 实机捕获未启动，Hook 尚未开发。2026-10-20 从 `main` 派生；不得把离线模型通过等同于实机成功。

## 任务

让运行原版《朱／紫》游戏内容的真实 Switch 房主在团体战启动时保留原版所有奖励，**仅在容量允许时**向 `RaidPoint` 奖励尾部追加 `subject=5` 行，使持有晶耀护符（Glimmering Charm）的参与者在原版结算阶段获得额外道具。

实际时机是**参与者就绪、战斗 Bootstrap 发出之前**；不是战斗已开始后才修改既有 Bootstrap，也不是从 PC 端直接修改官方服务器奖励。

## 文档入口

- [开发规划、证据等级、阶段任务与验收标准](DEVELOPMENT_PLAN.md)
- [main 中现有团体战技术文档](https://github.com/969981/pokeldn/blob/main/docs/sv_raid.md)
- [main 中 RaidPoint 生成与 Bootstrap 实现](https://github.com/969981/pokeldn/blob/main/pokeldn/sv/raid.py)
- [main 中原版奖励字节回归测试](https://github.com/969981/pokeldn/blob/main/tests/test_sv_raid.py)
- [research 中保存的历史 Bootstrap Encoder 研究](https://github.com/969981/pokeldn/blob/research/docs/research/sv/references/SV_RAID_BOOTSTRAP_ENCODER.md)
- [research 中 4.0.0 离线追加模型状态](https://github.com/969981/pokeldn/blob/research/docs/research/sv/references/Violet400_P1_solo_readiness.json)

## 分支边界

1. `host` 基于本仓库 `main`，不从 `research` 整分支合并；按需移植离线测试并保留来源。
2. `main`／`ew`／`research` 不由本工作修改；`host` 不自动反向并入。
3. 当前仓库 `main` 不包含 RaidCrawler 的 `format.rs`：需确认另一代码库与版本后，才能设计 Rust 层的具体改动。
4. 任何运行时改写必须版本／Build ID 严格匹配，有只读基线、可回滚和关闭开关；在线公网验证为单独决策门禁。

## 不宣称已经完成的能力

- 尚未在真实房主 Switch 观察到已发送的原始奖励行；
- 尚未在实机实现不减少原奖励的 `subject=5` 追加；
- 尚未验证 `20 × 999` 奖励实际全部显示、到账及重启保留；
- 尚未证实官方互联网房间经过同一条房主提供的奖励数据链。

详见 [开发规划](DEVELOPMENT_PLAN.md) 的 N0–N7 门禁。

## N0/N1 独立实现（2026-10-20）

- [上游研究迁移与真实房主只读观测合同](RESEARCH_MIGRATION.md)
- [版本化会话清单模板](session_manifest.example.json)（仅模板；必须替换真实实机数据）
- 自实现模块：`pokeldn/sv/host_trace.py`（见[源码](../../pokeldn/sv/host_trace.py)）。
- 回归：`tests/test_sv_host_trace.py`（见[测试](../../tests/test_sv_host_trace.py)），8 项离线测试通过。
- 只读 `point`／`bootstrap`／`application` 解码和 `P0→P3` 行/字节哈希对照；不执行 Switch 内存读写、Hook、网络操作或奖励修改。
