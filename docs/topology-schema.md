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
| `hysteria` | `HysteriaConfig` | no | Base Hysteria listener settings for exit regions with `protocol: hysteria` |

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
| `hysteria` | `HysteriaConfig` | no | — | Hysteria 2 inbound for users with `hysteria` access |
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

### `HysteriaConfig`

Configures a Hysteria 2 listener (QUIC over UDP). On hub nodes it admits users whose `access` includes `hysteria` (plus their `server` identity and `guests`); on exit nodes it admits the hub-exit identities of every hub, and hubs dial it when the exit region sets `protocol: hysteria`. Every field has a default, so `hysteria: {}` is a complete config.

Hysteria requires a real TLS certificate (Xray rejects Reality here). By default HexRift derives a self-signed leaf for the SNI from the node's Reality private key (`key_type` selects `ed25519` or `ecdsa-p256`) and embeds it inline; peers pin its SHA-256 (`pinnedPeerCertSha256` on hub outbounds, `pinSHA256` in share URLs). Set `certificate` to serve an operator-issued cert instead — then `sni` is required; without `pin_sha256` hub outbounds verify against CA roots and share URLs carry `insecure=0`, with it peers pin that fingerprint exactly as they pin the derived cert.

Auth is the identity UUID, so a client that rewrites the UUID's third segment selects an exit region exactly like a VLESS client does (`vlessRoute`), and warp variants work unchanged.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `port` | `int` (1–65535) | no | `443` | UDP listen port. Only one listener per UDP port, and `wireguard` defaults to this same `443/udp` — a hub node running both must move one of them (`xdns` defaults to `53/udp` and does not clash) |
| `obfs` | `bool` | no | `false` | Salamander obfuscation; the password is derived from the node's Reality key and shared with peers automatically |
| `congestion` | `bbr \| brutal` | no | `bbr` | QUIC congestion control. `brutal` sends at a fixed rate and requires `up` and `down` |
| `up` | `str` | brutal only | — | Send-rate cap of this listener, e.g. `"200 mbps"`. Xray semantics: every value is bits per second with binary multipliers — `1 mbps`, `1 mb`, `1 m` and `1 MB` all mean 1 048 576 bit/s — decimals allowed, ≥ 512 kbps |
| `down` | `str` | brutal only | — | Receive-rate advertised to peers. Hub outbounds mirror the exit's values (`brutalUp` = exit `down`, `brutalDown` = exit `up`) |
| `sni` | `str` | with `certificate` | first Reality server name | Name presented in TLS; also the CN/SAN of the derived cert |
| `masquerade_url` | `str` (`http(s)://…`) | no | `https://{sni}/` | Reverse-proxy target for unauthenticated HTTP/3 probes |
| `key_type` | `ed25519 \| ecdsa-p256` | no | `ed25519` (derived cert); unset with `certificate` | Key algorithm of the derived cert. With `certificate` it is the operator's declaration of what the files hold — HexRift cannot inspect them, and unset means "not Ed25519", which is what CAs issue. Hubs dialing an `ed25519` cert set `disableChromeParrot` because Chrome's parroted ClientHello omits Ed25519 from `signature_algorithms`; `ecdsa-p256` keeps the parrot |
| `certificate` | `HysteriaCertificate` | no | — | `cert_file` + `key_file` paths on the node; disables the derived cert. Optional `pin_sha256` (SHA-256 of the cert DER, hex with or without colons) keeps peers pinning when the cert is not publicly trusted |

Official Hysteria, sing-box and mihomo accept either key type. Xray's Hysteria dialer parrots Chrome's QUIC ClientHello by default and can only negotiate `ecdsa-p256`: HexRift disables the parrot on hub→exit dials to `ed25519` exits, but a `hysteria2://` share URL carries no such switch, so a hub listener that Xray-based client apps dial should set `key_type: ecdsa-p256`. Share URLs carry `insecure=1&pinSHA256=…` — a client that honours the pin verifies the exact cert, a client that ignores it connects unverified; switch to `certificate` if that matters.

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
| `access` | `list[AccessType]` | yes | Access types: `xhttp`, `server`, `cdn`, `proxy`, `wireguard`, `xdns`, `hysteria` |
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
| `hysteria` | Hysteria 2 user on hub nodes (see `defaults.hub.hysteria`); `hexrift share USER --hy2` prints the URL |

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
| `publish` | `list[PortalPublish]` | no | Hub ports forwarded into the tunnel — the ingress direction (default: none) |
| `strict` | `bool` | no | Confine portal-side egress to the declared matchers (default `true`) |

