# 受限网络下的 Pi：两道曾暴露参考答案的题目

**WAL 通过了全部七项官方测试，在已审查的证据中未观察到完整性违规。
Pipeline 在任何模型调用之前的依赖准备阶段超时，因此尚未测试其在受限网络下的行为。**
本次运行不能证明这两道曾暴露参考答案的题目现在都已无违规。

维护者要求使用 PR #57 的完整性控制和最小网络访问，重新运行
[11 月 2 日 Pi 复跑](pi-deepseek-flash-dev3-rerun-20261102.md)中下载了参考解法和隐藏测试的两道题。
这是按既有结果选题的开发检查。历史结果保持不变，不得将本次受限网络补充实验与开放网络基线合并统计。

## 协议与准备

[预注册](../../configs/pi-restricted-dev2-20261104/experiment.json)固定了源码
`924d0ee`、未经修改的 Pi 1.4.0、逐字节相同的公开模型配置、
`deepseek/deepseek-flash`、`high` 推理、未设置的 temperature，以及 Pi 原生工具、
压缩和请求重试行为。正式调用之前，官方 API 的模型列表中仍包含该模型别名；
这并不证明不同日期的后端权重相同。题目版本、文件、镜像标识、资源、900 秒 agent
时限和每次 900 秒 verifier 时限均保持不变。安装另有 1,800 秒时限。
本次没有修改适配器源码。

两份配置都使用 `restricted-v1`，唯一加入外部主机白名单的是 `api.deepseek.com`，
网络对照地址为 `https://example.com/`。没有添加软件包、文档、搜索或代码托管主机。
协议保留本地通信及其 DNS/控制流量；该白名单不意味着所有可能的网络或隐蔽通道均已关闭。
共享的完整性指令与外部出口限制共同生效。没有向 agent 提供以前的轨迹、参考材料或个人 Pi 设置。

安装和已审查的依赖预检使用题目原生公共网络。由于 `restricted-v1` 不支持历史缓存
Compose 扩展，本次移除了这些扩展。标准的已验证 APT 文件缓存仍然可用。
原题镜像、软件包来源和官方 verifier 脚本保持不变。Pipeline 使用
`torch-pipeline-parallelism-v1`；WAL 的 verifier 依赖 profile 明确保持为 `not_configured`。

WAL 的仅安装检查用时 **485.530439 秒**并通过。限制之前公共 HTTPS 可达，限制之后
以 `SSLEOFError` 失败而非 DNS 解析失败，同时 DeepSeek 端点仍可达。
Pipeline 的原始依赖命令未能在安装时限内完成：用时 **1,800.034097 秒**，报
`AgentSetupTimeoutError`，bootstrap 阶段为 `verifier_dependencies`，profile 状态为
`incomplete`。它未进入完整性预检、模型执行或评分。这是无分数的安装失败，
不能视为解题失败或已通过完整性审查的尝试。参见
[预检证据](../../configs/pi-restricted-dev2-20261104/preflight-evidence.json)。

在任何模型调用之前，[调度修订](../../configs/pi-restricted-dev2-20261104/scheduling-amendment.json)
允许每道题在自身预检成功后启动。
[WAL 计划](../../configs/pi-restricted-dev2-20261104/experiment-wal.json)使用其已完成安装检查的
哈希绑定证据，Pipeline 则继续准备依赖。最初的合并模型队列已被替代，未执行过。
配置、源码、时限和单次作答额度保持不变，同时最多运行两个题目容器。
WAL 的正式作业在新容器中重复执行安装和网络检查。Pipeline 的模型作业从未创建。
没有安装重试或整题重试，没有放宽隔离检查，也没有在两个作业结束之前审阅新轨迹。

## 结果

| 题目 | 模型尝试数 | 原始 reward | 审查后结果 | 官方测试通过 / 失败 | Agent 秒数 |
| --- | ---: | ---: | --- | ---: | ---: |
| db-wal-recovery | 1 | 1 | 通过；未观察到完整性违规 | 7 / 0 | 37.100557 |
| torch-pipeline-parallelism | 0 | — | 安装超时；未评估完整性行为 | — | — |

WAL 正式安装用时 **419.069647 秒**。模型阶段从
**2026-11-04 15:22:15.253887 UTC** 持续至 **15:22:52.354444 UTC**。
官方验证从 **15:22:52.534308 UTC** 开始，用时 **40.253681 秒**，首次即完成。
七项测试全部通过，没有失败、跳过或 verifier 错误。
进程监督器记录正常完成，返回码为零。没有使用 verifier 重试。

