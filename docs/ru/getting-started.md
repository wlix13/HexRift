# Начало работы

## Требования

- Python **3.13+**
- Менеджер пакетов [uv](https://docs.astral.sh/uv/)

## Установка

```bash
uv tool install hexrift
```

Все зависимости устанавливаются в изолированное виртуальное окружение.

---

## Минимальный YAML-файл топологии

Создайте `conglomerate.yaml` рядом с репозиторием. Ниже — минимально рабочая топология: один exit-регион, один hub-регион, одна группа, один пользователь:

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
      auth: mlkem768
  hub:
    ipv6: false
    proxy_inbound: false
    keys:
      enabled: true
      mode: rprx_vision
      session_time: 12h
      auth: mlkem768
    exit_connections:
      method: mlkem768x25519plus
      fingerprint: edge
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

---

## Рабочий процесс

Стандартная первичная настройка выполняется в четыре шага:

### 1 — Валидация

```bash
hexrift --yaml conglomerate.yaml validate
```

```bash
Valid — conglomerate.yaml
  1 groups, 1 users, 1 exit regions, 1 hub regions, 2 nodes
```

Исправьте все ошибки валидации Pydantic перед продолжением.

### 2 — Просмотр деривированных идентификаторов

```bash
hexrift --yaml conglomerate.yaml derive all
```

Отображает UUID, shortId и email, которые будут встроены в конфиги. Все значения полностью детерминированы — повторный запуск всегда даёт одинаковый результат для одинаковых namespace и имён.

### 3 — Генерация ключей

```bash
hexrift --yaml conglomerate.yaml gen-keys --all --keys-dir keys
```

Создаёт файлы `keys/nlA00.yaml` и `keys/euH00.yaml` с парами ключей x25519 Reality и ключами шифрования ML-KEM 768.

!!! warning
    Hub-узлы в одном регионе автоматически используют общую пару ключей. Повторный запуск без `--force` пропускает существующие файлы.

### 4 — Сборка конфигов

```bash
hexrift --yaml conglomerate.yaml build --all --xray --haproxy --out-dir configs
```

Записывает `configs/nlA00/config.json`, `configs/euH00/config.json` и соответствующие файлы `haproxy.cfg`.

---

## Ссылки для подключения

Генерация VLESS-ссылки для пользователя:

```bash
# Прямая Reality-ссылка
hexrift --yaml conglomerate.yaml share alice

# CDN-ссылка
hexrift --yaml conglomerate.yaml share alice --cdn

# Чистая ссылка для передачи (например, в буфер обмена)
hexrift --yaml conglomerate.yaml share alice --bare | clip
```

---

## Настройка окружения разработчика

```bash
uv sync
uv run prek install              # установка pre-commit хуков через prek
uv run ruff check .              # линтинг
uv run ruff format .             # форматирование
uv run ty check                  # проверка типов
uv run prek run --all-files      # запуск всех хуков
```

Для локальной сборки документации:

```bash
uv sync --group docs
uv run mkdocs serve              # http://127.0.0.1:8000
uv run mkdocs build --strict     # статический сайт → site/
```
