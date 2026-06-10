# Getting Started

## Prerequisites

- Python **3.13+**
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
uv tool install hexrift
```

This installs all runtime dependencies into an isolated virtual environment.

---

## Minimal topology YAML

Create `conglomerate.yaml` next to the repo. Below is the smallest valid topology — one exit region, one hub region, one group, one user:

```yaml
global:
  namespace: mynet
  aphelion_domain: exit.example.com
  bridge_domain: hub.example.com

defaults:
  exit:
    ipv6: false
    keys:
      auth: mlkem768
      mode: native
      session_time: 600s
  hub:
    ipv6: false
    proxy_inbound: false
    keys:
      auth: x25519
      mode: native
      session_time: 600s
    exit_connections:
      method: mlkem768x25519plus
      fingerprint: edge
    reality:
      dest: www.google.com:443
      xhttp_path: /stream

groups:
  - id: staff

users:
  - username: alice
    group: staff
    access: [xhttp, cdn]

routing:
  hub_default: hub-eu

regions:
  - id: exit-nl
    type: exit
    vless_route: 1
    nodes:
      - id: nlA00
        hostname: nl-a00.exit.example.com
        reality:
          dest: www.cloudflare.com:443
          xhttp_path: /stream

  - id: hub-eu
    type: hub
    nodes:
      - id: euH00
        hostname: eu-h00.hub.example.com
```

---

## Workflow

A typical first-time setup follows four steps:

### 1 — Validate

```bash
hexrift --yaml conglomerate.yaml validate
```

```bash
Valid — conglomerate.yaml
  1 groups, 1 users, 1 exit regions, 1 hub regions, 2 nodes
```

Fix any Pydantic validation errors before proceeding.

### 2 — Inspect derived identifiers

```bash
hexrift --yaml conglomerate.yaml derive all
```

Shows UUIDs, shortIds, and emails that will be embedded in configs. All values are fully deterministic — re-running always produces the same output for the same namespace and names.

### 3 — Generate keypairs

```bash
hexrift --yaml conglomerate.yaml gen-keys --all --keys-dir keys
```

Creates `keys/nlA00.yaml` and `keys/euH00.yaml` with x25519 Reality keypairs and ML-KEM 768 encryption keys.

!!! warning
    Hub nodes in the same region share a keypair. Re-running without `--force` skips existing files.

### 4 — Build configs

```bash
hexrift --yaml conglomerate.yaml build --all --xray --haproxy --out-dir configs
```

Writes `configs/nlA00/config.json`, `configs/euH00/config.json`, and corresponding `haproxy.cfg` files.

---

## Share links

Generate a VLESS URL for a user:

```bash
# Direct Reality URL
hexrift --yaml conglomerate.yaml share alice

# CDN URL
hexrift --yaml conglomerate.yaml share alice --cdn

# Bare URL for piping (e.g. to clipboard)
hexrift --yaml conglomerate.yaml share alice --bare | clip
```

---

## XDNS (optional)

Hub nodes can expose a DNS-interception inbound (**XDNS**) — VLESS over mKCP that intercepts queries for the listed domains. Enable it under `defaults.hub` and grant users `xdns` access:

```yaml
defaults:
  hub:
    # ...existing hub defaults...
    xdns:
      domains: [dns.google]

users:
  - username: alice
    group: staff
    access: [xhttp, cdn, xdns]
```

XDNS is baked into the hub's Xray config by `build` — there is no separate command.

---

## WireGuard (optional)

Hub nodes can also expose a **WireGuard** inbound. Enable it under `defaults.hub` and grant users `wireguard` access:

```yaml
defaults:
  hub:
    # ...existing hub defaults...
    wireguard:
      subnet: 10.0.0.0/24   # server holds .1, peers from .2

users:
  - username: alice
    group: staff
    access: [xhttp, cdn, wireguard]
```

WireGuard client configs are generated with the `share` command's `--wg` flag:

```bash
# WireGuard client config for alice
hexrift --yaml conglomerate.yaml share alice --wg
```

See the [Topology Schema](topology-schema.md) for the full `XdnsConfig` / `WireguardConfig` fields and per-node overrides.

---

## Developer setup

```bash
uv sync
uv run prek install              # install pre-commit hooks via prek
uv run ruff check .              # lint
uv run ruff format .             # format
uv run ty check                  # type-check
uv run prek run --all-files      # run all hooks
```

For building docs locally:

```bash
uv sync --group docs
uv run mkdocs serve              # http://127.0.0.1:8000
uv run mkdocs build --strict     # static site → site/
```
