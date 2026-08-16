# Comparing File-Reading Tools Across Five Agent Projects

> Generated from the Chinese source [`../zh-CN/read_tool.md`](../zh-CN/read_tool.md). Do not edit by hand.

## Scope

This document counts only **built-in tools that the model can invoke directly**. It does not conflate ordinary internal functions, test helpers, or RPCs intended for GUI clients with Agent tools. The conclusions are based on the following revisions checked out during the research. Source snapshots are not committed to this repository, so this document does not cite their local paths:

| Project | Current commit | Commit date |
| --- | --- | --- |
| `grok-build` | `c68e39f` | 2026-07-16 |
| `pi` | `5e336cfa` | 2026-07-15 |
| `claude-code` | `a371abb` | 2026-04-05 |
| `opencode` | `fab213312` | 2026-07-18 |
| `codex` | `1bbdb32789` | 2026-07-15 |

## Conclusions

| Project | Model-facing tool name | Core role | Text pagination | Non-text files |
| --- | --- | --- | --- | --- |
| Grok | `read_file` | Full-featured semantic file reader | `offset` and `limit`; up to 1,000 lines and 25,000 tokens by default | Images, PDFs, and PPTX; `.ipynb` read as text |
| Pi | `read` | Compact, embeddable reader with a replaceable backend | `offset` and `limit`; up to 2,000 lines or 50 KiB | Images |
| Claude Code | `Read` | Reader deeply integrated with permissions, context, and the skill system | `offset` and `limit`, with dual protection based on file size and token count | Images, PDFs, and Jupyter Notebooks |
| OpenCode | `read` | Location-scoped structured reader shared by files, images, and directories | `offset` and `limit`; up to 2,000 lines or 50 KiB for large files or explicit pagination | JPEG, PNG, GIF, and WebP; directory listings |
| Codex | **No dedicated text-reading tool**; normally uses `exec_command`, or `shell_command` in legacy configurations; uses `view_image` for images | Reuses the shell ecosystem, placing safety, session, and output controls in the command-execution layer | Implemented by commands such as `sed`, `rg`, and `head` | `view_image` supports images; no dedicated branch for PDFs or Notebooks |

The most important difference is that Grok, Pi, Claude Code, and OpenCode model “reading a file” as an explicit, read-only operation with structured parameters. Codex does not add another abstraction for text; instead, it lets the model invoke programs such as `rg`, `sed`, and `cat` through a general-purpose command-execution tool.

## Invocation Interfaces and Model-Visible Return Formats

Two layers must be distinguished here: a tool's internal implementation may return a struct or union type, while the model may ultimately see only a formatted segment of text. “Return format” in the table below refers specifically to the result actually visible in the model context, not the implementation's internal type.

| Project | Model invocation interface | Model-visible text or content | Return-format assessment |
| --- | --- | --- | --- |
| Grok | `read_file({ target_file, offset?, limit?, pages?, format? })` | Text comes from the internal `FileContent.content`; the first visible line and every line whose number is divisible by ten receive a `line number→` anchor. The unformatted source is also stored in `raw_output`, but it is not sent to the model as an ordinary text result | Formatted text; images and PDF pages use multimodal content blocks |
| Pi | `read({ path, offset?, limit? })` | The body remains unchanged and line numbers are not added automatically; when truncation or explicit pagination occurs, a note with the current range and the next `offset` is appended | Primarily plain text; images use a separate image content block |
| Claude Code | `Read({ file_path, offset?, limit?, pages? })` | Before the internal structured result enters the model context, it is converted to `tool_result.content`; every line receives a `line number→` or `line number<TAB>` prefix, and a `<system-reminder>` may be appended | Formatted text; images, PDFs, and Notebooks use dedicated content blocks |
| Classic OpenCode implementation | `read({ filePath, offset?, limit? })` | Returns an `output: string` wrapped in `<path>`, `<type>`, and `<content>`, with an `N: ` prefix added to every line of the body | XML-style formatted text |
| OpenCode V2 | `read({ path, offset?, limit? })` | Returns a structured union of `FileSystem.Content`, `TextPage`, or `ListPage`; the body is in the `content` field without line numbers, while pagination is expressed through `offset`, `truncated`, and `next` | Structured JSON; images additionally use a file content block |
| Codex | No dedicated text-reading tool; normally invokes `exec_command({ cmd, ... })` | The tool result is an object containing fields such as `output`, `exit_code`, and `session_id`; whether `output` is the original text, text with line numbers, or some other format depends entirely on the command executed | Structured command result; the format of the file body is not fixed |

