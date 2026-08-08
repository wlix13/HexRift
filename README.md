# HexRift

![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)
![Build](https://img.shields.io/github/actions/workflow/status/wlix13/hexrift/ci-code-quality.yaml?label=build&logo=github)
[![Coverage](https://codecov.io/gh/wlix13/HexRift/graph/badge.svg)](https://codecov.io/gh/wlix13/HexRift)
![License](https://img.shields.io/badge/license-MIT-green)
![uv](https://img.shields.io/badge/package%20manager-uv-blueviolet?logo=astral)
![Ruff](https://img.shields.io/badge/linter-ruff-orange?logo=ruff)

Config generator for the **Conglomerate** distributed proxy network. Takes a topology definition and produces Xray JSON configs and HAProxy configs for every node. Hub nodes additionally support WireGuard and XDNS inbounds.

> [!WARNING]
> **HexRift is in active development.** Until the `v1.0.0` release, the CLI, topology schema, and generated config output may change at any time — breaking changes can land in **any** release, including patch versions. Pin an exact version (e.g. `hexrift==0.8.0`) and check the [release notes](https://github.com/wlix13/HexRift/releases) before upgrading.

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
| `derive [users\|groups\|portals\|nodes\|all]` | Show derived identifiers (UUIDs, shortIds, emails) |
| `nodes [--names\|--domains] [--type exit\|hub]` | List nodes with hostnames; machine-friendly output for automation |
| `gen-keys [NODE_ID\|--all] [--force] [--keys-dir PATH]` | Generate x25519 + ML-KEM 768 keypairs for nodes |
| `build [NODE_ID\|--all] --xray\|--haproxy [--keys-dir PATH] [--out-dir PATH]` | Build Xray config.json and/or HAProxy .cfg |
| `gen-portal [PORTAL_ID\|--all] [--group ID] [--fp FINGERPRINT] [--out-dir PATH] [--keys-dir PATH]` | Build Xray bridge config.json for portal(s) from the top-level `portals:` section |
| `diff NODE_ID [--current-dir PATH] [--keys-dir PATH]` | Diff generated config against deployed config |
| `share USERNAME [--hub NODE_ID] [--fp FINGERPRINT] [--cdn] [--wg] [--server] [--guest LABEL] [--all-guests] [--bare] [--keys-dir PATH]` | Generate VLESS share URLs or WireGuard client configs (`--wg`) |

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

# Generate a WireGuard client config
hexrift share alice --wg
```

## Topology options

Beyond the basic hub/exit split:

- **HAProxy-less nodes** - by default every node runs HAProxy on `:443` in front of Xray. Set `haproxy: false` to drop HAProxy and have Xray's Reality inbound bind `0.0.0.0:443` (or `[::]:443` when ipv6 is supported) directly. `build --haproxy` then emits a no-op stub `haproxy.cfg` so managed HAProxy service stays up without touching `:443`. CDN (`cdn_xhttp_path`) needs HAProxy TLS termination and cannot be combined with `haproxy: false`.
- **All-in-one node** - set `routing.hub_default: direct` to make a hub egress everything itself (`direct` outbound) instead of routing to exit region. This allows topology with hub node(s) and **no exit regions** - single node clients connect to that proxies straight to the internet. `hub_routes` still apply for per-domain/user exceptions.
- **Site-to-site portals** - `portals:` declares a machine (e.g. a home server) that dials the hubs and opens a reverse tunnel; hub traffic from the portal's member users that matches `routes` egresses there. `publish:` forwards a hub-bound port into the tunnel for the ingress direction - that port is **unauthenticated internet ingress and ignores `portals[].users`**, so set `allow`. `strict: true` (the default) confines portal-side egress to the declared `routes`/`publish` matchers and blackholes the rest. See [Topology Schema](docs/topology-schema.md#portals).

## Architecture

```bash
hexrift/
  components/
    schema/     # Pydantic models for yaml
    derive/     # Identity derivation (UUIDs, shortIds, emails), defaults resolution,
                # topology->Xray-fragment construction, and WireGuard derivation/configs
    keys/       # x25519 + ML-KEM 768 keypair generation and storage
    render/     # Xray config builder + HAProxy Jinja2 templates
  core/         # BaseApplication / Component / Controller framework
  shared/       # Cross-component helpers (crypto encoding, Xray/xhttp constants)
  templates/    # Jinja2 stubs
    haproxy/
    wireguard/
```

### Derivation

All identifiers are deterministically derived from the topology:

- `NAMESPACE UUID` = UUID5(UUID(0), namespace)
- `User UUID` = UUID5(NAMESPACE_UUID, username)
- `Server UUID` = UUID5(USER_UUID, `{username}-server`)
- `Portal UUID` = UUID5(NAMESPACE_UUID, `portal/{id}`)
- `Guest UUID` = UUID5(USER_UUID, `{label}`)
- `Hub-exit UUID` = UUID5(NAMESPACE_UUID, `{hubId}-{exitId}`)
- `Warp UUID` = Hub-exit UUID with 3rd segment replaced by `ffff`
- `Group shortId` = SHA256[`{groupId}.{namespace}`](:16)
- `Hub shortId` = SHA256[`{nodeId}.hub.{namespace}`](:16)
- `Exit shortId` = SHA256[`{nodeId}.exit.{namespace}`](:16)
- `WireGuard keypair` = x25519(HMAC-SHA256(reality_private_key, `{identity_uuid}.wireguard.{namespace}`))

### Keys

Keypairs are stored in `keys/{nodeId}.yaml`. Hub nodes in the same region share the same keypair. Key strings follow the format:

- **Decryption** (server inbound): `{method}.{mode}.{session_time}[.{padding}].{PRIVATE_KEY_b64}`
- **Encryption** (client outbound): `{method}.{mode}.0rtt.{PUBLIC_KEY_b64}`
