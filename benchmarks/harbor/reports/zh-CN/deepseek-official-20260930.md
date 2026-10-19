# DeepSeek 官方端点 pilot20

将 20 题 pilot 集从 OpenRouter 切换到 DeepSeek 官方兼容 Anthropic 的端点，使用
`deepseek-flash` 重新运行。结果为 **18 次计分试验中通过 16 次**（Harbor 均值
0.80）；另有两次试验因基础设施故障而未能计分，并非模型失败。

完整配置、逐次用量、按 token 估算的费用和余额快照见
[公开结果](../../results/tb21-deepseek-official-pilot20-20260930.json)。原始证据保留在
记录中指定、由 Git 忽略的 `jobs/` 目录内。

## 配置

| 设置 | 值 |
| --- | --- |
| 作业 | `tb21-deepseek-official-pilot20-20260930` |
| Agent | `e75cacb6`（`0.8.1.dev45`），在本地构建并验证的 wheel |
| 端点 | `https://api.deepseek.com/anthropic`（Anthropic Messages） |
| 模型 | `deepseek-flash` |
| 任务 | 固定版本的 20 题 pilot 集 |
| 预算 | max_turns 100，max_tokens 65536，每题 agent 预算为原生时限减 180 秒 |
| 并发 / 尝试次数 / 重试次数 | 2 / 1 / 0 |
| 提供商固定 / HTTP 录制器 | 无——唯一变化是提供商 |

## 结果

| 分类 | 数量 |
| --- | ---: |
| 计划试验 | 20 |
| 计分试验 | 18 |
| 通过 | 16 |
| 奖励为 0 | 2 |
| 基础设施异常 | 2 |
| 计分试验通过率 | 88.9% |

- 奖励为 0：`torch-tensor-parallelism`、`pytorch-model-recovery`。
- `qemu-alpine-ssh`：agent 设置阶段获取固定版本的 Debian 包时遇到 HTTP 404；
  未发生模型调用。
- `torch-pipeline-parallelism`：agent 已完成，但官方 verifier 超过其原生 900 秒时限。

Token 用量：prompt 30,933,108（缓存 30,586,240，未缓存 346,868），completion
891,020。

## 无提供商费用 API 时的费用估算

DeepSeek 官方 API 返回 token 用量，但没有逐请求费用、generation id 或用量/计费
端点：`usage.cost` 和 `x-generation-id` 均不存在，`/v1/generation`、`/user/usage`、
`/billing/usage` 和 `/pricing` 均返回 404。因此，之前的 OpenRouter 对账路径无法
解析 DeepSeek 费用。

本分支新增**基于 token 的估算器**（见“实现”），按静态 DeepSeek 价目表计算返回
token 的费用（每百万 token 的美元价格：输入 0.3、缓存读取 0.006、缓存写入 0、
输出 1.2）。结果标记为 `kind: estimated`，以便与提供商返回的费用区分。

| 项目 | Token 数 | 单价 | 费用（美元） |
| --- | ---: | ---: | ---: |
| 未缓存输入 | 346,868 | 0.3 | 0.104060 |
| 缓存读取 | 30,586,240 | 0.006 | 0.183517 |
| 输出 | 891,020 | 1.2 | 1.069224 |
| **合计** | | | **1.356802** |

账户余额变化（`/user/balance`，¥106.63 → ¥102.01）仅记录为上界：运行期间交互式
助手会话使用了同一账户，因此它不是隔离的单次运行费用，且其币种为人民币。

## 实现

- `cost.py`：新增 `estimated_cost(model, usage)` 和静态 DeepSeek 价目表；
  `agent.py` 仅在 `usage_cost` 未能取得费用后才使用估算，因此提供商明确返回的
  费用始终优先。
- `harbor_adapter`：系统依赖的 `apt-get` 事务遇到暂时性 HTTP 404 时，重试一到
  两次再判定设置失败。后续 qemu 重跑在第 1/3 和 2/3 次尝试中触发了重试，但
  固定的 `bullseye-security` 索引指向已下架的 `.deb` 版本，因此该 404 必然发生，
  仅靠重试无法修复此任务。历史修复方案是从原始 APT 索引预加载经过验证的
  `.deb` 缓存。

## 比较限制

OpenRouter pilot20 运行使用了提供商固定、不同的快照日期和不同的观测工具，
而本次运行还存在两项基础设施异常。因此，这是一份提供商切换记录，不能作为
受控的因果比较。