Therefore, if “plain text” means the file body without added line numbers, tags, or a JSON wrapper, Pi comes closest. Claude Code, Grok, and classic OpenCode actively add positional or structural markers. OpenCode V2 preserves the original body but places it in a structured result. Codex delegates the format choice to the specific shell command.

## Code Agent File-Reading Tool Implementations

### 1. Grok: `read_file`

#### Tool entry point and parameters

- The model-facing tool name is `read_file`.
- Its parameters are:
  - `target_file`: a workspace-relative or absolute path;
  - `offset`: the starting line; accepts positive values, `0`, and negative values, with negative values locating lines backward from the end of the file;
  - `limit`: the number of lines to read;
  - `pages`: a PDF page number or range;
  - `format`: PDF output as either `image` or `text`.

#### Text reading

- The tool first reads the file as bytes, then converts it to text with fault-tolerant UTF-8 decoding; recognized binary files are rejected.
- By default, a single result contains at most 1,000 lines. Even if the caller supplies a larger `limit`, the configured ceiling takes precedence. A further 25,000-token ceiling protects the output.
- Exact windowed reads are supported. When a limit is exceeded, the tool suggests narrowing `offset`/`limit` or switching to a search tool. If the window contains only one extremely long line, it also suggests extracting characters with shell tools such as `jq` or `cut`.
- The actual text format does not prefix every line. The current implementation gives the first visible line and every line whose number is divisible by ten a `line number→` anchor, reducing the token cost of line numbers themselves.
- Text results can be streamed in chunks of approximately 4 KiB, with splits made at character boundaries, but the file itself is still loaded into memory in full before chunking.
- `SKILL.md` is an intentional exception: the tool ignores the supplied `offset`/`limit` and bypasses the normal line and token limits, ensuring that skill instructions are loaded in full.

#### Images and documents

- Images are detected by magic bytes rather than by trusting the extension alone.
- Images are converted to PNG, JPEG, or WebP accepted by the model endpoint, and automatically resized and compressed according to dimensions, total pixel count, and payload size. By default, the longest edge is at most 2,000 px, total area is approximately 1.05 Mpx or less, and the base64 payload is at most 768 KiB.
- PDFs are rendered as page-by-page images by default, or their text can be extracted with `format="text"`. When no page is specified, at most 10 pages are read automatically; with an explicit selection, at most 20 pages can be read at once. The file-size limit is 50 MiB and the processing timeout is 60 seconds.
- For PPTX files, the tool unpacks the archive and extracts the DrawingML text and speaker notes from each slide. Compressed input is likewise limited to 50 MiB, with a 60-second processing timeout.
- The tool description claims support for Jupyter Notebooks, but the current `read_file` implementation has no Notebook-specific branch; `.ipynb` files actually follow the ordinary JSON text path.

#### Additional integration with the Agent framework

- Depending on configuration, the tool can refuse to read files matched by `.gitignore`, reducing the risk of inadvertently reading secrets, build artifacts, and similar content.
- It attempts to correct Unicode filenames and produces friendlier suggestions for nonexistent paths.
- It can return structured errors such as “file does not exist,” “is a directory,” and “permission denied,” instead of only a mixed block of stderr.
- When reading a file, it can append matching Cursor rules so that path-specific rules enter the context alongside the source code.

### 2. Pi: `read`

#### Tool entry point and parameters

