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
hexrift nodes list [--names | --domains | --json] [--type exit|hub]
hexrift nodes add <NODE_ID> [options]
hexrift nodes remove <NODE_ID>
```

`add` and `remove` edit the `regions:` section of the topology YAML in place. Only the edited lines change and a missing final newline is added, comments, key order and blank lines elsewhere are kept. Files with YAML anchors, a flow-style or duplicated `regions:`/`hub_routes:`, or differently indented list items are refused. A region written in flow style, or with a non-empty flow `nodes:` list, refuses only its own edits, and `nodes: []` becomes a block list on the first `add`.

After writing, the file is re-validated. A validation failure is reported as a warning and the edit is kept, so a missing piece (typically an exit node's `reality` block, or a new `hub_default` when its region was emptied) can be filled in by hand.

### list

List nodes with their hostnames. Designed for use in shell scripts.

**Options:**

| Option | Description |
|--------|-------------|
| `--names` | Output node IDs only (one per line) |
| `--domains` | Output hostnames only (one per line) |
| `--json` | Output a JSON array of `{id, hostname, region, type}` objects, in topology order |
| `--type exit\|hub` | Filter by region type |

**Examples:**

```bash
# Tab-separated ID + hostname (default)
hexrift nodes list

# All exit node IDs — useful for loops
hexrift nodes list --names --type exit

# All hub hostnames
hexrift nodes list --domains --type hub

# Structured output for other tools
hexrift nodes list --json --type exit | jq -r '.[].hostname'
```

`--json` output:

```json
[
  {"id": "nlA00", "hostname": "nlA00.aphelion.example.com", "region": "nl", "type": "exit"},
  {"id": "mskA00", "hostname": "mskA00.perigee.example.com", "region": "msk", "type": "hub"}
]
```

### add

Add `NODE_ID` to its region, ordered by id. A missing region is created at the end of the section, exits get a random unused `vless_route`. Exit nodes are written with a `hysteria` block next to `reality` (`obfs: true`, `sni` set to the hostname, `masquerade_url` set to `https://` plus the Reality dest, port kept unless it is 443), so a new exit serves Hysteria alongside VLESS+Reality and fits a `protocol: hysteria` region without hand edits. In a region with `lb_strategy` but no `lb_fallback`, the current first primary node is written as `lb_fallback`. Adding a node that is already present is a no-op.

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--type exit\|hub` | region's type | Region type, required only when the region has to be created |
| `--region ID` | leading lowercase letters of `NODE_ID` | Region to add the node to (`nlA20` → `nl`) |
| `--hostname HOST` | derived | Exits: `<NODE_ID>.<aphelion_domain>`. Hubs: domain of the existing hub nodes |
| `--no-ipv6` | off | Write `ipv6: false` on the node |
| `--reality-dest HOST:PORT` | — | Reality `dest`, also the Hysteria masquerade target |
| `--reality-server-names LIST` | — | Comma-separated Reality `server_names`, requires `--reality-dest` |
| `--reality-xhttp-path PATH` | — | Reality `xhttp_path`, required together with `--reality-dest` |

### remove

Remove `NODE_ID` from its region. `hub_routes` entries and `lb_fallback` pointing at it are dropped with it, and so are `hub_routes` entries pointing at the region when this was its last node. An emptied region keeps its block and settings, renders nothing, and takes nodes again with `add`; other references (`hub_default`, portal `publish`) surface through the validation warning. A node that is not in the topology is skipped.

**Examples:**

```bash
# New exit node in the existing `nl` region
hexrift nodes add nlA40 --reality-dest www.samsung.com:443 \
  --reality-server-names www.samsung.com,samsung.com --reality-xhttp-path /login/

# New hub node, hostname follows the other `msk` hubs
hexrift nodes add mskA30 --no-ipv6

# First node of a new exit region, `--type` is required
hexrift nodes add frA00 --type exit

# Decommission
hexrift nodes remove nlA40
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
