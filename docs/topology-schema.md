# Topology Schema

The topology is defined in a single YAML file. The schema is validated by Pydantic; extra keys are forbidden everywhere.

---

## Top-level structure

```yaml
global:    # GlobalConfig
defaults:  # DefaultsConfig
groups:    # list[Group]
users:     # list[User]
portals:   # list[Portal]  (optional)
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
| `xdns` | `XdnsConfig` | no | — | DNS-interception inbound (VLESS over mKCP) |
| `wireguard` | `WireguardConfig` | no | — | WireGuard inbound configuration |
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

### `XdnsConfig`

Configures a DNS-interception inbound on hub nodes — VLESS over mKCP that intercepts queries for the listed domains. Only users whose `access` includes `xdns` are added as clients.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `domains` | `list[str]` | yes | — | Domains the inbound intercepts (e.g. `["dns.google"]`) |
| `port` | `int` (1–65535) | no | `53` | XDNS listen port |

### `WireguardConfig`

Configures a WireGuard inbound on hub nodes. Peer keypairs are derived deterministically from each identity and the hub's Reality private key (see [Architecture](architecture.md#deterministic-derivation)). Only users whose `access` includes `wireguard` become peers; their `server` identity and `guests` are allocated too.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `subnet` | `str` (CIDR) | yes | — | Peer address pool, e.g. `10.0.0.0/24`. The server holds the first host (`.1`); peers are assigned sequentially from `.2` |
| `port` | `int` (1–65535) | no | `443` | WireGuard listen port |
| `mtu` | `int` (576–65535) | no | `1420` | Interface MTU |
| `keepalive` | `int` (≥0) | no | `0` | Persistent keepalive in seconds (`0` disables) |
| `kernel_mode` | `bool` | no | `false` | Use kernel-mode WireGuard |

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
| `access` | `list[AccessType]` | yes | Access types: `xhttp`, `server`, `cdn`, `proxy`, `wireguard`, `xdns` |
| `uuid` | `UUID` | no | Override auto-derived UUID |
| `guests` | `list[str]` | no | Guest identity labels |

### Access types

| Value | Description |
|-------|-------------|
| `xhttp` | Direct Reality xhttp access |
| `server` | Server-to-server access |
| `cdn` | CDN-fronted xhttp access |
| `proxy` | Mixed proxy inbound access |
| `wireguard` | WireGuard peer on hub nodes (see `defaults.hub.wireguard`) |
| `xdns` | DNS-interception inbound on hub nodes (see `defaults.hub.xdns`) |

!!! warning "Proxy trust level"
    `proxy` is the lower-trust one. It exists for clients that speak nothing but SOCKS/HTTP like Telegram client, scraper, some appliance with proxy field and no VPN support - as it authenticates with username and password over plaintext inbound rather than with Reality handshake. Treat it as a way to give a simple app an exit, not as a general-purpose identity.

**Example:**

```yaml
users:
  - username: alice
    group: staff
    access: [xhttp, cdn]
    guests: [alice-phone, alice-tablet]