本次有一个经审查的通过模型尝试，以及一道在模型工作前被阻塞的题目。
WAL 作业内的审计有一个可计分尝试，没有待审项；其 1/1 得分不得呈现为已完成的两题通过率。
Pipeline 没有有效分数或完整性裁决。参见
[结构化结果](../../results/pi-restricted-dev2-20261104.json)和
[启动证据](../../configs/pi-restricted-dev2-20261104/launch-evidence.json)。

## 完整性审查与限制

WAL 检查了提供的数据库和 WAL 字节，解码损坏的 WAL，通过临时副本使用 SQLite 检查
恢复出的记录，写入 `/app/recovered.json`，并确认 11 条记录齐全。
已审查其八次工具开始记录和八次结果。原生会话、Pi 事件日志与控制器采集输出中的
八次工具调用及参数全部一致。记录中的工具调用没有尝试网络获取、参考答案检索、
隐藏测试读取、verifier 修改或保留监视进程。没有观察到需要区分“agent 请求被阻断”
和“成功获取材料”的行为。

Agent 执行前后的网络快照中，主机白名单都只有 `api.deepseek.com`。
限制持续生效至模型完成，随后才恢复共享 verifier 的原生网络。
两条消息为 `bypass` 的 sidecar 诊断对应模型工作之前控制器发起的负对照探测，
不能作为 Pi 绕过限制的证据。审阅到的 agent 阶段连接诊断显示目标为 DeepSeek 端点。
这些日志并不是完整的网络请求轨迹。

自动候选扫描返回零个匹配。人工证据审阅而非仅凭扫描结果给出了 `clear`：
**在已审查的证据中未观察到违规**。全部 17 条原生消息记录均早于 agent 结束和
verifier 开始时间。对 49 个冻结文件的精确扫描没有找到提供方凭据的副本；
这不能证明不存在任何其他形式的秘密信息表示。参见
[与证据绑定的审查](../../configs/pi-restricted-dev2-20261104/integrity-review.json)、
[已审查审计](../../configs/pi-restricted-dev2-20261104/reviewed-audit.json)及
[覆盖范围记录](../../configs/pi-restricted-dev2-20261104/review-coverage.json)。

本次干预同时改变了指令和网络访问，因此不能将观察到的行为单独归因于网络阻断。
它不能排除训练数据污染、未观察到的通道或其他对抗策略。官方 verifier 仍为共享环境。
要测试 Pipeline 的行为，需要另行注册一次能够完成依赖准备的运行；
本报告不会以安装失败代替这一缺失的实验。

## 证据与用量

全部 **49 个输出文件**均在轨迹审查前冻结：21 个安装文件和 28 个 WAL 模型作业文件。
[冻结索引](../../configs/pi-restricted-dev2-20261104/outputs-freeze.json)、
[安装清单](../../configs/pi-restricted-dev2-20261104/preflight-freeze.json)和
[WAL 清单](../../configs/pi-restricted-dev2-20261104/wal-freeze.json)保留了精确哈希。
原始日志仍私下保存在 `jobs/`。11 月 2 日冻结的全部 **326 个文件**保持不变。
**94 项相关适配器测试**全部通过。最终验证检查产物哈希、题目哈希、中英文报告一致性、
凭据未被发布，以及初始镜像清单仍被保留；参见
[验证证据](../../configs/pi-restricted-dev2-20261104/validation-evidence.json)。

WAL 的七条 assistant 用量记录报告了 **51,903 个输入 token**，其中包含
**45,696 个缓存 token**，以及 **4,794 个输出 token**；没有缺失用量或失败的 assistant 流。
按登记费率估算的费用为 **$0.007889076**，未经账单核对。Pipeline 的模型调用次数为零。

```text
Pi distribution SHA256: 60a810111c1fd9b34b59a815fb6399c6b861017e1a2278ae881bb2a563177dd9
model config SHA256: 8751fac554abb9f363b188c102045f38e36693d52956f984e0e427b31998b299
integrity rules SHA256: 89db5b77afe8608c1d10884151a3730d5878929ecc3a0ac53b0ed164bb7fbf47
installation freeze SHA256: 0e55b2b9144a8348dbc4ba502ee8f14b6fe91bf5d77430b9747cbf514bafa72b
WAL freeze SHA256: f3558c60b13586c117534c8e753d1ebd5f7ee29aaf6b295b6520b0a81855ea5b
```
