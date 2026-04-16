# Topology Schema

The topology is defined in a single YAML file. The schema is validated by Pydantic; extra keys are forbidden everywhere.

---

## Top-level structure

```yaml
global:    # GlobalConfig
defaults:  # DefaultsConfig
groups:    # list[Group]
users:     # list[User]
routing:   # RoutingConfig
regions:   # list[Region]
```

---

## `global`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `namespace` | `str` | yes | Unique identifier for this network — used as seed for all UUID/shortId derivation |
| `aphelion_domain` | `str` | yes | Base domain for exit node hostnames |
| `bridge_domain` | `str` | yes | Base domain for hub node hostnames |
| `cdn` | `CdnConfig` | no | CDN domains for xhttp transport |

### `global.cdn`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `exit_domain` | `str` | yes | CDN domain fronting exit nodes |
| `hub_domain` | `str` | yes | CDN domain fronting hub nodes |

---

## `defaults`

Default configuration applied to all exit or hub nodes. Node-level fields override these.

### `defaults.exit`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ipv6` | `bool` | yes | Enable IPv6 on exit nodes by default |
| `keys` | `KeysConfig` | yes | Encryption key configuration |

### `defaults.hub`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ipv6` | `bool` | yes | — | Enable IPv6 on hub nodes by default |
| `proxy_inbound` | `bool` | no | `false` | Enable mixed proxy inbound |
| `keys` | `KeysConfig` | yes | — | Encryption key configuration |
| `exit_connections` | `ExitConnectionsConfig` | yes | — | How hubs connect to exits |
| `reality` | `RealityConfig` | yes | — | Default Reality config for hub nodes |
| `mtproto` | `MtprotoConfig` | no | — | MTProto proxy configuration |
| `observatory` | `ObservatoryConfig` | no | see below | Health-check / load-balancer probe settings |

### `KeysConfig`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | `bool` | no | `true` | Whether encryption is active |
| `mode` | `str` | yes | — | Key mode string (e.g. `rprx_vision`) |
| `session_time` | `str` | yes | — | Session duration (e.g. `12h`) |
| `auth` | `mlkem768 \| x25519` | no | `mlkem768` | Encryption algorithm |
| `padding` | `str` | no | — | Optional padding value |

### `ExitConnectionsConfig`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `method` | `str` | yes | — | Handshake method (e.g. `mlkem768x25519plus`) |
| `fingerprint` | `str` | no | `edge` | Client TLS fingerprint |

### `ObservatoryConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sampling` | `int` (1–24) | `8` | Number of probe samples |
| `interval` | `str` | `15s` | Probe interval (format: `\d+(ms\|s\|m\|h)`) |
| `timeout` | `str` | `5s` | Probe timeout |
| `concurrency` | `bool` | `true` | Run probes concurrently |

### `MtprotoConfig`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `domain` | `str` | yes | — | Domain for the MTProto inbound |
| `port` | `int` (1–65535) | no | `1234` | MTProto listen port |

---

## `groups`

List of user groups. Groups provide a shared `shortId` for Reality inbound filtering.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | yes | Unique group identifier |
| `short_id` | `str` | no | Override auto-derived shortId |

If `short_id` is omitted it is derived as `SHA256("{id}.{namespace}")[:16]`.

**Example:**

```yaml
groups:
  - id: staff
  - id: vip
    short_id: deadbeef01234567
```

---

## `users`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | `str` | yes | Unique username — used as derivation seed |
| `group` | `str` | yes | Must reference an existing `groups[].id` |
| `access` | `list[AccessType]` | yes | Access types: `xhttp`, `server`, `cdn`, `proxy` |
| `uuid` | `UUID` | no | Override auto-derived UUID |
| `portals` | `list[Portal]` | no | Portal (site-to-site tunnel) definitions |
| `guests` | `list[str]` | no | Guest identity labels |

### Access types

| Value | Description |
|-------|-------------|
| `xhttp` | Direct Reality xhttp access |
| `server` | Server-to-server access |
| `cdn` | CDN-fronted xhttp access |
| `proxy` | Mixed proxy inbound access |

### `Portal`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | `str` | yes | Portal label (used in UUID derivation) |
| `routes` | `PortalRoutes` | yes | Traffic selectors for this portal |

### `PortalRoutes`

| Field | Type | Description |
|-------|------|-------------|
| `domains` | `list[str]` | Domain matchers |
| `ips` | `list[str]` | IP/CIDR matchers |

At least one matcher is required.

**Example:**

```yaml
users:
  - username: alice
    group: staff
    access: [xhttp, cdn]
    portals:
      - label: office
        routes:
          domains: [internal.example.com]
          ips: [10.0.0.0/8]
    guests: [alice-phone, alice-tablet]
```

---

