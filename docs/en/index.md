# HexRift

![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)
![Build](https://img.shields.io/github/actions/workflow/status/wlix13/hexrift/ci-code-quality.yaml?label=build&logo=github)
![License](https://img.shields.io/badge/license-MIT-green)
![uv](https://img.shields.io/badge/package%20manager-uv-blueviolet?logo=astral)
![Ruff](https://img.shields.io/badge/linter-ruff-orange?logo=ruff)

**HexRift** is a config generator for the **Conglomerate** distributed proxy network. It takes a topology YAML definition and produces [Xray](https://github.com/XTLS/Xray-core) JSON configs and HAProxy configs for every node.

---

## Quick start

```bash
# 1. Install
uv tool install hexrift

# 2. Validate your topology
hexrift --yaml conglomerate.yaml validate

# 3. Generate share links
hexrift --yaml conglomerate.yaml share alice --cdn
```

---

<div class="grid cards" markdown>

- :material-rocket-launch: **[Getting Started](getting-started.md)**

    Install HexRift, write your first topology YAML, and run the full workflow in minutes.

- :material-console: **[CLI Reference](cli-reference.md)**

    Complete reference for every command and every flag.

- :material-file-code: **[Topology Schema](topology-schema.md)**

    Full annotated YAML reference — every field, type, default, and validation rule.

- :material-cog: **[Architecture](architecture.md)**

    Component/Controller internals, deterministic derivation formulas, key storage format, and developer guide.

</div>
