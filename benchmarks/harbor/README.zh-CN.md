# Harbor adapter

[English](README.md) | [简体中文](README.zh-CN.md)

这个独立 workspace 包含 nanoPyCodeAgent 面向 Terminal-Bench 及其他 Harbor
评测任务的 adapter。它属于开发基础设施，不是面向普通用户的
`nanoPyCodeAgent` 软件包的一部分。该 workspace 的 lockfile 将 Harbor 固定在
0.21.0。

## 运行 benchmark

设置 CLI 使用的连接凭据。使用第三方或代理 endpoint 时，配置 API key 和 base
URL；模型由下方 Harbor 命令中的 `--model` 选择：

```bash
export ANTHROPIC_API_KEY="..."
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
```

新的 benchmark 统一从仓库根目录通过标准入口运行：

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/restricted-wal.json
```

此示例固定了 WAL 题目版本，模型为 `deepseek/deepseek-flash`。请配置对应的
endpoint 和凭证；测试其他模型或题目时，复制配置并修改 `agents[].model_name`、
题目选择及预算。这是增加了 `integrity` 段的 Harbor JSON 配置，入口会补齐标准验证器、完整性和缓存策略。
入口接受本仓库的 `NanoPyCodeAgent` adapter 和预算参数，凭证通过环境变量传入。

入口会将当前工作区（包括未提交修改）构建为 wheel，并核对其 Python 源码与保存的
快照一致；同时保存 adapter 快照及源码、wheel 的哈希，整个运行都使用该快照。
输入和日志保存在 `jobs/<job-name>-input/`，Harbor 输出保存在
`jobs/<job-name>/`，不会覆盖已有运行。`summary.json` 记录评分、安装和预检状态、
缓存使用情况及验证次数。基础设施异常保留为无评分，不会转换为 0 分。
执行错误或结果不完整时命令返回非零退出码；正常完成验证得到 0 分仍是有效结果。

可用 `--job-name <unique-name>` 命名运行。`--prepare-only` 只构建并保存输入，
不启动容器；`--install-only` 只执行依赖安装和预检，不调用模型、不运行官方测试。
完整运行仍会在自己的新容器里执行安装和预检，不能把 install-only 容器续跑为解题。

### 评测完整性协议

新的标准运行必须显式配置 `integrity`：

```json
{
  "integrity": {
    "protocol": "restricted-v1",
    "allowed_hosts": ["api.deepseek.com"],
    "probe_url": "https://example.com/"
  }
}
```

Nano、Pi 和 DeepSeek Harness adapter 使用相同策略与英文完整性规则，保留各自
原生工具和模型设置。实际推理服务域名必须显式列入，入口不会静默增加 provider
端点。只接受精确 DNS 主机名；拒绝通配符、IP、CIDR、额外 agent 网络例外、
注入的 skills、恢复会话、外部工具和日志过滤。不要允许通用代码托管或搜索站点，
否则会重新开放参考答案访问。题目明确需要的数据、经过审阅的依赖或文档服务必须
事先登记具体域名。允许的服务本身仍可能暴露参考材料；白名单并不是内容分类器。

安装与已登记的依赖预检使用题目原有的公开网络。模型开始工作前，公开 HTTPS
探针必须成功；应用白名单后同一探针必须失败，同时允许的主机仍须可达。探针不
跟随重定向。正向探针失败属于基础设施错误，不能当作阻断成功。
`--install-only` 也会执行这些检查。运行边界会在原生 agent 时限内再次检查限制。
网络限制由 Harbor 的外部 egress sidecar 执行，shell 代理环境变量不是安全边界。
题目容器移除 `NET_RAW`、`NET_ADMIN`、`SYS_ADMIN`、`SYS_PTRACE` 权限，禁止
通过 setuid 程序提升权限。包括 verifier 日志在内的宿主目录不会挂载进容器。
UDP DNS 转发仅允许到 Docker 可信 sidecar 报告的精确上游解析器地址，并记录
这些地址。DNS 解析失败不会被当作 HTTPS 阻断探针成功。

第一版支持原生网络策略为公开网络的单步 Linux Dockerfile/预构建镜像任务。
自定义 Compose 服务、额外挂载、环境覆盖和题目 MCP 服务暂不支持，遇到时直接
拒绝运行。历史依赖缓存 Compose 覆盖配置仍被排除；下文的可选托管 PyPI 缓存
具有单独强制执行的生命周期。
协议保留题目镜像、软件源、官方测试、资源和原生时限。CPU、内存、存储、GPU
和 TPU 的资源覆盖配置会被拒绝；CPU 和内存的执行策略必须为 `auto`（Docker
原生限制）或 `limit`。题目缺失依赖仍按原验证器
表现分类为安装错误或任务失败；网络限制不授权修改题目。

该协议下三个 agent 都使用进程托管，取消及清理期间网络仍受限。控制器采集的
输出、网络规则快照、预检结果和 sidecar 诊断日志保存到 job 的宿主专属
`.integrity/<trial-id>/` 目录，避开 Harbor 对原生 trial 日志的改写。
输出可能含凭据，因此这些记录保持私有。它们保全已采集的
字节，但不能证明完整观察了每次工具调用或网络请求。

现有共享验证器仍是共享模式：检查进程结束边界并收集证据后，恢复其原生网络以
执行官方验证。恶意提交代码及保留的服务仍可能干预评分。已经配置独立验证器的
题目保留原有边界，adapter 记录其模式，不改写题目。现有题目的迁移、评分器内部
对提交代码的隔离、私有保留集，以及 DNS/隐蔽通道防护属于后续工作。
`restricted-v1` 阻断本次观察到的直接网络答案下载途径，并不证明能抵抗所有
对抗策略或排除训练数据污染。

对于明确登记的历史协议复现，可用原配置加 `--legacy-open-network`。这一退出
选项会记录为 `legacy-open-network`，不能与 `integrity` 合用，也不提供完整性
防护。历史配置和报告保持原样。受限协议与历史结果不应合并成可直接比较的基线。

### 冻结、复核和完整性修正成绩

完成的受限运行会自动冻结输出哈希，并将候选线索写入
`jobs/<job-name>-input/audit/audit.json`，不会自动获得完整性复核通过的成绩。
也可以显式执行相同审计：

```bash
uv run --project benchmarks/harbor python -m harbor_adapter audit \
  --job-dir jobs/<job-name> --output-dir jobs/<job-name>-input/audit
