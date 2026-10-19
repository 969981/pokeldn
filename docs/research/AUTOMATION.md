---
title: Research 自动同步与构建
nav_exclude: true
---

# research 自动同步与构建

这里说明仅在本仓库 `969981/pokeldn` 中使用的自动整合流程。原版 Decryptu 和汉化 easyworld 的分支保持镜像属性，个人研究资料与代码仅在 `research` 分支维护。

## 触发方式

- `Sync upstream branches`：GitHub Actions 每五分钟轮询两个原始仓库，将变更分别镜像到 `main` 和 `ew`。
- `Integrate research upstreams`：镜像工作流成功完成后立即尝试整合，另设每小时兜底检查及手动触发；如果两个源 SHA 都已包含在 `research` 中则跳过。
- `Build research branch`：用户直接推送 `research` 或在该分支手动执行时，运行三平台回归测试，随后复用 `auto-build.yml` 构建 ESP32、桌面端、Android 和 iOS，发布独立预发行版。

## 自动整合的状态机

1. 从远端 `research` 当前 HEAD 建立 `automation/research-candidate-<run>-<attempt>` 候选分支。
2. 先合并本仓库 `main`，再合并本仓库 `ew`。不使用整树覆盖，不强制选择 `ours` 或 `theirs`。
3. 如产生合并冲突、工作树残留或删掉 `docs/research/`，保持 `research` 不变，上传冲突报告并创建/更新待处理 Issue。冲突时不会推送含冲突标记的分支。
4. 无冲突则在 Linux、Windows、macOS 上运行 Python 和 .NET 回归测试。
5. 仅当所有测试通过，才对候选 SHA 执行全平台打包。可复用构建工作流的 `publish: false` 只上传构建产物和 SHA256 校验，不创建 Release。
6. 所有构建成功后，检查 `research` HEAD 是否仍等于开始集成时的 SHA；使用非强制 fast-forward 更新。若期间有人工提交，放弃推进并重新整合。
7. 使用同一次 Workflow Run 的已验证产物创建 `snapshot-research-<完整 SHA>` 预发行版；无需重复编译。
8. 如果发布失败，已完成合并不会被强制回滚；保留本次 Workflow Run 的产物，产生 Issue，供人工重试发布。

## 失败时怎么办？

- **合并冲突**：查看 `research-merge-conflicts` Artifact 与 `[research-sync] Automation needs attention` Issue。根据冲突日志在修复分支解决后，向 `research` 提交 PR。
- **测试或候选完整构建失败**：`research` 保留原 HEAD；无冲突的候选分支留在远端，方便手动拉取并修复。
- **人工推送后测试或构建失败**：不删除人工提交；`[research-build] Build failed` Issue 显示 SHA 与失败工作流，且不将失败版本发布为新的成功预发行版。
- **上传 Release 失败**：编译通过的 Artifacts 仍在原工作流运行中，按保留期限提供下载；可修复上传流程后重试。
- **上游或研究分支再次更新**：工作流使用并发控制及安全推送，确保人工修改不会被覆盖。下一次成功检查可重新整合。

## 查看和手动执行

- [上游镜像同步](https://github.com/969981/pokeldn/actions/workflows/sync-upstreams.yml)
- [Research 自动整合](https://github.com/969981/pokeldn/actions/workflows/research-integrate.yml)
- [Research 手动提交构建](https://github.com/969981/pokeldn/actions/workflows/research-build.yml)
- [研究预发行版](https://github.com/969981/pokeldn/releases)

手动修复冲突时，以原版最新协议功能为基准，保留汉化映射与研究材料；在真正解决行为差异前不得自动选择某一侧全部改动。
