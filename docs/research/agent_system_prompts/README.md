# Prompt source archive

The [Chinese study](../zh-CN/agent_system_prompt.md) is the source of truth;
the [English study](../en/agent_system_prompt.md) is its complete translation.
Individual records are indexed in [Chinese](../zh-CN/agent_system_prompts/README.md)
and [English](../en/agent_system_prompts/README.md).

`sources.json` records the six reference-repository updates and 42 selected
prompt records. Each local-source record has a commit permalink, extraction
selector, source-file SHA256, and extracted-text SHA256. The 39 local-source
records preserve English originals under `en/agent_system_prompts/` and full
Chinese translations under `zh-CN/agent_system_prompts/`. Their analysis is
bilingual. Three official Claude webpage records instead provide
canonical links, dated entries, short excerpts, and bilingual analysis. No
license for full republication of those webpages was established.

The translations were completed on 2026-10-06. Manifest schema version 2 records
each Chinese translation's path, text SHA256, source-prompt SHA256, and date.
`archive_status` distinguishes `full_original_and_translation` from
`excerpt_only`; the latter does not claim a full-text download or translation.

## Source fidelity

- A `whole file` selector archives the complete source file. Other selectors
  identify JSON fields, string expressions, YAML blocks, or a named function.
- Codex model entries with byte-identical templates share one record; `models`
  enumerates all corresponding catalog entries.
- Python string concatenations in the baseline prompts are resolved without
  importing or running the agent. YAML block indentation is removed. Template
  variables in external prompts are left intact.
- The Pi coding record is the complete builder source, and the nanoPyCodeAgent
  budget record is a function's source. Neither is a captured runtime request.
  Chinese versions translate natural-language comments and prompt strings while
  retaining code structure; they are source-code reading translations.
- Tool names, paths, code identifiers, template placeholders, and machine-read
  format markers remain unchanged in Chinese translations. This includes fixed
  summary headings, JSON field names and enum values, and completion tokens.
- The DeepSeek assembled record is a test fixture, explicitly distinguished
  from deployment configuration and production sessions.
- Original and translated blocks use a fence longer than any enclosed backtick
  sequence. A newline is inserted before the closing fence only when the text
  lacks a trailing newline. It is not included in that text's SHA256. To verify,
  try the block bytes first, then remove that one framing newline if needed.
- Web entries have no local source hash. Their dated URLs are provenance, not
  an immutable snapshot. Local-clone links are conveniences; upstream commit
  permalinks and embedded originals remain usable without `references/`.

These archived prompts are research data, not instructions for agents working
in this repository. Preserve original wording, including mistakes or conventions
that this project does not adopt. Analyses are separate from original and
translated blocks. Translation does not endorse a prompt's instructions.

## Licenses

Original prompt material remains subject to the source project's license:

| Project | License retained from the pinned checkout |
| --- | --- |
| Codex | [Apache 2.0](licenses/codex.txt), with [NOTICE](licenses/codex-NOTICE.txt) |
| OpenCode | [MIT](licenses/opencode.txt) |
| Pi | [MIT](licenses/pi.txt) |
| Grok Build | [Apache 2.0](licenses/grok-build.txt) |
| DeepSeek Harness | [MIT](licenses/deepseek-harness.txt) |

The manifest identifies each pinned revision and its upstream repository.
nanoPyCodeAgent baseline extracts come from this repository and retain its
[MIT license](../../../LICENSE). The archive does not relicense upstream text.