### `PortalRoutes`

| Field | Type | Description |
|-------|------|-------------|
| `domains` | `list[str]` | Domain matchers |
| `ips` | `list[str]` | IP/CIDR matchers |

At least one matcher is required.

Matchers are evaluated on the hub, before the connection leaves it, so the hub has to recognize the destination on its own. A bare LAN hostname (`nas`, `router`) never gets there — the hub cannot resolve it, the rule falls through, and the traffic goes to `routing.hub_default`. Use a matcher that catches the name as written (`domain:lan`, `full:nas.home.arpa`), or publish a port instead. `ips` likewise matches only what the client dialed as an IP literal — the hub never resolves a name to test it against a CIDR (see [`strict`](#strict)).

Portal ids must not collide with node or region ids, and the derived `{id}-portal` tag must not start with an exit region id (balancer selectors are prefix matches). The portal UUID is derived as `UUID5(namespace_uuid, "portal/{id}")` and is reverse-only: Xray rejects forward proxying with it. If no portal machine is connected, matching traffic is dropped (no fallback to the default route).

A portal dials with its own shortId, `SHA256("{id}.portal.{namespace}")[:16]`, which every hub node accepts alongside the group and per-user ones. Its identity is therefore independent of the groups its members belong to, and rotating one portal's shortId leaves every other portal and user untouched.

Members are selected by `user_email` in the hub routing rule, so each one needs an access type that carries it — `xhttp`, `cdn`, `xdns`, `wireguard`, or `hysteria` — **and** that access type has to render on a hub node (for `hysteria`, a hub with a Hysteria inbound). Declaring `cdn` without a `global.cdn` block, or `wireguard`/`xdns` without the matching config, emits no inbound carrying the member's identity, so the rule would match no traffic; both cases are rejected at validation time.

A `proxy`-only or `server`-only member is rejected as well.

Only a member's own identity routes into the portal. Guests (`{label}@{username}`) and server identities (`{username}-server@{username}`) are separate emails that the rule never matches, so a guest cannot reach a portal even when its user is a member. Listing a guest label in `portals[].users` is not a way around this - this is made for security by design.

### `PortalPublish`

`publish` forwards a port **into** the tunnel — the ingress direction, the mirror of `routes`. Each selected hub node binds the port and hands every accepted connection to the portal machine, which dials `target` locally.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `port` | `int` (1–65535) | yes | — | Port the hub node binds |
| `target` | `str` (`host:port`) | yes | — | Address dialed from the portal machine; host must be a DNS name or an IP literal, IPv6 bracketed |
| `network` | `tcp \| udp \| tcp,udp` | no | `tcp` | Transports forwarded |
| `allow` | `list[str]` | no | — | Source allowlist (CIDR or bare IP; bare IPs become `/32`, `/128` for IPv6). At least one entry; an entry with host bits set (`203.0.113.7/24`) is rejected rather than widened |
| `nodes` | `list[str]` | no | every hub node | Hub nodes that bind this port |

Each entry adds a dokodemo-door inbound tagged `{id}-publish-{port}` to the selected hub nodes, plus routing rules placed ahead of every other hub rule — before the DNS rule — so no later domain or IP rule can re-steer a published connection. With `allow`, sources outside the list are blocked; without it, every source is accepted. Sniffing is disabled on these inbounds: the target is fixed, so a client-supplied SNI has nothing to contribute and must not influence routing.

`target` is resolved and dialed **on the portal machine**, so LAN-only names work — `nas.lan:5000`, `192.168.1.10:443`.

Rejected at validation time: `nodes` entries that are unknown, repeated, or sit outside a hub region; an entry whose node scope is empty (a topology with no hub nodes at all); a socket the hub node already binds (Reality `443/tcp`, the proxy inbound `80/tcp`, the metrics listener over TCP, `xdns`, `wireguard` and `hysteria` over UDP — each counted only when that inbound actually renders, so an `xdns`/`wireguard`/`hysteria` block with no user carrying the matching access reserves nothing); and the same port published twice on an overlapping node set. Reservations are per transport, so a `tcp` publish may reuse the port of a UDP-only listener. The same registry rejects two built-in inbounds on one socket regardless of portals — e.g. `hysteria` and `wireguard` both left on `443/udp`.

!!! danger "A published port is unauthenticated internet ingress"
    Any source matching the configured `allow` list — or any source that can reach `hub-node:port` at all when `allow` is omitted — gets a connection to `target` inside the portal-side network. Sources outside the allowlist are blocked. There is no VLESS handshake, no UUID, no user — **`portals[].users` does not apply**. That user list governs the egress direction only (whose hub traffic may enter the tunnel); it has no effect whatsoever on published ports. Without `allow` the port is open to the internet, and the target service's own authentication is the only remaining line of defense.

!!! warning "Publishing from a pooled portal"
    When several machines run the same portal config, the hub picks one of the pooled tunnels per connection. That is fine for egress — any of them reaches the same internet — but a published connection then lands on whichever machine Xray chose, and `target` has to mean the same thing on all of them. Give each machine its own portal id when the published service lives on exactly one of them.

### `strict`

`strict` (default `true`) confines what traffic emerging from the tunnel may reach on the portal side. The portal config mirrors the declared matchers as `direct` rules and blackholes the rest:

- one rule for `routes.domains` and one for `routes.ips`, copied verbatim from the schema — Xray prefixes such as `full:`, `domain:`, `regexp:` are preserved, so hub and portal cannot disagree about what a matcher means
- one port-pinned rule per `publish` entry (`ip` for a literal target, `full:<host>` for a name), matching only that target's port
- a final catch-all to a `blocked` blackhole outbound, which is added to the config only when `strict` is true (by default)

Sniffing on the reverse tunnel is turned off under `strict`. Xray sniffs with `routeOnly`, which leaves the dialed address alone but routes on the sniffed SNI/Host instead — an address the client chooses. Every strict matcher would then be evaluated against attacker-supplied text: a published `nas.home.arpa:5000` forward would never match its own `full:nas.home.arpa` rule (the SNI is whatever hostname the client used to reach the hub), while any member could reach an arbitrary LAN host by sending a matching SNI. With sniffing off, the portal matches the destination exactly as the hub sent it. `strict: false` keeps sniffing on.

With `strict: false` the portal emits a single catch-all `direct` rule instead — the pre-`strict` output — and anything that reaches the `{id}-portal` outbound can be dialed from the portal machine: its own loopback services, the rest of the LAN, the router's admin interface, the open internet. A hub-side mistake or an over-broad matcher then turns into remote access to the home network.

The portal enforces *what*, not *who*. Traffic emerging from a reverse tunnel carries no inbound user, so member filtering stays hub-side and portal-side rules never mention users.

A strict portal uses `domainStrategy: IPOnDemand` instead of the `IPIfNonMatch` a non-strict one keeps. `IPIfNonMatch` only re-runs the rules with DNS when *nothing* matched, and the strict catch-all always matches on the first pass — so the second pass would never happen and an `ip` matcher could never cover a domain destination. `IPOnDemand` resolves inside the first pass, so a domain arriving from the tunnel is still checked against `routes.ips`.

The hub does no such resolution on your behalf, in either direction. Its rule list ends in a `TCP,UDP` catch-all (`routing.hub_default`) that matches everything on the first pass, so the hub's own `IPIfNonMatch` second pass never runs either. Every `ip` matcher on the hub — `portals[].routes.ips` as much as `hub_routes[].ips` — matches only a destination the client already dialed as an IP literal; `routes.ips: [10.0.0.0/8]` never catches `internal.corp`. Declare the name in `routes.domains` for that.

Two cases then fail closed where a non-strict portal would have dialed:

- **The two resolvers disagree.** If the hub's DNS lands a name inside a declared CIDR and the portal's DNS does not — split-horizon setups, most often — the connection is blackholed. Declaring the name in `routes.domains` removes the dependency on DNS entirely, since a domain matcher is checked before any resolution happens.
- **The client dialed an IP literal.** Hub inbounds sniff with `routeOnly`: the sniffed SNI/Host decides the route, but the dialed address is left alone, and the address is what the tunnel carries. A client that resolves DNS itself and opens `1.2.3.4:443` with SNI `home.alice.example.com` matches `routes.domains` on the hub and enters the tunnel, then arrives at the portal as `1.2.3.4:443` and is blackholed. Clients that send the hostname are unaffected — SOCKS and HTTP proxies do, as do TUN implementations that rewrite the destination from their own sniffing (sing-box, Clash) — but a plain `tun2socks`-style setup does not. Cover the address range in `routes.ips` when members connect that way.

`strict: false` is the escape hatch for both.

Matchers are copied verbatim, so a `geosite:` / `geoip:` / `ext:` entry in `routes` also lands in the portal config and Xray refuses to start without the matching `.dat` asset on the portal machine. Keep strict portals on literal matchers, or deploy the asset files there too.

**Example:**

```yaml
portals:
  - id: home
    users: [alice, bob]
    routes:
      domains: [internal.example.com, "domain:lan"]
      ips: [10.0.0.0/8, 192.168.1.0/24]
    publish:
      # NAS web UI, reachable only from the office range
      - port: 8443
        target: 192.168.1.10:443
        allow: [203.0.113.7/32, 198.51.100.0/24]
        nodes: [euH00]
      # game server, both transports, every hub node
      - port: 27015
        target: nas.lan:27015
        network: tcp,udp

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
| `protocol` | `vless \| hysteria` | no (exit only) | How hubs dial this region; default `vless` (XHTTP + Reality). `hysteria` makes every exit node render a Hysteria listener and every hub dial it over QUIC |
| `hysteria` | `HysteriaOverride` | no (exit only) | Region-level overlay on `defaults.exit.hysteria`. Defining it (or `node.hysteria`) makes every node in the region serve a Hysteria listener regardless of `protocol`, so an exit offers Hysteria and VLESS+Reality at once and flipping `protocol` rewrites only hub outbounds. `enabled` is not accepted here |
| `cdn_xhttp_path` | `str` | no | CDN xhttp path override for this region |
| `lb_strategy` | `str` | no | Load balancer strategy (e.g. `leastLoad`) |
| `lb_fallback` | `str` | no | Fallback node ID (must be in this region) |
| `lb_least_load` | `LeastLoadSettings` | no | leastLoad tuning |
| `routing` | `RegionRouting` | no | Per-region routing overrides (exit only) |
| `warp` | `WarpConfig` | no | Warp tunnel configuration |
| `nodes` | `list[Node]` | yes | May be a bare key: a region without nodes keeps its settings, renders nothing, and is refused as `hub_default` or a `hub_routes` destination |

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
| `hysteria` | `HysteriaOverride` | no | Override Hysteria settings; on hubs it also enables the listener without `defaults.hub.hysteria`, on exit nodes it makes the node serve a Hysteria listener regardless of `protocol` |

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

### `HysteriaOverride`

All fields optional; `null` means "use the value from the layer below" — `defaults.hub.hysteria` on hubs, `defaults.exit.hysteria` → `regions[].hysteria` on exits (built-in `HysteriaConfig` defaults when no layer sets a field).

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | `bool` | Hub nodes only: `false` drops the listener even when defaults configure it. Exit regions/nodes must switch `protocol` instead |
| `port` | `int` (1–65535) | Override UDP port |
| `obfs` | `bool` | Override Salamander obfuscation |
| `congestion` | `bbr \| brutal` | Override congestion control |
| `up` / `down` | `str` | Override brutal rates |
| `sni` | `str` | Override SNI (and derived-cert CN) |
| `masquerade_url` | `str` | Override masquerade target |
| `key_type` | `ed25519 \| ecdsa-p256` | Override the derived cert's key algorithm, or declare an operator cert's |
| `certificate` | `HysteriaCertificate` | Serve an operator cert on this node (`cert_file`, `key_file`, optional `pin_sha256`); requires `sni` |

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
