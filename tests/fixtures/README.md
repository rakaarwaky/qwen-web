# tests/fixtures — Test Environment Mirror

This folder is a **controlled mirror** of the runtime folder structure, used exclusively for testing.
It is kept separate so that tests never depend on real production data.

## Runtime → Fixtures Mapping

```
Runtime (real data)                   Fixtures (test data)
────────────────────────────────────────────────────────────────
input/                          →     tests/fixtures/input/
  role-architect/PROMPT.md      →       role-architect/PROMPT.md  (minimal version)
  role-business-analyst/        →       role-business-analyst/
  role-tech-lead/               →       role-tech-lead/
  .processing/ done/ failed/    →       .processing/ done/ failed/ todo/ (empty)

output/                         →     tests/fixtures/output/
  role-architect/               →       role-architect/           (empty, filled by tests)
  role-business-analyst/        →       role-business-analyst/
  role-tech-lead/               →       role-tech-lead/

log/                            →     tests/fixtures/log/
  app.jsonl                     →       app.jsonl    (sample entries)
  errors.jsonl                  →       errors.jsonl (sample entries)
```

## Rules

- **Never** put real production data here.
- `PROMPT.md` files here are **minimal versions** — just enough to trigger the pipeline.
- `output/` folders start empty and are populated by tests at runtime.
- `.processing/`, `done/`, `failed/` folders start empty (clean initial state).

## Full Structure

```
tests/fixtures/
├── qwen_fixture.html              ← DOM mock of chat.qwen.ai (pre-existing)
├── README.md                      ← this file
├── input/
│   ├── role-architect/
│   │   ├── PROMPT.md              ← minimal prompt
│   │   ├── .processing/           ← empty
│   │   ├── done/                  ← empty
│   │   ├── failed/                ← empty
│   │   └── todo/                  ← empty
│   ├── role-business-analyst/
│   │   └── ...
│   └── role-tech-lead/
│       └── ...
├── output/
│   ├── role-architect/            ← empty, written by tests
│   ├── role-business-analyst/
│   └── role-tech-lead/
└── log/
    ├── app.jsonl                  ← sample structured log entries
    └── errors.jsonl               ← sample error entries
```