```

控制器采集的 `live-output.jsonl` 记录包含 UTF-8 文本块。解析原生 JSON 事件前，
应按各输出流的顺序拼接其 `text` 字段。分块采集可以完整保留很长的单行事件，
包括 Pi 最后的会话汇总，同时保持命令时限与取消机制不变。

输出目录必须位于 job 之外。未结束的 job、符号链接、特殊文件，以及冻结后发生
变化的证据都会被拒绝。扫描覆盖各 adapter 原生文本/JSON 日志、采集输出与网络
证据；线索只记录文件及行号，不摘录可能含凭据的原文。模式匹配仅用于初筛：
需要查看相关调用与结果，区分请求被阻断和实际获取成功，再作判断。未匹配到内容
不证明尝试干净；`clear` 表示在复核证据中未观察到违规。

复核文件须绑定 `freeze.json` 的精确 SHA256，并使用清单中的实际 trial ID 和
证据路径：

```json
{
  "freeze_sha256": "<SHA256 of freeze.json>",
  "trials": {
    "<trial-id>": {
      "verdict": "violation",
      "reviewer": "<reviewer identifier>",
      "reason": "Downloaded and used the task's reference solution.",
      "evidence": ["<trial-id>/agent/pi.txt"]
    }
  }
}
```

向审计命令传入 `--review /path/to/review.json`。结论可为 `clear` 或
`violation`；每条结论都需要复核者、理由和冻结证据。每份复核及其审计结果按
哈希另存，保留之前的决定。原始 Harbor reward 和异常不会被覆盖。确认违规的
尝试有效分数为零，并保留在分母中。待复核尝试没有有效分数；所有可评分尝试
复核完成前，不发布修正通过率。安装/verifier 错误仍不评分。原生 agent 超时
只有在取消已确认且存在官方二元 reward 时才可评分。缺失必需防护属于完整性错误。

可用已有、包含 Python 3 和 CA 证书的镜像运行不调用模型的 Docker 探针：

```bash
NANOPY_INTEGRITY_TEST_IMAGE=<image> uv run --project benchmarks/harbor pytest \
  -c benchmarks/harbor/pyproject.toml benchmarks/harbor/tests/test_integrity_docker.py
```

探针构建 Harbor 固定版本的 egress sidecar，检查允许及禁止的 HTTPS、验证无法
用 packet mark 绕过过滤，并只移除自己创建的容器。它不调用模型，也不运行
benchmark 参考解法或测试。

### 依赖缓存与预检

标准 adapter 自动使用被 Git 忽略的 `.cache/nanopy-harbor/` 跨运行共享缓存，
可通过 `NANOPY_HARBOR_CACHE` 或入口的 `--cache-dir` 覆盖。对于 APT 系统，先更新
索引并解析 SHA256 下载计划，再恢复匹配的缓存文件、下载缺失文件。下载成功后会先
校验并保存缓存，再安装，避免 APT 清理钩子删除共享副本。版本或哈希不匹配时不会
复用旧包，文件损坏会在模型调用前终止安装。其他包管理器使用 Harbor 的常规安装。

历史下载只需导入一次：

```bash
uv run --project benchmarks/harbor python -m harbor_adapter import-apt \
  /path/to/bootstrap-cache/manifest.json