- The model-facing name is `read`.
- Its parameter set is small: `path`, a 1-based `offset`, and `limit`.
- Paths may be relative or absolute. The path layer also handles `~` and `@` prefixes, Unicode spaces, narrow no-break spaces in macOS screenshot names, NFD filenames, and curly-quote variants.

#### Text reading

- By default, the tool reads the complete file into a `Buffer`, then selects the requested line range and truncates the output.
- Returned content is limited to 2,000 lines or 50 KiB, whichever limit is reached first, while avoiding partial lines whenever possible.
- A truncated result explicitly reports the current line range, the file's total number of lines, and the `offset` to use next.
- If the first line alone exceeds 50 KiB, the tool does not silently truncate that line. Instead, it returns an executable `sed | head -c` suggestion.
- `limit` first selects the window requested by the user, after which the shared line/byte limit is applied. An out-of-range `offset` produces an error that includes the total line count.
- Unlike Claude Code and Grok, Pi does not automatically add line numbers to ordinary text returned to the model. This saves tokens, at the cost of requiring the caller to establish its own positional anchors when referring to a particular line.

#### Images

- JPEG, PNG, GIF, WebP, and BMP are supported and detected from file signatures; a non-image disguised with an image extension does not enter the image branch.
- Formats such as BMP that the model API does not accept directly are converted to PNG first.
- By default, images are resized to no more than 2000×2000 and the base64 payload is kept to approximately 4.5 MiB or less. The tool tries PNG and JPEG, multiple JPEG quality levels, and progressively smaller dimensions.
- Images are attached to the model as genuine image content blocks rather than embedding base64 text in ordinary output. If the model does not support visual input, the result explicitly states that the image was omitted.

#### Additional integration with the Agent framework

- `ReadOperations` abstracts `readFile`, `access`, and MIME detection into replaceable operations. The same tool can therefore connect to SSH or another remote filesystem without changing the model protocol.
- It supports `AbortSignal`, allowing the session to cancel long-running operations.
- The TUI applies syntax highlighting by extension and collapses `SKILL.md`, `AGENTS.md`, `CLAUDE.md`, and Pi documentation into compact displays. This mainly improves the human interface and does not change the file body sent to the model.

### 3. Claude Code: `Read`

#### Tool entry point and parameters

- The tool is exposed to the model as `Read`.
- Its parameters are the absolute path `file_path`, a 1-based `offset`, `limit`, and the PDF-specific `pages`.
- The tool declares itself read-only and safe for concurrent execution, and includes the path in permission matching.

#### Text reading

- Returned content uses a format similar to `cat -n`, with a line number on every line. The default uses a right-aligned `line number→content` format; an experimental flag can instead use a compact tab-separated format.
- Ordinary files smaller than 10 MiB take a one-shot fast path. Large files, pipes, and special files use streaming scans. The streaming path retains only lines within the requested window and merely counts lines outside it, so reading a small window from a 100 GiB file does not cause memory use to grow with the file size.
- Both paths remove a UTF-8 BOM, normalize CRLF to LF, and support session cancellation.
- The default output limit is 25,000 tokens. When `limit` is omitted, a 256 KiB total-file-size gate also rejects large files early; when `limit` is explicit, a small window can be read from a large file, while the final result remains subject to the token limit.
- The tool prompt says “2,000 lines maximum by default,” but the current core `call` implementation does not set a default `limit` of 2,000. Instead, it primarily relies on the 256 KiB and 25,000-token limits. A 2,000-line constant is explicitly used by the automatic attachment-ingestion path. This is a discrepancy between the implementation and the prompt in the checked-out source.
- When the same range of the same file is read again and its modification time has not changed, subsequent reads return only a short “file unchanged” message. This reuses content from earlier in the conversation, reducing context usage and prompt-cache cost.

#### Images, PDFs, and Notebooks

