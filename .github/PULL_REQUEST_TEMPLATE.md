## Pull request type

<!-- Please check ONE that best describes this PR -->

- [ ] **Bug fix** (fixes an issue in config generation or CLI behavior)
- [ ] **New feature** (adds new generation capability or CLI command)
- [ ] **Enhancement** (improves existing generation logic or output)
- [ ] **Core** (changes to the Component/Controller framework or app structure)
- [ ] **Templates** (updates to Xray or HAProxy Jinja2 templates)
- [ ] **Schema** (changes to topology YAML models or validation)
- [ ] **Documentation** (updates to guides or configuration docs)
- [ ] **Security** (security-related improvements)
- [ ] **Dependencies** (updates to dependencies)
- [ ] **CI/CD** (changes to workflows or automation)

## Description

### What does this PR do?

<!-- Provide a clear and concise description of what this PR accomplishes -->

### Why is this change needed?

<!-- Explain the motivation and context for this change -->

### Related Issues

<!-- Link to related issues using "Fixes #123", "Closes #123", or "Relates to #123" -->

## Changes Made

<!-- Describe the changes you made. Use bullet points for clarity -->

-

## Testing

<!-- Describe how you tested your changes -->

- [ ] Tested with a sample topology YAML
- [ ] Verified generated configs are valid
- [ ] No testing required (documentation changes only)

## Checklist

<!-- Ensure all applicable items are completed before requesting review -->

- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Linter and type checker pass (`uv run ruff check .` and `uv run ty check`)
- [ ] Documentation updated (if applicable)

### Version Bumping

<!-- If changing generation behavior or CLI behavior don't forget to bump all version -->
- [ ] Version bumped in `__init__.py`
- [ ] Version bumped in `pyproject.toml`
- [ ] Version bumped in `uv.lock`