```

manifest 是包含 `url`、`filename`、`size`、`sha256` 的 JSON 对象数组，同目录下
配套 `packages/<filename>` 文件。导入时逐个校验，使用时还必须独立匹配当前 APT
索引。也可将整个共享缓存复制到其他机器。新机器没有匹配缓存时仍依赖原下载地址
可用；此机制不会更换软件源或伪造缺失版本。

验证器依赖预检配置位于 `src/harbor_adapter/bootstrap.py`，绑定已检查的题目版本。
目前 QEMU 配置会安装 `sshpass`，并通过 `pytest --version` 预热原验证器所需的
uv 0.9.5、Python 3.13、pytest 8.4.1 和 pytest-json-ctrf 0.3.5，不执行题目断言或
参考解。未知的 QEMU 版本会在安装阶段报错，要求先检查对应预检配置；没有预检配置
的其他题目明确记录为 `not_configured`。其他题目需要预检时，在这里新增配置及回归测试。

已检查的 `pytorch-model-recovery` 版本也有仅准备依赖的配置。它使用原始 uv 0.9.5
安装器和验证器所需的 Python 3.13、pytest 8.4.1、torch 2.7.1、pytest-json-ctrf
0.3.5，随后仅在 `/tmp` 执行 `pytest --version`。它不导入提交的模型，也不运行
题目测试。其他题目版本需要重新检查对应配置。

已检查的 `multi-source-data-merger`、`pytorch-model-cli`、`query-optimize`、
`torch-pipeline-parallelism` 和 `torch-tensor-parallelism` 版本也有仅准备依赖的
配置。它们保留各自原始脚本的 Python 版本、软件包版本、APT 依赖和索引选项，
仅在 `/tmp` 运行 `pytest --version`。其中仅 CLI 配置添加原脚本中的 PyTorch
CPU 索引和 `unsafe-best-match` 策略；其他 PyTorch 配置保留原始默认索引。
每个新检查的配置都记录题目元数据与验证器脚本的哈希。

每次安装都会写入 `agent/bootstrap.json`，失败时也保留已完成的步骤。预检失败会
在模型调用前终止 trial。官方验证脚本保持原样，执行时仍可能访问网络，所以预检
通过不能保证后续没有网络故障。完整标准运行默认启用下述验证超时重试，整题重试
次数为零。CI 会验证这些约定，不调用模型、不启动 Docker。

### 校验后的 PyPI wheel 传输

已有经审查 verifier 依赖 profile、且使用共享 verifier 的受限运行，可以添加
以下顶层设置来启用托管缓存：

```json
{"dependency_cache": "pypi-verified-v1"}
```

标准入口会对现有缓存脚本建立快照并记录哈希。控制器在依赖预检期间启动临时
辅助容器，在网络预检之前移除它，并在模型边界再次确认辅助容器及其本地回环
监听端口均不存在。只有未经修改的官方 verifier 命令才能在确认 agent 进程
停止后重新开启缓存。取消时也会移除辅助容器；无法确认清理成功则终止运行。
模型工作期间不存在缓存服务，主机白名单保持不变。不会向题目容器挂载宿主目录。

辅助容器使用此前已审查、固定 digest 的
`alexgshaw/pytorch-model-cli@sha256:c996884b5fb5fb2c0c07d67da2c4f974f271f07234ed28e1a868240375c57a67`
镜像，该镜像必须已存在于 Docker 中。它只接收只读脚本快照和共享 wheel 缓存，
禁用全部 capabilities 和权限提升，并限制为一个 CPU、512 MiB 内存。
题目自身的镜像与资源保持不变。PyPI 传输环境变量仅用于依赖预检和官方验证；
`UV_HTTP_TIMEOUT=600` 仍受已登记的各阶段时限约束。软件包选择仍依据原始 PyPI
当前元数据。所有受支持 agent 共用同一准备流程。

部分安装输出、缓存元数据/命中日志、辅助容器标识、脚本哈希及清理记录均保存在
宿主专属 `.integrity/<trial-id>/` 目录。完整性计分要求两个阶段都有清理证据，
并具有模型边界处缓存不存在的检查记录。官方 verifier 仍是共享环境；该缓存
不会建立独立评分边界。目前未知依赖 profile 和独立 verifier 均拒绝此选项。

如需同时复用经校验的原始 uv 和托管 Python 发行包，先按照下文说明使用
`uv_release_cache.py prepare` 准备新清单，再采用以下配置：

```json
{
  "dependency_cache": {
    "protocol": "pypi-verified-v1",
    "release_manifest": "/path/to/registered/dependency-release-manifest.json"
  }
}
```

清单与脚本一起复制并记录哈希。同一个辅助容器以只读方式挂载 `uv-releases`
缓存，在原有回环端口提供已登记的发行包。每个归档均按原始 GitHub 发布元数据
中的文件名、大小和 SHA256 校验；未登记的版本仍使用原始 GitHub URL。
仅安装和官方验证阶段会收到 `UV_INSTALLER_GITHUB_BASE_URL` 与
`UV_PYTHON_INSTALL_MIRROR`。原始安装脚本、uv 的 Python 版本选择和模型网络
策略均保持不变。发行包缓存请求记录在对应阶段日志中。

原有独立服务仍可用于明确登记的历史协议；不得将其接入受限模型执行阶段：

```bash
python benchmarks/harbor/scripts/pypi_wheel_cache.py \
  --cache .cache/nanopy-harbor/pypi-ranges --bind 127.0.0.1 --port 18744
