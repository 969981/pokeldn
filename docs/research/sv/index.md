---
title: 朱／紫（SV）
parent: 研究笔记
nav_order: 9
---

# 朱／紫（SV）

Pia 6、交换消息、太晶团体战、战斗服务器和奖励。

## 现有项目参考资料

- [原版：sv.md](../../sv.md) · [汉化：sv.md](../../zh-Hans/sv.md)
- [原版：sv_raid.md](../../sv_raid.md) · [汉化：sv_raid.md](../../zh-Hans/sv_raid.md)

## 个人研究记录

- [历史 donor BIN 解压、Ghidra 溯源与奖励字段偏移勘误](sv400-reward-donor-bin-ghidra-audit.md)：独立解压 1707→0xAA0，复核 45 条奖励表与 subject 字段，对照上游 Ghidra 地址及 0x798/0x79C 旧文档误差。

- [晶耀护符、太晶坑奖励资格与 999 道具案例](glimmering-charm-raid-rewards.md)：结合 PokéLDN 奖励结构、4.0.0 上游 ELF/Lua 逆向记录、联网模式证据分级和待验证实验。
- [FieldRaidJewelry.LotteryRewardItem 晶耀奖励生成链源码核验](fieldraidjewelry-lotteryrewarditem-glimmering.md)：逐参数还原数量表读取、18 项碎块道具映射及 subject=5 写入，区分旧版 Lua 与 4.0.0 实证并给出无损追加测试方案。

- [《紫》4.0.0 ELF：RaidPoint/bootstrap 原生机器码复核](violet400-elf-raid-bootstrap-audit.md)：核对用户 Library ELF 的 Build ID、SHA-256、15 条原始指令与逆向证据边界。
- [SV BattleRewardData 与 Bag 的 Lua 交叉分析](battle-reward-lua-cross-version.md)：找到公开旧版反编译 Lua，核对 ID 2481 的背包查询及 subject=5 过滤。
- [太晶坑奖励到背包与自动保存的 Lua 调用链](raid-reward-to-bag-save-chain.md)：胜利条件、资格过滤、SlotMaxNum、Bag.AddItem、RequestAutoSave 及证据界限。
- [自定义太晶坑奖励：主持端到《紫》4.0.0 ELF](custom-raid-rewards-host-elf.md)：命令行/GUI 到 RaidPoint 的真实组包代码、subject 资格字段及 ELF 指令核验（附新版本勘误）。
- [《紫》4.0.0 自定义奖励：动态指针及字节修改](sv400-custom-reward-pointer-patch.md)：实际 x20/x23 数据指针、逐字段偏移、可用 subject=0/5 配置、13/13 ELF 验证及离线明文编辑脚本。
- [4.0.0 保存协程/回调与截图道具上限](sv400-autosave-and-item-slotmax.md)：追到 SaveProcess 原生启动与完成轮询，给出实际道具 ID、PKHeX 999 交叉参照和原始 RomFS SlotMaxNum 解析工具。

- [太晶坑奖励保存协程与 SlotMaxNum 物品表研究](saveprocess-slotmax-followup.md)：追踪 StartSaveProcess → SaveProcess 轮询与 Native 回调、提供不依赖游戏文件的 FlatBuffers 解析器和待验证清单。
- [本地 LDN 奖励三点数据一致性验证计划](raidpoint-bootstrap-receiver-consistency.md)：P0 验证源 RaidPoint → Bootstrap → 接收端奖励筛选列表；包括独立采样点、日志格式、0/5 与原生 subject 实验矩阵、失败归因及 Hook 放置决策标准。

以下内容包含独立完成的 ELF 静态验证，以及尚未在实机闭环的假说。新研究应按照 [研究记录模板](../template.md) 记录版本、提交及结论状态。

[返回研究总索引](../index.md)
