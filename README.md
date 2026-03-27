# HexRift

![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)
![Build](https://img.shields.io/github/actions/workflow/status/wlix13/hexrift/ci-code-quality.yaml?label=build&logo=github)
![License](https://img.shields.io/badge/license-MIT-green)
![uv](https://img.shields.io/badge/package%20manager-uv-blueviolet?logo=astral)
![Ruff](https://img.shields.io/badge/linter-ruff-orange?logo=ruff)

Config generator for the **Conglomerate** distributed proxy network. Takes a topology definition and produces Xray JSON configs and HAProxy configs for every node.

## Installation

```bash
uv sync
```

## Usage

All commands require a topology YAML file:

```bash
hexrift --yaml conglomerate.yaml <command>
```

### Commands

| Command | Description |
|---------|-------------|
| `validate` | Validate the topology YAML against the schema |
| `show` | Visualize the network topology (regions, nodes, users, guests, portals) |
| `derive [users\|groups\|nodes\|all]` | Show derived identifiers (UUIDs, shortIds, emails) |
| `nodes [--names\|--domains] [--type exit\|hub]` | List nodes with hostnames; machine-friendly output for automation |
| `gen-keys [NODE_ID\|--all] [--force] [--keys-dir PATH]` | Generate x25519 + ML-KEM 768 keypairs for nodes |
| `build [NODE_ID\|--all] --xray\|--haproxy [--keys-dir PATH] [--out-dir PATH]` | Build Xray config.json and/or HAProxy .cfg |
| `diff NODE_ID [--current-dir PATH] [--keys-dir PATH]` | Diff generated config against deployed config |
| `share USERNAME [--hub NODE_ID] [--fp FINGERPRINT] [--cdn] [--guest LABEL] [--all-guests] [--bare] [--keys-dir PATH]` | Generate VLESS share URLs |

### Examples

```bash
# Validate topology
hexrift validate

# Visualize topology
hexrift show

# Show all derived identifiers
hexrift derive all

# List all exit node IDs (for scripts)
hexrift nodes --names --type exit

# Generate keys for all nodes
hexrift gen-keys --all

# Build Xray config for a specific node
hexrift build nlA00 --xray --out-dir ./out

# Build all configs (Xray + HAProxy)
hexrift build --all --xray --haproxy --out-dir ./out

# Diff against deployed config
hexrift diff nlA00 --current-dir /etc/xray

# Generate a share link (CDN URL)
hexrift share alice --cdn

# Generate share links for all guests of a user
hexrift share alice --all-guests --bare | clip
```

## Architecture

```bash
hexrift/
  components/
    schema/     # Pydantic models for yaml
    derive/     # Pure derivation functions (UUIDs, shortIds, emails)
    keys/       # x25519 + ML-KEM 768 keypair generation and storage
    render/     # Xray config builder + HAProxy Jinja2 templates
  core/         # BaseApplication / Component / Controller framework
  templates/
    haproxy/    # haproxy.cfg.j2
```

### Derivation

All identifiers are deterministically derived from the topology:

- `NAMESPACE UUID` = UUID5(UUID(0), namespace)
- `User UUID` = UUID5(NAMESPACE_UUID, username)
- `Server UUID` = UUID5(USER_UUID, `{username}-server`)
- `Portal UUID` = UUID5(USER_UUID, `{label}-portal`)
- `Guest UUID` = UUID5(USER_UUID, `{label}`)
- `Hub-exit UUID` = UUID5(NAMESPACE_UUID, `{hubId}-{exitId}`)
- `Warp UUID` = Hub-exit UUID with 3rd segment replaced by `ffff`
- `Group shortId` = SHA256[`{groupId}.{namespace}`](:16)
- `Hub shortId` = SHA256[`{nodeId}.hub.{namespace}`](:16)
- `Exit shortId` = SHA256[`{nodeId}.exit.{namespace}`](:16)

### Keys

Keypairs are stored in `keys/{nodeId}.yaml`. Hub nodes in the same region share the same keypair. Key strings follow the format:

- **Decryption** (server inbound): `{method}.{mode}.{session_time}[.{padding}].{PRIVATE_KEY_b64}`
- **Encryption** (client outbound): `{method}.{mode}.0rtt.{PUBLIC_KEY_b64}`