- Images are read as visual content and automatically resized, downsampled, or compressed according to the model's token budget. Original and displayed dimensions are returned as well, allowing the model to map coordinates back to the original image.
- PDFs can be sent directly as document blocks, or pages can be extracted and rendered as images according to `pages`. A page range is mandatory for PDFs longer than 10 pages, and at most 20 pages can be read at once. For files larger than 3 MiB, or when the model does not natively support PDFs, the tool attempts page extraction.
- `.ipynb` has a genuine Notebook branch: cells are parsed, with code, Markdown, output, and visualizations preserved, then mapped to a structured tool result instead of treating the Notebook as JSON text.
- Common binary extensions are rejected, except for natively supported types such as images, PDFs, and SVGs.

#### Additional integration with the Agent framework

- Before reading, the tool checks `Read(...)` allow/deny rules. Actual I/O for UNC paths is deferred until after user authorization, avoiding unapproved network authentication attempts.
- It explicitly blocks `/dev/zero`, `/dev/random`, stdin/tty, standard file-descriptor aliases, and other device files that could produce infinite output or block indefinitely.
- When a path does not exist, the tool tries macOS screenshot-space variants, candidate paths under the current working directory, and similar filenames, then offers a `Did you mean ...` suggestion.
- Reading a path can trigger skill-directory discovery and conditional skill activation. Automatically managed memory files also receive freshness information.
- Before text enters the model context, a malicious-code-analysis reminder is appended. Read events are also sent through hooks, listeners, and telemetry.

### 4. OpenCode: `read`

#### Tool entry point and layers

- The model-facing name is `read`; this section discusses the current V2 Location-scoped built-in tool.
- Its parameters are `path`, a positive 1-based integer `offset`, and a positive integer `limit`; the schema itself caps `limit` at 2,000. `path` can refer to a file or directory, so the current implementation no longer exposes a separate `list` tool.
- The implementation is deliberately split into two layers: `read.ts` handles the model schema, Location paths, permissions, file/directory dispatch, image normalization, and error projection; `read-filesystem.ts` handles independently testable I/O, pagination, format detection, and structured results.
- The return value is not a preformatted string, but a union of three structured results: `FileSystem.Content` for ordinary files, `TextPage` for paginated text, and `ListPage` for directories. Only images additionally produce a native media content block.

#### Text reading

- If a file is no larger than 50 KiB and the caller supplies neither `offset` nor `limit`, the tool reads the whole file in 64 KiB chunks and returns UTF-8 `FileSystem.Content`. Small files are therefore returned in full by default, and the 2,000-line limit does not apply to this fast path.
- Files larger than 50 KiB, or any request with an explicit range, automatically enter a streaming pagination path. It starts at line 1 by default, returns at most 2,000 lines and at most 50 KiB of body text, stops when either limit is reached, and reports `truncated` plus the `next` line number for a subsequent call.
- Pagination does not load an entire large file into memory. It scans from the beginning in 64 KiB chunks and retains only the current window. A high `offset` still requires a sequential scan of the preceding content, however; no byte index or seek is used.
- Each line retains at most 2,000 characters; if it is longer, an explicit truncation marker is appended. CRLF is normalized during line-by-line processing. UTF-8 decoding is fatal, so invalid bytes cause the read to fail instead of being replaced with `�` and allowing processing to continue.
- The text body does not receive automatic line numbers. A small-file result is `FileSystem.Content` JSON containing `content`, `encoding`, and `mime`; only paginated results additionally contain `offset`, `truncated`, and `next`. Positional anchors depend on pagination metadata rather than line-by-line prefixes as in Claude Code.
- Binary detection combines extensions, PDF magic bytes, NUL bytes, and the proportion of non-printing control characters. PDFs, Office documents, archives, executables, and similar files are rejected. `.ipynb` has no dedicated branch and is read as ordinary UTF-8 JSON text.

#### Images and directories

