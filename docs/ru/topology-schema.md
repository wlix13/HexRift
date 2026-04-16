# Схема топологии

Топология описывается в одном YAML-файле. Схема валидируется через Pydantic; лишние ключи запрещены везде.

---

## Структура верхнего уровня

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

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `namespace` | `str` | да | Уникальный идентификатор сети — используется как начальное значение для деривации UUID/shortId |
| `aphelion_domain` | `str` | да | Базовый домен для имён хостов exit-узлов |
| `bridge_domain` | `str` | да | Базовый домен для имён хостов hub-узлов |
| `cdn` | `CdnConfig` | нет | CDN-домены для xhttp-транспорта |

### `global.cdn`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `exit_domain` | `str` | да | CDN-домен для exit-узлов |
| `hub_domain` | `str` | да | CDN-домен для hub-узлов |

---

## `defaults`

Конфигурация по умолчанию, применяемая ко всем exit- или hub-узлам. Поля уровня узла переопределяют эти значения.

### `defaults.exit`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `ipv6` | `bool` | да | Включить IPv6 на exit-узлах по умолчанию |
| `keys` | `KeysConfig` | да | Конфигурация ключей шифрования |

### `defaults.hub`

| Поле | Тип | Обязательно | По умолч. | Описание |
|------|-----|-------------|-----------|----------|
| `ipv6` | `bool` | да | — | Включить IPv6 на hub-узлах по умолчанию |
| `proxy_inbound` | `bool` | нет | `false` | Включить смешанный proxy-inbound |
| `keys` | `KeysConfig` | да | — | Конфигурация ключей шифрования |
| `exit_connections` | `ExitConnectionsConfig` | да | — | Как hub-узлы подключаются к exit-узлам |
| `reality` | `RealityConfig` | да | — | Reality-конфигурация по умолчанию для hub-узлов |
| `mtproto` | `MtprotoConfig` | нет | — | Конфигурация MTProto-прокси |
| `observatory` | `ObservatoryConfig` | нет | см. ниже | Настройки health-check / балансировщика |

### `KeysConfig`

| Поле | Тип | Обязательно | По умолч. | Описание |
|------|-----|-------------|-----------|----------|
| `enabled` | `bool` | нет | `true` | Активно ли шифрование |
| `mode` | `str` | да | — | Строка режима ключа (например, `rprx_vision`) |
| `session_time` | `str` | да | — | Продолжительность сессии (например, `12h`) |
| `auth` | `mlkem768 \| x25519` | нет | `mlkem768` | Алгоритм шифрования |
| `padding` | `str` | нет | — | Опциональное значение padding |

### `ExitConnectionsConfig`

| Поле | Тип | Обязательно | По умолч. | Описание |
|------|-----|-------------|-----------|----------|
| `method` | `str` | да | — | Метод рукопожатия (например, `mlkem768x25519plus`) |
| `fingerprint` | `str` | нет | `edge` | TLS-отпечаток клиента |

### `ObservatoryConfig`

| Поле | Тип | По умолч. | Описание |
|------|-----|-----------|----------|
| `sampling` | `int` (1–24) | `8` | Количество выборок пробы |
| `interval` | `str` | `15s` | Интервал пробы (формат: `\d+(ms\|s\|m\|h)`) |
| `timeout` | `str` | `5s` | Таймаут пробы |
| `concurrency` | `bool` | `true` | Запускать пробы параллельно |

### `MtprotoConfig`

| Поле | Тип | Обязательно | По умолч. | Описание |
|------|-----|-------------|-----------|----------|
| `domain` | `str` | да | — | Домен для MTProto-inbound |
| `port` | `int` (1–65535) | нет | `1234` | Порт прослушивания MTProto |

---

## `groups`

Список групп пользователей. Группы предоставляют общий `shortId` для фильтрации Reality-inbound.

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `id` | `str` | да | Уникальный идентификатор группы |
| `short_id` | `str` | нет | Переопределение автоматически деривированного shortId |

Если `short_id` не указан, он деривируется как `SHA256("{id}.{namespace}")[:16]`.

**Пример:**

```yaml
groups:
  - id: staff
  - id: vip
    short_id: deadbeef01234567
```

---

## `users`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `username` | `str` | да | Уникальное имя пользователя — используется как семя деривации |
| `group` | `str` | да | Должно ссылаться на существующий `groups[].id` |
| `access` | `list[AccessType]` | да | Типы доступа: `xhttp`, `server`, `cdn`, `proxy` |
| `uuid` | `UUID` | нет | Переопределение автоматически деривированного UUID |
| `portals` | `list[Portal]` | нет | Определения порталов (site-to-site туннели) |
| `guests` | `list[str]` | нет | Метки гостевых идентификаторов |

### Типы доступа

| Значение | Описание |
|----------|----------|
| `xhttp` | Прямой доступ через Reality xhttp |
| `server` | Доступ сервер-сервер |
| `cdn` | Доступ через CDN-фронтированный xhttp |
| `proxy` | Доступ через mixed proxy inbound |

### `Portal`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `label` | `str` | да | Метка портала (используется при деривации UUID) |
| `routes` | `PortalRoutes` | да | Селекторы трафика для данного портала |

### `PortalRoutes`

| Поле | Тип | Описание |
|------|-----|----------|
| `domains` | `list[str]` | Домены-фильтры |
| `ips` | `list[str]` | IP/CIDR-фильтры |

Требуется хотя бы один фильтр.

**Пример:**

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

