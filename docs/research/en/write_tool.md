# Comparing File-Writing Tool Designs Across Five Agent Projects

> Generated from the Chinese source [`../zh-CN/write_tool.md`](../zh-CN/write_tool.md). Do not edit by hand.

## Scope of the Research

This document examines the model-callable file-writing tools in five mainstream code-agent projects, focusing on two questions:

1. Bash can already create and overwrite files, so why design a separate `write` tool?
2. What exactly do the `write`, `edit`, `apply_patch`, and other file-mutation tools in these projects implement, and why do they implement those features?

Although the subject is `write`, whole-file writes cannot be considered in isolation. `write` usually forms a file-mutation protocol together with `edit` and `apply_patch`: the former expresses “what the final file should be,” while the latter two express “what should change relative to the current file.” This document therefore examines all three categories, but excludes ordinary `fs/writeFile` RPCs intended for GUI clients rather than for model use.

The conclusions are based on the following source snapshots. Links are pinned to the checked-out commits. `claude-code` is the third-party source mirror used in the current directory, not an official Anthropic open-source repository.

| Project | Current commit | Commit date |
| --- | --- | --- |
| `grok-build` | [`500129c`](https://github.com/xai-org/grok-build/tree/500129c714ad1b10e6095481f4a8387a2ec52649) | 2026-07-29 |
| `pi` | [`c13ffe1`](https://github.com/earendil-works/pi/tree/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87) | 2026-07-30 |
| `claude-code` | [`a371abb`](https://github.com/yasasbanukaofficial/claude-code/tree/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367) | 2026-04-05 |
| `opencode` | [`8c38d26`](https://github.com/anomalyco/opencode/tree/8c38d260eb6555d2824230be100fb2a7eadd7513) | 2026-07-30 |
| `codex` | [`578c1b2`](https://github.com/openai/codex/tree/578c1b2230288104041e880a86d0f7f3a5ca6e47) | 2026-07-30 |

## Conclusions

The user's intuition is correct: **creating or overwriting a file with a sequence of bytes is not complicated, and Bash is entirely capable of doing it.** A standalone `write` tool usually adds no new filesystem-level capability; what it adds is a layer of **structured mutation protocol and control plane**.

The difference between the two paths is roughly:

```text
Write / Edit / Patch
  → structured intent
  → schema validation
  → path resolution and permissions
  → conflict checks and concurrency coordination
  → filesystem mutation
  → diff, history, events, LSP, UI

Bash
  → arbitrary command string
  → shell expansion, pipelines, redirection, subprocesses
  → arbitrary side effects
```

Bash can manually reproduce any step above, but when an agent framework sees an arbitrary shell program, it is difficult to answer the following questions reliably before execution:

- Which file will ultimately be changed, and which file will it be after symbolic links are resolved?
- Is this a create, overwrite, local replacement, move, or delete operation?
- What will the file look like when the user approves the operation?
- Has the file been changed by the user, a formatter, or another tool since the model read it?
- Which diff, diagnostics, history snapshot, and audit event should be sent to the UI?
- Are parallel calls in the same turn writing to the same underlying file?
- How can the same semantics be ported to Windows, SSH, a VM, or a virtual filesystem?

A more accurate summary is therefore:

> Bash answers “can it write?”; dedicated file tools answer “with what semantics does the model write, who approves it, how are incorrect writes prevented, and how does the system know what was written?”

The converse must also be emphasized: **a dedicated `write` tool is not itself a security boundary.** If the agent also has unrestricted Bash access, path protections implemented only in `write`/`edit` can still be bypassed through `printf > file`, Python, or `sed -i`. A real security boundary must cover every write channel—for example, by disabling Bash, placing Bash inside the same filesystem sandbox, or isolating the entire process at the OS, container, or VM layer.

## Overview

| Project | Model-facing file-mutation interface | Design orientation of whole-file writes | Key characteristics |
| --- | --- | --- | --- |
| Grok Build | Exposes `write`, `search_replace`, `apply_patch`, or Hashline `edit_file`, depending on the preset | The tool itself is thin; heavier capabilities live in session orchestration and adjacent editing protocols | Path permissions, plan gate, hooks, batch locks keyed by the path string in the arguments, mutation events, hunk/rewind support; `search_replace` and Hashline provide stronger preconditions |
| Pi | Enables `read`, `bash`, `edit`, and `write` by default | Lightweight, embeddable, and backend-replaceable | Automatic directory creation, tolerant path handling, a serial queue for the same underlying file, abort support, TUI preview, extension hooks, SSH/VM/`ExecutionEnv` support |
| Claude Code | `Write`, `Edit`, plus `NotebookEdit` | The heaviest “managed whole-file replacement” | Mandatory full Read first, mtime/content stale-write protection, path and symlink permissions, history backups, best-effort atomic replacement, permission-bit preservation, diff, LSP, editor notifications |
| OpenCode | Both V1 and V2 provide `write`, `edit`, and `apply_patch` | Two generations coexist in one repository; V1 has thick integration, while the V2 mutation core is stricter | Location boundaries, canonical paths, fine-grained permissions, BOM/newline handling; V2 edit provides byte-level CAS, while V1 provides formatters, events, LSP, and fuzzy editing |
| Codex | **No standalone whole-file `Write`**; uses `apply_patch` with a free-form syntax | Treats structured Patch as sufficient for both creation and modification; ordinary commands remain the responsibility of `exec_command` | Add/Delete/Update/Move, multi-file patches, context validation, approval and sandboxing, remote FS, structured diff/events; not a multi-file transaction |

These five projects effectively provide three different answers:

1. **Heavyweight dedicated tool**: Claude Code incorporates read state, permissions, history, disk writes, and IDE integration into the `Write` lifecycle.
2. **Lightweight structured interface**: Pi and Grok keep the whole-file `write` implementation simple; most of its value comes from schemas, hooks, UI, queues, events, and replaceable backends.
3. **No whole-file Write**: Codex provides only `apply_patch`; creating a file is an `Add File` patch, and a complete rewrite can also be expressed as a patch.

## Why Build a Dedicated Writing Tool?

### 1. Treat File Contents as Data, Not as Part of a Shell Program

`write({ path, content })` still requires correctly generated JSON, but `content` is no longer processed by shell variable expansion, command substitution, globs, heredocs, or redirection syntax.

Writing a file that contains backticks, `$()`, quotes, an arbitrary heredoc delimiter, or a binary NUL with Bash requires the model to handle both the “content language” and the “command language” correctly. A dedicated tool separates the two, and malformed JSON can be returned to the model as a schema error before execution so that it can be corrected.

This is also a cross-platform concern: a unified file API does not depend on Bash, `sed`, or `perl` happening to be installed on the target machine, nor does it require the model to master the quoting rules of POSIX shells, PowerShell, and `cmd.exe` separately.

### 2. Turn “Where to Write” into an Authorizable Resource

For a structured call, the framework knows the target path before execution and can:

- Normalize relative paths, `..`, and the home directory.
- Resolve the real paths of existing targets and parent directories.
- Check whether symbolic links escape the workspace.
- Authorize in-workspace files separately from explicitly external absolute paths.
- Reject all mutations in plan mode.
- Show the UI which file will be modified.

For arbitrary Bash, static analysis of `command` can usually handle only simple shapes such as `>`/`>>` reliably. Variables, functions, `eval`, subprocesses, interpreter scripts, dynamic filenames, and symlinks make it unreliable to derive the exact write set before execution.

This merely makes the policy enforcement point clearer; it does not create security automatically. Pi's security documentation explicitly states that tools inherit the permissions of the running process and have no built-in sandbox. Its path-protection extension example intercepts only `write`/`edit`, so it can be bypassed if Bash remains enabled. [Pi's default tools](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/agent-session.ts#L2556-L2595) and its [security-boundary documentation](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/docs/security.md#L31-L53) make this especially clear.

### 3. Turn “Which Old Version I Am Modifying” into a Precondition

One of the most dangerous write errors for an agent is not a syntax error, but a silent clobber:

1. The model reads old content.
2. The user, a formatter, or a parallel tool changes the file.
3. The model overwrites the entire file based on the old content.
4. The intervening update is silently lost.

A dedicated protocol can choose different strengths of protection:

- Claude Code requires an existing file to have been read in full and compares its mtime after that read; immediately before writing, it reads synchronously again and falls back to content comparison when necessary.
- OpenCode V2's `edit` reads the original bytes after permission is approved, then calls `writeIfUnchanged(expectedBytes)` while holding the same canonical-path lock at commit time.
- Edit/SearchReplace/Patch operations require the old text or context to still match; some Edit/SearchReplace implementations also require the match to be unique and reject the operation otherwise.
- Pi serializes in-process `write`/`edit` calls through a mutation queue for the same underlying path.

These mechanisms provide different levels of protection, and none is equivalent to a cross-process, kernel-level atomic compare-and-swap. An external program can still race between “check” and “write”; ordinary cross-process file locks usually coordinate only writers that participate in the same locking protocol. Stronger guarantees require mandatory revision/CAS semantics, a transactional backend, or complete isolation—not treating an advisory lock as a boundary that all processes must obey.

### 4. Coordinate Changes to the Same File Across Parallel Agents

Modern agents often execute multiple tool calls concurrently within a single turn. If two edits both perform “read old file → compute new content → write back,” the later write overwrites the earlier one.

Dedicated file tools can queue operations by canonical path or `realpath`:

- Serialize operations on the same underlying file.
- Continue processing different files in parallel.
- Try to coalesce symlink aliases into the same queue.
- Hold the lock for the entire read-compute-write sequence, not just the final `write()`.
- On abort, wait for the underlying I/O to settle before releasing the lock so that the canceled call does not interleave with a subsequent write.

Pi's implementation and documentation explicitly describe this queue as a mechanism for preventing lost updates: [mutation queue](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/file-mutation-queue.ts#L1-L60), [extension documentation](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/docs/extensions.md#L1865-L1873).

Bash writes and external editors do not automatically participate in such an in-process queue. Giving Bash the same guarantee requires proxying all file I/O through the same mutation service or relying on workspace isolation at a higher layer.

### 5. Generate Reviewable Information Before User Approval

A structured edit or patch can calculate the following before writing to disk:

- Whether the operation is a create, update, delete, or move.
- A unified diff.
- Additions and deletions.
- The number of matches and the fuzzy-matching method used.
- The set of canonical resources that will be affected.

The UI can therefore display an actual mutation preview instead of merely showing a shell command that might indirectly invoke ten programs. After the write, it can also return the final diff, so post-processing by a formatter does not cause the approved result and the actual result to diverge silently.

Whole-file `write` preview strategies vary: Pi shows only the new content to be written; Claude Code and OpenCode V1 read the old content and generate a diff; OpenCode V2 whole-file write does not generate a diff.

### 6. Integrate History, Events, Formatters, LSP, and Editors

A dedicated tool call provides a stable lifecycle boundary:

```text
before_tool / permission
→ before_file_edit snapshot
→ mutate
→ formatter
→ file-written event
→ LSP didChange / didSave / diagnostics
→ UI diff / history / telemetry
→ after_tool
```

Claude Code, OpenCode V1, and Grok each connect some of these stages to their file tools. When only arbitrary Bash is run, the framework generally has no option but to scan the entire working tree after the command finishes; that cannot provide a reliable pre-execution diff, and it is difficult to distinguish changes made by the current command from changes made by background processes, the user's editor, or a formatter.

### 7. Apply the Same Semantics to Different Execution Backends

Pi injects operations such as `readFile`, `writeFile`, and `mkdir` into its tools, while the Harness version requires all built-in tools to go exclusively through a host-provided `ExecutionEnv`. Repository examples reuse the same `write`/`edit` protocol for SSH hosts and Gondolin VMs: [operations interface](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/write.ts#L21-L40), [Harness constraint](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/agent/docs/agent-harness.md#L82-L84).

Codex likewise routes final Patch execution to a local, sandboxed, or remote filesystem implementation rather than requiring a complete shell on the remote system. This turns file mutation into a capability interface that the host can provide.

## Implementations by Project

### 1. Grok Build

#### The Tools Actually Exposed Depend on the Preset

Grok Build maintains multiple mutation protocols simultaneously rather than giving every model the full set of overlapping tools:

- The original `default_grok_build_toolset()` lists only `search_replace`.
- The current `grok-build` workspace preset adds an OpenCode-style `write` to that set.
- The default `AgentBuilder` also has `write_file_enabled` set to true and dynamically adds the write tool when none is present, so the default runtime toolset is likewise `search_replace` + `write`.
- The Codex preset uses `apply_patch`.
- The OpenCode preset uses `edit`/`write`.
- The optional Hashline configuration replaces the standard read/search/edit slots, but retains a standalone `write` when the default write feature is enabled.

These combinations are registered centrally in the [agent preset configuration](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-agent/src/config.rs#L170-L228) and [tool registry](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/registry/types.rs#L674-L757); the logic that dynamically adds Write by default is in [`AgentBuilder`](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-agent/src/builder.rs#L706-L765). This design shows that tool shape is also part of the model-adaptation layer: different models have different training distributions for whole-file writes, string replacement, patches, or hash anchors.

#### `write`

The model input consists of `file_path` and `content`. During execution, the tool:

1. Maps the model-provided path to the currently displayed workspace or forked worktree.
2. Reads the old content and existence state on a best-effort basis.
3. Creates parent directories recursively.
4. Writes the full content through the filesystem backend.
5. Emits a `FileWritten` event containing the previous and new content plus `is_new`.
6. Returns the create/update type, a structured whole-file edit, and line-count statistics.

The main implementation is [`OpenCodeWriteTool`](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/implementations/opencode/write/mod.rs#L20-L195).

Here, the old content is read to populate the mutation event and result; it is not a read-before-write guard. The current whole-file `write`:

- Does not check whether the model called Read first.
- Does not compare an mtime, hash, or expected bytes.
- Does not use a temporary file followed by rename.
- Uses straightforward last-writer-wins semantics.
- Retries only transient Windows sharing/lock failures in the local backend.

A read failure is treated as if the target did not exist, and processing continues rather than failing closed; this internal Read therefore cannot be interpreted as a safety check.

The corresponding local disk write is implemented by [`LocalFs::write_file`](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/computer/local/file_system.rs#L56-L87).

Heavier capabilities live in the outer session executor: a plan-mode gate, a pre-tool hook, edit permission requested for the target file, and a same-path mutex within one batch of model calls. [Permissions and hooks](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-shell/src/session/acp_session_impl/tool_calls.rs#L952-L1160) and the [batch lock](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-shell/src/session/acp_session_impl/tool_calls.rs#L453-L504) are reused by all structured writing tools. The lock key comes from the raw path string in the arguments and is valid only within the current parallel batch; `a.py`, `./a.py`, an absolute path, and a symlink alias can still receive different locks.

`FileWritten` is in turn consumed by the notification bridge for hunk tracking, auditing, and rewind. Thus, even though the `write` core is simple, the system still knows the before and after contents. The [event structure](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/notification/types.rs#L185-L209) explicitly stores the previous content, while the [notification bridge](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-shell/src/tools/notification_bridge.rs#L353-L376) passes it to the hunk tracker and rewind snapshot.

#### `search_replace` and Hashline

`search_replace` expresses a local edit with `old_string`/`new_string`:

- By default, the old string must be unique unless `replace_all` is explicitly set.
- `old_string=""` can also create or completely overwrite a file, and the protection that prevents an empty old string from overwriting an existing nonempty file is not enabled by default.
- It preserves CRLF.
- It can perform a limited fallback for Unicode confusables.
- It can reject targets matched by `.gitignore`.
- It returns a structured diff and context.
- “Read first” is primarily encouraged through the tool description and dependency metadata; no session read revision is enforced.

The implementation entry point and parameter semantics are documented in [`search_replace`](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/mod.rs#L59-L139).

The optional Hashline protocol makes Read return “line number + content hash” anchors. A single edit can combine replace, insert-after, and whole-file write operations. All anchors are validated against the current content before any write; a stale, ambiguous, overlapping, or missing anchor causes the entire logical batch of mutations to fail before writing. If validation succeeds, the new content is written once. The [Hashline interface](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/implementations/grok_build_hashline/edit/mod.rs#L25-L48) and [batch validation](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/implementations/grok_build_hashline/edit/apply.rs#L143-L305) embody the idea of “preventing the model from editing against stale context through explicit preconditions.” Hashline's built-in whole-file write carries no anchor and remains a complete overwrite.

Here, “the entire batch fails” describes in-memory mutation-validation semantics; it does not mean that the underlying filesystem write is transactional or crash-atomic. The current HashlineEdit metadata and run path also do not emit `FileWritten`, so although a structured diff is available, Grok's hunk-attribution and rewind before-snapshot notification chain does not run as it does for OpenCode Write/SearchReplace. The [Hashline execution path](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/implementations/grok_build_hashline/edit/mod.rs#L213-L434) shows that it reads, computes, writes, and returns the result directly.

### 2. Pi

#### `write` Itself Is Very Thin

The public schema contains only:

```text
path: string
content: string
```

The tool promises to create or overwrite a file and automatically create parent directories. Its prompt tells the model to use it only for new files or complete rewrites, leaving local modifications to `edit`. See the [schema and description](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/write.ts#L14-L40).

The execution layer implements:

- Tolerant handling of relative and absolute paths, `~`, `file://`, a leading `@`, and special Unicode spaces.
- A per-file mutation queue entered after resolving an existing file through `realpath`.
- Recursive `mkdir`.
- AbortSignal checks before and after I/O.
- Injectable `writeFile`/`mkdir` operations.
- The written length in a successful result.
- A streaming TUI display of the target path and syntax-highlighted new content, collapsed to the first ten lines by default.

The core call is in [`write.ts`](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/write.ts#L181-L260).

The abort semantics are worth noting: once the underlying I/O begins, it may not be cancelable. Pi waits for it to settle before reporting the abort and releasing the queue, preventing an unfinished write from interleaving with the next one. This provides concurrency ordering, not rollback.

#### `edit` Handles the Complexity of Local Mutations

Pi's `edit` accepts multiple `{ oldText, newText }` entries in one call:

- All old text is matched against the same original snapshot.
- Empty targets, missing matches, multiple matches, overlaps, and no-ops are rejected.
- Once all entries pass validation, they are applied in reverse order and written only once.
- If exact matching fails, it can tolerate trailing whitespace, Unicode NFKC, smart quotes, dashes, and special spaces.
- It preserves the BOM and the original newline style.
- It returns a compact diff for the TUI, a standard unified patch, and the first changed line.
- When the arguments are complete, it can generate an asynchronous diff preview before actual execution.

The multi-replacement algorithm is in [`edit-diff.ts`](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/edit-diff.ts#L251-L374), and execution and results are in [`edit.ts`](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/edit.ts#L287-L430).

#### Extensions and Boundaries

A `tool_call` hook can change arguments or block a call, while a `tool_result` hook can replace the result; an extension with the same name can also override a built-in implementation. This gives path protection, approval, auditing, SSH/VM backends, and custom renderers stable integration points.

Pi's limitations are equally explicit:

- Whole-file `write` has no prior-Read, mtime, hash, or expected-content check.
- The local implementation calls `writeFile` directly, with no temp + fsync + rename sequence.
- `write` does not read the old file to generate a diff; it previews only the new content.
- The mutation queue coordinates only Pi tools using the same queue, not Bash or external processes.
- Paths are not restricted to the cwd by default; `realpath` exists to coalesce queue entries, not to provide a sandbox.
- Tool arguments are not schema-validated again after an extension hook changes them.
- Bash is enabled by default, so hook-level path protection cannot independently form a permission boundary.

Pi's design emphasis is not “writing files better than Bash,” but obtaining a TUI, hooks, concurrency, and a replaceable execution environment through the smallest practical protocol.

### 3. Claude Code

#### A Clear Division of Responsibility Between Write and Edit

`Write` takes only an absolute `file_path` and the complete `content`. Its prompt explicitly says:

- Use `Write` only for new files or complete rewrites.
- Prefer `Edit` for modifying existing files because it sends only a diff.
- Existing files must first be read in full, or the tool fails.

See the [`FileWriteTool` description](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileWriteTool/prompt.ts#L1-L19). The system prompt also explains the product motivation directly: dedicated tools make work easier for users to understand and review, so files should not be created with heredocs or `echo` redirection. See the [system tool guidance](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/constants/prompts.ts#L286-L309).

#### Read First Is Actually Enforced at Runtime

This is not merely a prompt instruction:

1. Expand the path and check whether the content writes secrets into team memory.
2. Match deny rules early.
3. Do not stat a UNC path before permission is granted, avoiding Windows SMB/NTLM credential leakage.
4. Require a complete Read state for an existing file.
5. Reject the operation if the file's mtime postdates the prior Read.
6. Immediately before writing, synchronously read metadata and mtime again.
7. In environments such as Windows where mtime can produce false positives, fall back to content comparison if the file was read in full.
8. Deliberately avoid an asynchronous yield between the check and the write, narrowing the in-process race window.

Input checks are in [`validateInput`](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileWriteTool/FileWriteTool.ts#L153-L218), and the final pre-write recheck is in [the same tool's call](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileWriteTool/FileWriteTool.ts#L249-L305).

Permission checks consider not only the input string, but also the original path, the symlink chain, the nearest existing parent of a dangling target, special files, and the final resolved path, preventing authorization based only on the superficial path. See [file-operation permission resolution](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/utils/fsOperations.ts#L288-L381).

#### Writing to Disk and Post-Processing

Execution also:

- Creates parent directories automatically.
- Saves a file-history snapshot before writing.
- Preserves the encoding of an existing file.
- Treats the model-provided content as a complete replacement, respecting its explicit newlines instead of silently retaining the old file's CRLF style.
- Writes through a symlink to its target rather than replacing the link itself.
- Writes and flushes a temporary file in the same directory, preserves the original permission bits, and then renames it over the target.
- Cleans up the temporary file and falls back to a direct flushed write if the atomic-write path fails.
- Notifies LSP with `didChange`/`didSave` and clears stale diagnostics.
- Notifies the VS Code diff view.
- Updates Read state so that subsequent edits use the new version.
- Returns create/update status, a structured patch, the original content, and line-count statistics.

The best-effort atomic write and fallback are implemented by [`writeFileSyncAndFlush`](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/utils/file.ts#L354-L477); LSP, editor integration, and diff results are in [`FileWriteTool.call`](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileWriteTool/FileWriteTool.ts#L297-L416).

This is the most complete whole-file `write` lifecycle among the five projects, but it still has boundaries:

- If atomic rename fails, it falls back to a non-atomic overwrite.
- Read/mtime/content comparison is not a cross-process transactional CAS.
- Disk writes themselves use synchronous I/O.
- Whole-file content has a high token cost, so the prompt still instructs the model to prefer `Edit` for existing files.
- Bash is a separate capability channel, so security still depends on a unified permission and sandbox design.

### 4. OpenCode

The current OpenCode repository contains two implementations at the same time:

- V1/legacy: `packages/opencode/src/tool/*`, still used by the old Session/CLI/TUI path.
- Core V2: `packages/core/src/tool/*`, the newer Location-scoped, schema-first architecture.

They must not be conflated. V1's file tools have more complete integrations, while V2's mutation primitives and concurrency semantics are clearer. The individual V2 file-tool implementations still lack formatter, explicit file-edit/watcher events, and LSP integration, and snapshot/undo integration in those implementations remains marked TODO. However, the V2 session layer already has a general Snapshot capture/diff/restore service, so it would be incorrect to say that V2 as a whole has no snapshots. The [V2 `write` TODO](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/tool/write.ts#L19-L47) and [session-layer Snapshot calls](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/session/runner/llm.ts#L217-L333) illustrate these two layers respectively.

#### Why It Provides write, edit, and apply_patch Together

- `write`: Create a file or explicitly overwrite it when the model already knows the complete final content.
- `edit`: Express a small change with old/new strings, saving tokens and preserving the rest of the content.
- `apply_patch`: Express multi-file add/update/delete operations in one call, suited to models that work well with diffs.

The V1 registry selects interfaces by model: modern non-OSS GPT models receive `apply_patch`, while other models mainly see `edit` + `write`, avoiding presenting every overlapping tool to every model simultaneously. See [V1 tool selection](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/opencode/src/tool/registry.ts#L286-L306).

#### Core V2 Location and Permissions

The three mutation tools share `LocationMutation`:

- Relative paths must remain within the current Location; crossing the boundary with `../` fails immediately.
- Existing targets are resolved through `realPath`.
- For a nonexistent target, the nearest existing ancestor directory becomes the canonical anchor.
- A workspace symlink pointing outside the workspace produces `location_escape`.
- An explicit external absolute path first requests `external_directory` permission for its parent directory, then `edit` permission for the specific resource.
- Permission resources use Location-relative identities for internal paths and canonical absolute identities for external paths.

See [`LocationMutation`](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/location-mutation.ts#L90-L152).

#### Core V2 `write`

V2 whole-file `write` resolves and authorizes the target, creates parent directories automatically, preserves a UTF-8 BOM, and returns `created`/`wrote` status, the canonical target, the permission resource, and `existed`. See the [execution flow](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/tool/write.ts#L63-L97).

It intentionally retains clear last-writer-wins semantics:

- It does not require a prior Read.
- It has no mtime, hash, or expected-bytes check.
- It does not generate a diff.
- It does not perform a temporary-file rename.
- It does not explicitly manage or return the mode. Overwriting an existing regular file generally retains the underlying file permissions; permissions on a new file depend on backend defaults and the umask.
- It provides only in-process serialization for the same canonical target.

V2 `edit` is stricter:

- It requires an exact match for the old string.
- It prohibits an unchanged replacement and an empty old string.
- The match must be unique by default, unless `replaceAll` is set explicitly.
- It preserves the BOM and original newline style.
- It returns replacements, a unified diff, and addition/deletion counts.
- After authorization, it reads the original bytes, then commits under a canonical-path lock using `writeIfUnchanged(expectedBytes)` and reports stale if the file has changed.

See [`edit`](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/tool/edit.ts#L42-L159) and [`FileMutation`](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/file-mutation.ts#L69-L166).

V2 `apply_patch` first parses and resolves all hunks, authorizes them in a batch, and reads and preflights every update/delete before committing them in order. Add uses create-only `wx`, so it cannot overwrite a file that appears during approval; Update uses expected bytes; Move is not yet supported. See the [Patch flow](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/tool/apply-patch.ts#L85-L202).

It is explicitly not transactional: if a later operation fails during the commit phase, earlier successful mutations remain and are listed in the error. Delete also has no expected-content CAS at commit time.

#### V1's Thick Integration

V1 `write` reads the old content to generate a permission diff, preserves the BOM, writes after authorization, runs the formatter, publishes file/watcher events, touches the LSP, and waits for diagnostics. See [V1 `write`](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/opencode/src/tool/write.ts#L46-L122).

V1 `edit` also implements multiple layers of fuzzy replacers, a per-file semaphore, a final post-formatter diff, file events, and LSP error feedback. V1 Patch supports move, but both Add and Move can overwrite their targets, and neither provides V2's byte-level CAS.

One implementation/prompt-text mismatch worth recording is that V1 `write.txt` and `edit.txt` claim existing files must first be read or the tool will fail. The actual code does not query session Read history or mtime; it simply reads the current file itself and proceeds. The [prompt text](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/opencode/src/tool/write.txt#L1-L8) and [actual implementation](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/opencode/src/tool/write.ts#L46-L122) do not agree.

This demonstrates that “having a separate tool” merely provides a place to implement a guard; it does not guarantee that the guard actually exists. Research must distinguish among prompts, TODOs, and runtime code.

### 5. Codex

#### No Whole-File Write

Codex's standard local Coding Turn does not expose `write_file` or `edit_file` to the model; it provides only `apply_patch` with free-form input. App Server also has an `fs/writeFile` RPC, but that is intended for the host client rather than as a model tool and does not belong in this comparison.

`apply_patch` does not ask the model to assemble a shell command. It is a free-form tool with its own grammar:

- `*** Add File`
- `*** Delete File`
- `*** Update File`
- `*** Move to`
- Multi-file patches
- Context lines and an EOF anchor

The tool schema and syntax are defined by [`apply_patch_spec`](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/core/src/tools/handlers/apply_patch_spec.rs#L18-L31) and the [Lark grammar](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/core/src/tools/handlers/apply_patch.lark#L1-L19).

This provides the most direct counterexample to the question at hand: **needing structured file mutations does not imply needing a standalone whole-file `Write`.** Add File can already create a complete file, while Update Patch is better suited to ordinary code changes.

#### Implemented Capabilities

The execution chain:

1. Parses the complete patch.
2. Reads old files for Update/Delete, computing the new content and a unified diff for Update; Add directly carries the target content.
3. Validates all hunks before executing any action.
4. Searches for context in stages: exact → ignore trailing whitespace → trim both sides → normalize Unicode punctuation.
5. Classifies safety under the permission profile, requests approval when necessary, and uses a platform sandbox in managed configurations.
6. Executes against a local, sandboxed, or remote filesystem.
7. Sends begin/end events for the execution lifecycle; when the corresponding feature is enabled, it can also stream patch-diff updates while arguments are being generated.
8. Returns stable A/M/D results and integrates with hooks.

Parsing and prevalidation are implemented in the [`apply-patch` invocation](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/apply-patch/src/invocation.rs#L180-L239), context matching in [`seek_sequence`](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/apply-patch/src/seek_sequence.rs#L1-L96), and safety classification in [`safety.rs`](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/core/src/safety.rs#L32-L86).

Even if the model invokes it through a shell-shaped call such as `apply_patch <<'PATCH' ...`, Codex recognizes that constrained form and routes it through the same Patch safety chain rather than treating it as arbitrary shell side effects.

#### Important Boundaries

- A multi-file Patch is not transactional: hunks are written in order, and a later failure does not roll back previously successful items.
- Add File can currently overwrite an existing target; it is not create-only.
- Move writes the target first and then deletes the source, so a failed deletion can leave both files in place.
- The end result is still a whole-file text rewrite; binary deltas and mode metadata are unsupported.
- `apply_patch` does not run in parallel by default and acquires an exclusive lock on the shared execution gate for the tool batch. This is not a session-wide, process-wide, or file-level global lock, however, and it provides no cross-process revision CAS.
- An external user process can race between validation and the final write.
- No tool-local patch-size limit is evident in the `apply-patch` parser/runtime, although model, API, and context layers still constrain practical input size.

Sequential execution and retention of already-committed deltas after failure are implemented in the [`apply-patch` library](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/apply-patch/src/lib.rs#L390-L510).

Codex places much of the infrastructure in its general command-execution layer and Patch runtime instead of building separate model interfaces for Read, Write, and Edit. This reduces the number of tools but does not eliminate the complexity of permissions, sandboxing, output, events, remote filesystems, and concurrency control; it merely moves that complexity to a different layer.

## Mapping Features to Design Goals

| Feature | Primary problem addressed | Project examples |
| --- | --- | --- |
| `{ path, content }` schema | Separating content from commands, argument validation, cross-platform quoting | Pi, Claude Code, OpenCode, Grok |
| Semantic division among Write/Edit/Patch | Controlling tokens, preserving untouched content, adapting to different models | All five projects; Codex retains only Patch |
| Canonical-path / symlink permission checks | Permission aliases and path escape | Claude Code, OpenCode V2 |
| Queue coalescing by `realpath` | Making path aliases share an in-process write queue where possible | Pi |
| Automatic parent-directory creation | Saving one tool call and avoiding a preliminary `mkdir` | The create path in all five projects |
| Prior Read / mtime / expected bytes | Preventing stale-context overwrites of newer changes | Claude Code, OpenCode V2 edit |
| Exact old text / patch context / hash anchor | Turning assumptions about the old version into verifiable preconditions | Pi/OpenCode/Grok edit, Codex Patch, Grok Hashline |
| Per-file queue / lock | Preventing lost updates from parallel calls by the same agent | Pi, OpenCode V2; OpenCode V1 only for edit; Grok only for identical raw path strings in the same batch; Codex uses a coarser batch execution gate |
| Temp + flush + rename | Reducing the risk of a crash or interruption leaving a truncated file | Claude Code; most other whole-file Write implementations overwrite directly |
| Mode / permission-bit management | Avoiding damage to executable bits and other permissions when replacing a file | Claude Code |
| BOM / newline-style handling | Avoiding unrelated diffs from small changes or damage to encoding markers | Pi edit, OpenCode; Claude Code preserves encoding but respects model-specified newlines |
| Diff / additions / deletions | Approval, review, model feedback, telemetry | Claude Code, OpenCode edit/patch, Pi edit, Codex Patch |
| History / rewind / file events | Undo, auditing, UI synchronization, hunk attribution | Claude Code, Grok, OpenCode V1 |
| Formatter / LSP diagnostics | Creating an automatic mutation–diagnosis–repair loop after writing | Claude Code, OpenCode V1 |
| Operations / ExecutionEnv / FS trait | SSH, VMs, containers, remote or virtual filesystems | Pi, Codex, Grok |
| Hook and/or permission lifecycle | Blocking, rewriting, approving, and recording a mutation | All five projects have some subset; Pi relies mainly on extension hooks and has no built-in sandbox/approval |

## Costs and Pitfalls of Dedicated Writing Tools

### 1. They Can Easily Create Duplicate Implementations

If `write`, `edit`, `apply_patch`, and Bash each have separate path-resolution, permission, disk-write, and event logic, inconsistencies emerge:

- One tool checks symlinks while another does not.
- One tool replaces atomically while another truncates directly.
- One tool generates the final diff while another generates only the pre-approval diff.
- One tool participates in a same-file queue while Bash does not.
- The prompt claims Read is mandatory, but the runtime does not check state.

The parity gaps between OpenCode V1 and V2, and Bash bypasses in Pi, both show that the more dedicated tools there are, the more important it becomes to have a shared mutation core rather than duplicating multiple `writeFile()` calls.

### 2. “Structured” Does Not Mean “Atomic” or “Transactional”

These three concepts should be separated:

- **Structured**: the framework knows the operation's intent and target.
- **Single-file crash atomicity**: observers generally see either the complete old version or the complete new version.
- **Multi-file transaction**: the entire batch succeeds or rolls back as a unit.

Claude Code provides only a best-effort single-file temp + rename path and falls back on failure; Codex and OpenCode Patch are explicitly not multi-file transactions; Pi, Grok, and OpenCode whole-file writes primarily overwrite directly.

### 3. Whole-File Write Can Cost More Tokens

If the model must resend the complete content to modify three lines in a large file:

- It uses more input tokens.
- It is more likely to accidentally change parts of the file that were not meant to be touched.
- Conflict retries are more expensive.
- The UI must recompute a diff from the whole file.

Claude Code, Pi, and OpenCode therefore position `Write` for new files or complete rewrites and prefer `Edit`/Patch for ordinary changes. Codex goes one step further and does not provide a whole-file Write at all.

### 4. Models Can Waver Between Overlapping Tools

Putting three similar schemas into the system prompt consumes context and increases tool-selection errors. OpenCode switches between Patch and Edit/Write by model, while Grok uses presets to select SearchReplace, OpenCode, or Hashline protocols. This shows that tool interfaces need to be designed together with the model's training distribution.

### 5. They Can Create a False Sense of Security

Adding a “cannot change `.env`” hook to `write` is easy, but as long as Bash can still execute `python -c` or use redirection, the rule is not a boundary. The correct approach is to:

- Disable Bash in restricted mode; or
- Put Bash and file tools inside the same workspace/filesystem sandbox; or
- Control the entire agent at the container, VM, or OS-permission layer;
- Use hooks only as a friendlier policy and approval layer, without presenting them as the sole security mechanism.

## When Bash Is Already Enough

Using Bash alone is a reasonable product choice, especially when all of the following are true:

- The execution environment is trusted and handles only a temporary local workspace.
- The agent is single-threaded and will not modify the same file concurrently.
- The user does not need pre-execution diffs, per-file approvals, history rollback, or real-time IDE synchronization.
- There is no need to disable arbitrary commands while exposing only the ability to modify files.
- There is no need to support backends without a complete shell, such as SSH/VM/browser virtual filesystems.
- The model is well trained for shell use.
- The project is willing to invest in security, approval, and output control at the exec layer.

Codex proves that “no whole-file Write” is entirely viable, but it is not “bare Bash”: it still has structured `apply_patch`, and its command-execution layer itself provides sandboxing, approval, sessions, output budgets, and remote-environment support.

Bash also remains better suited to:

- Running formatters, code generators, compilers, or database migration tools.
- Applying mechanical transformations across many files.
- Managing chmod, symlinks, special modes, pipelines, and complex file selection.
- Using mature CLIs for operations not represented by dedicated tools.

## Recommendations for nanoPyCodeAgent

> **Revision dated 2026-08-04**: The first version of this section reduced the value of a thin `write` over Bash to “minor quoting convenience” and therefore recommended remaining Bash-first. After review, that framing was found to understate two benefits. The revised conclusion is: **a thin `write` is worthwhile now because it separates content from commands and improves terminal presentation—not because it provides a control plane.**

The principle “do not add a thin wrapper merely because mainstream agents all have one” still holds; the critical question is whether the rationale is genuine. There are two reasons to add one now:

**First, separating content from commands prevents silently corrupted files, not merely inconvenient quoting.** The typical failure when using a heredoc to write a file is not an error followed by a retry: if the delimiter is unquoted, `$var`, backticks, and `$()` inside the content are expanded by the shell. The resulting file is corrupted while the exit code remains 0, so the model receives no error to retry. If the content happens to contain the delimiter, the file is silently truncated. For a nano agent without diff review or post-write verification, these silent corruptions are precisely the failures that are hardest to detect. `write({path, content})` treats content as data and eliminates this entire class of failures from day one, without depending on any control plane.

**Second, this repository has already used `read` to reject the argument that “if Bash can do it, it does not need a dedicated tool.”** The `read` tool adds no filesystem capabilities beyond `cat`/`sed` either. It exists to standardize line numbers and output limits, and to return not only an explanation when something fails, but also an immediately actionable next step—for example, reporting the total line count or giving a Bash command for splitting overlong lines. These are purely structural and UX benefits. The value of `write` is exactly analogous: structured input, explicit error semantics, and terminal presentation. After tool-output shading, a Bash command carrying hundreds of lines of heredoc content is unreadable in the terminal, whereas a `write` call can follow Pi in collapsing its display to “target file + first few lines of content.”

The revised tradeoff between the two paths is therefore as follows.

### Path A (Revised): Bash + a Thin `write`

This is appropriate for nanoPyCodeAgent's current stage, which emphasizes a minimal implementation and a trusted local workspace:

- Retain Bash as the general-purpose interface for text and system operations; formatters, bulk transformations, appends, and similar work still use Bash.
- Implement the workspace sandbox, approval, and output budget at the exec layer.
- Add a thin `write`, with size and style aligned to `read_tool.py`: a `{path, content}` schema, rejection of directories and non-regular files, automatic parent-directory creation, and a collapsed terminal display. The tool description must not claim any security properties.
- Do not introduce prior-Read checks, mtime, `expected_revision`, or atomic replacement: in the current single-threaded design without an approval UI, they would be false assurances, and the semantics are simply last-writer-wins.
- Implement `write` before `edit`: `write` is the simplest implementation and has the least ambiguous semantics, whereas the complexity of `edit` lies entirely in matching semantics—uniqueness, fuzzy fallback, newline style—and `apply_patch` additionally requires its own parser. Add `edit` only when the token cost of whole-file rewrites becomes a real pain point.

### Path B: Build a Unified File-Mutation Control Plane

When the product needs diff approval, a restricted mode, parallel tool calls, remote environments, undo, or IDE integration, upgrade the file tools into a unified control plane. At that point the important consideration is not the tool names but establishing, first, a core shared by every mutation tool:

1. Normalize and canonicalize the target, with an explicit workspace and symlink policy.
2. Separate create from overwrite, supporting `must_not_exist` or `expected_revision`/`expected_digest`.
3. Recheck preconditions after permission approval.
4. Serialize read-compute-write by canonical path.
5. Write to a temporary file in the same directory, flush, preserve the mode, and attempt an atomic rename.
6. Return create/update/delete/move status, diffs, and old/new revisions uniformly.
7. Emit before/after, history, LSP/formatter, and other events uniformly.
8. Have `Write`, `Edit`, and `Patch` all call this core.
9. Keep Bash constrained by the same filesystem sandbox so it cannot bypass the boundary.

On top of this architecture, the model interface can remain small:

```text
Write(path, content, expected_revision?)
Edit(path, old_text, new_text, replace_all?, expected_revision?)
ApplyPatch(patch_text)
```

The revised final assessment is:

- **Building `write` as a control plane is not worthwhile yet: permissions, review, concurrency, history, and remote execution should still follow Path B when those needs arise (the original judgment stands).**
- **Building a thin `write` for content/command separation and terminal presentation is worthwhile now: it eliminates the entire class of silently corrupted heredoc output, based on the same value judgment already validated by the `read` tool.**
- **A thin `write` must be honest: it must not claim to be a security boundary or introduce stale-write and atomicity mechanisms that add no meaningful value in a single-threaded design.**
- **Defer `edit`/`apply_patch` and the control plane until real needs arise; when they do, all mutation tools should share a mutation core rather than wrapping `writeFile()` as an isolated feature (the original judgment stands).**
