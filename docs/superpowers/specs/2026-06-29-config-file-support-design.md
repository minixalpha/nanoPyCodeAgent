# 设计 Spec — 配置文件支持（`~/.nanoPyCodeAgent/settings.json`）

- **日期**: 2026-06-29
- **分支**: `claude/agent_loop`
- **状态**: 已实现

> 正文用中文便于审阅（沿用本目录已有 spec 的惯例，并符合项目对 `docs/superpowers/specs/`
> 下 spec 文档的中文例外规则）；交付物（`src/` 代码、测试、英文文档）一律英文。
>
> **实现说明**：初稿曾计划保留项目级 `.env` 作为中间一级优先级（引入 `python-dotenv`），
> 但实现阶段决定**不引入该依赖、不支持 `.env`**，最终为「真实环境变量 > `settings.json`」
> 两级。本文已按最终落地方案更新。

---

## 1. 背景与目标

`agent.run()` 的配置来源为真实环境变量：`anthropic.Anthropic()` 与模型解析
（`os.environ.get("ANTHROPIC_MODEL")`）都直接读 `os.environ`。

`docs/dev_notes/zh-CN/0.2.x.md` 描述了第二种配置来源：用户级配置文件
`~/.nanoPyCodeAgent/settings.json`，其 `env` 字段与 Claude Code settings 约定一致，可配
`ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` / `ANTHROPIC_MODEL`。

**目标**：实现对该配置文件的支持，明确「真实环境变量 > 配置文件」两级优先级。

## 2. 优先级（已确认）

**真实环境变量 > `~/.nanoPyCodeAgent/settings.json`**

- 真实 shell 环境变量最高；
- 全局 `settings.json` 作为兜底默认值，只填补环境变量未设置的键。

> 初稿曾计划在两者之间加入项目 `.env`（真实 env > `.env` > settings.json），但为
> 「不引入新依赖」（§8）放弃了 `.env`，因此最终为上述两级。

## 3. 方案

**方案 A —— 注入 `os.environ`（采用）**：新增 `load_settings_env()`，读取
`settings.json` 的 `env` 字段，用 `os.environ.setdefault(k, v)` 写入。靠
「`setdefault` 只填补未设置的键」天然得到「真实环境变量优先」。下游
`anthropic.Anthropic()` 与模型解析逻辑**完全不改**，也不引入 `python-dotenv`。

方案 B（显式配置对象，把 `api_key/base_url/model` 显式传给 `Anthropic(...)`）改动更多、
偏离现有「从环境变量读取」风格；方案 C（Pydantic 类型化模型）对 nano 项目过度设计。均不采用。

## 4. 详细设计

文件：`src/nanopycodeagent/agent.py`

```python
def _default_settings_path() -> Path | None:
    """Resolve the user config path, or None if the home dir is unknown."""
    try:
        return Path.home() / ".nanoPyCodeAgent" / "settings.json"
    except RuntimeError:
        return None


SETTINGS_PATH = _default_settings_path()


def load_settings_env(path: Path | None = None) -> None:
    """Apply the `env` mapping from settings.json into os.environ.

    Fills only ANTHROPIC_* keys not already set, so real environment variables
    take precedence and unrelated variables are never injected. A missing file
    (or an unresolvable home dir) is fine (silent). An unreadable / non-UTF-8 /
    malformed file, or a non-object `env`, prints a warning and is otherwise
    ignored. Empty / whitespace-only / non-string values, and values the OS
    rejects, are skipped.
    """
```

`run()` 接入顺序：

```python
load_settings_env()             # settings.json fills unset ANTHROPIC_* keys
client = anthropic.Anthropic()  # reads os.environ, unchanged
```

`SETTINGS_PATH` 作为模块级常量（home 目录不可解析时为 `None`），便于测试 monkeypatch，且
不会在 import 期因 `Path.home()` 抛 `RuntimeError` 而崩溃。

## 5. 边界与错误处理

- **文件不存在 / home 目录不可解析** → 静默跳过（无配置文件是正常情况）。
- **读取失败（含非 UTF-8 编码）/ JSON 解析失败 / `env` 不是对象** → `print` 一行警告后继续
  （优雅降级，绝不中断启动）。
- **非 `ANTHROPIC_` 前缀的键** → 忽略，避免共享配置文件静默注入 `HTTPS_PROXY` 等无关变量。
- **单个值为空串、纯空白、非字符串，或被 OS 拒绝（如含 NUL）** → 跳过或打印警告后继续。
  关键原因：空 `ANTHROPIC_BASE_URL` 会破坏请求，空 `ANTHROPIC_API_KEY` 会让凭据检查误判；
  且 dev notes 的示例里这些字段就是空串占位。
- `model` 解析行 `os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL` 无需改动。

## 6. 测试（TDD，沿用现有 mock 风格）

文件：`tests/test_agent.py`

1. settings.json 提供 `ANTHROPIC_MODEL` 且 env 未设 → 该模型到达 API 调用（`messages.kwargs`）。
2. 真实 env 的 `ANTHROPIC_MODEL` 覆盖 settings.json（优先级顺序）。
3. 缺失文件 / home 不可解析 → 不报错、行为如常。
4. 非法 JSON / 非 UTF-8 文件 → 打印警告且仍能进入循环。
5. 直接单测 `load_settings_env`：空串 / 纯空白 / 非字符串值、非 `ANTHROPIC_` 键、被 OS
   拒绝的值均不写入 `os.environ`。

测试需复位相关环境变量（`monkeypatch.delenv` / `setenv`）并对 `agent.SETTINGS_PATH` 打桩，
避免读到用户真实配置文件。

## 7. 文档

- 更新 `docs/dev_notes/zh-CN/0.2.x.md`：说明两种配置来源（环境变量与 `settings.json`），
  以及「环境变量优先级高于配置文件」。
- 配置说明随 dev notes 与双语 README 的「Configuration」小节维护，本次**不新增**独立的
  `docs/user_guide/` 目录（对 nano 项目而言与 README/dev notes 重复，YAGNI）。

README / CHANGELOG / 英文 dev note 的同步按项目惯例（`land-pr` skill）在合并阶段处理。

## 8. 不在范围内

- 不引入新依赖（含 `python-dotenv`）。
- 不支持项目 `.env`（改由用户级 `settings.json` 承担兜底配置）。
- 不支持 `env` 之外的配置字段（YAGNI；loader 对未知字段天然忽略，为将来留口）。
- 不改 `release.yml` / 发布流程。
