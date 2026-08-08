# Changelog

## [0.11.2](https://github.com/wlix13/HexRift/compare/v0.11.1...v0.11.2) (2026-08-08)


### Features

* **portals:** add support for publishing hub ports into reverse tunnel ([2181d98](https://github.com/wlix13/HexRift/commit/2181d98799eff3eef5df80cc1367e4fdc8e1efd9))
* **portals:** confine portal egress to declared matchers ([23e6339](https://github.com/wlix13/HexRift/commit/23e6339b7880dc55469d527b25ccc7b62246d1c8))


### Documentation

* **portals:** document published ports feature ([5d04818](https://github.com/wlix13/HexRift/commit/5d0481827a5c81c0486d09e224b9666dc9add83f))

## [0.11.1](https://github.com/wlix13/HexRift/compare/v0.11.0...v0.11.1) (2026-08-01)


### Bug Fixes

* **portals:** allow default final rule egress from reverse tunnel on portal ([a74d9ba](https://github.com/wlix13/HexRift/commit/a74d9ba24a7487706871fcd8ce3ffe6207feec0f))
* **portals:** stop deriving portal `sockopt` dial from hub IPv6 ([734fc16](https://github.com/wlix13/HexRift/commit/734fc16a8130b0afee19076832c29a6c3e5149e9))

## [0.11.0](https://github.com/wlix13/HexRift/compare/v0.10.2...v0.11.0) (2026-08-01)


### ⚠ BREAKING CHANGES

* **portals:** `users[].portals` no longer exists. Move each portal to top-level `portals:` section and list allowed users in `portals[].users`.

### Features

* **portals:** move portals to top-level section ([8a9ad92](https://github.com/wlix13/HexRift/commit/8a9ad926f71814af88395457cdb0b4e529ef99d4))


### Bug Fixes

* **schema:** reject portal members without routable identity ([a5f209e](https://github.com/wlix13/HexRift/commit/a5f209efcd0414ea878179f668955086fd28abc1))
* **schema:** reject uuid overrides that shadow another identity ([920c244](https://github.com/wlix13/HexRift/commit/920c244b9ca512e927a1375ffdfa2cadab1420b6))


### Documentation

* add explanations for trust levels and destructive operations ([8f0491d](https://github.com/wlix13/HexRift/commit/8f0491d49c9e443323d7436e6f8d2367a772c9b2))
* **portals:** add documentation about top-level portals ([2b8d920](https://github.com/wlix13/HexRift/commit/2b8d9201ed6ef8b60f4cedc3eaf263421c48248d))

## [0.10.2](https://github.com/wlix13/HexRift/compare/v0.10.1...v0.10.2) (2026-07-18)


### Features

* **observability:** opt-in Xray stats API and logging control ([9889c6d](https://github.com/wlix13/HexRift/commit/9889c6d27123fa73f5a940030376e719400df18c))

## [0.10.1](https://github.com/wlix13/HexRift/compare/v0.10.0...v0.10.1) (2026-07-15)


### Bug Fixes

* **xray:** replace hardcoded DNS rules with dynamic generation ([c7e70a1](https://github.com/wlix13/HexRift/commit/c7e70a1fc189f2cf0025c04726c8fe31e361e055))

## [0.10.0](https://github.com/wlix13/HexRift/compare/v0.9.1...v0.10.0) (2026-06-23)


### ⚠ BREAKING CHANGES

* **xray:** routeOnly is now set dynamically based on region type

### Features

* **xray:** replace SNIFFING with dynamic configuration based on region type ([4bb4f95](https://github.com/wlix13/HexRift/commit/4bb4f952fb48c7be83be76760bbf1d330d05c4d3))

## [0.9.1](https://github.com/wlix13/HexRift/compare/v0.9.0...v0.9.1) (2026-06-18)


### Features

* **haproxy:** add support for HAProxy-less topology ([8f43102](https://github.com/wlix13/HexRift/commit/8f431025747841277301cb3b117b3241792b1d05))


### Bug Fixes

* **xray_defaults:** set trusted_headers always ([69dec25](https://github.com/wlix13/HexRift/commit/69dec25566c8ecfa2548f3d00c3534caec0c8f0b))


### Documentation

* **README:** add paragraph about  HAProxy-less and all-in-one node topologies ([c4534b3](https://github.com/wlix13/HexRift/commit/c4534b36c0d627ee1998532684612caf5c34f085))

## [0.9.0](https://github.com/wlix13/HexRift/compare/v0.8.0...v0.9.0) (2026-06-14)


### ⚠ BREAKING CHANGES

* **render:** rename command `portal-gen` to `gen-portal`
* topology.yaml no longer accepts `mtproto`; configs that set it will fail schema validation. Remove all mtproto keys before upgrading.

### Features

* **constants:** add new constants and patterns; refactor schema models ([012d85a](https://github.com/wlix13/HexRift/commit/012d85a1fc2ad9f5520a8d54f9a1536f05983795))
* **docs:** add documentation for WireGuard and XDNS support ([8c30615](https://github.com/wlix13/HexRift/commit/8c30615afdff2de6204e5fba4f16fc22a810ae13))
* **inbounds:** introduce inbound spec base, registry, and modules ([a8a65b6](https://github.com/wlix13/HexRift/commit/a8a65b6f3c846db8d88792cfe21eb8d440b580d4))


### Documentation

* **readme:** add Codecov coverage badge ([cee2e46](https://github.com/wlix13/HexRift/commit/cee2e4617271cf05d09c552997104de48653ef3a))


### Code Refactoring

* remove mtproto support ([d91ab0b](https://github.com/wlix13/HexRift/commit/d91ab0b6249d3884b0623ef32bb9e5d266dc7118))
* **render:** consolidate render pipeline and drop context module ([baf32ed](https://github.com/wlix13/HexRift/commit/baf32ed41d533658af0497faee1e1d6a6251259d))
