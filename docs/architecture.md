# Architecture

## Component / Controller / Application pattern

HexRift is structured around a lightweight **Component/Controller/Application** framework in `hexrift/core/`.

```bash
BaseApplication  (singleton registry + dependency injector)
└── registers Components in order:
    ├── SchemaComponent    → SchemaController    (app.schema)
    ├── DeriveComponent    → DeriveController    (app.derive)
    ├── KeysComponent      → KeysController      (app.keys)
    ├── RenderComponent    → RenderController    (app.render)
    └── TopologyComponent  → TopologyController  (app.topology)
```

### `BaseApplication` (`hexrift/core/application.py`)

- Singleton — only one instance exists at runtime.
- Iterates `default_components` on `__init__`, calling `self.register(component_cls)`.
- `register(...)` instantiates the component, stores it in `self.components`,
  exposes controller attributes (when enabled), then runs `component.on_register()`.
- Exposes each controller as an attribute: `app.schema`, `app.derive`, `app.keys`, `app.render`, `app.topology`.
- Holds a shared `rich.Console` for all output.

### `BaseComponent` (`hexrift/core/component.py`)

- Layer between Click CLI and business logic.
- Defines `name`, `controller_class`, and optionally `expose_controller`.
- `expose_cli(base: click.Group)` registers Click commands on the main group at import time.

### `BaseController` (`hexrift/core/controller.py`)

- Holds business logic; receives `app` for cross-component access.
- Example: `RenderController` calls `self.app.schema.config` and `self.app.keys.load_node_keys(...)`.

### Request flow

```bash
CLI command invoked
  → Click routes to component's expose_cli handler
  → handler accesses app (passed via ctx.obj)
  → app.schema loads YAML (cached after first load)
  → handler calls controller method
  → controller accesses other components via self.app.*
```

---

## Deterministic derivation

All identifiers (UUIDs, shortIds, emails) are derived from the topology — never randomly generated. Re-running always produces the same output for the same `namespace` and names.

!!! danger "`namespace` seeds every identity"
    `global.namespace` feeds the namespace UUID that every user, guest, server, group and hub-exit identifier derives from. Changing it re-derives all of them at once, so every issued client config stops authenticating until it is reissued. Renaming a user or a node has the same effect for that one identity. Pin an existing value with `users[].uuid`, `portals[].uuid` or `groups[].short_id` when a name has to change but the credential must not.

Source: `hexrift/components/derive/identity.py` — `Namespace` class.

### UUID derivation

| Identifier | Formula |
|------------|---------|
| Namespace UUID | `UUID5(UUID(int=0), namespace)` |
| User UUID | `UUID5(namespace_uuid, username)` |
| Server UUID | `UUID5(user_uuid, "{username}-server")` |
| Guest UUID | `UUID5(user_uuid, guest_label)` |
| Portal UUID | `UUID5(namespace_uuid, "portal/{id}")` |
| Hub-Exit UUID | `UUID5(namespace_uuid, "{hub_id}-{exit_id}")` |
| Warp UUID | Hub-Exit UUID with 3rd segment replaced by `ffff` |

The `portal/` seed prefix contains a character that is illegal in identifiers, so a portal UUID can never collide with a user or hub-exit UUID.

A user's UUID can be overridden with `users[].uuid`, a portal's with `portals[].uuid`. An override that lands on any other identity is rejected: Xray matches an inbound client by `id` alone, so a duplicate would silently disable one of the two.

### ShortId derivation

ShortIds are the first 16 hex characters of a SHA-256 hash:

| Identifier | Input string |
|------------|-------------|
| Group shortId | `"{group_id}.{namespace}"` (or override via `groups[].short_id`) |
| Hub shortId | `"{node_id}.hub.{namespace}"` |
| Exit shortId | `"{node_id}.exit.{namespace}"` |
| User shortId | `"{username}.user.{namespace}"` |
| Portal shortId | `"{portal_id}.portal.{namespace}"` |

### Email derivation

| Email | Format |
|-------|--------|
| User | `{username}@{namespace}` |
| Server | `{username}-server@{username}` |
| Portal | `{id}@portal.{namespace}` |
| Guest | `{label}@{username}` |
| Hub-Exit | `{hub_id}-{exit_id}@{namespace}` |
| Warp | `warp-{hub_id}-{exit_id}@{namespace}` |

### WireGuard keypair derivation

WireGuard peer keys are also deterministic. For each identity (user, server, guest) a 32-byte seed is derived from the hub's Reality private key and the identity, then expanded into an x25519 keypair:

```text
seed    = HMAC-SHA256(reality_private_key, "{identity_uuid}.wireguard.{namespace}")
keypair = x25519(seed[:32])
```

Peer addresses are allocated sequentially from `defaults.hub.wireguard.subnet`: the first host (`.1`) is reserved for the server, then peers are assigned from `.2` in user → server → guest order.

### Hysteria certificate and obfuscation derivation

Hysteria needs a real TLS certificate, and both are derived from the node's Reality private key rather than stored:

```text
seed     = HMAC-SHA256(reality_private_key, "hysteria-tls.{namespace}")             # key_type: ed25519
         | HMAC-SHA256(reality_private_key, "hysteria-tls-ecdsa-p256.{namespace}")  # key_type: ecdsa-p256
cert_key = Ed25519(seed) | ECDSA-P256(seed mod (n - 1) + 1)
cert     = self-signed leaf, CN/SAN = sni, fixed serial and validity, signed by cert_key
pin      = SHA-256(cert DER)                       # pinnedPeerCertSha256 / pinSHA256
obfs     = base64url(HMAC-SHA256(reality_private_key, "hysteria-obfs.{namespace}"))
```

Ed25519 signs deterministically by construction and ECDSA uses RFC 6979 nonces, so the same key and SNI always yield byte-identical DER and a stable pin; hub nodes that share keys within a region therefore also share the cert. Hubs dialing an `ed25519` exit add `disableChromeParrot` to the trunk's `quicParams`: Xray's Hysteria dialer parrots Chrome's QUIC ClientHello, whose `signature_algorithms` omit Ed25519, so the exit would have no certificate to offer. Source: `hexrift/components/derive/hysteria.py`.

---

## Key storage

Keypairs are generated by `gen-keys` and stored in `keys/<nodeId>.yaml`.

Source: `hexrift/components/keys/store.py`, `reality.py`, `decryption.py`.

### File format

```yaml
reality_private_key: "<base64url-no-padding>"   # x25519 private key (32 bytes)
reality_public_key:  "<base64url-no-padding>"   # x25519 public key (32 bytes)
decryption: "mlkem768x25519plus.rprx_vision.12h.{private_key_b64}"   # server inbound
encryption: "mlkem768x25519plus.rprx_vision.0rtt.{public_key_b64}"   # client outbound
```

### Key string format

| String | Usage | Format |
|--------|-------|--------|
| `decryption` | Xray server inbound | `{method}.{mode}.{session_time}[.{padding}].{private_key_b64}` |
| `encryption` | Client share URL | `{method}.{mode}.0rtt.{public_key_b64}` |

File permissions are set to `0o600` (owner read/write only).

!!! info "Hub key sharing"
    Hub nodes in the same region share the same keypair. `gen-keys` detects this automatically and only generates one file.

---

## Adding a component

Follow the pattern established by the existing components:

### 1. Create module structure

```bash
hexrift/components/myfeature/
├── __init__.py
├── component.py   # Click CLI registration
└── controller.py  # Business logic
```

### 2. Define controller

```python
# hexrift/components/myfeature/controller.py
from hexrift.core.controller import BaseController


class MyController(BaseController["HexRiftApp"]):
    def do_something(self) -> None:
        cfg = self.app.schema.config  # access other components
        ...
```

### 3. Define component

```python
# hexrift/components/myfeature/component.py
import rich_click as click
from hexrift.core.component import BaseComponent
from .controller import MyController


class MyComponent(BaseComponent["HexRiftApp", MyController]):
    name = "myfeature"
    controller_class = MyController
    expose_controller = True

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        @base.command()
        @click.pass_obj
        def mycommand(app: "HexRiftApp") -> None:
            """One-line help text."""
            app.myfeature.do_something()
```

### 4. Register in the app

```python
# hexrift/app.py
from hexrift.components.myfeature.component import MyComponent


class HexRiftApp(BaseApplication["HexRiftApp"]):
    default_components = [..., MyComponent]
    myfeature: MyController
```

---

## Adding a hub→exit link protocol

Hub→exit outbounds are built by `LinkSpec`s in `hexrift/links/`, the counterpart of the `InboundSpec` registry. Each spec turns one (hub node, exit node, identity UUID) into a `LinkContext` and renders that context to an Xray outbound; `links/registry.py` keys the specs by `ExitProtocol` and `build_hub_context` picks one per exit region via `resolve_link_protocol` (`regions[].protocol`, default `vless`).

To add a protocol:

1. Add the member to `ExitProtocol` in `hexrift/constants.py`.
2. Create `hexrift/links/<proto>.py` with a `LinkContext` subclass (`protocol` class var + the resolved dial fields) and a `LinkSpec` implementing `build_context(env, identity, tag_prefix)` and `fragment(ctx, ipv6)`; register the instance in `LINK_SPECS`.
3. Give exits something to listen with: an `InboundSpec` in `hexrift/inbounds/` whose `build_context` returns `None` unless the region's link protocol matches (see `HysteriaSpec`), plus schema for any tuning and its `resolve_*` overlay.
4. Cover it in `tests/unit/links/` and the golden fixture.

Existing goldens stay byte-identical as long as the VLESS spec is untouched — the registry only decides which spec runs, not the order of outbounds.

## Developer commands

```bash
uv run ruff check . --fix        # lint + auto-fix
uv run ruff format .             # format
uv run ty check                  # type-check
uv run prek run --all-files      # run all pre-commit hooks
```

### Commit convention

```bash
<type>[scope]: <description>

Examples:
  feat(render): add CDN support
  fix(schema): validate unique vless_route values
  chore(release): bump version to 0.6.0
```