- Images are identified as JPEG, PNG, GIF, or WebP from their content signatures, which take precedence over extensions; a valid image disguised as `.bin` can therefore still be read. Original media ingestion is limited to 20 MiB, with checks against both the `stat` size and the number of bytes actually streamed, preventing file growth during a read from bypassing the limit.
- Images are limited by default to 2000×2000 and a 5 MiB base64 payload. When a limit is exceeded, Photon/WASM with Lanczos3 progressively downsizes the image and tries PNG followed by several JPEG quality levels. These thresholds and automatic resizing can be configured through `attachments.image`. If the resizer itself is unavailable, the current policy retains the original image instead of failing an ordinary read.
- An image result contains a “read succeeded” message and a native `file` content block; base64 is not disguised as ordinary text. General text-output truncation does not remove the media block.
- A directory read resolves the real path of every direct child and retains only regular files and directories that remain within the directory. It therefore excludes broken links, special files, and symbolic links pointing outside the directory. Entries are sorted with directories first and by name within each kind; at most 2,000 entries are returned, and `next` supports continued pagination.

#### Paths, permissions, and the output lifecycle

- Relative paths must stay within the current Location, and absolute paths within that Location are also accepted. Relative `..` traversal outside the Location, or escape through symbolic links, is rejected. An explicit absolute path outside the Location first requires `external_directory` authorization, followed by `read` authorization for the target resource.
- During pagination, the tool itself constrains the text window to 2,000 lines/50 KiB. During finalization, the Tool Registry adds a general model-output safeguard with the same defaults of 2,000 lines/50 KiB. If the complete structured result still exceeds the limit, the full content is saved to a managed `tool-output` file, while the model receives a head-and-tail preview and its path. The default retention period is 7 days.
- Not all expected errors are exposed verbatim. Binary files, media-ingestion limits, image-decoding failures, and dimension errors retain their specific messages, while path errors, ordinary filesystem errors, permission errors, invalid UTF-8, out-of-range offsets, and similar conditions are currently projected to `Unable to read <path>`. This reduces leakage of internal errors but makes recovery guidance for some failures less specific than Pi's or Claude Code's.

### 5. Codex: No Dedicated Text `read_file`

#### Tools the model actually uses

The current Codex tool registry has no ordinary file reader. The `read_file` references in the source are merely remote tool names in MCP server examples and tests, not model tools built into Codex. When Unified Exec is supported, the default tool plan exposes:

- `exec_command`: execute shell commands;
- `write_stdin`: continue interacting with a command that is still running;
- `view_image`: read and view local images.

When Unified Exec is not supported, or a legacy model configuration is used, Codex exposes `shell_command` instead.

Codex therefore normally reads text by asking `exec_command` to run commands such as:

```text
rg -n '^' path/to/file
sed -n '100,180p' path/to/file
head -n 200 path/to/file
```

#### What `exec_command` adds beyond Bash

- It provides structured fields for `workdir`, the shell, whether to use a login shell, whether to allocate a PTY, how long to wait before returning, the output token budget, and more.
- It waits 10 seconds by default and has a model-facing output budget of 10,000 tokens; internal collection also has a 1 MiB limit. Overlong output is truncated in the middle and its original token count is reported. Retaining the beginning and end is usually more useful than a simple `head` for seeing a command's conclusion or errors.
- Long-running commands do not block the entire Agent: the tool returns a `session_id`, which the model can use with `write_stdin` to poll, send input, or continue collecting output.
- Commands run inside filesystem and network sandboxes. Out-of-scope access goes through structured approval, and controlled command-prefix rules can be recorded.
- Local and attached remote environments are supported, and the tool returns structured metadata including `exit_code`, elapsed time, session ID, and truncation state.

#### Implementation details of output budgets, middle truncation, and session continuation

The “10,000-token budget, middle truncation, and session continuation” described above are distributed across three layers. Together they form a combination of byte-level truncation in the collection layer, token-level truncation in the rendering layer, and session continuation through a process repository.

**Collection layer: byte-level head/tail buffering (`HeadTailBuffer`)**

