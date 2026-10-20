---
title: 《紫》4.0.0 Lua5.4 奖励函数尾部嫁接与字节码重封实验
parent: 朱／紫（SV）
nav_order: 14
---

# 《紫》4.0.0：LotteryRewardItem Lua 5.4 尾部嫁接、重封与实机验收边界

- **研究日期**：2026-10-20
- **目标**：以原生 `LotteryRewardItem` 生成的 `BattleRewardData[3]` 为基础，保留既有奖励，最多额外追加一条 `ItemNo=492, ItemNum=1, rareType=0, subjectType=5`。
- **证据状态（2026-10-20 后续更新）**：已取得用户 Library 中完整原版 `main.blua`，SHA 与已知 4.0.0 相同；确认 PC475 是 `RETURN` B=2 而不是 `RETURN1`；已重封实际 4.0.0 字节码并经标准 Lua 5.4 VM **load-only** 检查通过。真实 Switch 游戏运行、LayeredFS 覆盖、奖励到账和存档保留仍未验证。
- **代码**：[重封实验器](../../../scripts/research/sv400_lua54_reward_tail_experiment.py) · [实验 Helper](../../../scripts/research/sv400_charm_single_append_helper.lua) · [Lua VM 回归测试](../../../tests/test_sv400_lua54_reward_tail_experiment.py)。
- **关联**：[原版 4.0.0 Prototype 锚点](violet400-lotteryrewarditem-exact-prototype.md) · [原版后置追加策略](sv400-lua-post-lottery-append-hook.md)。

## 1. 版本锚点与为什么 PC 475 不是可直接写入的补丁

此前的精确静态分析报告记录：原版《紫》4.0.0 `main.blua` 为 12,912,264 字节，SHA-256 为 `c1a4f4e2625912cf0b739a642a79ba3357df0557a544b92da22a6cb139de2815`；目标 `LotteryRewardItem` 为 `root/2899`，指令区 `0x377501`，477 条指令，**后置候选 PC475 对应文件偏移 `0x377C6D`**。

- 这是**历史 bytecode 定位报告**，不是本轮读取原文件重新得到的 PC475 机器字；**已有后续实证：PC475 为 `RETURN`（opcode 70，A=8，B=2，k=1），不是 `RETURN1`（opcode 72）。**
- 本工具默认拒绝不同 SHA、不同 Prototype code start，以及 PC475 不是 Lua 5.4 **单结果** `RETURN B=2` 或 `RETURN1` 的输入。**不会静默套用** 3.0.1 的偏移。
- 对目标函数其它 `RETURN` 路径不会无条件修改；只有所选的、通过校验的单条返回路径被跳转到新增尾部。

## 2. 已实现：Lua 5.4 本体的重封实验

实验器有完整的 Lua 5.4 chunk / Prototype 结构解析和偏移检查，重新写出以下字段：

1. 在原**单结果 RETURN**处替换为经过范围校验的 `JMP`；
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
| PC475 为单结果 `RETURN` 且对应 R8 确实是 BattleRewardData 对象 | 才能考虑尾部嫁接；否则研究其它返回 PC 或方法包装 |
| RETURN 的寄存器、maxstack 与跳转路径 | 必须以实际 raw code/CFG 验证 |
| Helper 的 Haxe 数组与匿名结构 ABI | 需在 4.0.0 Lua VM 中测试，不能仅凭标准 Lua 5.4 通过认定 |
| 修改后 chunk 的 loader 接受度 | 需校验实际加载；不等于只用标准 luac 编译成功 |
| 原版奖励 + 1，且实际 0x2F 和 Bag 同步 | 需实机三点捕获，任何失败停止 |
| 保存重启仍保留 | 必须单独验证 |

## 6. 当前结论

**当前完成：可运行的标准 Lua 5.4 Prototype 尾部嫁接/重封实验器 + 七项 Lua VM 合成样本测试 + 4.0.0 的 SHA/PC 严格阻断。**

**后续已完成原始 PC475 指令复核与 4.0.0 主脚本离线改写/加载校验；但仍未完成安装、实机奖励到账、保存重载。** 不应为追求可运行而使用猜测的 PC/opcode，也不能把原版 45 行覆盖成一套自定义奖励。

