# QueryClaw Release Process

## Required Steps for Every Release

**All version releases MUST update RELEASE_NOTES (both EN and CN) before pushing to GitHub and publishing to PyPI.**

### Checklist

1. **Update version** in `pyproject.toml` and `queryclaw/__init__.py`
2. **Update RELEASE_NOTES.md** and **RELEASE_NOTES_CN.md**:
   - Move "Unreleased" items to a new version section with the release date
   - Add a new "Unreleased" section for future changes (optional)
3. **Commit** with a descriptive message
4. **Push** to GitHub
5. **Build and publish** to PyPI: `rm -rf dist/ && python -m build && twine upload dist/*`

### RELEASE_NOTES Format

- Each version has a `## X.Y.Z (YYYY-MM-DD)` header
- Group changes by type: **Features**, **Fixes**, **Changes**
- Keep entries concise; link to issues/PRs if relevant
