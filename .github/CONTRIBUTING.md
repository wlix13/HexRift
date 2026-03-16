# Contribution Guidelines

First of all, thank you for your interest in the project.

Regardless of whether you are thinking about creating an issue or opening a pull request, I truly appreciate the help.
Without communication, I cannot know what the community wants, what they use or how they use it.
Pull requests and issues are exactly what gives me the visibility I need, so thank you.

## Getting started

While following the exact process is neither mandatory nor enforced, it is recommended to try following it as it may help avoid wasted efforts.

### Creating an issue

Whether you have a **question**, found a **bug**, would like to see a **new feature** added or anything along those lines, creating an issue is
going to be the first step. The issue templates will help guide you, but simply creating an issue with the reason for the creation
of said issue is perfectly fine.

Furthermore, if you don't want to fix the problem or implement the feature yourself, that's completely fine.
Creating an issue alone will give both the maintainers as well as the other members of the community visibility on said issue,
which is a lot more likely to get the issue resolved than if the problem/request was left untold.

### Solving an issue

Looking to contribute? Awesome! Look through the open issues in the repository, preferably those that are already labelled.

If you found one that interests you, try to make sure nobody's already working on it.
Adding a comment to the issue asking the maintainer if you can tackle it is a perfectly acceptable way of doing that!

If there's no issue yet for what you want to solve, start by [Creating an issue](#creating-an-issue), specify
you'd like to take a shot at solving it, and finally, wait for the maintainer to comment on the issue.

You don't _have_ to wait for the maintainer to comment on the issue before starting to work on it if you're sure that there's no other
similar existing issues, open or closed, but if the maintainer has commented, it means the maintainer has, based on the comment itself,
acknowledged the issue.

## Development Setup

### Package Management

This project **only** supports the `uv` installation method. Other tools, such as `conda`
or `pip`, don't provide any guarantees that they will install the correct
dependency versions. You will almost certainly have _random bugs, error messages,_, and other problems if you don't use `uv`.
Please _do not report any issues_ if you use non-standard installations, since almost all such issues are invalid.

Furthermore, `uv` is [up to 115x faster](https://github.com/astral-sh/uv/blob/main/BENCHMARKS.md)
than `pip`, which is another _great_ reason to embrace the new industry-standard
for Python project management.

**Quick & Easy Installation Method:**

There are many convenient ways to install the uv command on your computer. Please check the link below to see all options.

[Installation Guide](https://docs.astral.sh/uv/getting-started/installation/)

Alternatively, if you want a very quick and easy method, you can install it as follows:

```bash
pip install -U uv
```

### Pre-commit Hooks (via prek)

This project uses pre-commit hooks to ensure code quality and consistency. Before making any commits, please install and set up prek:

```bash
# Install prek (if not already installed)
uv tool install prek
# or use with uv run (as dev environment already has it covered)
uv run prek

# Install the pre-commit hooks
prek install
```

The pre-commit hooks will automatically run on each commit to check for:

- Code formatting
- Linting issues
- Other quality checks

If any hooks fail, please fix the issues before committing. You can manually run all hooks with:

```bash
prek run --all-files
```

## Commits

All commits are expected to follow the conventional commits specification.

```text
<type>[scope]: <description>
```

It's not a really big deal if you don't, but the commits in your PR might be squashed into a single commit
with the appropriate format at the reviewer's discretion.

Here's a few examples of good commit messages:

- `feat(api): Add endpoint to retrieve images`
- `fix(alerting): Remove bad parameter from Slack alerting provider`
- `test(security): Add tests for basic auth with bcrypt`
- `docs: Add paragraph on running the application locally`
