# Transport internals

Why the generated Xray config looks the way it does, and which knobs actually take effect.

Every claim below is traced to Xray-core source. References are `file:line` against Xray-core at commit `6e3322d2`. Re-verify them when bumping the Xray version — several are load-bearing and none are part of a stable API.

---

## Layer order

Direct path (`AccessType.XHTTP` → `inbounds/xhttp.py`):

```text
inner traffic (the client's own TLS to the destination)
└─ XTLS Vision framing              flow: xtls-rprx-vision
   └─ VLESS header + body
      └─ VLESS Encryption AEAD      decryption / encryption
         └─ XHTTP request bodies    network: xhttp
            └─ REALITY              security: reality
               └─ TCP :443
```

CDN path (`AccessType.CDN` → `inbounds/cdn.py:94`) is the same stack with `security: none`; HAProxy terminates TLS in front of it.

The order follows Xray's dial order: the transport is built first, then the encryption layer wraps whatever it returned (`proxy/vless/outbound/outbound.go:211-216`), then the VLESS header goes on that, then Vision wraps the body writer (`proxy/vless/encoding/addons.go:70-72`).

---

## Vision over XHTTP requires VLESS encryption

This is a hard dependency, and not an obvious one.

At the moment Vision stops framing and hands off to direct copy, it must drain the outer connection's already-buffered plaintext. It does this by reading `input` / `rawInput` struct fields through reflect + unsafe pointer arithmetic (`outbound.go:286-289`, `inbound.go:583-586`). Only connection types that *have* those fields are accepted:

| Connection type | Accepted | Where |
|---|---|---|
| `encryption.CommonConn` | yes | `outbound.go:268`, `inbound.go:565` |
| `tls.Conn` / `tls.UConn` | yes | `outbound.go:274-279` |
| `reality.UConn` (out) / `reality.Conn` (in) | yes | `outbound.go:280`, `inbound.go:577` |
| anything else | **no** — `XTLS only supports TLS and REALITY directly for now.` | `outbound.go:284`, `inbound.go:581` |

XHTTP's dialer returns `*splitConn` (`transport/internet/splithttp/connection.go`). REALITY lives *inside* the `http.Transport` (`splithttp/dialer.go:136`), not in the connection chain — so `splitConn` is what Vision sees, and it is not on the list.

`encryption.CommonConn` declares `input bytes.Reader` and `rawInput bytes.Buffer` (`proxy/vless/encryption/common.go:36-37`) precisely to satisfy this contract. Enabling VLESS encryption is therefore what makes Vision usable over XHTTP at all.

The server rejects the inverse mismatch: an account configured with `flow: xtls-rprx-vision` that receives an empty flow is refused (`inbound.go:593`).

!!! warning "`NodeKeys.flow` coupling is load-bearing"
    `NodeKeys.flow` and `NodeKeys.client_flow` return `""` when `encryption == "none"` (`components/keys/store.py:33-43`). That is what upholds the invariant. Changing them to return the Vision flow unconditionally would make every generated config fail at dial time with `XTLS only supports TLS and REALITY directly for now.` — including nodes where `defaults.*.keys.enabled` is `false`.

---

## Splice is never available over XHTTP

Vision can normally escalate to a kernel-space `splice()` for the bulk phase. Over XHTTP it cannot, on either leg:

- `IsRAWTransportWithoutSecurity` only returns true for `proxyproto.Conn`, `net.TCPConn`, or `UnixConnWrapper` (`proxy/proxy.go:802-809`). With XHTTP the unwrapped conn is `splitConn`, so it returns false.
- Both sides then pin `CanSpliceCopy = 3` (`outbound.go:269-271`, `inbound.go:566-568`).
- `CopyRawConnIfExist` falls back to the userspace `readV` path when any participant is `3` (`proxy/proxy.go:730-741`).

Consequence: all proxied bytes pass through userspace buffers. This is inherent to the XHTTP transport, not something the config can recover. Budget CPU accordingly on hub nodes, which carry aggregated traffic for every user.

---

## What Vision's direct copy actually writes to

After handoff, Vision re-points its reader and writer at the *unwrapped* connection (`proxy/proxy.go:282`, `:344`). Where that unwrapping stops depends on the encryption mode:

| `keys.mode` | `UnwrapRawConn` returns | Effect after handoff |
|---|---|---|
| `native` (current) | `splitConn` | VLESS Encryption AEAD is **bypassed**; inner records go into the HTTP body as-is |
| `xorpub` | `splitConn` | same as `native` |
| `random` | `encryption.XorConn` (`proxy.go:681-683`) | AEAD bypassed, but the 5-byte record headers stay CTR-masked |

`UnwrapRawConn` sets `isEncryption = true` and deliberately skips TLS/REALITY penetration in that case (`proxy.go:690`), so REALITY's record layer is still in the path.

With the current `mode: native`, confidentiality of the bulk phase rests on REALITY (direct path) or HAProxy's TLS (CDN path) — not on the VLESS Encryption layer. The AEAD covers the handshake and the pre-handoff frames only. This is intended behaviour and mirrors how Vision works under plain TLS; it is worth knowing before reasoning about what the encryption layer protects.

---

## `mode: "auto"` resolves differently per path

`make_xhttp_settings` passes `mode="auto"` for both paths. Xray's client resolves it at dial time (`splithttp/dialer.go:363-370`):

| Path | Security | `auto` resolves to |
|---|---|---|
| Direct (`inbounds/xhttp.py`) | `reality` | **`stream-one`** |
| CDN (`inbounds/cdn.py`) | `none` | **`packet-up`** |
| Direct with `downloadSettings` set | `reality` | `stream-up` |

`stream-one` is a single full-duplex HTTP request — upload in the request body, download in the response body — and no session ID is generated for it (`dialer.go:373-376`). `packet-up` splits the upload across sequential POSTs with a long GET for download.

This means the two paths behave quite differently despite sharing `XHTTP_EXTRA`.

---

## Which `extra` keys are live where

From `shared/xhttp.py`. Several entries are inert on the path they are set on:

| Key | Read at | Active in |
|---|---|---|
| `xPaddingBytes` | `config.go` padding helpers, `hub.go:222` | all modes, both paths |
| `noGRPCHeader` | `config.go:325` | any request with a body — `stream-one`/`stream-up` upload, `packet-up` POSTs |
| `scMaxEachPostBytes` | `dialer.go:483-490` (client), `hub.go:184` (server limit) | `packet-up` |
| `scMinPostsIntervalMs` | `dialer.go:536-538` | `packet-up`, client only |
| `scMaxBufferedPosts` | `hub.go:72` (upload queue depth) | `packet-up`, server only |
| `scStreamUpServerSecs` | `hub.go:218-227` | `stream-up` server only, **and** only when the request carries a `Referer` or obfs padding was accepted |
| `xPaddingMethod`, `xPaddingObfsMode`, `xPaddingPlacement`, `xPaddingHeader` | `config.go:300-320` | all modes (CDN preset only) |

So on the **direct path** (`stream-one`), only `xPaddingBytes` and `noGRPCHeader` do anything. `scMaxEachPostBytes`, `scMinPostsIntervalMs`, `scMaxBufferedPosts`, and `scStreamUpServerSecs` are dead weight there. They are live on the CDN path, which currently is not deployed (`global.cdn: null`).

---

## `xmux` is client-side only

`XmuxConfig`'s accessors are referenced exclusively from `splithttp/mux.go` and `splithttp/dialer.go`; `hub.go` never reads them. The server has no xmux concept.

Two consequences for the generated output:

1. The `xmux` block in the **inbound** fragment (`inbounds/xhttp.py:160`, `inbounds/cdn.py:95`) is inert.
2. Share URLs carry only `encryption`, `flow`, `security`, `sni`, `fp`, `pbk`, `sid`, `type`, `host`, `path`, `mode` (`inbounds/xhttp.py:197-211`). No `xmux` and no `extra`. **End-user clients use their own defaults**, whatever the app ships.

`XMUX` therefore governs exactly one thing: the hub→exit outbounds (`components/render/xray.py:175`).

---

## xmux connection lifecycle → REALITY handshake rate

An xmux client is retired when its connection closes, `leftUsage` hits 0, `LeftRequests` hits 0, or `UnreusableAt` passes (`mux.go:84-87`). Retirement means the next proxy connection performs a **fresh REALITY handshake**.

### Request accounting per mode

`LeftRequests` is seeded from `hMaxRequestTimes` (`mux.go:71-73`) and decremented per HTTP request:

| Mode | Decrements | Where |
|---|---|---|
| `stream-one` | **1 per proxy connection** | `dialer.go:456` |
| `stream-up` | 2 per proxy connection (download GET + upload stream) | `dialer.go:465`, `:474` |
| `packet-up` | 1 for the download GET, then **1 per POST** | `dialer.go:465`, `:542` |

Under `packet-up` the budget is consumed in proportion to upload *request count*, not connection count. POST size is bounded above by `scMaxEachPostBytes` but not below — `buf.SplitSize` sends whatever the pipe has buffered — so chatty interactive uploads burn the budget far faster than the byte ceiling suggests.

### Connection creation

- `maxConnections: 0` → the eager-create branch at `mux.go:106` never fires. A new connection is opened only when the client list is empty (`:101`) or every existing client has `Running >= maxConcurrency` (`:112-125`). This is the reuse-first behaviour.
- `cMaxReuseTimes` decrements once per `GetXmuxClient` call, i.e. per proxy connection (`mux.go:129-131`).

With the current `XMUX` values and `stream-one`, `cMaxReuseTimes: "10-100"` is the **tightest** of the three limits and retires connections first: 10–100 proxy connections, versus 600–900 requests or 1800–3000 seconds. Raising its floor is the direct lever on handshake rate.

!!! note "`packet-up` and `hMaxRequestTimes` interact badly"
    Switching the direct path to `packet-up` without also raising `hMaxRequestTimes` multiplies the REALITY handshake rate, because every POST spends a request from a budget sized for whole connections.

---

## Encryption key strings

Built by `components/keys/decryption.py`:

```text
decryption  = mlkem768x25519plus.{mode}.{session_time}[.{padding}].{server_key_b64}
encryption  = mlkem768x25519plus.{mode}.0rtt.{client_key_b64}
```

### `auth` selects the long-term key only

`defaults.*.keys.auth` chooses the **nfs** (non-forward-secret, long-term) tier. Xray distinguishes the two by decoded byte length alone:

| `auth` | Server block | Client block | Xray branch |
|---|---|---|---|
| `x25519` | 32-byte private key | 32-byte public key | `client.go:46-51`, `server.go:55-60` |
| `mlkem768` | 64-byte seed | 1184-byte encapsulation key | `client.go:52-56`, `server.go:61-67` |

The **pfs** (per-session) tier is always ML-KEM-768 + X25519 hybrid regardless of this setting — `mlkem.GenerateKey768()` and an X25519 key are generated unconditionally (`client.go:133-135`), and both shared secrets are concatenated into `pfsKey` (`client.go:172-175`). Session keys are `unitedKey = pfsKey ‖ nfsKey` (`client.go:175`).

So `auth: x25519` still yields post-quantum forward secrecy for session traffic; it only makes the long-term server identity key classical. The naming suggests otherwise.

### 0-RTT and ticket lifetime

The server side is configured with `session_time` and the client with `0rtt`:

- With `secondsTo` unset, the server picks a per-ticket lifetime of a random 50–100% of `session_time` (`server.go:272-277`) — so `600s` yields 300–600 s.
- The client caches `pfsKey` + ticket until expiry (`client.go:188-194`) and then skips the 1-RTT exchange, gluing payload onto the handshake via `PreWrite` (`client.go:117-126`).
- Replay is refused per `nfsKey`: one use each (`server.go:223-225`).
- An expired or unknown ticket gets answered with random bytes deliberately crafted to fail `DecodeHeader` (`server.go:214-221`), which the client interprets as `new handshake needed` and retries with a full 1-RTT (`common.go:112-119`). No error surfaces to the user.

Note that 0-RTT saves the VLESS-layer round trip only. The REALITY handshake still happens once per TCP connection, so ticket resumption does not reduce handshake count — only xmux reuse does.

### Padding

`KeysConfig.padding` is unset, so Xray applies its built-in defaults (`encryption/common.go:261-262`):

```text
lengths  100-111-1111  and  50-0-3333
gaps     75-0-111
```

Read as `probability-from-to`. These fragment the encryption handshake across writes with random millisecond gaps (`client.go:142-153`, `server.go:296-307`). Override via `defaults.*.keys.padding` if needed; the first length block must be ≥ 35 (`common.go:243-245`) and total padding ≤ 65553 (`common.go:253-255`).

