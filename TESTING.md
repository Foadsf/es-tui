# TESTING

## Prerequisites (Windows 10/11)
- Python 3.9+
- `pip install -r requirements-dev.txt` (see below)
- Ensure **Windows Search** is enabled and running
- (Optional) `Everything` CLI (`es.exe`) in `PATH` for compatibility probes

### Dev Requirements
```bash
pip install pytest pytest-cov pywin32 windows-curses pywinpty
````

> If `pywinpty` fails on your machine/runner, the TUI system tests will be skipped.

## Running Tests

### Unit tests

```bash
pytest tests/unit -q
```

### System/Heuristic tests (CLI)

```bash
pytest tests/system -k "cli" -v
```

### System/Heuristic tests (TUI)

```bash
pytest tests/system -k "tui" -v
```

> If running on a non-Windows host, these are skipped.

### Coverage

```bash
pytest -q --cov --cov-report=term-missing
```

## Using `act` to run GitHub Actions locally

1. Install `act`: [https://github.com/nektos/act](https://github.com/nektos/act)
2. From repo root:

   ```bash
   act -j tests  # runs the 'tests' job
   ```

## Troubleshooting

* **Index not warm**: occasionally Windows Search needs a moment. Re-run, or increase waits in `conftest.py`.
* **pywinpty unavailable**: `pip install pywinpty` or rely on CLI tests only.
* **Everything not installed**: compatibility probes are skipped automatically.
