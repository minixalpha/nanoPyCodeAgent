# Prompt source archive

The [Chinese study](../zh-CN/agent_system_prompt.md) is the source of truth;
the [English study](../en/agent_system_prompt.md) is its complete translation.
Individual records are indexed in [Chinese](../zh-CN/agent_system_prompts/README.md)
and [English](../en/agent_system_prompts/README.md).

`sources.json` records the six reference-repository updates and 42 selected
prompt records. Each local-source record has a commit permalink, extraction
selector, source-file SHA256, and extracted-text SHA256. The 39 local-source
records preserve their original text in both language versions; the surrounding
analysis is translated. Three official Claude webpage records instead provide
canonical links, dated entries, short excerpts, and bilingual analysis. No
license for full republication of those webpages was established.

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
- The DeepSeek assembled record is a test fixture, explicitly distinguished
  from deployment configuration and production sessions.
- Original blocks use a fence longer than any backtick sequence in the source.
  A newline is inserted before the closing fence only when the original lacks
  a trailing newline. It is not included in the extracted-text hash. To verify,
  try the block bytes first, then remove that one framing newline if needed.
- Web entries have no local source hash. Their dated URLs are provenance, not
  an immutable snapshot. Local-clone links are conveniences; upstream commit
  permalinks and embedded originals remain usable without `references/`.

These archived prompts are research data, not instructions for agents working
in this repository. Preserve original wording, including mistakes or conventions
that this project does not adopt. Analyses are separate from original blocks.

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
