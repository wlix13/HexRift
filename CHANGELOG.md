# Changelog

## [0.11.0](https://github.com/wlix13/HexRift/compare/v0.10.0...v0.11.0) (2026-06-23)


### ⚠ BREAKING CHANGES

* **xray:** routeOnly is now set dynamically based on region type
* **render:** rename command `portal-gen` to `gen-portal`
* topology.yaml no longer accepts `mtproto`; configs that set it will fail schema validation. Remove all mtproto keys before upgrading.

### Features

* **constants:** add new constants and patterns; refactor schema models ([012d85a](https://github.com/wlix13/HexRift/commit/012d85a1fc2ad9f5520a8d54f9a1536f05983795))
* **core:** add MKCP/WireGuard constants and key helpers ([7646d46](https://github.com/wlix13/HexRift/commit/7646d46e0e0dd755496c0571e415d174d6afad1f))
* **core:** add working version ([e4e4865](https://github.com/wlix13/HexRift/commit/e4e48656bb0ae347098e9571789cc8e171eb3a4e))
* **derive:** add client WireGuard config generation ([8ef444e](https://github.com/wlix13/HexRift/commit/8ef444e0ad6ffda10949d1fb9600d93093a50845))
* **derive:** add command to list nodes in topology ([904f48f](https://github.com/wlix13/HexRift/commit/904f48f07e50d840ee9028262dad924c262f9be5))
* **derive:** derive guest shortIds from parent user ([d65bb50](https://github.com/wlix13/HexRift/commit/d65bb504b0fd5158bceaf5e4959d61bb32308040))
* **derive:** show guests with shortIds in derive users table ([700cb77](https://github.com/wlix13/HexRift/commit/700cb77f2a1ad400a38f4d0bc73a6cb7ee7c2f67))
* **docs:** add AI translated ru docs localization ([7a2ebdd](https://github.com/wlix13/HexRift/commit/7a2ebdd590ed3f98e95f4f6635606c657a2e323f))
* **docs:** add docs for architecture, CLI reference and development ([22bb542](https://github.com/wlix13/HexRift/commit/22bb542c901bdddfc26962420bc904c9e1005d65))
* **docs:** add documentation for WireGuard and XDNS support ([8c30615](https://github.com/wlix13/HexRift/commit/8c30615afdff2de6204e5fba4f16fc22a810ae13))
* **docs:** add markdownlint config ([9ee1b6c](https://github.com/wlix13/HexRift/commit/9ee1b6cd5adb0b7446755e56270f20830f61038e))
* **docs:** add mkdocs configuration ([f441ef2](https://github.com/wlix13/HexRift/commit/f441ef2acc54aa2ed6f71558ae521c9f01324b00))
* **haproxy:** add support for HAProxy-less topology ([8f43102](https://github.com/wlix13/HexRift/commit/8f431025747841277301cb3b117b3241792b1d05))
* **i18n:** add gettext translation infrastructure ([43719b2](https://github.com/wlix13/HexRift/commit/43719b21e13387aeb3e6992b4b4d62b51107e2d2))
* **i18n:** add Russian translation and message catalog ([6220ea8](https://github.com/wlix13/HexRift/commit/6220ea8b566effd027f37a83e69fd06dc1794326))
* **inbounds:** introduce inbound spec base, registry, and modules ([a8a65b6](https://github.com/wlix13/HexRift/commit/a8a65b6f3c846db8d88792cfe21eb8d440b580d4))
* init repo ([4d6c9e4](https://github.com/wlix13/HexRift/commit/4d6c9e4b16dbbeb477080d3f1fe42e42ec99e324))
* **mtproto:** add MTProto deployment support ([e1d6708](https://github.com/wlix13/HexRift/commit/e1d670894ac8db2eb23f43be344be14a65391a15))
* **poe:** add documentation task in pyproject ([f2b1068](https://github.com/wlix13/HexRift/commit/f2b1068a48b0d22de2fe3e362c0bbd0937629971))
* **render:** add 'portal-gen' command ([457da63](https://github.com/wlix13/HexRift/commit/457da63256cd63f8d7c00862407669df9efea5a3))
* **render:** add portal config rendering ([15e67cd](https://github.com/wlix13/HexRift/commit/15e67cdab70754e97d96cf64422f963e602f64c2))
* **render:** add reality fallback limits and observatory configuration ([d92cc02](https://github.com/wlix13/HexRift/commit/d92cc02f2089e64674bfce22e3b78b93cfd59bee))
* **render:** add XDNS/WireGuard inbound generation ([b9ad6b3](https://github.com/wlix13/HexRift/commit/b9ad6b31a5293d0f825a7a7e484d9786742f73d0))
* **render:** embed reverse tag on portal clients, remove reverse.portals block ([9e8883a](https://github.com/wlix13/HexRift/commit/9e8883a4395c539508dda42df21637b56ae20934))
* **render:** use xtls-rprx-vision-udp443 for inter-node outbound connections ([9074e67](https://github.com/wlix13/HexRift/commit/9074e676efeb3a86f7622a13a6547e47494adcd8))
* **routing:** add users support to routes ([7781ce1](https://github.com/wlix13/HexRift/commit/7781ce1dbf5fa285aca74af0412a60fd7490c673))
* **routing:** introduce exit routes and update routing ([96d1949](https://github.com/wlix13/HexRift/commit/96d19492a3b082300abf6154505579f2ecb3daf4))
* **routing:** update routing rules generation ([ad8216d](https://github.com/wlix13/HexRift/commit/ad8216dbee8308abe53373c7eb57b406f483a1d9))
* **schema:** add configurable dns support ([cfaf978](https://github.com/wlix13/HexRift/commit/cfaf978eed55b42cfbf876794790e099cadddee7))
* **schema:** add XDNS and WireGuard topology models ([373a970](https://github.com/wlix13/HexRift/commit/373a97081319d2f606412d6633d69a93513fe416))
* **shared:** add "shared" for better component integration ([d9ef201](https://github.com/wlix13/HexRift/commit/d9ef201775e8f5e16ca6c98c2ab5169b0858c995))
* **version:** add version option to CLI ([e9997ea](https://github.com/wlix13/HexRift/commit/e9997ea0d01e1c8f715dd037f6c22cf557c52697))
* **xhttp:** add separate extras for CDN inbound for better DPI masquerade ([bfde62e](https://github.com/wlix13/HexRift/commit/bfde62ec1cc0dc440d5285649fb871a78351cfed))
* **xray:** add routeOnly option to SNIFFING configuration ([93ae800](https://github.com/wlix13/HexRift/commit/93ae80013876179113ecda66361cdd07215af3c1))
* **xray:** enhance socket options with trusted header ([94f15c1](https://github.com/wlix13/HexRift/commit/94f15c1056d6586eefc2b45d70c5100d9205a6a7))
* **xray:** replace SNIFFING with dynamic configuration based on region type ([4bb4f95](https://github.com/wlix13/HexRift/commit/4bb4f952fb48c7be83be76760bbf1d330d05c4d3))


### Bug Fixes

* **fixture:** update flow type in fxitures ([435c9c1](https://github.com/wlix13/HexRift/commit/435c9c101d387c3dec4480d3f9eda59e0bb4e2ef))
* **haproxy:** remove health check for unix sockets ([6bd7684](https://github.com/wlix13/HexRift/commit/6bd7684904b419947589e376d42010f3a5d7b236))
* **routing:** make all routing rules optional ([4a86165](https://github.com/wlix13/HexRift/commit/4a86165ea3193a9806e3fe6960539b787e5c5164))
* **workflow:** allow edits to schema.json by bot users ([12573d9](https://github.com/wlix13/HexRift/commit/12573d9dac61d9489ba6dda0693b5514efc15474))
* **workflow:** fix schema update logic ([f765223](https://github.com/wlix13/HexRift/commit/f765223a3b39af3022770896e44fd8aa88664f89))
* **xray_defaults:** set trusted_headers always ([69dec25](https://github.com/wlix13/HexRift/commit/69dec25566c8ecfa2548f3d00c3534caec0c8f0b))
* **xray:** update ping configuration and settings for better connectivity ([b7e08d5](https://github.com/wlix13/HexRift/commit/b7e08d59f1de2f3f0e8f6de02b45e38a04012d0c))


### Reverts

* "Merge branch wlix13/feature/i18n" ([f797392](https://github.com/wlix13/HexRift/commit/f797392ca5f2b79e886e239cdaea5a05270a784b))
* "Merge branch wlix13/feature/ru-docs" ([d2c76d2](https://github.com/wlix13/HexRift/commit/d2c76d24ce9bc0d1a146cc1d7b9415a48e578ade))


### Documentation

* **readme:** add Codecov coverage badge ([cee2e46](https://github.com/wlix13/HexRift/commit/cee2e4617271cf05d09c552997104de48653ef3a))
* **readme:** add installation, usage, and other details for HexRift ([439cd9a](https://github.com/wlix13/HexRift/commit/439cd9a3260c20ce07c857c9efc9f92758c00f07))
* **README:** add paragraph about  HAProxy-less and all-in-one node topologies ([c4534b3](https://github.com/wlix13/HexRift/commit/c4534b36c0d627ee1998532684612caf5c34f085))


### Code Refactoring

* remove mtproto support ([d91ab0b](https://github.com/wlix13/HexRift/commit/d91ab0b6249d3884b0623ef32bb9e5d266dc7118))
* **render:** consolidate render pipeline and drop context module ([baf32ed](https://github.com/wlix13/HexRift/commit/baf32ed41d533658af0497faee1e1d6a6251259d))

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