```

Docker 题目中，让 sidecar 与题目共享网络命名空间，并仅向 sidecar 挂载缓存。
在题目环境中注册 `UV_DEFAULT_INDEX=http://127.0.0.1:18744/simple`。
服务始终获取当前 PyPI 索引元数据，保留所有版本、依赖要求、撤回标记、哈希和
额外索引设置，仅将 wheel URL 指向回环缓存。源码分发 URL 与 PEP 658 元数据
内容保持原样，元数据每次从上游转发。每次 wheel 请求都先根据当前 PyPI 发布
元数据重新核对文件名、大小、SHA256 和原始 HTTPS URL，再恢复缓存内容。
元数据不可用或文件损坏时直接失败，不使用离线或替代软件源。

首次请求的 wheel 会先完整下载并校验，再返回内容。应在单独注册的安装时限
范围内设置合适的 uv HTTP 等待时间（例如 `UV_HTTP_TIMEOUT=600`）。原生
agent 和验证器时限保持不变。

已有的有界分段下载器会校验每个范围及整个 wheel 的摘要。文件锁保护多个
题目 sidecar 之间的缓存发布。模型运行前应注册传输配置及脚本，执行仅依赖
预检，并保留原始题目镜像、脚本、软件包版本、来源以及每次 agent / 验证器时限。

使用 `--audit-log /cache/run-events.jsonl`，可在 sidecar 退出后保留当前发布
元数据及已校验的缓存命中事件。追加日志使用跨进程锁，并记录来源容器实例。

### Pi agent baseline

同一个标准入口也支持 `harbor_adapter:PiCodeAgent`。在 agent kwargs 中用
`distribution_path` 和 `distribution_sha256` 注册本地未修改的 Pi 二进制发行包，
用 `model_config_path` 指定公开模型配置，并可选设置 `thinking`。
摘要覆盖发行包内每个文件及其权限。工作流会在共享缓存中保存一份按内容寻址的
发行包快照，安装前再次校验，并为每个任务记录文件清单与公开模型配置。
Pi 使用原生提示词、工具、上下文压缩和重试行为；不会构建或安装 nanoPyCodeAgent wheel。

目前该 adapter 支持 DeepSeek 官方 OpenAI 兼容 API。公开模型文件必须引用
`${DEEPSEEK_API_KEY}`，真实密钥通过进程环境提供。个人 Pi 配置、扩展、skills
和历史会话不会复制到任务环境。禁用模型目录自动更新，以保证已记录的配置可复现。
仅安装检查会验证实际二进制和模型注册，不调用模型，并沿用相同的已审阅 verifier
依赖 profile。原生会话及完整事件保存在 `agent/pi/` 和 `agent/pi.txt`。
即使 Pi 返回零退出码，模型加载诊断也会导致检查失败；离线列表必须包含请求的
provider/model。同一任务中多个 Pi agent 的不同公开配置会分别保存为不可变的
任务本地文件，清单记录各自的 `model_config_file` 和摘要。并发准备会复用其他
进程已发布且通过核验的分发包，成功或失败后均清理暂存目录。
用量统计在 Pi 提供数据时包含上下文压缩；费用为估算值，缺失用量会单独标注。
Pi 目前不生成 ATIF trajectory。
失败的 assistant 流即使随后通过原生重试成功，其初始化的零用量仍视为未知。
保留已知 token 和费用小计，并对缺失用量或费用设置不完整标记。
在 Linux 上，Pi 命令由 child subreaper 托管。取消执行时，运行器会先停止整个
进程树（包括工具创建的独立会话），再将控制权交回 Harbor。正常完成的任务仍可
保留有意启动的后台服务。设置 `verifier.kwargs.require_agent_quiescence=true`
后，执行官方断言前必须有正常完成或已确认取消的进程托管记录；记录缺失或不完整
时停止评分。安装检查会在不调用模型的前提下验证运行器；中断执行的用量和费用
总计会标记为部分数据。

比较运行器支持 Pi arm，以及先安装检查、再执行模型队列的 `--phase all`。
注册的 `minimum_free_disk_bytes` 会在空间不足时阻止启动新任务。
已有任务和失败尝试均保留。各 agent 的预算差异必须在实验中说明，不能假设原生默认值相同。
Docker 空间受限时，可以通过 `batch_images` 计划按批恢复已注册 repository digest
对应的镜像、验证镜像身份，并仅清理本轮初始清单中不存在的镜像引用。
运行器会检查 Docker 实际存储分区，且不会强制删除镜像或容器。

