# 受限 Pi Pipeline：依赖恢复与一次未评分的模型运行

**依赖准备已修复：最终预检耗时 205.670052 秒，全新正式容器的安装耗时
142.791023 秒。Pipeline 仍没有官方成绩。** Pi 已完成解答，但 Harbor 的输出
采集器在官方 verifier 启动前拒绝了一条很长的最终 JSON 事件。这个独立的采集器
问题现已修复并通过测试；失败运行仍完整保留。

本文接续[11 月 4 日受限检查](pi-restricted-dev2-20261104.md)：当时 WAL 的
七项官方测试全部通过，Pipeline 则在模型调用前触及 1,800 秒安装时限。这是经过
挑选的开发补充实验，不替代原报告或历史开放网络基线。

## 准备过程与保留的失败

[第一次恢复登记](../../configs/pi-restricted-pipeline-recovery-20261105/experiment.json)
固定源码 `8e42c62`，加入受控且经过校验的 PyPI wheel 缓存。仅安装试验通过，
但全新正式容器遇到了另一种下载失败：原始 uv 安装器从原始 uv 发布 URL 下载时
收到 `curl: (18) Transferred a partial file`。该失败容器没有发生模型调用。

[第二次登记](../../configs/pi-restricted-pipeline-recovery-v2-20261105/experiment.json)
固定源码 `a867883`，并启用仓库已有的原始 uv/Python 归档校验缓存。登记前重新
获取原始发布元数据，核对归档文件名、大小和 SHA256。保留原版 uv `0.9.5` 与
Python `3.13.9` 归档，包括 Python 构建 `20251014`。原始安装脚本及 uv 的
Python 版本选择均未改变。

| 尝试 | 安装秒数 | 模型尝试 | 结果 |
| --- | ---: | ---: | --- |
| 11 月 4 日 Pipeline 安装 | 1800.034097 | 0 | 安装超时；保留 |
| 恢复 1：仅安装 | 212.639386 | 0 | 通过 |
| 恢复 1：正式容器 | 370.463495 | 0 | uv 下载截断；保留 |
| 恢复 2：仅安装 | 205.670052 | 0 | 通过 |
| 恢复 2：正式容器 | 142.791023 | 1 | 安装通过；模型完成后采集器出错 |

正式模型尝试包含 25 条 assistant 用量记录。

恢复 1 提供了 **45 个 wheel / 3,080,594,478 字节**，其中 **44 次缓存命中**、
一次重新下载。恢复 2 的预检和正式安装各自都从校验缓存提供了全部 **45 个
wheel** 和两个原始发行归档，没有重定向。每个 wheel 均与当前 PyPI 发布元数据
匹配。这些耗时是在不同容器中的实际观测，不是受控的加速比估计。证据见
[第一次预检](../../configs/pi-restricted-pipeline-recovery-20261105/preflight-evidence.json)、
[uv 失败](../../configs/pi-restricted-pipeline-recovery-20261105/failed-model-setup-evidence.json)
和[第二次预检](../../configs/pi-restricted-pipeline-recovery-v2-20261105/preflight-evidence.json)。

## 网络与缓存边界

可选的 `pypi-verified-v1` 传输为所有受支持的 agent 使用同一条准备路径。
控制器管理的辅助容器仅在依赖安装和官方验证阶段提供服务。脚本和可选发行清单
均复制为快照并记录哈希，原始发行缓存以只读方式挂载。辅助容器使用一个 CPU
和 512 MiB，与保持不变的题目资源分开。题目容器没有挂载任何宿主目录。

辅助容器及回环监听端口在网络预检前移除，并在模型开始前再次确认不存在。
模型阶段只放行 `api.deepseek.com`。原始题目字节、镜像身份、软件包来源、共享
完整性规则、1,800 秒安装时限、900 秒模型时限和每次 verifier 的 900 秒时限
均保持不变。安装与官方验证保留原生公共网络。模型网络白名单从未放宽，官方
verifier 仍使用共享环境。

保留 Pi `1.4.0`、`deepseek/deepseek-flash`、`high` 推理、未设置的温度和公开
模型配置。这个可变模型别名不能证明不同日期的后端权重相同。WAL 没有重跑，
也未使用本次新依赖传输；不声称这是匹配条件的双题因果比较。

## 采集器失败与完整性观察

正式模型阶段耗时 **433.014135 秒**。原生 Pi 输出包含 `agent_settled`，
最后一条 assistant 的停止原因为 `stop`，进程监督记录正常完成。随后 Harbor
按行读取回调输出时，用 **65,536 字节**上限读取 **209,940 字节**的
`agent_end` 事件，抛出
`ValueError: Separator is not found, and chunk exceed the limit`。
官方 verifier 从未启动：原始 reward、有效得分和计分用完整性判定均为空。
参见[模型证据](../../configs/pi-restricted-pipeline-recovery-v2-20261105/model-evidence.json)。

