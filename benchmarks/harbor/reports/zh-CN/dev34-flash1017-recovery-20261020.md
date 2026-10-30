# Flash 1017：三题 verifier 恢复补充实验

本次单独授权的补充实验完成了 3 个全新 agent 试次，结果为 **1 题通过、1 题评分失败、1 题 verifier 错误且未评分**。[原 dev34 baseline](dev34-flash1017-main-20261019.md) 仍为 **26 题通过、5 题评分失败、3 题 verifier 错误且未评分**。原容器已删除，且未归档 `/app` 解答，因此这些新解答无法重新评估原产物，也不能填补原试次缺失的评分。用户明确选择了每题重新生成一份解答、verifier 最多尝试 3 次、保留工作目录，并单独报告。

[机器可读结果](../../results/dev34-flash1017-recovery-20261020.json) 保存原生评分、分析分类、全部尝试记录、用量、产物哈希和原 baseline 完整性证据。[登记说明](../../configs/dev34-flash1017-recovery-20261020/README.md) 记录不可变计划和预检历史。[完整英文版](../en/dev34-flash1017-recovery-20261020.md)。

核心 agent 和 385 词提示词与 baseline main `ce28b1e826a292d796ba64f13e79199b66f65758` 逐字节一致。冻结的运行版本为 `40fdd041c370a96dc06f86b436eacc01ce1566d7`；其 verifier harness 增加了需显式选择的 pytest 收集错误恢复。模型为 `deepseek/deepseek-flash`，端点为 `https://api.deepseek.com/anthropic`。10 月 20 日核对的[官方文档](https://api-docs.deepseek.com/quick_start/agent_integrations/) 将此可变别名映射到 DeepSeek-V4.1-Flash-1017，无法固定不可变 checkpoint。temperature 和 reasoning effort 均未设置。每题保留 100 次回复、每次最多 65,536 个输出 token、720 秒工作预算、1,800 秒安装时限，以及原始镜像、资源、软件包来源、测试和单次 verifier 900 秒时限。有效计划 SHA256：`a6c1a9433aafcdb9ce4d834b99d2c91aab2148488626b8b7fb31857f95a4b481`。

3 个全新的仅安装检查均成功。每题的 verifier 依赖 profile 均明确记录为 `not_configured`；安装成功不能认证 verifier 依赖可用。初版计划只执行了这些检查。在任何模型调用之前，v2 同时选用了 `environment.kwargs.keep_containers=true` 和 `environment.delete=false`，因为在 Harbor 0.21 中仅设置后者仍会删除 Docker 容器。初版计划与配置保持原样，v2 通过哈希绑定成功的原生预检记录。

现有比较编排器调用标准入口 `uv run --project benchmarks/harbor python -m harbor_adapter run --config ...`。它先并行运行数据合并和 CLI，再运行模型恢复，观察到的最大并发为 2。每题 agent 只运行一次。超时、pytest 启动前识别到的 uv 网络错误，以及明确识别到的 pytest 收集中断，在同一容器和同一份 agent 产物上共享最多 3 次尝试。本次单独授权的补充实验显式开启了 `retry_dependency_errors` 和 `retry_collection_errors`。任何有效评分（包括 0 分）都会立即停止。各次尝试之间保留 verifier 对文件系统的修改和依赖缓存。没有修补解答，也没有向模型反馈测试结果。

下表的官方 pytest 完整结果按 **通过 / 失败 / 错误 / 跳过** 排列。横线表示没有完成的断言结果；`null` 表示未评分。原生评分及各次归档输出保存在结果与本地证据中。

| 题目 | 结果 | 分析评分 | Pytest P/F/E/S | Verifier 尝试 |
| --- | --- | --- | --- | --- |
| `multi-source-data-merger` | 通过 | 1.0 | 3 / 0 / 0 / 0 | 1: completed (48.73s) |
| `pytorch-model-cli` | 评分失败 | 0.0 | 5 / 1 / 0 / 0 | 1: timeout (900.00s); 2: completed (492.35s) |
| `pytorch-model-recovery` | verifier 错误，未评分 | null | — | 1: timeout (900.00s); 2: timeout (900.00s); 3: timeout (900.00s) |

**`multi-source-data-merger`:** 官方 verifier 执行了全部 3 项检查并通过。只进行 1 次验证；新解答的合并值和冲突报告满足官方断言。

**`pytorch-model-cli`:** 第 1 次 verifier 在依赖安装阶段运行满 900 秒后超时，尚未进入 pytest。第 2 次完成了测试，5 项通过、1 项失败：检查的 50 张图中有 10 张预测错误。提交的 cli_tool 是 ELF 可执行文件（5,877,872 字节）。其 C++ 源码使用 (pixel/255 - 0.1307)/0.3081，而官方数据流程使用 ToTensor()，没有额外的均值/方差归一化。这是已观察到的预处理差异；没有测试任何修补后的解答。有效的 0 分使恢复在 2 次尝试后停止。

**`pytorch-model-recovery`:** agent 重建了编码器/解码器，仅通过岭回归调整 output_layer，并导出 TorchScript 模型。题目没有要求特定优化方法。提交源码和工具调用中未观察到读取隐藏测试的行为；最终 verifier 状态另行收集。 3 次 verifier 均在下载 PyTorch/CUDA 依赖时耗尽原定 900 秒时限，尚未进入 pytest。保留原生 VerifierTimeoutError 和 null 评分。没有执行官方断言，因此这份新 TorchScript 产物的正确性仍未验证。

本次补充实验共执行 **6 次 verifier**，其中 **3 次为重试**。模型阶段墙钟时间为 **82.90 分钟**，不含仅安装预检。记录的输入/输出/缓存 token 为 **1,168,608 / 47,844 / 1,143,168**。用量和费用记录分别有 **3/3** 和 **3/3** 个试次完整。adapter 估算总费用为 **USD 0.071903808**；这是估算，未进行账单对账。

3 个 agent 执行和验证前产物归档均于 **2026-10-20T14:27:02.680316+00:00** 冻结，之后才查看新轨迹、产物内容或官方测试输出。最后一个 verifier 在冻结后继续运行。审计覆盖 3 份 ATIF 轨迹、3 份 agent 标准输出、全部 68 次工具调用参数，并对全部 40 个冻结文件扫描已配置凭据的精确匹配（0 次）。未观察到获取题目专属参考解答或读取隐藏 verifier 内容的行为。CLI 使用常规编译器和软件包工具；模型恢复使用题目提供的权重/数据及输出层岭回归，题目未禁止这种方法。这些观察不能证明不存在先前接触或训练污染。这些是开发题目，解答为独立重新生成，恢复策略也有变化，因此不能得出仅由 checkpoint 变化导致的结论，也不属于留出集评测。

Harbor 在验证前为每题收集 `/app`，并为数据合并题收集 `/data`。下列原始主容器均已停止并保留；3 个镜像身份仍与 baseline 一致，且主容器均未被 OOM 杀死。JSON 记录完整文件哈希、符号链接目标、清单、源码/wheel 指纹和原生证据哈希。原始日志和解答文件保存在由 Git 忽略的 `jobs/` 中。

| 题目 | 保留的主容器 | 容器 ID | 原始镜像 ID |
| --- | --- | --- | --- |
| `multi-source-data-merger` | `multi-source-data-merger__jnm6pzd__env-main-1` | `e16fca632789` | `sha256:8b32782078ff7383a1b4e5d3cecca8ce287e30f50bb4c0e5db009a18064e666e` |
| `pytorch-model-cli` | `pytorch-model-cli__p8vpnwh__env-main-1` | `5906632d1db2` | `sha256:c996884b5fb5fb2c0c07d67da2c4f974f271f07234ed28e1a868240375c57a67` |
| `pytorch-model-recovery` | `pytorch-model-recovery__ncs7y4h__env-main-1` | `e8f4a6bb804b` | `sha256:7c2bb52851cef25bdc3939e473496d25fbf11fd0cb7ab58bcf3cefcb751cdc0e` |

| 试次 | 题目版本 | 原生结果 SHA256 | ATIF SHA256 |
| --- | --- | --- | --- |
| `multi-source-data-merger__jNM6pZd` | `sha256:70367c38732e1beda7b229968a48d60242277c2fa4db91339c3f064c4c230d49` | `a7b0dd5432c9c2039c843f48248ddb269ad759173031736da46ba96e6b7d7b79` | `b8d4e011e14fda92785c457dbb1dacfeec4f8bf70f180b39e65128a51c1429f6` |
| `pytorch-model-cli__P8vPNwH` | `sha256:6f11544dcc81a380dc4611902961f5520259c462d9fceb413419d66ab9a96c79` | `1c4d0b6360600073b5dedd1ca089f4f8cff37819935549362f02ff06b1bd0056` | `f05243db52fdae75e29108803ba60fdc2bca54c9de9c997d6b1ff08789f080fa` |
| `pytorch-model-recovery__nCs7Y4H` | `sha256:2e628841cff93290919172398e573e794f34c95d9382b7425adde4364022decc` | `2a61cc964ad2a684e2b4adb3e5d333f75093db51320f7e448a2cb83446998e34` | `73b4f374dbfb89dd3d3b94d572136c2f613bc1666aad87b8a6454c3316bb3f3d` |

verifier 安装依赖时，根分区可用空间降至 2.99 GiB。6 个重复 OCI 归档和 44 个已校验镜像缓存 blob（共 1,576,934,879 字节）被暂存到内存中的 `/tmp`，在持有缓存单写者锁期间以符号链接保留原路径。发布前，全部 50 个常规文件均已恢复并通过 SHA256 校验。此次主机维护没有改动 Docker 原始镜像、解答产物、依赖缓存、软件包来源或 verifier 脚本。

验证：190 项本地 Harbor adapter 测试通过，覆盖超时上限、显式收集/下载错误恢复、有效评分后停止和日志保留。冻结的源码/提示词/题目/配置/wheel/镜像检查通过；原 baseline 结果及原 3 个试次已记录的证据哈希保持不变。两份完整报告从同一结果数据同时生成，并核对了结果、计数、标识符、哈希、限制和链接的一致性。