首份 [Pi + DeepSeek Flash dev34 报告](reports/zh-CN/pi-deepseek-flash-dev34-20261024.md)
保留了全部 34 次尝试、进程托管修正、两次不评分的旧超时、公开参考材料接触和
不完整用量统计，不宣称完整且无答案接触的 34 题通过率。

经授权的[三题 Pi 重跑](reports/zh-CN/pi-deepseek-flash-dev3-rerun-20261102.md)
记录了两次官方通过，以及一次超时后确认停止的计分失败。两次新的通过都访问了
公开参考解法和测试，均不属于独立解题。原始结果保持不变。本次重跑还修复了
Harbor 返回缺失输出流时 Pi 安装检查失败的问题。

[受限网络下的两题后续检查](reports/zh-CN/pi-restricted-dev2-20261104.md)
在模型工作期间仅将 DeepSeek API 主机加入白名单。WAL 通过全部七项官方测试，
在已审查证据中未观察到完整性违规。Pipeline 在任何模型调用之前的依赖准备阶段超时，
因此该轮未能测试其在受限网络下的行为。历史结果仍单独保留。

[Pipeline 依赖恢复](reports/zh-CN/pi-restricted-pipeline-recovery-20261105.md)
使用经校验的 wheel 和原始 uv/Python 缓存，将全新容器安装缩短到 142.791023 秒；
模型阶段缓存服务不存在。未观察到 Pi 获取外部答案，但很长的最终 JSON 事件使
Harbor 输出采集器在官方验证之前出错。采集器现已修复并通过测试；Pipeline
仍未评分，报告保留本地搜索行为的限定说明和所有失败尝试。

### DeepSeek Harness baseline

`harbor_adapter:DeepSeekHarnessAgent` 使用上游 Python SDK 的 `sdk-minimal`
配置运行，这是 DeepSeek Harness 的 `BENCHMARK.md` 推荐的基准配置。
在 agent kwargs 中注册 `distribution_path`、`distribution_sha256` 和可选的
`reasoning_effort`（默认为 `high`）。分发目录包含离线 `wheels/` 目录，内有
SDK、原生运行时以及所有 Python 依赖；另有 `distribution.json`，记录
`version`、`source_commit`、`source_archive_sha256`、`sdk_wheel` 和
`runtime_wheel`。摘要覆盖每个文件及其权限；标准流程会保存快照并重新校验。

按照选定上游检出的 Python 贡献者文档构建运行时和 SDK。任务安装使用
Python 3.13 和冻结的 wheel 集合。仅安装检查会初始化真实 SDK 配置和模型，
但不发送任务提示，并执行已有的验证器依赖预检。模型执行需要
`DEEPSEEK_API_KEY`，使用官方 Messages 端点。每道题都使用全新的 Harness
目录与会话，保留上游提示词、工具、上下文压缩、重试及生成默认值。原生日志
保存在 `agent/dsh/`，SDK 事件、完成状态和诊断信息保存在旁边。

配置必须设置 `verifier.kwargs.require_agent_quiescence=true`。
共享的 Linux 进程监督器在验证前确认 agent 进程树已被取消。SDK 返回非
`completed` 的结束原因时记为执行错误。报告的 token 包含原生助手消息和
压缩请求用量；缺失记录和中断运行仍标记为部分统计，费用保持未知。
此 baseline 不强制套用 Pi 的生成设置或 Nano 的轮数和工作时间预算。

首份[官方 Harness dev34 报告](reports/zh-CN/deepseek-harness-dev34-20261030.md)
在 Pi 已使用的 34 道题上记录了 22 道通过、六道计分失败、六道因错误不计分。
固定版本的上游运行时在正常关闭 SDK 时会停止托管的后台服务，包括探针中
通过 `nohup` 启动的服务。这会影响服务题：KV 和 PyPI 在 agent 自测成功后，
官方检查仍然失败。报告保留这些失败，并记录了
[无密钥生命周期探针](scripts/probe_deepseek_lifecycle.py)。这些结果衡量的是
注册的 SDK 配置。

另行授权的[六题补测](reports/zh-CN/deepseek-harness-dev6-supplement-20261101.md)
使用经过审核的依赖预检和经过校验的原始 PyPI wheel 下载通道，重跑未计分题目：
四题通过、两题失败，无剩余未计分项。原始结果保持不变。将原始 28 次有效尝试
与这六次新尝试结合，得到 26 题通过、八题失败的混合覆盖；这种根据原始结果
选取的补测不构成独立基准。

### 缓存原始任务镜像

如果 Docker 拉取镜像反复停滞，可用缓存工具从同一 Docker Hub 公共仓库分段并行下载：

```bash
python benchmarks/harbor/scripts/cache_image.py \
  alexgshaw/git-multibranch:20251031 \
  --cache .cache/nanopy-harbor/images --load
```

