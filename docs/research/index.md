---
title: 研究笔记
nav_order: 90
has_children: true
---

# 研究笔记

此目录是 [969981/pokeldn](https://github.com/969981/pokeldn) 的 **research 分支**独立研究区。它与原版 `docs/*.md` 和汉化版 `docs/zh-Hans/*.md` 平行维护，不直接改写上游研究结论。

研究目标：以 Decryptu 的新功能为技术基线，合并 easyworld 的中文内容，在单独目录记录源码阅读、逆向分析、协议实验、数据结构、复现结果和未解决问题。

## 按主题查找

- [通用通信与协议](common/index.md)：跨游戏的 LDN、Pia、加密、可靠传输、抓包解析及报文重放。
- [硬件与无线固件](hardware/index.md)：ESP32、串口帧、COBS/CRC、Wi-Fi、BLE、无线时序与硬件适配。
- [火红／叶绿（FRLG）](frlg/index.md)：GBA RFU、交换与通信状态机、神秘礼物、ROM、ARM 载荷、存档和随机数。
- [红宝石／蓝宝石／绿宝石（RSE）](rse/index.md)：与 GBA 通信机制相关的研究、数据格式、版本差异及实验。
- [Let's Go 皮卡丘／伊布（LGPE）](lgpe/index.md)：Pia 协议、交换码、PB7 数据和联机消息。
- [剑／盾（SWSH）](swsh/index.md)：Pia 4、交换状态机、神秘礼物、极巨团体战及遭遇数据。
- [晶灿钻石／明亮珍珠（BDSP）](bdsp/index.md)：Pia 5、Union Room、连接握手、交换协议和 PB8 数据。
- [传说 阿尔宙斯（PLA）](pla/index.md)：Pia 头部、应用消息、交换处理以及 PA8 数据。
- [朱／紫（SV）](sv/index.md)：Pia 6、交换消息、太晶团体战、战斗服务器和奖励。
- [传说 Z-A（PLZA）](za/index.md)：交换协议、版本兼容性、应用消息及 PA9 数据。
- [跨游戏实验与工具](experiments/index.md)：跨游戏验证、实验设计、辅助脚本、复现步骤和工具链研究。

## 文档约定

- **已证实**：存在可重复的源码调用路径、报文证据或实体主机实测；注明具体证据。
- **推断**：由多项事实支持但仍缺验证；明确推断条件与替代解释。
- **待验证**：研究猜想或待执行实验；不能作为程序实现的既定前提。
- 记录目标游戏及版本、测试平台、源代码 commit SHA、函数/偏移/数据格式、复现步骤和误差/限制。
- 二进制偏移、报文 Hex、函数名和 API 字段保留原样。中文名称作为解释，不替换协议字段。
- 协议与代码记录放本目录；一次性实验脚本优先放仓库根目录的 `experiments/<game>/`（按需创建）。
- 不提交个人 `prod.keys`、登录凭据、未脱敏网络数据、商业 ROM 或机密资源。
- 原项目文档仅作为依据；若发现错误，在个人研究笔记中记录证据，再考虑单独向上游提交改进。

参见 [研究记录模板](template.md) 和 [首次集成基线](BASELINE.md)。 另见 [自动同步与构建流程](AUTOMATION.md)。