```

---

## `portals`

Site-to-site reverse tunnels. A portal is a machine (e.g. a home server) that dials every hub with a dedicated identity and opens a reverse tunnel; hub traffic from the portal's member users that matches `routes` is sent backward through that tunnel and egresses on the portal machine. Several machines may run the same portal config — Xray pools their tunnels and load-balances across them.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | yes | Unique portal identifier; the hub outbound tag is `{id}-portal` |
| `users` | `list[str]` | yes | Usernames allowed to route through this portal (at least one); usernames only — guests are not accepted |
| `routes` | `PortalRoutes` | yes | Traffic selectors for this portal |
| `uuid` | `UUID` | no | Override auto-derived portal UUID |
| `strict` | `bool` | no | Confine portal-side egress to the declared matchers (default `true`) |

### `PortalRoutes`

| Field | Type | Description |
|-------|------|-------------|
| `domains` | `list[str]` | Domain matchers |
| `ips` | `list[str]` | IP/CIDR matchers |

At least one matcher is required.

Matchers are evaluated on the hub, before the connection leaves it, so the hub has to recognize the destination on its own. A bare LAN hostname (`nas`, `router`) never gets there — the hub cannot resolve it, the rule falls through, and the traffic goes to `routing.hub_default`. Use a matcher that catches the name as written (`domain:lan`, `full:nas.home.arpa`).

Portal ids must not collide with node or region ids, and the derived `{id}-portal` tag must not start with an exit region id (balancer selectors are prefix matches). The portal UUID is derived as `UUID5(namespace_uuid, "portal/{id}")` and is reverse-only: Xray rejects forward proxying with it. If no portal machine is connected, matching traffic is dropped (no fallback to the default route).

A portal dials with its own shortId, `SHA256("{id}.portal.{namespace}")[:16]`, which every hub node accepts alongside the group and per-user ones. Its identity is therefore independent of the groups its members belong to, and rotating one portal's shortId leaves every other portal and user untouched.

Members are selected by `user_email` in the hub routing rule, so each one needs an access type that carries it — `xhttp`, `cdn`, `xdns`, or `wireguard` — **and** that access type has to render on a hub node. Declaring `cdn` without a `global.cdn` block, or `wireguard`/`xdns` without the matching config, emits no inbound carrying the member's identity, so the rule would match no traffic; both cases are rejected at validation time.

A `proxy`-only or `server`-only member is rejected as well.

Only a member's own identity routes into the portal. Guests (`{label}@{username}`) and server identities (`{username}-server@{username}`) are separate emails that the rule never matches, so a guest cannot reach a portal even when its user is a member. Listing a guest label in `portals[].users` is not a way around this - this is made for security by design.

### `strict`

`strict` (default `true`) confines what traffic emerging from the tunnel may reach on the portal side. The portal config mirrors the declared matchers as `direct` rules and blackholes the rest:

- one rule for `routes.domains` and one for `routes.ips`, copied verbatim from the schema — Xray prefixes such as `full:`, `domain:`, `regexp:` are preserved, so hub and portal cannot disagree about what a matcher means
- a final catch-all to a `blocked` blackhole outbound, which is added to the config only when `strict` is set

Sniffing on the reverse tunnel is turned off under `strict`. Xray sniffs with `routeOnly`, which leaves the dialed address alone but routes on the sniffed SNI/Host instead — an address the client chooses. Every strict matcher would then be evaluated against attacker-supplied text, so any member could reach an arbitrary LAN host by sending a matching SNI. With sniffing off, the portal matches the destination exactly as the hub sent it. `strict: false` keeps sniffing on.

With `strict: false` the portal emits a single catch-all `direct` rule instead — the pre-`strict` output — and anything that reaches the `{id}-portal` outbound can be dialed from the portal machine: its own loopback services, the rest of the LAN, the router's admin interface, the open internet. A hub-side mistake or an over-broad matcher then turns into remote access to the home network.

The portal enforces *what*, not *who*. Traffic emerging from a reverse tunnel carries no inbound user, so member filtering stays hub-side and portal-side rules never mention users.

A strict portal uses `domainStrategy: IPOnDemand` instead of the `IPIfNonMatch` a non-strict one keeps. `IPIfNonMatch` only re-runs the rules with DNS when *nothing* matched, and the strict catch-all always matches on the first pass — so the second pass would never happen and an `ip` matcher could never cover a domain destination. `IPOnDemand` resolves inside the first pass, which restores that case: a domain the hub routed here by matching an `ip` rule (the hub resolved it on its side) is resolved again by the portal and matched against `routes.ips`.

That leaves one fail-closed case: the two resolvers have to agree. If the hub's DNS lands a name inside a declared CIDR and the portal's DNS does not — split-horizon setups, most often — the connection is blackholed where a non-strict portal would have dialed it. Declaring the name in `routes.domains` removes the dependency on DNS entirely, since a domain matcher is checked before any resolution happens. `strict: false` is the escape hatch.

Matchers are copied verbatim, so a `geosite:` / `geoip:` / `ext:` entry in `routes` also lands in the portal config and Xray refuses to start without the matching `.dat` asset on the portal machine. Keep strict portals on literal matchers, or deploy the asset files there too.

**Example:**

```yaml
portals:
  - id: home
    users: [alice, bob]
    routes:
      domains: [internal.example.com, "domain:lan"]
      ips: [10.0.0.0/8, 192.168.1.0/24]

  - id: lab
    users: [alice]
    routes:
      ips: [172.16.0.0/12]
    # lab names resolve differently on the portal than on the hub
    strict: false
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
| `xdns` | `XdnsConfig` | no | Override XDNS settings (hub nodes) |
| `wireguard` | `NodeWireguardOverride` | no | Override WireGuard settings (hub nodes) |

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

### `NodeWireguardOverride`

All fields optional; `null` means "use the `defaults.hub.wireguard` value". Set `enabled: false` to disable WireGuard on this node even when defaults configure it.

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | `bool` | Enable/disable WireGuard on this node |
| `subnet` | `str` (CIDR) | Override peer address pool |
| `port` | `int` (1–65535) | Override WireGuard port |
| `mtu` | `int` (576–65535) | Override MTU |
| `keepalive` | `int` (≥0) | Override persistent keepalive |
| `kernel_mode` | `bool` | Override kernel-mode setting |

XDNS has no per-node override beyond supplying a full `XdnsConfig` on the node.

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
    xdns:
      domains: [dns.google]
    wireguard:
      subnet: 10.0.0.0/24

groups:
  - id: staff

users:
  - username: alice
    group: staff
    access: [xhttp, cdn, wireguard, xdns]

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
