---
title: 《紫》4.0.0 Lua5.4 奖励函数尾部嫁接与字节码重封实验
parent: 朱／紫（SV）
nav_order: 14
---

# 《紫》4.0.0：LotteryRewardItem Lua 5.4 尾部嫁接、重封与实机验收边界

- **研究日期**：2026-10-20
- **目标**：以原生 `LotteryRewardItem` 生成的 `BattleRewardData[3]` 为基础，保留既有奖励，最多额外追加一条 `ItemNo=492, ItemNum=1, rareType=0, subjectType=5`。
- **证据状态**：真正的 Lua 5.4 解释器已执行合成样本的字节码改写，7 项本地测试通过；**本轮未拿到完整原版 `main.blua`，所以还不能判断 PC 475 的真实 opcode，也没有 Switch、LayeredFS 或存档到账实测**。
- **代码**：[重封实验器](../../../scripts/research/sv400_lua54_reward_tail_experiment.py) · [实验 Helper](../../../scripts/research/sv400_charm_single_append_helper.lua) · [Lua VM 回归测试](../../../tests/test_sv400_lua54_reward_tail_experiment.py)。
- **关联**：[原版 4.0.0 Prototype 锚点](violet400-lotteryrewarditem-exact-prototype.md) · [原版后置追加策略](sv400-lua-post-lottery-append-hook.md)。

## 1. 版本锚点与为什么 PC 475 不是可直接写入的补丁

此前的精确静态分析报告记录：原版《紫》4.0.0 `main.blua` 为 12,912,264 字节，SHA-256 为 `c1a4f4e2625912cf0b739a642a79ba3357df0557a544b92da22a6cb139de2815`；目标 `LotteryRewardItem` 为 `root/2899`，指令区 `0x377501`，477 条指令，**后置候选 PC475 对应文件偏移 `0x377C6D`**。

- 这是**历史 bytecode 定位报告**，不是本轮读取原文件重新得到的 PC475 机器字；**没有证据证明 PC475 的 opcode 已经确认为 RETURN1**。
- 本工具默认拒绝不同 SHA、不同 Prototype code start，以及 PC475 不是 Lua 5.4 `RETURN1` 的输入。**不会静默套用** 3.0.1 的偏移。
- 对目标函数其它 `RETURN` 路径不会无条件修改；只有所选的、通过校验的单条返回路径被跳转到新增尾部。

## 2. 已实现：Lua 5.4 本体的重封实验

实验器有完整的 Lua 5.4 chunk / Prototype 结构解析和偏移检查，重新写出以下字段：

1. 在原 `RETURN1` 处替换为经过范围校验的 `JMP`；
2. 在该 Prototype 的代码末尾追加 `CLOSURE → MOVE → CALL → 原 RETURN1`；
3. 把完全独立的零 upvalue Helper Prototype 追加为当前 Prototype 的新子函数；
4. 同步扩充 Lua 指令数量、子 Prototype 数量、maxstacksize 以及存在的 debug lineinfo；
5. 重新解析改写后的整个 chunk；校验原函数其余所有原版指令的值保持一致。

**这样做不是把原版所有逻辑清空后替换为自定义奖励，而是只在一个返回路径上执行额外的函数调用。**

### 奖励 Helper 的精确逻辑

[实验 Lua 源码](../../../scripts/research/sv400_charm_single_append_helper.lua) 只访问返回对象本身；不依赖外部 Lua 全局。它检查 `reward[3]`、`rows.length` 和容量阈值 45，然后以 `rows:push` 追加匿名奖励记录：

~~~lua
local item = {
  ItemNo = 492,
  ItemNum = 1,
  rareType = 0,
  subjectType = 5,
  __fields__ = {ItemNo=true,ItemNum=true,rareType=true,subjectType=true}
}
~~~

这是**语义候选实现**。原版 Haxe / Lua 运行时对匿名记录是否还要求额外 `L16_1` 构造步骤，需要在真正 4.0.0 中验证；合成 Lua table 测试不能替代实机 ABI 测试。

## 3. 可复现的测试

在含 Lua 5.4 库的 Python 环境：

~~~powershell
pytest -q tests/test_sv400_lua54_reward_tail_experiment.py
~~~

本轮本地真正的 Lua VM 合成字节码实验共 7 项通过：

- 重打包样本经 Lua 5.4 VM 正常加载；新增 `ItemNo=492` 行；
- 拒绝非 `RETURN1` PC、SHA 不匹配、Prototype 偏移不符；
- 原始代码所有其他指令不变；
- 对含一条原版奖励的合成数组追加，原有行未被移除；
- 模拟原始 45 行已满时保持 45 行，不越界追加。

**测试不会带有原版 `main.blua`，也不会把“合成 Lua VM 执行成功”写成“零售版运行成功”。**

## 4. 原版 4.0.0 输入到手后的实验命令

先只读确认 PC475 的原始指令，若不是 `RETURN1` 就停止该方案：

~~~powershell
python scripts/research/sv400_exact_reward_gate.py "D:\SV\main.blua" --output violet400_reward_gate.json
~~~

然后用**标准 Lua 5.4 编译器**生成 Helper chunk（普通 `luac`，不是游戏打包器）：

~~~powershell
luac -o sv400_charm_single_append_helper.luac scripts/research/sv400_charm_single_append_helper.lua
~~~

经本机复核确定 PC475 与相关控制流可以重定向后，再生成仅用于**离线分析**的产物：

~~~powershell
python scripts/research/sv400_lua54_reward_tail_experiment.py "D:\SV\main.blua" sv400_charm_single_append_helper.luac --output trial_main.blua --report trial.json
~~~

**目前没有执行上述真实原版重封**。本工具生成的是 Lua chunk，并不负责 `arc/scriptluabinreleasemainmain.blua.trpak` 的资源重封，也不自动安装 LayeredFS Mod。工具不会绕过 hash/原始返回指令校验来强行产出文件。

## 5. PC475 决策门槛

| 检查 | 有结果时如何处理 |
|---|---|
| SHA / 原版 4.0.0 root 与 Prototype 匹配 | 不匹配则拒绝 |
| PC475 为 `RETURN1` 且确实返回 BattleRewardData 对象 | 才能考虑尾部嫁接；否则研究其它返回 PC 或方法包装 |
| RETURN1 返回寄存器、maxstack 与跳转路径 | 必须以实际 raw code/CFG 验证 |
| Helper 的 Haxe 数组与匿名结构 ABI | 需在 4.0.0 Lua VM 中测试，不能仅凭标准 Lua 5.4 通过认定 |
| 修改后 chunk 的 loader 接受度 | 需校验实际加载；不等于只用标准 luac 编译成功 |
| 原版奖励 + 1，且实际 0x2F 和 Bag 同步 | 需实机三点捕获，任何失败停止 |
| 保存重启仍保留 | 必须单独验证 |

## 6. 当前结论

**当前完成：可运行的标准 Lua 5.4 Prototype 尾部嫁接/重封实验器 + 七项 Lua VM 合成样本测试 + 4.0.0 的 SHA/PC 严格阻断。**

**当前未完成：PC475 原始指令复核、真正 4.0.0 主脚本生成/安装、实机奖励到账、保存重载。** 不应为追求可运行而使用猜测的 PC/opcode，也不能把原版 45 行覆盖成一套自定义奖励。

参考 Lua 5.4 编码定义：[官方 lopcodes.h](https://www.lua.org/source/5.4/lopcodes.h.html) 和 [ldump.c](https://www.lua.org/source/5.4/ldump.c.html)。