---

## Freedom blocks by default, and what it blocks depends on the inbound

A `freedom` outbound picks a default rule from the name of the inbound that fed it (`proxy/freedom/freedom.go:154-168`):

| `inbound.Name` | Default rule | Set at |
|---|---|---|
| `vless-reverse` | block everything | `proxy/vless/outbound/outbound.go:103` |
| `vless`, `vmess`, `trojan`, `hysteria`, `wireguard`, `shadowsocks*` | block private IPs | e.g. `proxy/vless/inbound/inbound.go:536` |
| anything else, including `mixed` (which is `socks`, `infra/conf/xray.go:27`) | none | `proxy/socks/server.go:68` |

Two consequences fall out of that table, in opposite directions.

Traffic emerging from a reverse tunnel is `vless-reverse`, so on a portal machine the default is **block everything** — the routing rules can hand a connection to `direct` and freedom will still blackhole it, logging `blocked target: …, blackholing connection for …` (`freedom.go:335-338`, `:354`). Portal configs therefore declare `"settings": {"finalRules": [{"action": "allow"}]}`. Configured rules are consulted before the default and the first match wins (`matchFinalRule`, `:187-197`), and an empty rule matches every network, port and address (`buildFinalRule` `:103-121`, `matchPort` `:130-135`, `matchIP` `:136-142`). A leading blanket allow also stops freedom resolving a domain purely to evaluate rules (`shouldResolveDomainBeforeFinalRules`, `:171-185`).

On a hub the opposite applies: user traffic arrives over `vless` or `wireguard`, so `direct` already refuses RFC1918 destinations — reaching a private network is what portals are for. The `mixed` proxy inbound is the exception, since `socks` matches no case and gets no default rule at all.

`finalRules` cannot express what a portal is confined to. The config accepts `action`, `network`, `port`, `ip` and `blockDelay` (`infra/conf/freedom.go:46-52`) and `ip` goes through an IP matcher, so CIDRs and `geoip:` entries only — a portal routed by domain has no expressible form, and freedom would resolve the name and match the resolved address instead. Confinement stays in the routing rules, which match domains natively.

---

## Reverse tunnels are health-checked outside `subjectSelector`

Every time a portal machine establishes its reverse mux, the hub's VLESS inbound probes that tag directly (`proxy/vless/inbound/inbound.go:665`):

```go
if burstObs, ok := observer.(extension.BurstObservatory); ok {
    go burstObs.Check([]string{r.Tag()})
}
```

`Observer.Check` hands the tag straight to `HealthPing.Check` → `doCheck` (`app/observatory/burst/healthping.go:148-154`); `subjectSelector` is read only by `StartScheduler` for the periodic sweep (`app/observatory/burst/burstobserver.go:69-79`). So the check runs on `{id}-portal` whatever the selectors say, and the only way to avoid it is to emit no `burstObservatory` block at all.

The probe dials `pingConfig.destination` through the tunnel, so on the hub it appears as `taking platform initialized detour [{id}-portal] for [tcp:www.apple.com:80]`, and on the portal as a request arriving from the reverse inbound. Consequences:

- the result is inert: only balancers read `HealthPing.Results`, and a portal tag can never enter a balancer selector — `ConglomerateConfig` rejects a portal whose tag prefixes an exit region id
- expect one `error ping … with {id}-portal` warning per reconnect whenever the portal does not route the probe destination
- a portal confined to its declared matchers blackholes the probe, so it never leaves the portal-side network — an unconfined one really does fetch the destination from there on every reconnect

---

## Summary of currently-inert configuration

Not bugs — just settings that cost nothing and do nothing where they are:

| Setting | Location | Why inert |
|---|---|---|
| `xmux` in inbound fragments | `inbounds/xhttp.py:160`, `inbounds/cdn.py:95` | xmux is client-side only |
| `scMaxEachPostBytes`, `scMinPostsIntervalMs`, `scMaxBufferedPosts` | direct path `extra` | `packet-up` only; direct path resolves to `stream-one` |
| `scStreamUpServerSecs` | both paths | `stream-up` only |
| `XHTTP_EXTRA` / `XMUX` for end users | share URLs | not encoded in the VLESS URL |
| `AccessType.CDN` presets | `inbounds/cdn.py` | `global.cdn: null` |