| Поле | Тип | Обязательно | По умолч. | Описание |
|------|-----|-------------|-----------|----------|
| `hub_default` | `str` | да | — | Регион по умолчанию для несопоставленного hub-трафика; должен ссылаться на существующий `regions[].id` |
| `exit_warp_global` | `list[str]` | нет | `[]` | Список доменов, направляемых на warp-интерфейс на всех exit-узлах |
| `exit_routes_global` | `list[ExitRoute]` | нет | `[]` | Глобальные правила exit-маршрутизации для всех exit-узлов |
| `hub_routes` | `list[HubRoute]` | нет | `[]` | Правила hub-маршрутизации (упорядочены; побеждает первое совпадение) |

### `ExitRoute`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `destination` | `direct \| blocked \| warp` | да | Направление маршрутизации |
| `domains` | `list[str]` | усл. | Домены-фильтры (требуется хотя бы один из `domains`/`ips`) |
| `ips` | `list[str]` | усл. | IP/CIDR-фильтры |

### `HubRoute`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `destination` | `str` | да | ID региона, ID узла, `direct`, `blocked` или `warp` |
| `domains` | `list[str]` | усл. | Домены-фильтры |
| `ips` | `list[str]` | усл. | IP/CIDR-фильтры |
| `users` | `list[str]` | усл. | Применять только для этих пользователей |
| `proxy_users` | `list[str]` | усл. | Применять только для этих proxy-пользователей |

Требуется хотя бы один фильтр (`domains`, `ips`, `users` или `proxy_users`).

---

## `regions`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `id` | `str` | да | Уникальный идентификатор региона |
| `type` | `exit \| hub` | да | Тип региона |
| `vless_route` | `int` | только exit | Числовой тег маршрута; уникален среди всех регионов |
| `cdn_xhttp_path` | `str` | нет | Переопределение CDN xhttp-пути для данного региона |
| `lb_strategy` | `str` | нет | Стратегия балансировщика (например, `leastLoad`) |
| `lb_fallback` | `str` | нет | Запасной узел (должен находиться в этом регионе) |
| `lb_least_load` | `LeastLoadSettings` | нет | Тонкая настройка leastLoad |
| `routing` | `RegionRouting` | нет | Переопределения маршрутизации для региона (только exit) |
| `warp` | `WarpConfig` | нет | Конфигурация warp-туннеля |
| `nodes` | `list[Node]` | да | Минимум один узел |

### `LeastLoadSettings`

| Поле | Тип | По умолч. | Описание |
|------|-----|-----------|----------|
| `baselines` | `list[str]` | `["30ms","100ms","250ms"]` | Латентные корзины |
| `expected` | `int` (≥1) | `1` | Ожидаемое количество активных узлов |
| `max_rtt` | `str` | `750ms` | Максимальный допустимый RTT |
| `tolerance` | `float` (0–1) | `0.5` | Коэффициент допуска |

### `RegionRouting` (только для exit-регионов)

| Поле | Тип | Описание |
|------|-----|----------|
| `warp_extra` | `list[str]` | Дополнительные домены для warp в данном регионе |
| `routes` | `list[ExitRoute]` | Per-region exit-маршруты (destination — только специальные значения) |

### `WarpConfig`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `vless_route` | `int` | да | Тег warp vless-маршрута; уникален среди всех регионов |

---

## `Node`

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `id` | `str` | да | Уникальный идентификатор узла (глобально уникален) |
| `hostname` | `str` | да | FQDN узла |
| `ipv6` | `bool` | нет | Переопределение настройки IPv6 по умолчанию |
| `lb_role` | `backup` | нет | Пометить узел как запасной для балансировщика |
| `reality` | `RealityConfig` | exit-узлы | Reality TLS-конфигурация (обязательна для всех exit-узлов) |
| `keys` | `NodeKeysOverride` | нет | Переопределение настроек ключей |
| `exit_connections` | `NodeExitConnectionsOverride` | нет | Переопределение настроек подключения к exit (hub-узлы) |
| `proxy_inbound` | `bool` | нет | Переопределение proxy inbound (hub-узлы) |
| `mtproto` | `NodeMtprotoOverride` | нет | Переопределение настроек MTProto (hub-узлы) |

### `RealityConfig`

| Поле | Тип | Обязательно | По умолч. | Описание |
|------|-----|-------------|-----------|----------|
| `dest` | `str` | да | — | Запасной destination (например, `www.cloudflare.com:443`) |
| `server_names` | `list[str]` | нет | — | Список SNI; автоматически деривируется из `dest`, если не указан |
| `xhttp_host` | `str` | нет | — | Переопределение заголовка Host для xhttp |
| `xhttp_path` | `str` | да | — | Путь xhttp-запроса (например, `/stream`) |
| `fallback_limits` | `RealityFallbackLimits` | нет | см. ниже | Ограничения трафика при fallback |

### `RealityFallbackLimits`

| Поле | Тип | По умолч. | Описание |
|------|-----|-----------|----------|
| `after_bytes` | `int` | `16384` | Байты до срабатывания fallback |
| `bytes_per_sec` | `int` | `50000` | Устойчивый лимит скорости |
| `burst_bytes_per_sec` | `int` | `100000` | Пиковый лимит скорости |

---

## Полный минимальный пример

```yaml
global:
  namespace: mynet
  aphelion_domain: exit.example.com
  bridge_domain: hub.example.com

defaults:
  exit:
    ipv6: false
    keys:
      enabled: true
      mode: rprx_vision
      session_time: 12h
  hub:
    ipv6: false
    keys:
      enabled: true
      mode: rprx_vision
      session_time: 12h
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
