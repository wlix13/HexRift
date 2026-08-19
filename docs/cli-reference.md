# CLI Reference

All commands require a topology YAML file passed. By default the path is `conglomerate.yaml`.
It is possible to override that via the global `--yaml` option:

```bash
hexrift --yaml conglomerate.yaml <command> [options]
```

## Global options

| Option | Default | Description |
|--------|---------|-------------|
| `--yaml PATH` | `conglomerate.yaml` | Path to topology YAML |
| `-V, --version` | — | Show version and exit |

---

## validate

```bash
hexrift validate
```

Validate the topology YAML against the Pydantic schema and report any errors.

**Output on success:**

```bash
Valid — conglomerate.yaml
  2 groups, 5 users, 2 exit regions, 1 hub regions, 6 nodes
```

**Output on failure:** prints the validation error and aborts.

---

## show

```bash
hexrift show
```

Visualize the full network topology as a tree: global settings, regions, nodes, users (by group), portals, and guests. Each portal lists its members, its `strict` state, and one line per published port carrying that port's source allowlist and node scope.

---

## derive

```bash
hexrift derive <entity>
```

Show derived identifiers in a table.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `users` | UUIDs, emails, server UUIDs, and guest shortIds for every user |
| `groups` | ShortIds for every group |
| `portals` | Tags, UUIDs, emails, short IDs, member users, `strict` state, and published ports (`port/network -> target  allow: …  nodes: …`, where `allow: any` means open to the internet and `nodes: all` means every hub node binds it) for every portal |
| `nodes` | ShortIds / hub-exit UUIDs for every node |
| `all` | All of the above |

**Example:**

```bash
hexrift derive users
hexrift derive all
```

---

## nodes

```bash
hexrift nodes [--names | --domains] [--type exit|hub]
```

List nodes with their hostnames. Designed for use in shell scripts.

**Options:**

| Option | Description |
|--------|-------------|
| `--names` | Output node IDs only (one per line) |
| `--domains` | Output hostnames only (one per line) |
| `--type exit\|hub` | Filter by region type |

**Examples:**

```bash
# Tab-separated ID + hostname (default)
hexrift nodes

# All exit node IDs — useful for loops
hexrift nodes --names --type exit

# All hub hostnames
hexrift nodes --domains --type hub
```

---

## share

```bash
hexrift share <username> [options]
```

Generate VLESS or Hysteria share URLs — or WireGuard client configs — for a user.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `USERNAME` | Username defined in `users[].username` |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--hub HUB_ID` | all hub nodes | Generate config for a specific hub node |
| `--fp FINGERPRINT` | from config | Client TLS fingerprint |
| `--cdn` | off | Generate CDN URL instead of direct Reality URL |
| `--hy2`, `--hysteria` | off | Generate a `hysteria2://` URL instead of direct Reality URL |
| `--wg`, `--wireguard` | off | Generate a WireGuard client `.conf` instead of a VLESS URL |
| `--server` | off | Generate config for the user's `server` identity |
| `--guest LABEL` | — | Generate config for a specific guest identity |
| `--all-guests` | off | Generate config for all guests of the user |
| `--bare` | off | Output raw URLs/configs only — no formatting, suitable for piping |
| `--keys-dir PATH` | `keys` | Directory containing key files |

!!! note
    `--guest` and `--all-guests` are mutually exclusive. `--server` cannot be combined
    with `--guest` or `--all-guests`. `--wg`, `--cdn` and `--hy2` are mutually exclusive.

!!! info "WireGuard configs"
    `--wg` requires the user to have `wireguard` access and the hub to define
    `defaults.hub.wireguard`. Generated configs use `1.1.1.1` as the client DNS resolver.

!!! info "Hysteria URLs"
    `--hy2` requires the user to have `hysteria` access and the hub to render a Hysteria
    listener. With the default derived certificate the URL carries `insecure=1&pinSHA256=…`;
    with an operator `certificate` it carries `insecure=0`. `obfs=salamander&obfs-password=…`
    is added when the listener enables `obfs`.

**Examples:**

```bash
# Direct Reality link for alice on all hubs
hexrift share alice

# CDN link on a specific hub
hexrift share alice --cdn --hub euH00

# Hysteria 2 link, bare, piped to clipboard
hexrift share alice --hy2 --bare | clip

# WireGuard client config for alice
hexrift share alice --wg

# WireGuard configs for all of alice's guests, piped to clipboard
hexrift share alice --wg --all-guests --bare | clip

# All guest links, piped to clipboard
hexrift share alice --all-guests --bare | clip
```