参考 Lua 5.4 编码定义：[官方 lopcodes.h](https://www.lua.org/source/5.4/lopcodes.h.html) 和 [ldump.c](https://www.lua.org/source/5.4/ldump.c.html)。

## 7. 2026-10-20：实际原版 main.blua 回归、PC475 更正与零售字节码重封

### 7.1 输入身份和四个 Prototype 重新确认

从用户自己的 Library 提取原始 `main.blua`（只在本地分析，不提交游戏二进制到公开仓库），文件大小 **12,912,264** 字节，SHA-256：

```text
c1a4f4e2625912cf0b739a642a79ba3357df0557a544b92da22a6cb139de2815
```

直接重新解析并核对：

| 方法 | Proto | code 文件偏移 | 指令数 |
|---|---|---|---:|
| LotteryRewardItem | root/2899 | 0x377501 | 477 |
| subject=5 过滤 | root/4870 | 0x410673 | 137 |
| RaidResultAddItem | root/3756 | 0x3B1E39 | 69 |
| 45 奖励槽序列化 | root/27146 | 0xAA084E | 91 |

原版 `root/2899` 的 `maxstacksize=44`，有 1 个子 Prototype；调试行号数组为 0 字节。其它三个函数指纹也与旧报告完全相符。

### 7.2 PC475 **不是 RETURN1**：真实字节验证

```text
Lua 指令： PC 475
文件位置： 0x377C6D
原始字节： 46 84 02 00
指令字：   0x00028446
Opcode：   70  = OP_RETURN
A：        8   = R8 作为返回结果起点
B：        2   = 返回 1 个值
C：        0
k：        1   = RETURN 关闭 upvalue / to-be-closed 状态的原有语义保留

PC 476：   0x00018D46 = OP_RETURN，A=26，B=1（返回 0 个值）
```

早退 PC 27、33、39、53 同样是 `0x00028446`。本阶段只重定向正常完成后的 PC475，保留提前返回路径，不修改 PC476。

旧实现将 `RETURN1` 判为唯一有效返回形式，在此版本上会拒绝正确的目标。已修正为：仅当 **`OP_RETURN1` 或 `OP_RETURN B=2`** 时才允许单结果尾部嫁接。对 `RETURN B=1`（无结果）或其它 opcode，继续拒绝。

### 7.3 在用户提供的真实字节码上重封成功

零售脚本：`root/2899` PC475 原 `RETURN` → `JMP`。PC477 尾部新添 `CLOSURE helper; MOVE R8; CALL helper; 原 RETURN`。精确修改：

| 检查 | 原版 | 改写后 |
|---|---|---|
| PC475 指令字 | `0x00028446` | `0x80000038` |
| 当前函数指令数 | 477 | 481 |
| 当前函数子 Prototype 数 | 1 | 2 |
| 整个脚本 Prototype 数 | 37,743 | 37,744 |
| 文件大小（字节） | 12,912,264 | 12,912,579 |
| 其它 37,742 个既有 Prototype 代码 | — | 与原版逐字节一致 |

修改后主脚本 SHA-256：

```text
9434ec3d8f7eddeaff2a9d7f55925b1a7c6b8d8c120757d976dd9c56e0c8a3ef
```

重新解析整个原版和改写版，全局仅 **`root/2899`** 的代码数组改变，其他已有 Prototype 的指令数据完全相同；新子 Prototype `root/2899/1` 有 **0 个 upvalue**。

**实际 Lua 5.4 VM（`luaL_loadbufferx`）加载原版与完整改写版均返回 0 / OK**。额外用合成 Lua 5.4 VM 样本验证普通 `RETURN B=2,k=1` 的返回跳转后，执行新增 Helper 使原 0 行变为 1 行、道具编号 492；无结果返回的误用被拒绝。本地回归共 **10 项通过**。

### 7.4 剩余技术风险与部署门槛

1. **“标准 Lua VM 可加载”仅是二进制结构正确**，不是游戏 4.0.0 已执行实际函数，也不是 LayeredFS 覆盖生效。
2. 追加 Helper 直接构造带 `__fields__` 的匿名表；原版 Haxe Lua 的 `L16_1` 包装/构造兼容性尚未从实机确认，可能需要进一步适配。
3. 当前修改只有正常奖励生成结束的 PC475 一条路径；早退仍走原版。
4. 按原版 `rows.length<45` 限制追加一条并保留所有原奖励，但游戏里实际的已收集对象、完整队伍 0x2F、过滤器和胜利后背包尚未观察。
5. `main.blua` 是完整游戏私有资源；**不要提交文件本体到公开仓库**。若做个人本地 Mod，还需验证对应 RomFS/Trpfs 的覆盖加载方式。
6. 唯一成功标准：相同 raid 基线全保留、新奖励 `subject=5` 在源 `BattleRewardData`→真实房主 `RaidPoint`→接收端过滤中一致，战后真实到账，保存完成且重启后保留。

**当前评级：零售 4.0.0 原版脚本 SHA 已确认、PC475 真实指令复核完成、Lua 5.4 静态重封与 VM 加载通过；实机功能未验证。**
