# Publishing to PyPI

## Prerequisites

- PyPI account and API token (https://pypi.org → Account settings → API tokens)
- Credentials: use `~/.pypirc` or env (see project-cursor-memory/cursor-mem for reference). Upload: Username `__token__`, Password = your PyPI API token.

## Build and upload

From the **queryclaw** project root (this directory):

```bash
pip install build twine
rm -rf dist/ && python -m build
twine upload dist/*
```

## Bump version for next release

1. Update `version` in `pyproject.toml` and `queryclaw/__init__.py`.
2. Re-run build and upload above.