---

## gen-keys

```bash
hexrift gen-keys [NODE_ID | --all] [options]
```

Generate x25519 Reality keypairs and ML-KEM 768 encryption keys. One YAML file is written per node to `<keys-dir>/<nodeId>.yaml`.

!!! info
    Hub nodes in the same region automatically share a keypair.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `NODE_ID` | Generate keys for a single node |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--all` | off | Generate keys for all nodes in the topology |
| `--force` | off | Overwrite existing key files |
| `--keys-dir PATH` | `keys` | Directory to store key files |

!!! danger "`--force` invalidates everything issued for that node"
    A node's Reality keypair is baked into every share URL and client config generated for it. Overwriting it means every client of that node fails to connect until its config is regenerated and redistributed. Without `--force` existing key files are left alone, which is why it is not the default.

**Examples:**

```bash
# Single node
hexrift gen-keys nlA00

# All nodes, overwrite existing
hexrift gen-keys --all --force

# Custom keys directory
hexrift gen-keys --all --keys-dir /etc/hexrift/keys
```

---

## build

```bash
hexrift build [NODE_ID | --all] --xray|--haproxy [options]
```

Generate Xray `config.json` and/or HAProxy `.cfg` for node(s). Output is written to `<out-dir>/<nodeId>/`.

!!! warning "Generated configs are secrets"
    A node's `config.json` embeds its Reality private key and every client UUID, so it is written with `0o600` permissions. Keep that out of version control and off any shared artifact store — treat it like the key file it is derived from.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `NODE_ID` | Build config for a single node |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--xray` | off | Render Xray `config.json` |
| `--haproxy` | off | Render HAProxy `haproxy.cfg` |
| `--all` | off | Build configs for all nodes |
| `--out-dir PATH` | `configs` | Output directory |
| `--keys-dir PATH` | `keys` | Directory containing key files |

!!! warning
    At least one of `--xray` or `--haproxy` must be provided.

**Examples:**

```bash
# Xray config for one node
hexrift build nlA00 --xray

# All nodes, both Xray and HAProxy
hexrift build --all --xray --haproxy --out-dir ./out

# Custom directories
hexrift build euH00 --xray --keys-dir /etc/hexrift/keys --out-dir /etc/xray
```

---

## gen-portal

```bash
hexrift gen-portal <PORTAL_ID> [options]
hexrift gen-portal --all [options]
```

Generate the Xray bridge `config.json` for portal(s) declared in the top-level `portals:` section. Each config is written to `<out-dir>/<portal-id>/config.json` with `0o600` permissions (it embeds key material). Deploy it on the portal machine; several machines may run the same config — the hubs pool their tunnels.

Unless the portal sets [`strict: false`](topology-schema.md#strict), the generated routing mirrors the portal's `routes` and `publish` matchers and blackholes everything else, so the config has to be regenerated whenever those matchers change.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PORTAL_ID` | Portal to generate (or pass `--all`) |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--all` | — | Generate configs for every portal |
| `--fp FINGERPRINT` | from config | Client TLS fingerprint |
| `--out-dir PATH` | `configs/portals` | Output directory |
| `--keys-dir PATH` | `keys` | Directory containing key files |

**Examples:**

```bash
# All portals
hexrift gen-portal --all

# A single portal, into a custom directory
hexrift gen-portal home --out-dir ./portals
```

!!! danger "Published ports"
    A portal's [`publish`](topology-schema.md#portalpublish) entries make hub nodes bind ports that reach into the portal-side network with no authentication and no user check — `portals[].users` does not apply to them. `allow: any` (as shown by [`derive portals`](#derive)) means no allowlist was configured, so the published port is exposed publicly and the target service's own authentication is the only line of defense; configure `allow` with restrictive trusted source IP ranges instead. Give a published service its own portal id rather than sharing one config across pooled machines.

---

## diff

```bash
hexrift diff <NODE_ID> [options]
```

Show a unified diff between the freshly generated `config.json` and the currently deployed one.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `NODE_ID` | Node to diff |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--current-dir PATH` | `configs` | Directory containing currently deployed configs |
| `--keys-dir PATH` | `keys` | Directory containing key files |

**Examples:**

```bash
# Diff against local configs/ directory
hexrift diff nlA00

# Diff against deployed config
hexrift diff nlA00 --current-dir /etc/xray
```

Prints `No differences.` if configs match.
