# Polyglot Repository Health Monitor

CLI tool that clones public GitHub repositories, analyzes Python, Java, JavaScript, and C# files with tree-sitter ASTs, and writes Markdown health reports. It caches results in SQLite, scans pull-request diffs when requested, and publishes reports as GitHub Actions artifacts.

## Features
- Multi-language tree-sitter AST parsing
- Cyclomatic complexity, nesting depth, and function length metrics
- SQLite cache keyed by repository and commit SHA
- Optional GitHub Copilot CLI refactor suggestions
- GitHub Actions artifact publishing

## Real-world data source
Uses GitHub REST API v3 (`https://api.github.com`) for repository metadata, commit SHAs, language breakdowns, pull-request files, and raw file contents. It also clones public repositories with `git` when available.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment variables
- `GITHUB_TOKEN`: optional; required for private repositories
- `COPILOT_CLI_BIN`: optional path to GitHub Copilot CLI; otherwise the tool checks `copilot` and `gh`

## Run
```bash
python main.py analyze --owner octocat --repo hello-world
python main.py analyze --owner octocat --repo hello-world --pr 1
```
Reports are written to `reports/`.