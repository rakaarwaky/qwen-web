<div align="center">

# 🤖 Qwen AI Web Automation CLI

**Automate Markdown-based prompt processing via Qwen AI Web (`chat.qwen.ai`)**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/playwright-1.40%2B-green.svg)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Headless Mode](https://img.shields.io/badge/browser-headless%20supported-purple.svg)]()

[Features](#-key-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [Usage Modes](#-usage-modes) • [CLI Reference](#-cli-reference)

</div>

---

## 📖 Overview

**Qwen AI Web Automation CLI** is a lightweight, robust automation pipeline designed to automatically send Markdown prompt files (`.md`) to **Qwen AI (`chat.qwen.ai`)**, wait for the AI to complete its response, extract the output, and save it locally.

It eliminates manual copy-pasting and supports **real-time file watching**, **folder batch processing**, and an **interactive CLI menu**.

---

## ✨ Key Features

- **👀 Real-Time File Watcher Mode**: Automatically monitors the `input/todo/` directory for new `.md` files, processes them instantly, saves outputs to `output/`, and moves completed inputs to `input/done/`.
- **📂 Batch Folder Pipeline**: Processes entire directories of Markdown files sequentially in a single browser session.
- **🖥️ Interactive Terminal UI**: Zero CLI flag memorization required—simply run `python3 src/qwen_auto.py` to open an interactive selection menu.
- **🔑 Persistent Session Login**: Retains session cookies in `./qwen_session`. Log in **once**, then run seamlessly in `--headless` mode indefinitely.
- **⚡ Smart Response Detection**: Dynamically polls AI generation progress and handles streaming until completion before outputting.
- **🛡️ Cross-Platform Input Fallback**: Handles React/Vue framework event dispatches, simulated typing, and clipboard paste shortcuts for Windows, macOS, and Linux.

---

## 📁 Repository Structure

```text
web-ai/
├── src/
│   └── qwen_auto.py       # Main Python automation script & CLI
├── input/
│   ├── todo/              # Drop new .md prompt files here
│   └── done/              # Processed prompt files are moved here
├── output/                # Generated AI response .md files
├── qwen_session/          # Persistent browser profile & session cookies
├── README.md              # Project documentation
└── requirements.txt       # Python dependencies
```

---

## 🚀 Installation

### 1. Clone Repository & Navigate
```bash
git clone https://github.com/your-username/qwen-web-automation.git
cd qwen-web-automation
```

### 2. Install Dependencies
```bash
pip install playwright
python3 -m playwright install chromium
```

---

## 🎮 Quick Start

Run the script without flags to launch the **Interactive Menu**:

```bash
python3 src/qwen_auto.py
```

### Interactive Menu Interface:
```text
==================================================
🤖 Qwen AI Web Automation Tool
==================================================
1. 👀 File Watcher Mode (Real-time folder monitoring)
2. 📂 Batch Folder Mode  (Process all files in input/todo/ once)
3. 📄 Single File Mode   (Process a specific markdown file)
4. ❌ Exit
==================================================
Pilih menu [1-4] (default: 1): 
Jalankan di latar belakang (Headless)? [Y/n] (default: Y): 
```

---

## ⚙️ Usage Modes

### 1. Real-Time File Watcher Mode (`--watch`)
Monitors `input/todo/` every $N$ seconds. Drop any `.md` file into `input/todo/` while the watcher is running to process it automatically.

```bash
python3 src/qwen_auto.py --watch --headless
```

### 2. Batch Folder Mode
Processes all current files inside `input/todo/` once and exits upon completion:

```bash
python3 src/qwen_auto.py -i input/todo -o output -d input/done --headless
```

### 3. Single File Mode
Processes a specific Markdown file directly:

```bash
python3 src/qwen_auto.py -i input.md -o output.md --headless
```

> **Note on Initial Setup:** On your very first run, execute without `--headless` so you can manually log into your Qwen AI account in the browser window if prompted. All future runs can use `--headless`.

---

## 🛠️ CLI Reference

| Flag / Option | Argument | Description | Default |
| :--- | :--- | :--- | :--- |
| `-w, --watch` | None | Enable continuous File Watcher mode | `disabled` |
| `--interval` | `INT` | Polling interval in seconds for watcher mode | `3` |
| `-i, --input` | `PATH` | Input markdown file or `todo` directory | `input/todo` |
| `-o, --output` | `PATH` | Output markdown file or `output` directory | `output` |
| `-d, --done-dir` | `PATH` | Directory to move completed input files | `input/done` |
| `--headless` | None | Run browser in background without GUI window | `false` |
| `--data-dir` | `PATH` | Directory storing browser profile & cookies | `./qwen_session` |
| `--timeout` | `INT` | Max wait time in seconds for AI response | `300` |

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
