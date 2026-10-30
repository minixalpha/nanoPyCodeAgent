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
export ANTHROPIC_BASE_URL="https://gateway.example"
```

新的 benchmark 统一从仓库根目录通过标准入口运行：

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/qemu-alpine-ssh.json
```

此示例固定了 QEMU 题目版本，模型为 `deepseek/deepseek-flash`。请配置对应的
endpoint 和凭证；测试其他模型或题目时，复制配置并修改 `agents[].model_name`、
题目选择及预算。这是普通的 Harbor JSON 配置，入口会补齐标准验证器和缓存策略。
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

每次安装都会写入 `agent/bootstrap.json`，失败时也保留已完成的步骤。预检失败会
在模型调用前终止 trial。官方验证脚本保持原样，执行时仍可能访问网络，所以预检
通过不能保证后续没有网络故障。完整标准运行默认启用下述验证超时重试，整题重试
次数为零。CI 会验证这些约定，不调用模型、不启动 Docker。

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
用量统计在 Pi 提供数据时包含上下文压缩；费用为估算值，缺失用量会单独标注。
Pi 目前不生成 ATIF trajectory。
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
