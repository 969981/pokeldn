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

- [晶耀护符、太晶坑奖励资格与 999 道具案例](glimmering-charm-raid-rewards.md)：结合 PokéLDN 奖励结构、4.0.0 上游 ELF/Lua 逆向记录、联网模式证据分级和待验证实验。

- [《紫》4.0.0 ELF：RaidPoint/bootstrap 原生机器码复核](violet400-elf-raid-bootstrap-audit.md)：核对用户 Library ELF 的 Build ID、SHA-256、15 条原始指令与逆向证据边界。
- [SV BattleRewardData 与 Bag 的 Lua 交叉分析](battle-reward-lua-cross-version.md)：找到公开旧版反编译 Lua，核对 ID 2481 的背包查询及 subject=5 过滤。
- [太晶坑奖励到背包与自动保存的 Lua 调用链](raid-reward-to-bag-save-chain.md)：胜利条件、资格过滤、SlotMaxNum、Bag.AddItem、RequestAutoSave 及证据界限。

以下内容包含独立完成的 ELF 静态验证，以及尚未在实机闭环的假说。新研究应按照 [研究记录模板](../template.md) 记录版本、提交及结论状态。

[返回研究总索引](../index.md)
