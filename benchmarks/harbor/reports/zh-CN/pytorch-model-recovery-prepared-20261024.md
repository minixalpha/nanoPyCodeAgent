# PyTorch 模型恢复：单独准备依赖后的验证

日期：2026-10-24。本次经过授权的追加实验复用
[10 月 20 日补充实验](dev34-flash1017-recovery-20261020.md)中冻结的
`pytorch-model-recovery__nCs7Y4H` 解答，接续
[10 月 21 日 verifier 追加验证](pytorch-model-recovery-verifier-20261021.md)。

**保留解答通过了全部 5 项官方测试，得分为 1.0。** 依赖准备用时 1,127.589 秒，
超过了原来的 900 秒限制。随后，保持原样的官方验证器在原有 900 秒时限内，用
49.934 秒完成验证。本次没有调用模型，也没有重新生成解答。

| 阶段 | 独立时限 | 实际耗时 | 结果 |
| --- | --- | --- | --- |
| 依赖准备 | 3,600 秒 | 1,127.589 秒 | 成功；依赖已安装，`pytest --version` 成功 |
| 官方验证 | 900 秒 | 49.934 秒 | 成功；得分 1.0；5 项测试通过 |

pytest 会话本身报告耗时 5.00 秒。验证器的 49.934 秒还包括原脚本中的 APT 索引
更新、uv 安装器和剩余依赖检查。这些步骤均未被删除，也没有获得额外时间。
依赖准备和正式验证各执行一次。这是该解答的第 7 次 verifier 尝试，之前 6 次均
未进入 pytest。

## 官方测试结果

| 测试 | 结果 |
| --- | --- |
| `test_weights_file_unchanged` | 通过 |
| `test_model_file_exists` | 通过 |
| `test_model_loads_weights` | 通过 |
| `test_state_dicts_match` | 通过 |
| `test_model_loss` | 通过 |

没有失败或跳过的测试。pytest 输出了两项不影响通过的警告：NumPy 不可用，以及
Transformer 的布局未启用嵌套张量优化。依赖要求保持不变。

## 准备策略与实现

新增的 `--dependency-timeout-sec 3600` 选项使用已检查的
`pytorch-model-recovery-v1` 配置，绑定题目版本
`sha256:2e628841cff93290919172398e573e794f34c95d9382b7425adde4364022decc`。
它核对已登记的题目配置及测试脚本哈希，使用原始 uv 0.9.5 安装器，以及 Python
3.13、pytest 8.4.1、torch 2.7.1 和 pytest-json-ctrf 0.3.5 的原有依赖要求，仅在
`/tmp` 执行 `pytest --version`。它不导入提交的模型，也不执行题目断言。

若准备失败，会记为安装失败，不评分，也不进入官方验证。准备成功后，才启动独立
的原生 verifier 时限；3,600 秒的准备预算不会延长该时限。原始任务镜像、资源、
包来源和官方脚本均被保留。原生测试日志记录的版本为 Python 3.13.12、pytest
8.4.1、pluggy 1.7.0 和 pytest-json-ctrf 0.3.5。

实际执行的实现提交为 `f7383dd69cec928ce61e12c49f3850c2edb34be5`。原解答生成时
使用的核心 agent 提交为 `ce28b1e826a292d796ba64f13e79199b66f65758`，运行时提交为
`40fdd041c370a96dc06f86b436eacc01ce1566d7`。冻结的 `/app/model.pt` SHA256 仍为
`098642cbf41010a7fab7a9cf32995b49300cc3ccb1d724e7d57d729330f0bb4e`。

## 完整性与比较限制

本次使用同一保留容器和同一份解答。冻结解答和测试的哈希在执行前后均通过核对，
原 trial 文件已逐字节恢复。项目的 3 个容器均已停止并继续保留，身份不变，也没有
容器 OOM 标记。临时迁移的 50 个重复镜像缓存文件已全部恢复，并通过 SHA256 校验。
已准备完成的依赖环境继续保留。本地 Harbor 测试套件 **209 项通过**，覆盖独立
时限、准备失败时阻止验证，以及证据恢复。

这一准备策略改变了评估环境；实时依赖解析及缓存状态也限制了可比性。10 月 19 日
baseline 仍为 **26 题成功、5 题有效评分失败、3 题 verifier 错误未评分**。
10 月 20 日和 10 月 21 日记录均保持不变。本次通过结果单独记录，不替换旧结果，
也不生成混合后的 dev34 分数。新增模型调用次数和模型费用均为零。

- [机器可读结果](../../results/pytorch-model-recovery-prepared-20261024.json)
- [已登记的依赖准备与验证计划](../../configs/pytorch-model-recovery-prepared-20261024.json)
- 本地证据：`jobs/pytorch-model-recovery-prepared-20261024/`，包括分开的依赖准备与
  verifier 日志、CTRF 测试结果、实际执行的源码、源码和产物哈希、完整性检查及
  容器保留记录。
- 在新批次前后，实时的当前 verifier 日志可能属于原 trial；本结果以单独归档的
  新批次日志为准。
- [完整英文版本](../en/pytorch-model-recovery-prepared-20261024.md)