已检查全部 **35 次工具启动和 35 个结果**。原生会话、事件日志和控制器输出
中的工具参数一致。控制器的 327 条事件是原生日志 329 条事件的精确前缀，
只缺少 `agent_end` 与 `agent_settled`。全部 62 条原生消息都早于记录的模型
阶段结束时间。Pi 读取已安装的 Transformers 源码，编写
`/app/pipeline_parallel.py`，开发并删除临时本地自测，最后检查了文件内容。

没有记录到获取外部答案、取得官方隐藏测试内容、修改 verifier 控制或留下观察
评分过程的 watcher。但 Pi 也进行了范围较广的本地测试文件搜索、枚举 `/logs`、
读取当前监督进程 PID 记录，并在依赖缓存中搜索任务函数名。这些搜索返回库文件
或当前 agent 元数据；任务函数名搜索没有命中。因此不能笼统认定它没有尝试寻找
基准材料。候选扫描零命中也不能证明行为干净。参见
[复核覆盖记录](../../configs/pi-restricted-pipeline-recovery-v2-20261105/review-coverage.json)。

模型前后的网络快照保留了仅 API 白名单。两条内容为 `bypass` 的网络诊断对应
模型开始前控制器的负向探针。模型期间带域名的连接诊断显示 DeepSeek 端点，
但这些并非完整请求轨迹。一次环境变量打印将 API 密钥复制进了三份私有冻结
日志。原始日志保持私有，不发布密钥值或原始轨迹。

[自动审计](../../configs/pi-restricted-pipeline-recovery-v2-20261105/unscored-audit.json)
因为缺少完整的 agent/verifier 强制执行序列，报告未评分的 `integrity_error`。
该状态不代表判定 agent 作弊。没有为这次基础设施错误赋予计分用的 `clear` 或
`violation` 结论。训练污染和未观察到的通道仍不在本次复核所能排除的范围内。

## 修复、验证与证据

源码 `1b6e3dc` 将受限环境采集器改为保留 UTF-8 边界的分块读取，同时保留精确
输出、命令时限、stdin 处理、取消和进程清理。**410 项 Harbor 测试通过**，
另外显式启用的 **3 项** Docker 测试也通过，包括一条 **300,000 字节**的
UTF-8 长行，以及受限模型阶段缓存不存在的检查。参见
[实现验证](../../configs/pi-restricted-pipeline-recovery-v2-20261105/implementation-validation.json)。

[冻结原生事件日志的回放](../../configs/pi-restricted-pipeline-recovery-v2-20261105/native-event-replay.json)
复现了原采集器错误，并确认修复后的采集器精确保留完整输出。该检查没有调用模型。

四个已结束恢复 job 的全部 **71 个文件**在模型轨迹复核前冻结。
[冻结索引](../../configs/pi-restricted-pipeline-recovery-v2-20261105/outputs-freeze.json)
绑定四份清单。此前受限运行的 **49 个文件**及 11 月 2 日的 **326 个文件**
保持不变。[结构化结果](../../results/pi-restricted-pipeline-recovery-20261105.json)
保留所有安装错误和缺失的官方成绩。最终检查记录在
[验证证据](../../configs/pi-restricted-pipeline-recovery-v2-20261105/validation-evidence.json)。

Pi 报告 **667,185 个输入 token**，其中 **639,872 个缓存 token**，以及
**24,996 个输出 token**；共 25 条用量记录，没有缺失。估算费用为
**$0.042028332**，不是账单对账结果。没有 assistant API 错误。

本次错误后没有追加模型尝试。仓库的[重试规则](../../../../AGENTS.md)只允许
verifier 超时重试，因此额外模型尝试需要维护者明确允许例外。修复后的采集器
已通过不调用模型的测试；Pipeline 的官方结果仍未确定。

```text
Pi distribution SHA256: 60a810111c1fd9b34b59a815fb6399c6b861017e1a2278ae881bb2a563177dd9
model config SHA256: 8751fac554abb9f363b188c102045f38e36693d52956f984e0e427b31998b299
Recovery 2 release manifest SHA256: 3a132b29494bea24ec2c872a9b9c88dda059575a0bb9f2d869f9ff1c50810edb
Recovery 2 model freeze SHA256: 7597e12251e688623cd7de611404650cc5dba063b5f4eccba6c2117ea640d24d
```