## `routing`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `hub_default` | `str` | yes | — | Default region tag for unmatched hub traffic; must reference an existing `regions[].id` |
| `exit_warp_global` | `list[str]` | no | `[]` | Domain list routed to the warp interface on all exit nodes |
| `exit_routes_global` | `list[ExitRoute]` | no | `[]` | Global exit routing rules applied to all exit nodes |
| `hub_routes` | `list[HubRoute]` | no | `[]` | Hub routing rules (ordered; first match wins) |

### `ExitRoute`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `destination` | `direct \| blocked \| warp` | yes | Routing destination |
| `domains` | `list[str]` | cond. | Domain matchers (at least one of `domains`/`ips` required) |
| `ips` | `list[str]` | cond. | IP/CIDR matchers |

### `HubRoute`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `destination` | `str` | yes | Region ID, node ID, `direct`, `blocked`, or `warp` |
| `domains` | `list[str]` | cond. | Domain matchers |
| `ips` | `list[str]` | cond. | IP/CIDR matchers |
| `users` | `list[str]` | cond. | Match only these usernames |
| `proxy_users` | `list[str]` | cond. | Match only these proxy usernames |

At least one matcher (`domains`, `ips`, `users`, or `proxy_users`) is required.

---

## `regions`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | yes | Unique region identifier |
| `type` | `exit \| hub` | yes | Region type |
| `vless_route` | `int` | exit only | Numeric route tag; must be unique across all regions |
| `cdn_xhttp_path` | `str` | no | CDN xhttp path override for this region |
| `lb_strategy` | `str` | no | Load balancer strategy (e.g. `leastLoad`) |
| `lb_fallback` | `str` | no | Fallback node ID (must be in this region) |
| `lb_least_load` | `LeastLoadSettings` | no | leastLoad tuning |
| `routing` | `RegionRouting` | no | Per-region routing overrides (exit only) |
| `warp` | `WarpConfig` | no | Warp tunnel configuration |
| `nodes` | `list[Node]` | yes | At least one node required |

### `LeastLoadSettings`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `baselines` | `list[str]` | `["30ms","100ms","250ms"]` | Latency buckets |
| `expected` | `int` (≥1) | `1` | Expected alive count |
| `max_rtt` | `str` | `750ms` | Maximum accepted RTT |
| `tolerance` | `float` (0–1) | `0.5` | Tolerance ratio |

### `RegionRouting` (exit regions only)

| Field | Type | Description |
|-------|------|-------------|
| `warp_extra` | `list[str]` | Additional warp domain overrides for this region |
| `routes` | `list[ExitRoute]` | Per-region exit routes (destination must be a special destination) |

### `WarpConfig`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `vless_route` | `int` | yes | Warp vless route tag; must be unique across all regions |

---

## `Node`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | yes | Unique node identifier (globally unique across all regions) |
| `hostname` | `str` | yes | Node FQDN |
| `ipv6` | `bool` | no | Override default IPv6 setting |
| `lb_role` | `backup` | no | Mark as load-balancer backup node |
| `reality` | `RealityConfig` | exit nodes | Reality TLS config (required for all exit nodes) |
| `keys` | `NodeKeysOverride` | no | Override default key settings |
| `exit_connections` | `NodeExitConnectionsOverride` | no | Override exit connection settings (hub nodes) |
| `proxy_inbound` | `bool` | no | Override proxy inbound setting (hub nodes) |
| `mtproto` | `NodeMtprotoOverride` | no | Override MTProto settings (hub nodes) |

### `RealityConfig`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `dest` | `str` | yes | — | Fallback destination (e.g. `www.cloudflare.com:443`) |
| `server_names` | `list[str]` | no | — | SNI list; auto-derived from `dest` if omitted |
| `xhttp_host` | `str` | no | — | xhttp Host header override |
| `xhttp_path` | `str` | yes | — | xhttp request path (e.g. `/stream`) |
| `fallback_limits` | `RealityFallbackLimits` | no | see below | Fallback traffic limits |

### `RealityFallbackLimits`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `after_bytes` | `int` | `16384` | Bytes before fallback triggers |
| `bytes_per_sec` | `int` | `50000` | Sustained rate limit |
| `burst_bytes_per_sec` | `int` | `100000` | Burst rate limit |

### `NodeKeysOverride`

All fields optional; `null` means "use the default":

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | `bool` | Override `enabled` |
| `mode` | `str` | Override `mode` |
| `session_time` | `str` | Override `session_time` |
| `auth` | `mlkem768 \| x25519` | Override auth algorithm |
| `padding` | `str` | Override padding |

### `NodeMtprotoOverride`

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | `bool` | Enable/disable MTProto on this node |
| `domain` | `str` | Override MTProto domain |
| `port` | `int` (1–65535) | Override MTProto port |

---

## Complete minimal example

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
    keys:
      auth: x25519
      mode: native
      session_time: 600s
    exit_connections:
      method: mlkem768x25519plus
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
