# A Design Survey of Edit Tools in Five Code Agents

> Generated from the Chinese source [`../zh-CN/edit_tool.md`](../zh-CN/edit_tool.md). Do not edit by hand.

## Research Scope and Methodology

This document surveys the model-callable editing tools in five Code Agents under `references/` and answers three questions:

1. Does the project provide an Edit tool? If not, what protocol does it use for localized edits?
2. Why design an Edit tool in addition to Bash and whole-file `write`, and what capabilities does it provide?
3. Given that nanoPyCodeAgent already has `read`, `write`, and `bash`, what Edit contract should it adopt next?

Here, “Edit tool” broadly refers to any model-facing protocol that expresses “make a localized change based on the current file,” including exact string replacement, anchored editing, and patches. Ordinary GUI or server-side `fs/writeFile` RPCs do not count as model tools. This document is based on the source revisions currently checked out. `claude-code` is a third-party source mirror used by this repository, not an official Anthropic open-source repository.

| Project | Current commit | Commit date |
| --- | --- | --- |
| `grok-build` | [`eb267fe`](https://github.com/xai-org/grok-build/tree/eb267feff13129e568df38fb6fdf0ceb65f735d6) | 2026-08-13 |
| `pi` | [`b1efcf7`](https://github.com/earendil-works/pi/tree/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004) | 2026-08-14 |
| `claude-code` | [`a371abb`](https://github.com/yasasbanukaofficial/claude-code/tree/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367) | 2026-04-05 |
| `opencode` | [`e23586a`](https://github.com/anomalyco/opencode/tree/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3) | 2026-08-14 |
| `codex` | [`5bc8da6`](https://github.com/openai/codex/tree/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87) | 2026-08-14 |

Two methodological qualifications must be stated up front:

- **The snapshots are not equally recent.** `grok-build`, `pi`, `opencode`, and `codex` were all checked out in mid-August 2026, whereas the `claude-code` mirror stops at 2026-04-05, roughly four months earlier than the other four. The conclusions about Claude Code apply only to this mirror and must not be treated as a description of the current Claude Code release.
- **Disambiguate identically named tools by package.** Some repositories contain multiple Edit implementations. This survey covers only the implementation that the model actually calls in the relevant Code Agent. Pi's CLI is provided by `@earendil-works/pi-coding-agent` (`bin: pi` → `cli.ts` → `main.ts` → `AgentSession` → `createAllToolDefinitions`), which leads to [`packages/coding-agent/src/core/tools/edit.ts`](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit.ts); that is the implementation described here. The generic agent kernel `@earendil-works/pi-agent-core` has another implementation at [`packages/agent/src/harness/tools/edit.ts`](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/agent/src/harness/tools/edit.ts). It shares the same matching algorithm but replaces I/O with a fully `env`-abstracted layer. It is currently referenced only by `server/create-harness.ts` and is not reachable from the CLI. The two OpenCode generations differ far more substantially, so they are recorded separately as V1 and V2.

## Conclusions

All five projects provide structured localized-editing capabilities, but they have not converged on one kind of Edit tool:

| Project | Model tool named Edit? | Primary editing protocol | Design orientation |
| --- | --- | --- | --- |
| Grok Build | No `edit` by default; the default is `search_replace`, while other presets can select `hashline_edit`, OpenCode `edit`, or `apply_patch` | Exact old/new strings; optional line-hash anchors or Patch | Select the protocol by model/preset; uniformly apply permissions, hooks, plan gates, and events in the outer tool layer |
| Pi | Yes, `edit` | Single-file `edits[]`, each containing `oldText`/`newText` | Submit multiple non-overlapping localized replacements at once; lightweight, embeddable, and backend-replaceable |
| Claude Code | Yes, `Edit`, plus `NotebookEdit` | One `old_string`/`new_string` pair, with optional `replace_all` | Strong Read-before-Edit, stale-state protection, history, permissions, LSP, and IDE integration |
| OpenCode | Both V1 and V2 have `edit` as well as `apply_patch` | One old/new pair plus `replaceAll`; V1 uses Patch instead for GPT models | V1 emphasizes fuzzy matching and ecosystem integration; V2 emphasizes exact matching, canonical paths, and in-process expected-bytes conditional writes |
| Codex | **No** string-based `edit` | Free-form `apply_patch` | Use one Patch protocol for multi-file add/update/delete/move operations, reducing overlapping tools |

The true commonality among these “Edit tools” is therefore neither their name nor their schema. It is this: **the model expresses only the change and its preconditions; the runtime reads the current file, validates those preconditions, and preserves everything outside the requested change.**

Compared with whole-file `write`, Edit's first benefit is sending fewer tokens and rewriting less unrelated content. Compared with Bash, its first benefit is enabling the Agent runtime to understand which resource is changing, which old content is the precondition, and what diff was actually produced. Edit is still not inherently a security boundary or a transaction: if Bash can write arbitrary files, path rules can be bypassed; if validation and persistence are not one strongly consistent storage transaction, external processes can still create races.

## Why Design an Edit Tool?

### 1. Replace Whole-File Retransmission with Incremental Expressions

When changing three lines of code, `write(path, complete_content)` requires the model to resend the entire file. As files grow, so do the input-token cost, the probability of unintentionally changing an unexamined region, the retry cost after conflicts, and the UI cost of recomputing the diff. Edit sends only the target old and new text; Patch sends only hunks with context.

This is why Claude Code, Pi, and OpenCode reserve `write` for file creation or complete rewrites and use Edit for ordinary modifications. Codex goes further: it exposes no whole-file Write at all, expressing new files through `*** Add File` patches as well.

### 2. Turn the Old State Assumed by the Model into a Verifiable Precondition

A localized edit does not mean “write at line 37.” It means “replace this old content only if it still exists and can be located uniquely.” If the user, a formatter, or another tool has already changed it, Edit should fail and make the model read again, rather than overwrite the current version as a whole-file Write would.

The projects choose preconditions of different strengths:

- String Edit: the old text exists and is unique by default;
- Patch: the context hunk can still be located;
- Hashline: the line number and content hash returned by Read still validate;
- Claude Code: additionally tracks session Read state and compares mtime/content;
- OpenCode V2: reads the original bytes after permission approval, then performs `writeIfUnchanged(expectedBytes)` at commit time.

String Edit and Patch use “semantic preconditions”; Claude Code and OpenCode V2 additionally bind the operation to a read version. All are better than unconditional overwrite, but none automatically constitutes cross-writer CAS or a file-system transaction.

### 3. Fail by Default Instead of Guessing a Location

When old text occurs multiple times, replacing only the first occurrence by default is dangerous. Mainstream string Edit tools generally require a unique match; the model must either add a small amount of context or explicitly enable `replace_all`. Batch protocols also reject overlapping ranges so that applying one replacement cannot change the meaning of another.

This fail-closed behavior also makes errors recoverable: the tool can explicitly report “not found,” “found N occurrences,” “file changed,” or “anchor is stale,” rather than handing the model only a fragment of shell stderr.

### 4. Establish an Approvable, Observable File-Mutation Lifecycle

Structured input tells the Agent runtime the target path before execution and lets it obtain the old/new content or a unified diff afterward, enabling an auditable lifecycle. Projects differ in when they request authorization; a fuller sequence looks like this:

```text
Resolve target and canonical path
→ Authorize path/read access (before reading sensitive content)
→ Read current content and validate preconditions
→ Compute final diff / approve content / optional pre-write checkpoint
→ Revalidate before commit or perform an expected-bytes conditional write
→ Persist
→ Formatter / LSP / file event / history / undo / audit
→ Summary for the model and structured result for the Agent runtime
```

Arbitrary Bash can of course modify files too, but the Agent runtime cannot reliably infer the final write set, pre-execution diff, and ownership of each hunk from a dynamic shell program.

### 5. Adapt to the Model's Training Distribution Instead of Pursuing One Universal Protocol

OpenCode exposes `apply_patch` to modern non-OSS GPT models and `edit`/`write` to other models. Grok Build likewise uses presets to switch among search/replace, Hashline, OpenCode Edit, and Codex Patch. This demonstrates that the tool schema is a model-adaptation surface; it cannot be chosen solely according to implementation convenience in the Agent runtime.

String replacement is simplest for a model; Patch is better suited to multi-file changes in one call; Hashline most strongly encodes “the old content is still the version I saw,” but requires Read output and Edit input to adopt a new shared anchor language. No interface is optimal for every model.

## Implementations by Project

### 1. Grok Build

#### Does It Have Edit?

It has localized-editing capabilities, but the default tool is named `search_replace`. The default Grok Build toolset registers `read_file` + `search_replace`, with the workspace version additionally registering `write`; the Codex preset uses `apply_patch` instead. The file tools can also be switched as a group to `hashline_read`/`hashline_edit`/`hashline_grep`, and the registry explicitly rejects mixing standard and Hashline file tools. The [preset configuration](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-agent/src/config.rs#L170-L347) and [mutual-exclusion validation](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/registry/types.rs#L878-L908) embody this design of replacing tools as a protocol-level set.

#### `search_replace`

Its input is:

```text
file_path: string
old_string: string
new_string: string
replace_all: boolean = false
```

It performs an exact string search first. Matches must be unique by default; only `replace_all=true` replaces all non-overlapping matches. `old_string == new_string` fails. If the file contains any CRLF, matching moves into a logical LF space and the entire output is then converted back to CRLF. Ordinary CRLF files therefore retain their style, while mixed line endings are normalized. The [schema and description](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/mod.rs#L53-L139) and the [matching, newline, and persistence code](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/mod.rs#L522-L738) define the actual semantics.

After exact matching fails, the default behavior is only to return diagnostics about nearby lines, possible user modifications, and Unicode typography. Unicode-confusable normalization fallback is enabled only by an optional configuration. This fallback maps smart quotes, dashes, special spaces, and similar characters before matching, maps the resulting range back to the original UTF-8 bytes, and fails closed on partial expansions, overlaps, and ambiguity. The [normalization fallback](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/helpers.rs#L136-L263) is deliberately more conservative than “fuzzily find something close and edit it.”

An empty `old_string` doubles as file creation/whole-file writing. One compatibility detail is easy to misread: `empty_old_string_does_not_override` still defaults to false, so it can overwrite an existing non-empty file, while the success message still calls the file “created.” Only after the guard is explicitly enabled do the intended semantics narrow to create-or-fill-empty. Even that guard is not strictly fail-closed: the creation branch swallows read errors and treats an unreadable target as nonexistent. The [versioned parameter](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/mod.rs#L94-L139) and [empty-string branch](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/mod.rs#L294-L405) explain this historical compatibility tradeoff.

A successful result contains modification context and line numbers; the `patch` field in the result structure is currently always `None`. The tool emits `FileWritten` with previous/new content for the hunk tracker, rewind, and UI. The outer session then uniformly applies the plan-mode gate, pre-tool hooks, and edit permissions. The core search/replace implementation is therefore relatively thin, with most control-plane logic in the orchestration layer. However, the repository's `FileOperationLockManager` is not currently connected to this execution path.

The boundaries are as follows: it has no session-level prior-Read revision, mtime, expected-bytes CAS, or shared path lock; other tools and external processes can still race with the read-compute-write sequence. CRLF restoration normalizes line endings across the entire output, so a file with mixed line endings can acquire unrelated changes. UTF-8 decoding remains lossy by default, creating a risk of replacement characters when editing invalid UTF-8 text. Permissions match lexical paths, while an existing target is canonicalized before I/O; if a symlink points into another permission domain, safety must come from the outer OS sandbox rather than the tool rules alone.

#### `hashline_edit`

Hashline Read returns a `LINE:HASH[:CONTEXT_HASH]` anchor for each line. Edit accepts multiple operations in one call:

- `replace(anchor, end_anchor?, content)`: replace/delete one line or a range;
- `insert_after(anchor, content)`: accepts an ordinary anchor, BOF `0:`, or `EOF`;
- `write(content)`: replace the whole file without an anchor.

See [`types.rs`](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build_hashline/edit/types.rs#L7-L116) for the schema. Every anchor is validated against the same pre-edit snapshot; if any anchor is stale, ambiguous, not found, or overlaps another range, the entire logical batch fails before disk is written. Once validation passes, all operations are applied once from bottom to top, and localized excerpts with fresh anchors are returned for subsequent edits. See [batch validation and application](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build_hashline/edit/apply.rs#L143-L305).

It addresses ordinary line numbers drifting after insertions/deletions and long old text wasting tokens. A stale anchor also triggers a search for relocated candidates nearby, but the tool returns only a fresh anchor so the model can retry rather than editing on its own initiative. The cost is that Read and Edit must be coupled as one protocol. The default three-character hash, which ignores some whitespace differences, is not a cryptographic revision either. The model may also accidentally copy anchor prefixes into the content, so the implementation explicitly detects and reports this error. A logical batch's “validate everything, then write once” behavior does not imply atomic visibility, crash durability, or cross-writer CAS. Unlike the default `search_replace`, the current Hashline Edit does not emit a `FileWritten` event, and ordinary replace/insert operations normalize CRLF to LF.

#### Other Compatibility Presets

Grok Build also retains two implementations ported from other Agent protocols rather than merely renaming its tools:

- `Codex:apply_patch` accepts a JSON `patch` field whose Patch body supports multi-file Add/Delete/Update/Move operations. It first parses and computes all changes in memory, then performs I/O sequentially. A hunk failure can stop the operation before any write, but a failure during persistence does not roll back earlier writes; Add and Move destinations can also overwrite existing files. The [tool and three-phase execution](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/codex/apply_patch/tool.rs#L25-L105) and [commit phase](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/codex/apply_patch/tool.rs#L313-L477) show that it is “full preflight + non-transactional commit.”
- `OpenCode:edit` uses `filePath`/`oldString`/`newString`/`replaceAll`, but this port performs only exact matching and does not include OpenCode V1's current multi-layer fuzzy matching. An empty old string can create a file or overwrite an empty file; ordinary edits require uniqueness by default and emit `FileWritten`. See the [schema and execution](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/opencode/edit/mod.rs#L45-L88) and [replacement path](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/opencode/edit/mod.rs#L333-L472).

These two compatibility implementations likewise have no prior-Read revision, shared file lock, or atomic replacement. Their main value is matching the tool-training distribution of particular models, not providing stronger file-system guarantees.

### 2. Pi

#### Does It Have Edit?

Yes. The default toolset contains `read`, `write`, `edit`, and `bash`. The current schema has evolved from an earlier single old/new pair to:

```text
path: string
edits: Array<{
  oldText: string
  newText: string
}>
```

`edits` must be non-empty. Every `oldText` is matched against the same original file rather than against the result of the previous item. The tool prompt asks the model to put multiple distant changes in one call and merge adjacent or overlapping changes into a single block. See the [schema and model guidance](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit.ts#L34-L64).

Pi once supported both single-edit and multi-edit schemas, but models repeatedly produced invalid calls by mixing the two shapes. It ultimately retained only `edits[]`. When restoring an old session, `prepareArguments` still folds top-level `oldText`/`newText` into an array and tolerates some models double-encoding the array as a JSON string. This [compatibility conversion](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit.ts#L105-L135) shows that schema simplicity is itself a reliability feature.

#### Capabilities and Algorithm

All replacements in one call are validated first, then applied in reverse order with only one write:

- Empty `oldText` is forbidden, so Edit does not create files;
- Each `oldText` must match exactly once; zero matches and multiple matches are rejected. The batch fails if its final content is unchanged, but there is no per-item no-op validation;
- Overlapping ranges among edits are rejected;
- After exact matching fails, it falls back to NFKC, per-line trailing-whitespace, smart-quote, dash, and special-space normalization;
- It preserves the UTF-8 BOM and restores ordinary LF/CRLF files to the detected line-ending style;
- On a fuzzy match, only the lines actually touched are rewritten; untouched lines are copied back from the original content to avoid normalizing the entire file;
- It returns a display diff, a standard unified patch, and the first changed line. When the arguments are complete, the TUI asynchronously previews the diff before execution.

See [`edit-diff.ts`](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit-diff.ts#L295-L374) for the core algorithm and [`edit.ts`](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit.ts#L298-L367) for the execution path. Notably, the model-facing description says “exact,” while the implementation has fuzzy fallbacks. This improves the success rate when copied text differs slightly, but also means that a human cannot infer the actual matching boundary from the prompt alone.

Pi abstracts `readFile`, `writeFile`, and `access` as injectable operations, allowing the same protocol to target backends such as SSH and VMs. All `write`/`edit` operations also share an in-process mutation queue keyed by the `realpath` of existing files: operations on the same real file are serialized, while operations on different files can still run concurrently. When an operation is aborted, the queue is released only after the underlying I/O has settled, preventing a write already reported as canceled from interleaving with the next write. The [operations](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit.ts#L81-L103) and [mutation queue](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/file-mutation-queue.ts#L1-L60) reflect Pi's lightweight, embeddable orientation.

The boundaries are as follows: the queue coordinates only participating Pi tools, not Bash or external editors. There is no mtime/hash/expected-bytes check and no temp + fsync + rename sequence. Paths are not restricted to the cwd by default. The fuzzy fallback normalizes entire touched lines, so it can still change trailing whitespace or Unicode forms on those lines outside `oldText`. Mixed line endings are normalized to the first detected style, and bare CR becomes LF. UTF-8 decoding is lossy, with no NUL/binary guard. Injectable I/O helps remote backends, but the surrounding tool infrastructure has not caught up: both the mutation queue's `realpath` call and the TUI's pre-execution diff preview directly use local `node:fs`, bypassing `operations`. The abstraction is therefore incomplete.

### 3. Claude Code

#### Does It Have Edit?

Yes. It has `Edit` and separately provides `NotebookEdit` for `.ipynb` files. The ordinary Edit schema is:

```text
file_path: string  # the schema text requires an absolute path; the runtime also accepts relative paths and ~
old_string: string
new_string: string
replace_all: boolean = false
```

Claude Code's `Write` prompt directly instructs the model to prefer Edit when modifying an existing file because Edit “only sends the diff”; Write is reserved for creating a file or rewriting it completely. The [Write tool prompt](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileWriteTool/prompt.ts#L10-L17) gives the product-level rationale for Edit: compress model output while avoiding retransmission of unchanged regions.

`old_string` must be unique by default. If it occurs more than once, the model is told to add context or explicitly use `replace_all`. The tool prompt explicitly warns against copying Read's line-number prefixes into the string. Although the schema text requires an absolute path, the runtime's `expandPath` also accepts relative paths and `~`, so the described contract and implementation boundary do not align completely. The [schema](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/types.ts#L5-L34), [prompt](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/prompt.ts#L4-L27), and [path expansion](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/utils/path.ts#L8-L84) demonstrate detailed constraints tailored to Claude's output habits, while also exposing interface drift.

#### Enforced Read-before-Edit and Stale-State Protection

Claude Code does not merely recommend Read in the prompt; it enforces it at runtime. An ordinary existing file must have session Read state, and a partial view automatically injected by the system is insufficient. The tool rejects the edit if the current mtime is later than the read time. The implementation also attempts to accept a pure touch when the cache state has no recorded offset/limit and the content is unchanged, but FileRead records `offset=1` by default, so an ordinary full read generally cannot reach this fallback either. Immediately before the real write, it synchronously reads the current metadata/content again and deliberately inserts no asynchronous yield between that check and persistence, narrowing the race window within a single JS event loop. Its [input validation](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/FileEditTool.ts#L137-L361) and [pre-commit revalidation](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/FileEditTool.ts#L425-L491) constitute the heaviest session-level protection among the five projects.

An empty `old_string` is a restricted creation path: it is allowed if the target does not exist or the existing file is blank, and rejected for non-empty files, preventing implicit whole-file overwrite through Edit. FileEdit's core matcher tries exact matching first; on failure, it normalizes only straight/curly quotes and restores the new string to the file's original typography style. Earlier in the call chain, before the input reaches the tool, a fixed set of desanitization rules restores a small number of tokens hidden or abbreviated by the API. It still does not perform arbitrary indentation or anchor-similarity fallback like OpenCode V1. See [quote matching](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/utils.ts#L18-L135) and [input restoration](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/utils.ts#L526-L657). When deleting, `new_string=""` also has a convenience behavior that removes an immediately following newline. However, this special branch is defective when combined with `replace_all`: for example, deleting every `x` in `x\nx` may leave the final occurrence in place even though the result text still claims that all occurrences were replaced. See the [deletion implementation](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/utils.ts#L206-L228).

#### Control Plane and Output

Edit reuses Claude Code's complete mutation lifecycle: path/deny/UNC and symlink permission checks, team-memory secret validation, optional history, UTF-8/UTF-16LE and dominant-line-ending restoration, structured patches, VS Code/LSP notification when available, diagnostic cleanup, and telemetry. After success it updates the Read state so the next consecutive edit is based on the new content. It does not automatically run a formatter. See [post-write integration and results](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/FileEditTool.ts#L490-L593). The low-level write prefers a temporary file in the same directory, flushes it, preserves the mode, and then renames it. On failure, it silently falls back to direct overwrite, so this is only best-effort atomic replacement rather than a strong guarantee. See the [write implementation](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/utils/file.ts#L369-L477).

It is still not cross-writer CAS: a window remains between the mtime/content check and the final write. The synchronous write path provides in-process “no await” ordering, not a kernel transaction. Enforcing a prior Read also adds tool-call cost, and a path policy applied only to Edit can still be bypassed through Bash. Another contract boundary worth noting is that API message normalization silently removes per-line trailing whitespace from non-Markdown `new_string` values, so the bytes written need not exactly match the model arguments. See [input normalization](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/utils.ts#L526-L657).

`NotebookEdit` deserves separate treatment because a Notebook is not an ordinary JSON text-replacement problem. It performs replace, insert, and delete operations using either real cell IDs or synthetic `cell-N` IDs from FileRead. When changing a code cell, it clears outputs and the execution count and maintains nbformat 4.5+ cell IDs. It also requires Read-before-Edit and fresh mtime. The [validation](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/NotebookEditTool/NotebookEditTool.ts#L176-L294) and [cell operations](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/NotebookEditTool/NotebookEditTool.ts#L295-L453) demonstrate why structured files benefit from domain-specific Edit tools rather than forced reuse of text replacement. However, it checks for staleness only during initial validation, without the ordinary Edit's final revalidation after waiting for permissions/history, and it re-stringifies the entire notebook. Editing one cell can therefore still overwrite concurrent changes and produce a large formatting diff. Its [prompt still describes](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/NotebookEditTool/prompt.ts#L1-L8) `cell_number`, which is no longer present in the schema—another example of drift between prose and implementation.

### 4. OpenCode

The OpenCode repository contains two generations of the implementation: V1/legacy under `packages/opencode` and the new Location-scoped V2 architecture under `packages/core`. They share names but not semantics and must not be conflated. V1 chooses between `apply_patch` and `edit` + `write` according to the model; the current [V2 built-ins](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/tool/builtins.ts#L20-L42) register all three, then filter them by permission.

#### Why Have Both `edit` and `apply_patch`?

The V1 registry selects by model: modern non-OSS, non-GPT-4 GPT models see `apply_patch`, while other models see `edit` + `write`; it does not give one model all three overlapping interfaces. See [tool selection](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/tool/registry.ts#L286-L297). This directly demonstrates that the two interfaces primarily serve different model capabilities: old/new is easier to generate, while Patch is better suited to multi-file edits and GPT's training distribution.

#### V1 `edit`: Permissive Matching and Deep Integration

Its inputs are `filePath`, `oldString`, `newString`, and optional `replaceAll`. A per-file semaphore covers read-compute-write. For an existing file, an empty old string is forbidden; for a nonexistent target, an empty old string creates the file. It preserves the BOM and the file's original LF/CRLF style, first generates a diff to request `edit` permission, then persists, runs the formatter, recomputes the final diff from the post-formatter result, publishes file/watcher events, triggers LSP, and returns diagnostics to the model. See the [execution lifecycle](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/tool/edit.ts#L35-L215).

The matching strategy tries, in order: exact, per-line trim, first/last-line block anchors with Levenshtein similarity, whitespace normalization, flexible indentation, escape normalization, boundary trim, context-aware matching, and multiple occurrences. After the replacer selects one concrete actual string, the outer layer requires that string to be unique by default; only `replaceAll` changes every occurrence. However, block-anchor fuzzy matching selects the highest-scoring candidate among several, retains the first on a tie, and does not require the original fuzzy candidates to be globally unique. A separate guard rejects a matched span that is excessively large relative to `oldString`, preventing a short fuzzy input from consuming a large block. See the [replacer implementation](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/tool/edit.ts#L217-L736).

This strategy is highly tolerant of small model transcription errors, but also carries the greatest risk: the prompt's claimed “exact edit” is far removed from the actual runtime boundary, and a block anchor with 0.65 similarity can accept a middle region that has already changed substantially. A permission diff can provide a backstop when a human approves the operation; permissive fallbacks deserve more caution under automatic approval. V1's [prompt also claims that Read is required before modification](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/tool/edit.txt#L1-L8), but the corresponding FileTime/read-state check has been removed from the current implementation—another counterexample of drift between the prompt contract and runtime.

V1 `apply_patch` uses a `{ patchText }` JSON wrapper around a Codex-like Patch language and supports multi-file add/delete/update/move in one call. Matching falls back progressively through exact, `trimEnd`, `trim`, and Unicode-punctuation normalization. All changes are computed and approved together first, after which files are persisted one by one, formatted, and sent through events and LSP. Add and Move destinations overwrite existing files. The commit does not roll back and has no expected-bytes CAS. Because formatting occurs after the approved diff, the final actual changes can exceed the approval preview. Although a Move destination enters metadata and can separately trigger external-directory authorization, it is not added to the `edit` permission's path patterns, leaving the approval scope for internal destinations incomplete as well. The [tool execution](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/tool/apply_patch.ts#L18-L278) and [Patch matching](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/patch/index.ts#L430-L506) show this combination of “Patch expressiveness + deep V1 integration.”

#### V2 `edit`: Exact + Expected Bytes

V2 keeps the same single old/new + `replaceAll` shape but does not use V1's similarity-based fuzzy matching. The source lists V1 fuzzy matching, formatting, watcher integration, snapshot/undo, and LSP as future TODOs. It:

- Canonicalizes paths through `LocationMutation`, preventing relative paths and workspace symlinks from escaping the workspace; an explicitly external absolute path requests `external_directory` first;
- Forbids an empty old string and no-op changes, requiring uniqueness or explicit replace-all;
- Strips the UTF-8 BOM before matching, converts `oldString` and `newString` together to the file's detected line ending, and restores the BOM when writing;
- Returns replacements, a unified patch, additions/deletions, and a bounded old/new diff preview for the model;
- Reads source bytes only after permission approval, then compares current bytes with expected bytes inside an in-process canonical-path lock at commit time, reporting stale state if they differ.

To be precise, V2's exact matching is not raw-byte exact. It is exact **after removing the BOM and converting old/new to the file's line endings**: `detectLineEnding` classifies a file as CRLF if `\r\n` occurs even once, and `convertToLineEnding` first normalizes input to LF before converting it back to CRLF when needed. See the [normalization helpers](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/tool/edit.ts#L42-L53) and [pre-match conversion](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/tool/edit.ts#L161-L165). This conversion has a deterministic direction and an enumerable scope, and it rewrites only the matched span while leaving unmatched regions as the original bytes. It therefore solves both “Read output stripped `\r`, so the model cannot provide the original CRLF text” and “do not casually normalize the whole file.” Among the five projects, this is the most restrained treatment of the problem. The cost is a coarse classification: one occurrence of `\r\n` causes the tool to treat the entire file as CRLF when converting `oldString` and `newString`, so pure-LF fragments in a mixed-line-ending file cannot match; the tool must fail closed and make the model read again.

See [`V2 edit.ts`](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/tool/edit.ts#L22-L223) for execution and [`file-mutation.ts`](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/file-mutation.ts#L54-L171) for the in-process keyed lock and expected-bytes conditional write. The comparison and ordinary write are contiguous only with respect to OpenCode mutations that cooperate through that lock; an external process or Bash can still race between them. This reflects a strategy of first clarifying explainable exact matching and in-process concurrency semantics, then gradually adding UX features.

V2 `apply_patch` supports add/update/delete in one call. It first parses and resolves every target, authorizes them in a batch, then performs preflight reads. Add uses create-only `wx`; Update uses expected bytes. Commits remain sequential, so a later failure does not roll back earlier successful items. Delete has no expected-content CAS, and Move is not yet supported. See [V2 Patch](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/tool/apply-patch.ts#L17-L218). “Batch preflight” must therefore not be described as a “multi-file transaction.”

### 5. Codex

#### No String-Based Edit

Codex does not register `edit`/`edit_file`. [When an environment exists and the model metadata declares `apply_patch_tool_type`](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/core/src/tools/spec_plan.rs#L1090-L1110), it registers free-form `apply_patch`, currently its only dedicated file-mutation tool. The schema is not JSON old/new; it is text constrained by a Lark grammar:

```text
*** Begin Patch
*** Add File: path
+new content
*** Update File: old-path
*** Move to: new-path
@@ optional context
-old
+new
*** Delete File: path
*** End Patch
```

The tool definition explicitly says that it is “for editing files” and must not be wrapped in JSON, and it marks the free-form custom tool as suitable for GPT-5. The provider-side Lark grammar supports multi-hunk add/delete/update/move operations. See the [tool spec](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/core/src/tools/handlers/apply_patch_spec.rs#L5-L27) and [grammar](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/core/src/tools/handlers/apply_patch.lark#L1-L19). The old JSON/function calling surface was later [removed](https://github.com/openai/codex/commit/e783341b705721728a8fa422416c10c3a09c7716), preventing both models and tests from having to handle two equivalent protocols. Patch is executed by a built-in Rust parser and does not depend on a system-installed `patch(1)`.

This is an important counterexample: needing a dedicated localized-editing protocol does not necessarily mean needing a string-based Edit tool. Add File covers creation, Update suits ordinary modifications, and multiple files share one parser and permission entry point. The cost is that the model must generate the Patch language reliably.

#### Capabilities and Boundaries

Before execution, Codex parses the entire Patch, reads old content for Update/Delete, computes new content and a unified diff for every Update hunk, and rejects multiple operations that use the same source path. Only then does it classify safety, request approval, and execute in the sandbox based on the complete change set. The [pre-validation](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/apply-patch/src/invocation.rs#L200-L280) and [handler](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/core/src/tools/handlers/apply_patch.rs#L359-L447) embody “understand the changes first, then decide whether they may execute.” The same rule does not fully cover conflicts among Move destinations or between destinations and other sources, so sequential execution can still partially fail.

Context location tries, in order: exact, ignoring trailing whitespace, trimming both sides, and normalizing Unicode punctuation/special spaces. An EOF anchor searches from the end of the file first. See [`seek_sequence`](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/apply-patch/src/seek_sequence.rs#L1-L115). Even if the model invokes the tool through a restricted `apply_patch <<'PATCH' ...` shell form, Codex recognizes it and routes it through the same Patch approval/sandbox chain rather than treating it as arbitrary Bash.

Important Patch limitations include:

- Actual file operations commit in file-action order; failures do not roll back, and the return value carries the deltas already committed;
- Add can overwrite an existing target rather than being create-only;
- Move writes the destination first and then deletes the source, so failure to delete the source can leave both copies;
- There is no expected-bytes CAS between validation of an Update and actual persistence. After approval, the runtime rereads the file and recomputes the Patch. If an external change does not invalidate the hunk, it can continue applying the Patch to the new file, and the final result can differ from the approval preview;
- The final operation is a whole-file text rewrite and does not express binary deltas, `chmod`, or similar metadata.

See [`apply-patch/src/lib.rs`](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/apply-patch/src/lib.rs#L438-L663) for sequential commit and Move behavior. The outer tool layer also provides writable-root safety classification, platform sandboxing, hooks, streaming diff events, and remote file systems, but these are Codex control-plane capabilities rather than atomicity inherent in the Patch grammar.

## Capability Comparison

| Capability | Grok `search_replace` / Hashline | Pi | Claude Code | OpenCode V1 / V2 | Codex |
| --- | --- | --- | --- | --- | --- |
| Ordinary interface | One old/new pair; Hashline can batch | Batched old/new in `edits[]` | One old/new pair | One old/new pair | Multi-file Patch |
| Unique match by default | Yes | Required for every item | Yes | V1 block fuzzy can select the best candidate; V2 yes | A hunk takes the first context candidate |
| Replace all | `replace_all` | No direct switch | `replace_all` | `replaceAll` | Multiple hunks/contexts |
| Multiple locations/files in one call | Search can change identical literals; Hashline supports multiple operations; Patch supports multiple files | Multiple operations in one file | `replace_all` can change identical literals; no multiple distinct operations/files | Edit can change identical literals; Patch supports multiple files | Multiple files |
| Creation | Empty old in `search_replace`; Hashline write | No | Restricted creation with empty old | Empty old in V1; no V2 Edit creation; Patch Add | Patch Add |
| Fuzzy fallback | Optional Unicode for search; Hash anchor recovery | NFKC/trailing whitespace/Unicode | Quote normalization + fixed desanitization | Multi-layer fuzzy in V1; V2 exact only after BOM/line-ending conversion | Hunk trim/Unicode |
| CRLF/BOM | Search preserves LF or normalizes to CRLF; Hashline converts to LF; no special BOM protection | BOM and ordinary LF/CRLF; mixed line endings are normalized | UTF-8/UTF-16LE and dominant LF/CRLF | V1 Edit preserves them; V2 strips BOM for matching and converts old/new to file line endings; Patch may mix line endings | Converts to LF by default; an experimental feature can preserve line endings; no special BOM handling |
| Stale-state protection | Old/anchor precondition | Old precondition | Prior Read + mtime/content | V1 Edit: old; V2 Edit/Patch Update: expected bytes; Add: `wx`; Delete: none | Hunk precondition, no CAS |
| In-process serialization for the same file | No shared path lock | Realpath queue | No `await` in the final section, but no path lock | V1: Edit semaphore only; V2: canonical lock per target | No path lock/CAS |
| Diff/UI | Context; Search has `FileWritten` events | Preview + diff + patch | Structured patch + IDE | V1/V2 diff | Diff event + A/M/D summary |
| Formatter/LSP/history | Search connects to hunk/rewind; no in-tool formatter | Extension hooks; no built-in LSP | No formatter; optional history/LSP | Present in V1; TODO in V2 | General events/hooks; no in-tool formatter |

## Design Tradeoffs

### Exact vs. Fuzzy

Exact matching is explainable and testable: the tool changes precisely the precondition submitted by the model. Its drawback is that small differences in Read formatting, CRLF, trailing whitespace, smart quotes, and similar details cause retries.

Fuzzy matching can improve first-attempt success, but expands the range the tool is effectively authorized to change. Grok's Unicode offset map maps a match under limited normalization back to the original bytes and rejects candidates that cannot be mapped back completely. Pi instead replaces within normalized text and restores only untouched blocks of original lines, so touched lines can also acquire NFKC, punctuation, or trailing-whitespace changes. OpenCode V1's block similarity is more aggressive and requires additional span guards and an approval diff. At the other end of the spectrum, OpenCode V2 deliberately limits itself to two deterministic, enumerable conversions—BOM and line endings—with no similarity judgment, so the matched range still corresponds exactly to the literal submitted by the model. For a small Agent without a pre-execution approval UI, exact-first/fail-closed is more appropriate. The allowed conversions must be a short, enumerable list that can be written into the tool description, not a chain of heuristics.

### Single Replacement, Batched Replacements, and Patch

- Single old/new: the smallest schema and a high model success rate; multiple calls repeat I/O and cannot atomically validate a group of changes as one logical unit.
- Same-file `edits[]`: one read, full validation, one write; the contract must define whether all matches use the original content or progressive results and must handle overlaps.
- Patch: the greatest multi-file expressiveness, but also the highest costs for parsing, error recovery, partial commits, and model adaptation.

Pi's evolution also shows that one schema should not expose both top-level old/new and `edits[]` as equivalent shapes; models will mix them. Choose one stable public interface and confine compatibility to a runtime input-migration layer.

### “Validate Then Write” vs. True Atomicity

Five concepts must be distinguished:

1. **Complete logical validation**: first confirm in memory that every replacement can apply;
2. **Single-file atomic visibility**: concurrent observers see either the complete old version or the complete new version, usually provided by temp + rename on the same file system;
3. **Crash durability**: after success is reported, the file and directory entry remain reliable even after power loss, usually requiring file/directory `fsync` as well;
4. **Cross-writer concurrent CAS**: commit only if the file still has a specified revision/byte sequence;
5. **Multi-file transaction**: either every operation succeeds or all are rolled back.

Pi/Hashline batched Edit provides item 1. Claude's low-level write makes a best effort to use temp + rename but can silently fall back, so it only attempts item 2 and does not fully provide items 3 or 4. OpenCode V2's `writeIfUnchanged` is a conditional write protected by an in-process lock, not cross-writer CAS. None of the multi-file Patch implementations above—Grok compatibility presets, OpenCode, or Codex—provides item 5. Reports and tool errors must not present one of these layers as another.

## Design Recommendations for nanoPyCodeAgent

### Current Constraints

nanoPyCodeAgent currently exposes only `read`, `write`, and `bash`, with Claude Sonnet 4.6 as the default model. A single-threaded loop executes tool calls in the order returned by the model. The [system prompt and toolset](../../../src/nanopycodeagent/agent.py#L37-L50) and [sequential dispatch](../../../src/nanopycodeagent/agent.py#L169-L179) mean there is currently no in-process concurrent lost-update problem.

The existing `write` is explicitly last-writer-wins: it calls `Path.write_bytes` directly, does not require a prior Read, does not check a revision, provides no atomic replacement, and follows symlinks that point to regular files. See [`write_tool.py`](../../../src/nanopycodeagent/write_tool.py#L89-L153). `read` loads at most 10 MB for an entire file and strips CRLF's `\r` in its display. The [size limit](../../../src/nanopycodeagent/read_tool.py#L13-L23) and [line-ending view](../../../src/nanopycodeagent/read_tool.py#L117-L129) mean that multi-line old text copied by the model usually contains only LF. A new Edit must be compatible with these actual semantics; it cannot suddenly claim a security boundary that Bash can bypass and Write does not provide.

### Conclusion: Add a Thin, Exact, Single-Replacement Edit Now

`write` already handles new files and whole-file rewrites, but ordinary code modifications still require retransmitting the entire file or falling back to Bash. Edit now offers direct benefits in token usage, preservation of untouched content, and old-text preconditions, making it worthwhile as a fourth built-in tool.

The first version should use:

```text
Edit(
  path: string,
  old_text: string,
  new_text: string,
  replace_all: boolean = false,
)
```

`path` keeps the interface consistent with this project's Read/Write tools; snake_case matches Python and the current schema style. Although Claude Code uses `old_string`, a clear tool description is enough to teach the default Claude model. There is no need to fragment this project's field naming merely to copy one product.

The exact contract for the first version should be:

1. Edit only existing regular UTF-8 files; missing targets, directories, FIFOs, and devices fail. Creation and whole-file overwrite remain the responsibility of `write`.
2. `old_text` must not be empty, and `old_text == new_text` fails. `new_text=""` is valid and means exact deletion, with no hidden behavior such as “also remove the next newline.”
3. Perform an exact literal match first (item 6 permits one, and only one, subsequent CRLF retry). Zero matches fail. More than one match with `replace_all=false` fails and reports the match count. `replace_all=true` replaces every non-overlapping match and returns the actual count.
4. Do not use regex, trim, indentation, similarity, or Unicode fuzzy matching. The only permitted input conversions are the BOM and line-ending conversions in items 5 and 6. They are deterministic and enumerable and must be stated truthfully in the tool description; unlike OpenCode V1 and Pi, the tool must not claim exact matching to the model while implementing a wider matching boundary. Errors should prompt the model to Read and expand or correct the context. The first version has no pre-execution diff approval, so an extra retry is preferable to silently expanding the authorized mutation range.
5. Decode UTF-8 strictly and reject invalid UTF-8 and files containing NUL. `read` uses the replacement character for invalid bytes to make them viewable; if Edit round-tripped the file that way, it would permanently corrupt the original bytes. Strip a UTF-8 BOM before matching and restore it unchanged when writing. This cannot be omitted: `read` currently does not strip U+FEFF, so the model sees an invisible character at the start of the first line; failing to strip it would make `old_text` targeting that line mysteriously fail. Pi and OpenCode V2 handle it this way as well.
6. To match Read's line-ending view, follow OpenCode V2's approach with **one deterministic conversion**, not several parallel candidates. First perform raw exact matching with `old_text` unchanged. Only if the match count is zero, the file contains `\r\n`, and `old_text` contains `\n` but no `\r`, retry exactly once with the LF→CRLF form of `old_text`; in that case, also convert `new_text` from LF to CRLF before writing. Do not take the union of both passes: uniqueness checks and `replace_all` counts occur only within the pass that actually matched, avoiding ambiguity from candidate deduplication and overlapping spans across encodings. (Taking a union would create exactly this ambiguity: for content `"a\r\na\na"` with `old_text="a\na"`, the two encodings respectively match `[3,6)` and `[0,4)`, which overlap.) If `old_text` explicitly contains `\r`, perform raw exact matching only, treating the model as expressing the original bytes. Both passes rewrite only matched spans, always preserving unmatched regions as the original bytes. Because the second pass runs only after the first has zero matches, one call can match only one line-ending style. In a mixed-line-ending file, fragments using the other style will not match in that call—an intentional fail-closed behavior, and the error must state that the CRLF retry was attempted. This limitation affects only multi-line `old_text`: single-line `old_text` without `\n` is independent of line endings, can match across both styles in the first pass, and does not trigger the retry.
7. Reuse the 10 MB `MAX_READ_BYTES` size limit because the implementation requires a whole-file read-compute-write cycle. Errors should explicitly recommend Bash or a purpose-built script for larger files.
8. Align path expansion, regular-file checks, symlink behavior, and error formatting with `read`/`write`. The first version still writes back directly and explicitly provides no mtime/CAS/atomic replacement.

### Capabilities Not Recommended for the First Version

- **Do not enforce a prior Read.** The current session has no read-revision registry, and Read may expose only a window. A unique `old_text` match already serves as a localized precondition. Recording mtime by force would add state without eliminating TOCTOU.
- **Do not add batched `edits[]`.** The current loop executes multiple tool calls sequentially. Start with a single replacement for model reliability and a small implementation. Upgrade like Pi only if either tool round-trip latency or the need for multiple edits within one file becomes a measured bottleneck, and retain only one public schema when doing so.
- **Do not add `apply_patch`.** A parser, multi-file partial commits, move/delete operations, and permission target sets would substantially enlarge the nano agent's core. The default Claude model is also more familiar with old/new Edit.
- **Do not add localized versions of a formatter, LSP, history, approval, or workspace sandbox.** These belong to the overall mutation/exec control plane. Path protection on Edit alone can be bypassed through Bash.
- **Do not add a per-file queue yet.** Tool execution is currently single-threaded. When parallel tool calls are actually introduced, key a shared mutation queue by canonical/real path and place the entire Read-Compute-Write sequence inside it.

### Model Prompt, Results, and Terminal Display

The tool description should tell the model directly:

- Prefer Edit for ordinary localized changes; use Write for new files or complete rewrites; use Bash for bulk mechanical transformations;
- `old_text` must match file content literally and be unique by default. Two to four lines are usually enough. Do not include Read's line-number prefixes. The only exceptions are line endings and the BOM: Read displays LF, and the tool converts CRLF files itself, so the model need not and should not construct `\r` manually;
- On a mismatch, Read the latest content first rather than repeatedly submitting the same call;
- Use `replace_all` only when every identical literal is intentionally being changed.

Keep a successful result concise, for example:

```text
[edited src/app.py: replaced 1 occurrence, lines 42-44]
```

In the terminal, show `[edit] path` and a collapsed small old/new diff. Do not place the complete large strings in the tool result again, because they are already present in the assistant's tool input. If generating a unified diff, give it a hard limit similar to Bash/Read and mark truncation explicitly.

Errors should contain recovery information: not-found should recommend reading again; duplicate should return the match count and recommend adding context or explicitly using `replace_all`; invalid UTF-8, oversize files, and non-regular files should each explain why they cannot be round-tripped safely instead of collapsing into “edit failed.”

### Recommended Test Matrix

The first version should cover at least:

- Unique replacement, deletion, Unicode, empty files, and no-op changes;
- Not-found, duplicate matches, `replace_all`, and returned counts;
- LF, CRLF, no final newline, and preservation of untouched content in files with mixed line endings;
- Multi-line LF-form `old_text` matching a CRLF file and writing back as CRLF; one call matching only one style in a mixed-line-ending file while failing closed on the other; single-line `old_text` matching across both styles without triggering a retry; `old_text` that explicitly contains `\r` using raw exact matching only; correct `replace_all` counts in each pass;
- Stripping the UTF-8 BOM before matching and restoring it when writing, including successful `old_text` matching against the first line; rejection of invalid UTF-8 and NUL;
- Missing targets, directories, FIFOs/devices, and files above the size limit;
- `~`, relative/absolute paths, and symlink behavior consistent with Write;
- Collapsed terminal previews and correct `is_error` values in tool results;
- Multiple Edit calls in the same model response observing the result of each previous call in order.

### Conditions for Further Evolution

When the product introduces parallel calls, an approval UI, undo, remote file systems, or a restricted mode, establish a shared mutation core for Write/Edit/Patch: canonical paths, uniform permissions, expected digests, a per-file queue, best-effort atomic replacement, mode/BOM/line-ending policies, before/after events, and bounded diffs. Bash must be brought under the same OS/container/VM file-system boundary at the same time, or the control plane remains bypassable.

The final recommendation can be summarized as follows:

> What nanoPyCodeAgent needs now is a thin Edit that “fails on inexact matches and describes its semantics honestly,” not the full control plane of a mature Agent compressed into one Python file. First use a unique old-text precondition to address token costs and accidental overwrites in localized modifications. Upgrade the mutation core only when the architecture genuinely develops concurrency, approval, and remote-access requirements, rather than simulating safety in advance.
