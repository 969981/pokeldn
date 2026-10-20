# N0/N1 源资料迁移决策与只读观测设计

**状态：已实现离线只读解码/对照工具与测试；未安装 Switch 原生探针，未观察真实房主，未实现奖励写入。**

## 来源与证据等级

上游固定版本：[Decryptu/pokeldn@8b2c19c480400a6805eeeff266e13ded20c97475 — docs/research/sv](https://github.com/Decryptu/pokeldn/tree/8b2c19c480400a6805eeeff266e13ded20c97475/docs/research/sv)。

| 上游资料 | 有用证据 | host 迁移决策 |
|---|---|---|
| `SV_RAID_BOOTSTRAP_ENCODER.md` | 模拟房主向正版参与者发送 `0x012F`；更换奖励曾实际发放先机球 ×500；LZ4 与外层 zlib 的边界 | 保留证据，不迁移 donor 清空/替换代码 |
| `SV_RAIDPOINT_REVERSE_ENGINEERING.md` | `0xAA0` 布局、原生序列化复制、生成端候选 | 用作定位的历史依据，精确位置须目标版本重验 |
| `SV_RAID_REWARD_PROFILES.md` | 完整报文、校验器、固定 donor 成功经验 | 用于输入校验思路；拒绝 donor 模板依赖 |
| `SV_PIA_IDENTITY_REVERSE_ENGINEERING.md` | 可靠消息、ACK、会话/站点身份背景 | 只引用观测层标记，不重用模拟房主的会话伪造逻辑 |
| `ESP32_RETAIL_RAID_GUEST_LEGACY.md` | 原版参与者进入团体战的实证 | 背景参考，不能证明真实 Switch 房主追加 |
| `TODO.md` | 尚未完成的零售验证和未知字段 | 作为未知项清单；不等于已实现能力 |
| `fixtures/sv_raid_reward_donor.bin` | 单一 4.0.0 Avalugg donor 消息 1707B | 只作离线回归对照，不作为通用实时写入模板 |

你自己的 `research` 分支已经按固定 Blob SHA 归档过这些文档，本分支只做**独立实现和来源链接**，不再次复制同名文档，不合并 `research`。

## 必须纠正的历史结构差异

早期文档在 `RaidPoint+0xE0` 一带使用 `marker,item,quantity,reserved` 的推测布局；但当前 `main/pokeldn/sv/raid.py` 与最新 `main/docs/sv_raid.md` 的原版回归采用：

- `RaidPoint` 长 `0x3E8`，在 Bootstrap 偏移 `0x6B8`；
- 奖励区是 `+0xE4..+0x3B3`，共 `45 × 16B`；
- 每条为 `<4I` 小端：`item_id, quantity, rare_flag, subject`；
- `0x3B4` 后的元数据不属于奖励区；
- 原版 `subject=4`、`subject=5` 行都应如实保留。

新实现 `pokeldn/sv/host_trace.py` **只读**以上结构；若遇到空洞、无效物品/数量或异常 subject，将发出警告，不默默修复或清除。

## 真正的房主观察链

`P0` 原版 Lua `FieldRaidJewelry.LotteryRewardItem` 输出的 `BattleRewardData[3]` 中的奖励行，在只读捕获端导出为 `rows JSON`。

`P1` 原生 RaidPoint 形成后、复制前，对 `0x3E8` 字节做快照。

`P2` 完整 `0xAA0` Bootstrap **明文**、LZ4 压缩之前快照。

`P3` 真实房主发出前已组装完成的 `0x3380/0x2F`、内部类型 `0x012F` 应用消息。若数据来自可靠流分片，先按已有 `pokeldn.sv.streams` 实现执行分片重组和外层 zlib 解压，输入必须是**完整 `0x012F` 应用消息**；本工具不会抓包或自动重组网络分片。

比对逻辑：`P0/P1` 的有序奖励行 SHA-256 与逐行值；`P1/P2/P3` 要求**整个 RaidPoint 字节的 SHA-256 相等**，以避免只看奖励而漏掉其他字段变化。各阶段必须是**同一局房主会话**，且记录目标 Title ID / Build ID / 游戏版本、来源文件 SHA-256。捕获来源真实性、同局归属需现场日志佐证；manifest 中填相同会话 ID 并不构成真实性证明。

## 只读工具命令

`python -m pokeldn.sv.host_trace inspect --kind point --input ./p1.bin`

`python -m pokeldn.sv.host_trace inspect --kind bootstrap --input ./p2.bin`

`python -m pokeldn.sv.host_trace inspect --kind application --input ./p3.bin`

`python -m pokeldn.sv.host_trace correlate --manifest ./session.json`

`session.json` 示例（`sha256` 建议放真实 SHA-256；未提供则不做来源完整性验证）：

```json
{
  "format": "pokeldn.host.reward-trace.v1",
  "session_id": "local-controlled-raid-001",
  "title_id": "01008F6008C5E000",
  "build_id": "REPLACE_WITH_VERIFIED_BUILD_ID",
  "game_version": "4.0.0",
  "checkpoints": [
    {"stage": "P0", "kind": "rows", "file": "p0.json"},
    {"stage": "P1", "kind": "point", "file": "p1.bin"},
    {"stage": "P2", "kind": "bootstrap", "file": "p2.bin"},
    {"stage": "P3", "kind": "application", "file": "p3.bin"}
  ]
}
```

`p0.json` 数据格式是有序数组，例如 `[[1127, 1, 0, 0], [1867, 2, 0, 5]]`。**P0 捕获须来自生成完成的原生列表**，不是 PC 使用伪造数组。

输出状态：`PENDING_CAPTURE` / `MISMATCH_OR_LAYOUT_WARNING` / `SNAPSHOTS_MATCH_NOT_HARDWARE_PROVEN`。最后一种仅代表输入快照内部一致，不自动表示来源真实、Hook 可达、原版发奖成功或保存可靠。

## 实施边界与后续接口

- 本提交**没有**原生 ARM64 Hook、Switch 内存读取、权限/模块加载、网络发送或奖励更改。
- 优先从《紫》4.0.0 实机只读导出四阶段快照；任何代码地址/脚本原型必须经该版本 ELF / `main.blua` Build ID/SHA 复核，不能硬编码历史 Ghidra 绝对地址。
- 若 `P0→P1` 不匹配，先排除随机重算、来源列表选择错误、仅包含固定奖励而不包含补充奖励、不同场战斗混用；不要直接改写数据来“让测试通过”。
- 只有 N1 的**真实房主**四点证据闭合，才依据生命周期选择 N2 入口；然后进行 N3 原版奖励尾部追加器，保留原版已有 `subject=4/5`。
- Rust `RaidCrawler/format.rs` 若属外部项目，须取得其 repo/版本和真实入口后另行集成；本仓库没有 `format.rs`，不制造占位式 Hook。
- 网络为本地 LDN 或官方互联网需要在捕获日志里明确标识；离线快照一致不证明官方互联网接受修改。

## 回归测试

`python -m pytest tests/test_sv_host_trace.py -q`。

覆盖：三类二进制格式、45 槽计数、subject 分类、空洞/异常字段报警、坏消息/压缩标志拒绝、四点一致、发送阶段发生变化时报警、不完整四点不算完成、Build ID 与来源 checksum 必填或校验。通过仅表明离线解析/比对函数在测试输入上符合预期。

**下一个真实开发任务**：编写本机只读 Capture Adapter，将真实房主 `P0/P1/P2/P3` 的原始数据按本工具格式导出；至少两次不同 seed/成员组合比对通过，才算达到 N1。