- Each process has a single 1 MiB output buffer, split equally between a head and a tail of 512 KiB each.
- Writes fill the head first, after which all output goes into the tail. The tail is a rolling queue: once over budget, it discards bytes from the front and retains only the final 512 KiB. Discarded bytes only increment an `omitted_bytes` counter.
- A read assembles `head + "... N bytes omitted ..." + tail`.
- This layer provides a hard memory ceiling. Background tasks continuously write PTY output into the buffer, but even a process with infinite output, such as `yes`, still uses a constant 1 MiB of memory.

**Rendering layer: token-level middle truncation (`truncate_middle_with_token_budget`)**

- Token counting does not use an actual tokenizer. It simply rounds up “number of bytes ÷ 4” (`APPROX_BYTES_PER_TOKEN = 4`).
- After converting the token budget to a byte budget, it divides that budget equally between the beginning and end, cuts at character boundaries, and replaces the middle with an `…N tokens truncated…` marker.
- The final text also receives a `Warning: truncated output (original token count: N)` header. During assembly, the implementation checks for an existing byte-level marker to avoid inserting a duplicate. The two truncation markers are independent and may both appear.
- The 10,000-token budget is calculated as `min(caller-provided max_output_tokens or the default 10000, truncation_policy ceiling for the model tier)`: the model may explicitly request more output in the parameters, but the policy still caps it. This budget applies only to the rendering layer; the collection layer remains fixed at 1 MiB.

**Session layer: process repository and deadline-bounded collection**

- `exec_command` first assigns a random process_id from 1000 to 100000. After spawning a PTY, it immediately stores the process in a repository (HashMap). Storing it before waiting for output is intentional: if the user interrupts the current turn, releasing the last reference must not accidentally kill the background process.
- The core `collect_output_until_deadline` loop repeatedly drains the shared buffer, waits for notifications of new output, and detects process exit. After exit, it keeps a 50 ms grace period to capture residual output. This continues until the deadline; the wait duration is clamped to 250 ms–30 s and defaults to 10 s.
- If the process has exited by the deadline, the tool returns its exit_code and releases the process_id. If it is still running, the response includes a session ID and the process remains in the repository.
- `write_stdin` retrieves the same set of output handles by process_id, writes to stdin, and then enters the same deadline-bounded collection loop. Output produced between tool calls is not lost: the background task continuously writes into the shared buffer, which the next call drains immediately. An empty `write_stdin` has polling semantics, with a broader wait window of 5 s–300 s.
- The repository retains up to 64 concurrent sessions. When full, it prunes by LRU while protecting the 8 most recently used sessions and preferring to remove processes that have already exited.

The implementation's complexity is distributed very unevenly. Head/tail buffering and token truncation together take fewer than 350 lines, have no unusual dependencies, and are easy to port. Session continuation is the genuinely heavy part: PTYs, background collection tasks, the process repository, and exit-race handling account for most of the code.

#### `view_image`

`view_image` is Codex's only model tool dedicated to the contents of local files. It:

- checks whether the model supports image input;
- reads an image inside the selected environment and filesystem sandbox;
- uses the `high` detail level by default and can request `original` when the model supports it;
- converts the file to a data URL and sends it to the model as a genuine image content item.

#### Do not confuse it with `fs/readFile`

The Codex app server also provides an `fs/readFile` JSON-RPC method. It accepts an absolute path and returns the raw bytes as base64. This method is intended for app-server clients, is not part of the model tool plan, and has no `offset`, `limit`, line numbers, text-token controls, or document parsing. It therefore should not be counted as a built-in file-reading tool for the Codex Agent.


In summary:

