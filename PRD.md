# Product Requirements Document (PRD)
## Qwen AI Web Automation CLI (`qwen-web-automation`)

---

### 1. Overview & Vision
`qwen-web-automation` is a high-performance, resilient CLI automation tool designed to interact with the Qwen AI web interface (`chat.qwen.ai`) without relying on official API keys. It enables batch prompt processing, real-time file watching, session persistence, and structured audit logging via Playwright automation.

---

### 2. Core Operating Modes

#### 2.1 Interactive Terminal UI (TUI) Mode
- **Behavior**: Triggered when the script is executed without CLI arguments.
- **Features**:
  - Interactive selection menu for mode choice (Watcher, Batch, Single File, Exit).
  - Prompts for execution environment (Headless vs. Headed browser mode).
  - Graceful handles keyboard interrupts (`Ctrl+C`).

#### 2.2 File Watcher Mode (`--watch` / `-w`)
- **Behavior**: Continuous polling of an input directory (`input/todo/`) at configurable intervals (`--interval`, default 3s).
- **Workflow**:
  - Detects new `.md` prompt files in `input/todo/`.
  - Maintains directory subfolder structures in `output/` and `input/done/`.
  - Processes files sequentially using a persistent browser instance.
  - Automatically moves processed files to `input/done/`.

#### 2.3 Batch Folder Mode
- **Behavior**: One-shot batch execution of all pending files in the input directory.
- **Workflow**:
  - Discovers all non-hidden files under `input/todo/`.
  - Sequentially executes prompts across a single persistent browser context.
  - Generates a terminal completion summary (total files, successes, failures).

#### 2.4 Single File Mode (`-i <file>` / `-o <output>`)
- **Behavior**: Direct execution of a single specified Markdown prompt file.
- **Workflow**:
  - Validates input file existence.
  - Processes prompt and writes output directly to specified target path.
  - Relocates prompt to `input/done/` if source path is within `todo`.

---

### 3. Functional Requirements & Automation Pipeline

#### 3.1 Session & Security Management
- **Persistent Context**: Uses `launch_persistent_context` to retain cookies, LocalStorage, and login session in `qwen_session/`.
- **Anti-Automation Bypass**: Launches with `--disable-blink-features=AutomationControlled` and custom viewport settings.
- **Security Check Interception**: Detects Cloudflare challenges (`cf-challenge`, "Just a moment") and login redirects (`/login`, `/signin`), prompting the user in headed mode while pausing execution.

#### 3.2 Network & Performance Optimization
- **Resource Route Blocking**: Aborts requests for images, media, and web fonts (`image`, `media`, `font`) to accelerate navigation speed and minimize memory overhead.
- **Context Reuse**: Reuses existing pages or triggers "New Chat" button actions instead of performing hard browser reloads whenever possible.

#### 3.3 Prompt Text Injection Engine
To support ultra-large prompts (100k+ characters) without UI lag or truncation, the tool implements a **3-tier injection fallback strategy**:
1. **Tier 1 (Direct DOM JS Injection)**: Native prototype setter invocation (`HTMLTextAreaElement.prototype`) combined with synthetic React `input` and `change` event dispatches.
2. **Tier 2 (Playwright `fill()`)**: standard automated field filling.
3. **Tier 3 (Clipboard Paste & Direct Typing)**: Writes text to system clipboard via permissions API (`clipboard-read`, `clipboard-write`) and simulates `Ctrl+V` key combination.

#### 3.4 Response Generation & Stability Detection Engine
- **Element Resiliency**: Uses fallback selector lists for chat inputs, submit buttons, and assistant message nodes.
- **Fast Adaptive Wait**: Polls for initial message DOM node creation (up to 5s) before entering the stability loop.
- **Sub-Second Stability Loop**:
  - Polls assistant message DOM text every 300ms.
  - Marks generation complete when response text remains identical across 5 consecutive checks (1.5 seconds stability window).
  - Displays real-time terminal spinner with current output character count.

#### 3.5 Fault Handling & Automatic Recovery
- **Retry Mechanism**: Automatically retries failed prompt operations up to 3 times (`process_file_with_retry`).
- **Page Re-initialization**: Navigates browser to `about:blank` on failure prior to retrying.
- **Error Logging**: Appends detailed stack traces and timestamps to `output/errors.log`.

---

### 4. Traceability & Audit Trail

#### 4.1 Metadata Traceability Injection
Every generated output file begins with an HTML comment block detailing metadata:
- `Run ID` (Timestamp + unique UUID hex)
- `Source File` & `Processed At`
- `Duration (seconds)`
- `Input Characters` vs. `Output Characters`

#### 4.2 Structured Audit Trail (`audit_history.jsonl`)
- Logged in JSON Lines (`JSONL`) format inside the output directory.
- Captures status (`SUCCESS` / `FAILED`), run ID, file paths, character counts, execution duration, and error messages.

---

### 5. CLI Arguments & Configuration Matrix

| Flag / Option | Short | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `--input` | `-i` | `BASE_DIR/input/todo` | Input Markdown file or directory path |
| `--output` | `-o` | `BASE_DIR/output` | Output file or target directory path |
| `--done-dir` | `-d` | `BASE_DIR/input/done` | Target folder for completed input files |
| `--watch` | `-w` | `False` | Enables continuous folder watcher mode |
| `--interval` | N/A | `3` | Polling interval (in seconds) for watcher mode |
| `--headless` | N/A | `False` (CLI) / Prompted (TUI) | Runs browser in background headless mode |
| `--data-dir` | N/A | `BASE_DIR/qwen_session` | Directory for storing browser session data |
| `--timeout` | N/A | `300` | Maximum response waiting time (in seconds) |

---

### 6. Non-Functional Requirements

- **Performance**: Polling overhead under 300ms per cycle; route blocking cuts network bandwidth usage by ~40-60%.
- **Reliability**: No loss of input files during move failures (`safe_move` overwrites destination safely).
- **Usability**: ANSI terminal color palettes, clean summary panels, and live progress indicators.
