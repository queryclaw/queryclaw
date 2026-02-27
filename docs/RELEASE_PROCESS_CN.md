# QueryClaw 发布流程

## 每次发布必须完成的步骤

**所有版本发布在推送到 GitHub 和发布到 PyPI 之前，必须同步更新 RELEASE_NOTES（中英文两份）。**

### 检查清单

1. 在 `pyproject.toml` 和 `queryclaw/__init__.py` 中**更新版本号**
2. **更新 RELEASE_NOTES.md** 和 **RELEASE_NOTES_CN.md**：
   - 将「Unreleased」中的内容移到新版本小节，并注明发布日期
   - 可选：新增「Unreleased」小节用于后续变更
3. **提交**（使用清晰的提交信息）
4. **推送**到 GitHub
5. **构建并发布**到 PyPI：`rm -rf dist/ && python -m build && twine upload dist/*`

### RELEASE_NOTES 格式

- 每个版本使用 `## X.Y.Z (YYYY-MM-DD)` 标题
- 按类型分组：**功能**、**修复**、**变更**
- 条目保持简洁；如有需要可链接到 issue/PR