- **Claude Code `Read`**: has the richest semantics, particularly for streaming scans of large files, deduplicating repeated reads, permissions, and Notebook/PDF integration. The tradeoff is a complex implementation tightly coupled to Claude Code's internal state.
- **Grok `read_file`**: broadly covers images, PDFs, and PPTX; has clear output anchors and token protection; and explicitly handles rules, skills, and extremely long lines. Ordinary text is still loaded into memory in full before processing.
- **OpenCode `read`**: V2 has clear layering and structured-result boundaries; text and directories both support resumable pagination; large files are not loaded in full; and Location permissions and general oversized-output retention are unified. It supports fewer document types, text has no line numbers, and some recoverable errors are collapsed into generic messages.
- **Pi `read`**: has the most direct implementation, predictable 50 KiB/2,000-line limits, useful image handling, and a practical remote-backend abstraction. It supports few document types and does not automatically add line numbers to text.
- **Codex `exec_command` + `view_image`**: derives its text capabilities from Unix/PowerShell composition, making it flexible and able to reuse the surrounding ecosystem. Safety, sessions, approvals, and output budgets are handled uniformly by the execution layer, but it lacks a dedicated read protocol for text ranges, total line counts, PDFs, and Notebook semantics.

## Comparing Bash and Read Tools

To investigate whether a dedicated file-reading tool is more effective than Bash, this research also examined tests, design documents, system prompts, changelogs, and source comments in all five projects. It specifically searched `eval`, `bench`, and `benchmark` directories, as well as tests containing both Read and `cat`/Bash. No genuine end-to-end A/B evaluation was found: there was no test in which the same model completed the same task once with only a dedicated Read tool and once with only Bash, followed by measurements of task success rate, token usage, latency, or error rate.

The existing evidence supports much narrower claims:

- A dedicated Read tool can provide bounded pagination, deterministic continuation positions, structured permissions, native multimodal content, and recoverable errors more consistently.
- Some framework-level optimizations apply only to dedicated Read tools and do reduce repeated context or prompt-cache cost.
- These behaviors are covered by extensive unit and regression tests.
- They do not, however, directly establish that “an Agent using Read has a higher overall task success rate than an Agent using Bash.”

Text in a system prompt that says to “prefer Read” demonstrates only the product's design intent and is not, by itself, evidence of effectiveness.

The following sections therefore compare the advantages and disadvantages of dedicated file-reading tools.

### Advantages of a Dedicated File-Reading Tool

#### 1. Less invocation ambiguity and shell risk

A dedicated tool represents the path, starting line, line count, and PDF page number as typed fields. The model does not have to assemble quoting, escape spaces, handle `$()`, or account for cross-platform command differences. Nor does it incidentally gain the full expressive power of a shell merely to “read one file.” The permission system can also identify the operation unambiguously as read-only.

#### 2. Proactive context-window protection

By default, `cat` dumps all content to stdout. If the file is huge, the Agent can only deal afterward with a result the platform has already truncated. At the read-protocol layer, a dedicated tool knows the total number of lines, the current window, and the next offset, and limits its result by line count, byte count, or token budget. This brings three direct benefits:

- A single tool result does not consume a disproportionate amount of context.
- It avoids oversized API requests, out-of-memory failures, and long blocking operations.
- Even after truncation, it gives a deterministic position from which reading can continue, rather than an unidentified fragment.

Although Codex has no dedicated text reader, `exec_command` still provides a default 10,000-token budget, middle truncation, and original-size information at the command-output layer.

#### 3. Stable positional anchors for the model

Claude Code numbers every line, while Grok anchors the first line of a window and every tenth line. OpenCode leaves the body unchanged but identifies window boundaries with structured `offset`/`next` fields. The model can refer to code locations, plan subsequent range reads, and map observations to edit operations. Ordinary `cat` provides no line numbers. Bash can add them with `nl` or `cat -n`, but the model must remember to choose a consistent format every time.

#### 4. Native multimodal and document understanding

Reading an image with Bash normally produces binary garbage or base64, and tools such as `pdftotext`, `jq`, and `unzip` may not be installed. A dedicated tool can:

- represent an image as visual tokens instead of text;
- automatically correct orientation, resize, transcode, and compress;
- render a PDF by page or extract its text;
- split a Notebook into cells;
- split a PPTX into slides and notes.

These capabilities are more than command shortcuts: they transform “file bytes” into “content the model can understand” at the protocol boundary.

#### 5. Friendlier failure recovery