首次请求记录仓库的 manifest 摘要；后续请求若发现 tag 指向的摘要改变，会拒绝继续。
每个下载对象都必须匹配大小和 SHA256，每层解压后的摘要也必须匹配原始镜像配置。
生成的 [OCI 归档](https://github.com/opencontainers/image-spec/blob/main/image-layout.md)
逐字节保留原始 manifest、配置和压缩层；Docker 导入后必须保留原始仓库摘要。

该 Linux 工具支持使用 gzip 层和 SHA256 描述符的公共 `linux/amd64` 镜像。
对于 OCI index 和 Docker manifest list，会保留未修改的父索引及唯一的本机平台
镜像 manifest，只下载该平台的层。本机镜像关联的 attestation 会保留原始 manifest、
配置和 in-toto payload，并逐个校验摘要。其他平台及其 attestation 仍由原始索引引用，
但不会下载它们的 blob。Docker 显式加载本机平台，并且必须保留原始父索引的仓库摘要。
`--load` 需要 Docker 的 containerd 镜像存储及按平台导入能力。
同一缓存目录同时只允许一个写入进程；
`--workers` 控制分段请求并发数，默认 8、最多 16。下载中断后可复用已完成的对象和分段，
完整对象会重新校验。请将 manifest 锁定记录纳入实验的证据归档。
这个步骤只准备 Docker 镜像缓存；随后仍需使用标准 benchmark 入口并执行安装预检，
之前出现的环境启动失败应单独保留。

大镜像传输会在匿名 registry 令牌到期前刷新令牌，并在收到 HTTP 401 后刷新一次。
中断的传输会复用已保存的分段，导入前仍校验完整 blob 摘要。
HTTP 错误仅报告状态码，不暴露带签名的 URL。

### 缓存不可变的 APT 索引

如果原始 APT 索引下载反复停滞，可用可选的宿主机代理，通过校验过的并行分段请求
获取 `/by-hash/SHA256/<digest>` 不可变索引：

```bash
python benchmarks/harbor/scripts/apt_index_proxy.py \
  --bind 172.17.0.1 --port 18742 \
  --cache .cache/nanopy-harbor/apt-indexes --workers 16
```

地址应使用本机实际的 Docker 网桥地址。通过 Docker 的 `extra_docker_compose`
登记只读 APT 配置挂载，以 `Acquire::http::Proxy::<原始主机名>` 分别指定代理。
[34 题实验登记](configs/dev34-main-baseline-20261012/README.md) 提供了示例。
不要设置全局代理环境变量，模型 API 和非 APT 工具应保留正常的网络路径。

代理仅允许原始公共 Debian/Ubuntu APT 主机。索引必须通过精确分段、大小和完整
SHA256 校验后才能提供给客户端；缓存命中也会重新校验哈希。可变的 release 元数据
和软件包下载直接转发、不由代理缓存。APT 仍校验签名元数据及当前软件包哈希。
软件源、任务镜像和测试脚本保持原样。预检及模型运行期间需保持代理运行，将挂载
文件与工具哈希登记进实验计划，并保留之前的安装失败记录。

如果容器无法访问宿主机监听端口，可将该工具运行在独立辅助容器中，设置
`network_mode: service:main`，绑定 `127.0.0.1`，并配置就绪健康检查。上述登记示例
采用这一方式。辅助容器只挂载代理代码和索引缓存，不共享题目文件或凭据。多个
代理进程通过按摘要划分的文件锁协调缓存写入；此模式不需要宿主机代理进程，也
不向宿主机发布端口。

### 缓存原始 uv 发布压缩包

如果官方 uv 安装器反复遇到 GitHub 下载不完整，可按公共发布索引缓存对应的原始版本：

```bash
python benchmarks/harbor/scripts/uv_release_cache.py prepare \
  --cache .cache/nanopy-harbor/uv-releases \
  --manifest /path/to/new-run/uv-release-manifest.json \
  --version 0.9.11 --version 0.9.5
```

工具要求压缩包匹配 GitHub 发布元数据中的文件名、大小和 SHA256，通过分段及完整
文件校验后才接受，并按内容哈希保留原始元数据。已有 manifest 不可覆盖。目前只准备
`x86_64-unknown-linux-gnu` 压缩包，题目镜像保持原样。

在共享 `service:main` 网络命名空间的回环辅助容器中运行
`uv_release_cache.py serve --cache /cache --manifest /manifest.json`，配置就绪健康
检查，并以只读方式挂载缓存和 manifest。在题目容器中仅设置官方安装器支持的
`UV_INSTALLER_GITHUB_BASE_URL=http://127.0.0.1:18743` 环境变量。安装脚本、版本、
软件包内容及正常模型流量保持原样。已登记压缩包在提供下载前重新校验；未缓存的
uv 版本或平台重定向至其原始 HTTPS GitHub 地址。在模型运行前登记此下载配置、
工具、manifest 和原生预检证据；缓存不代表未配置的验证器依赖已通过预检。

若已观察到 uv 管理的 Python 下载失败，可将对应原始构建及文件名加入新的 manifest，
例如 `--python-build 20251014
--python-asset cpython-3.13.9+20251014-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`。
同样按原始 `astral-sh/python-build-standalone` 发布元数据校验。将官方文档中的
[`UV_PYTHON_INSTALL_MIRROR`](https://docs.astral.sh/uv/configuration/environment/#uv_python_install_mirror)
设置为 `http://127.0.0.1:18743/astral-sh/python-build-standalone/releases/download`。
这只改变下载路径，保留 uv 原来的 Python 版本选择和压缩包内容。未缓存的 Python
构建重定向至其原始 GitHub 地址，不替换 uv 内置的 Python 下载索引。

### 直接调用 Harbor

开发 adapter 或对照已发布版本时，仍可使用底层 Harbor 入口，并固定容器内 agent 版本：

```bash
uv run --project benchmarks/harbor harbor run \
  --task terminal-bench/openssl-selfsigned-cert \
  --agent harbor_adapter:NanoPyCodeAgent \
  --agent-kwarg git_ref=<commit-sha> \
  --model anthropic/claude-sonnet-4-6 \
  --verifier harbor_adapter:RetryingVerifier \
  --verifier-timeout-multiplier 4 \
  --env docker \
  --n-concurrent 1 \
  --n-attempts 1
```

如需安装已经发布到 PyPI 的版本，请使用
`--agent-kwarg version=<released-version>` 代替 `git_ref`。这两个版本参数互斥；
如果都未提供，adapter 会安装最新发布版本。为了让 benchmark 结果可复现，请始终
提供其中一个参数。`git_ref` 最好使用完整的 40 位 commit SHA；Harbor 可能把
`83e6271` 这样的无引号短 SHA 解析成数字。如果需要使用短 revision，请通过
`--agent-kwarg 'git_ref="83e6271"'` 保留其字符串类型。

adapter 通过 stdin 发送任务指令，在 task 容器的当前目录中运行 agent，并把合并后
的 stdout/stderr 保存到 `/logs/agent/nanopycodeagent.txt`。它默认沿用 CLI 的 50
轮限制；可以通过 `--agent-kwarg max_turns=20` 覆盖此设置。

可用 `--agent-kwarg time_budget_seconds=N` 限制解题时间，并在时间或轮数接近耗尽时
提醒模型收尾。预算应落在每题原生时限内，至少预留 30 秒费用补查时间，以及轨迹写入
和 harness 开销。例如，本轮原生 3600 秒的针对性实验使用 3420 秒；该值不能用于
900 秒题目。adapter 不会自动推导时间预算。

每次回复的生成上限可通过 `--agent-kwarg max_tokens=32768` 指定，它会转换为容器内的
`--max-tokens 32768`，优先于透传的 `ANTHROPIC_MAX_TOKENS` 环境变量。未指定时，
adapter 不添加该 flag，沿用已安装 agent 的环境变量／配置文件／默认值（引入该参数的
版本默认为 32768）。安装旧版本时需省略新参数。生效预算会记录到启动日志和 ATIF
trajectory 的 `agent.extra.max_tokens`。

adapter 还会要求 agent 将 ATIF-v1.7 trajectory 直接写入
`/logs/agent/trajectory.json`。Harbor 会把该文件作为 trial 的原生 ATIF 输出采集，
并将 prompt、completion、cache token 和 cost 汇总回填到 agent result。trajectory
缺失、无效或指标不完整时会保留明确诊断；未知 usage 或 cost 不会被记成零。
只要费用中包含估算，`final_metrics.extra` 就会记录 `cost_is_estimated: true`，
并通过 `estimated_cost_usd` 单独记录估算部分的金额。adapter 会将这两个字段保留到
agent result 的 `metadata.trajectory`，费用仅部分已知时也一样。带 generation ID
的估算费用仍会进行账单补查；补查成功后，真实费用会替换估算值。

默认情况下，adapter 会移除 `--model` 中的第一个 provider 前缀，并将结果作为
`ANTHROPIC_MODEL` 传给 nanoPyCodeAgent。只有自定义 endpoint 要求的实际模型名与
Harbor 的 `provider/model` 身份不同时，才显式设置 `ANTHROPIC_MODEL`；该覆盖值优先。
Harbor 原生的 provider 凭证和已经配置的 base URL 也会转换为 nanoPyCodeAgent SDK
所需的 `ANTHROPIC_*` 变量。

## 验证器超时重试

上面的示例使用 `harbor_adapter:RetryingVerifier`，适用于单阶段 Linux 题目。
原始测试脚本**总共最多执行 3 次**，仅当脚本超过题目原生的
`[verifier].timeout_sec` 时才重试。900 秒时限的题目，每次仍最多执行 900 秒。
验证完成后立即停止，包括得分为 0 的情况。脚本错误、评分缺失或格式错误、取消执行
都不会触发下一次尝试。

`--verifier-timeout-multiplier 4` 为 Harbor 外层时限预留 3 次尝试以及上传测试、
清理进程和收集日志的时间，不会延长每次测试脚本的时限。如果其他超时覆盖或上限
导致总时间不足，会报错。可用 `--verifier-kwarg max_attempts=2` 将总尝试次数设为
2 次，或用 `max_attempts=1` 只执行一次；不允许设置为超过 3 次。

重试复用同一容器、agent 产物和依赖缓存，agent 只运行一次。测试脚本需要能够在该
环境中重复执行，验证过程对文件系统的修改不会回滚。超时后会先终止测试进程组以及
同一 Linux session 中的其他进程，再开始下一次尝试。每次日志及评分文件归档到
`verifier/attempts/1/`、`2/`、`3/`。下一次尝试开始前会清理当前验证输出，避免旧
评分被误用。`verifier/retry-summary.json` 记录每次状态、耗时及可用的退出码。
所有尝试均超时后，仍以 Harbor 的 `VerifierTimeoutError` 结束。

容器需要 `python3` 和 `bash`，nanoPyCodeAgent adapter 会安装它们。这些选项用于
新运行，无法恢复旧 trial 已删除的容器或缺失的任务产物。Harbor 原生的
`--max-retries` 会重新执行整道题（包括 agent），与这里的验证尝试次数相互独立。

对单独授权的基础设施恢复运行，可显式设置验证器参数
`retry_dependency_errors=true`。这也会重试 pytest 启动前识别到的 uv 网络下载
错误，复用同一容器和 agent 产物，保留原生单次时限，总尝试次数仍最多为 3。
只要已有 CTRF 报告、pytest 执行输出或成功评分，就不会进行这种恢复；有效的失败
评分也会立即停止。依赖错误耗尽尝试后抛出 `VerifierDependencyError`，保留每次
证据并清除当前评分。默认仍只重试超时；实验计划应记录授权和实际选用的策略。

对单独授权的 pytest 收集失败恢复，还可设置
`retry_collection_errors=true`。它只重试尚未运行任何测试用例时明确发生的收集中断。
成功评分、已执行的测试用例或含义不明确的 CTRF 报告都会阻止这种恢复。耗尽次数后
抛出 `VerifierCollectionError`，保留归档评分，但不发布当前评分。默认值为 false，
与超时及依赖恢复共享最多三次的尝试上限。

如果之后可能需要继续验证，应设置 Docker 的
`environment.kwargs.keep_containers=true` 保留已停止的任务容器，并在 `artifacts`
中登记 `/app` 等解答路径。仅设置 `environment.delete=false` 仍会删除 Docker
容器。Harbor 会在验证前收集已登记的文件。
将产物清单和文件哈希与运行证据一起保存；仅有轨迹无法保留二进制文件和原始系统状态。

对于明确授权、使用已保留 Docker trial 的额外 verifier 批次，可通过仓库入口执行，
无需启动 agent：

```bash
uv run --project benchmarks/harbor python -m harbor_adapter verify-retained \
  --trial-dir jobs/example/task__trial \
  --task-dir /path/to/the/original/task \
  --container task__trial__env-main-1 \
  --output-dir jobs/example-additional-verifier-batch
```

原项目的所有服务必须处于停止状态。该命令启动原来的容器，等待服务健康检查通过，
核对冻结的 `/app` 产物和原始测试的哈希，并使用题目原生时限执行最多三次尝试。
可选的 `--retry-dependency-errors` 和 `--retry-collection-errors` 标志与对应的
verifier 参数一样，需要单独授权。任何已完成的评分都会结束该批次，包括得分为 0。
原 trial 日志会暂存在保留容器内，并在结束后恢复。新增尝试日志、执行源码、策略、
哈希和完整性检查写入单独的输出目录。批次结束后，容器会被停止并继续保留。
该命令不会修改原 trial 的结果，也不会自动授权后续重复批次。

若要为保留解答的依赖准备单独分配时间，可添加 `--dependency-timeout-sec 3600`。
这要求精确题目版本已有检查过的依赖配置，并核对其中登记的任务文件哈希。依赖准备
在同一容器中、正式验证前执行一次，日志和状态单独记录到 `dependency-preparation/`。
准备超时或以非零状态退出时，结果为安装失败、不评分，也不会启动正式验证。准备
成功后，保持原样的官方验证脚本按原生单次时限执行（`pytorch-model-recovery` 为
900 秒）。脚本内剩余的依赖检查仍计入这 900 秒。更长的准备时限不会延长正式验证
时限。即使解答相同，也应将这一准备策略与先前 baseline 分开记录。

## Benchmark 报告

报告提供[英文](reports/en/)和[简体中文](reports/zh-CN/)两个版本，文件名一一对应。
新增或更新报告时，应同时生成或刷新两个完整版本，保留全部结果和证据引用。
原始运行证据保留在由 Git 忽略的 `jobs/`，机器可读结果仍放在 `results/`。

## 测试 adapter

```bash
uv run --project benchmarks/harbor pytest \
  -c benchmarks/harbor/pyproject.toml \
  benchmarks/harbor/tests
```