A dedicated tool knows the current working directory, total line count, supported formats, and invocation parameters. It can therefore return action-oriented errors such as “offset out of range,” “this is a directory,” “the file is excluded by `.gitignore`,” or “did you mean this similar path?” Ordinary Bash usually returns only an errno or a particular command's stderr.

#### 6. Integration with the Agent lifecycle and state

Claude Code can avoid resending unchanged files, activate path-specific skills, and record freshness for memory files. Grok can inject path rules. Pi can swap in a remote read backend. OpenCode connects Location permissions, image normalization, and oversized-result retention to a unified finalization pipeline. Codex's command tool can leave a running command in a resumable session, accept later input, and integrate with approvals. A one-off `cat` process has none of these session semantics on its own.

#### 7. Clearer observability and policy controls

The framework can record “which file was read, how much was read, whether the result was truncated, and whether a permission rule matched” as structured events. If the system sees only an arbitrary shell script, it must first parse the command and still may not be able to determine precisely what a pipeline, redirection, or subprocess ultimately read.


### Drawbacks of a Dedicated File-Reading Tool

- **Implementation and maintenance cost grows linearly with file types**: each format needs its own branch, and tool descriptions can easily drift from implementations. Grok's claimed Notebook support without a dedicated implementation branch and the discrepancy between Claude Code's prompt saying “2,000 lines maximum by default” and its core implementation are both examples.
- **Tool definitions consume context**: each dedicated tool's schema and description enter the system prompt. When its capabilities overlap with Bash, prompt guidance is also needed for the model to select the right tool consistently; otherwise, it may oscillate between the two.
- **Expressiveness has a ceiling**: line-based offset/limit pagination cannot handle extremely long individual lines or field-based extraction. When faced with a long line, both Pi and Grok explicitly recommend falling back to `sed | head -c` or `jq`. The dedicated tools thus acknowledge their own boundaries and complement Bash rather than replace it.


Bash remains appropriate in the following situations:

- When only content matching is needed, `rg` uses fewer tokens than reading an entire section.
- For a single extremely long JSON record, field- or character-based extraction with `jq`, `cut -c`, or a script is more effective than line pagination.
- Mature CLI tools are more flexible when filtering, sorting, decompression, and deserialization must be composed.
- Pi and Grok both load an entire ordinary file into memory first. For a small window into an extremely large file, Claude Code's or OpenCode's streaming implementation, or `sed`/`awk`, uses less memory.
- Codex's general-purpose shell approach can immediately use a new format processor already installed on the machine, without first adding another built-in branch to the Agent.

The Codex example must be interpreted correctly. It does not prove that “Bash alone is enough”; it shows that “with sufficiently substantial infrastructure in the command-execution layer—sandboxes, approvals, output budgets, and session management—Bash can perform text reading.” The complexity has not disappeared; it has merely moved from the read tool to the exec tool. Codex has not entirely escaped dedicated reading tools either: `view_image` is one, because image content cannot be expressed through text output at the protocol layer. The real scope of a Bash-only approach is therefore limited to text.

Another easily overlooked variable is the model's training distribution: tool shapes and models co-evolve. Claude-family models are trained with extensive use of Read/Edit pairs, where line-number anchors directly support subsequent edits. Codex models are trained specifically for shell use. “Codex works well with Bash” is partly true because its models were trained that way; the conclusion does not transfer to other models for free.

A more accurate conclusion is not “dedicated tools replace Bash,” but rather:

- **Routine reading of source code, configuration, and multimedia**: dedicated tools are safer, more stable, and more context-efficient.
- **Search, extremely long lines, and ad hoc format conversion**: Bash/CLI is more capable.
- **The best Agent implementations** usually retain both, prompting the model to prefer the dedicated reader and fall back to the shell only for windows or transformations the dedicated tool cannot express.
- The fundamental distinction is not feature coverage—Bash can do almost anything—but **which layer bears the complexity** and **whether permission semantics can be expressed statically**. Dedicated tools move safety and budgets forward into the protocol layer, while the Bash approach requires equally strong sandboxing and approval infrastructure in the execution layer.
