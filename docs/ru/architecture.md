# Архитектура

## Паттерн Component / Controller / Application

HexRift построен на лёгком фреймворке **Component/Controller/Application**, реализованном в `hexrift/core/`.

```bash
BaseApplication  (синглтон-реестр + инжектор зависимостей)
└── регистрирует компоненты по порядку:
    ├── SchemaComponent    → SchemaController    (app.schema)
    ├── DeriveComponent    → DeriveController    (app.derive)
    ├── KeysComponent      → KeysController      (app.keys)
    └── RenderComponent    → RenderController    (app.render)
```

### `BaseApplication` (`hexrift/core/application.py`)

- Синглтон — во время выполнения существует только один экземпляр.
- Обходит `default_components` при `__init__`, вызывая `self.register(component_cls)`.
- `register(...)` создаёт компонент, сохраняет его в `self.components`,
  публикует атрибуты (когда включено), потом запускает `component.on_register()`.
- Открывает каждый контроллер как атрибут: `app.schema`, `app.derive`, `app.keys`, `app.render`.
- Хранит общий `rich.Console` для всего вывода.

### `BaseComponent` (`hexrift/core/component.py`)

- Слой между Click CLI и бизнес-логикой.
- Определяет `name`, `controller_class` и опционально `expose_controller`.
- `expose_cli(base: click.Group)` регистрирует Click-команды в основной группе при импорте.

### `BaseController` (`hexrift/core/controller.py`)

- Содержит бизнес-логику; получает `app` для доступа к другим компонентам.
- Пример: `RenderController` обращается к `self.app.schema.config` и `self.app.keys.load_node_keys(...)`.

### Поток запроса

```bash
Вызвана CLI-команда
  → Click перенаправляет в обработчик expose_cli компонента
  → обработчик получает app (передаётся через ctx.obj)
  → app.schema загружает YAML (кешируется после первой загрузки)
  → обработчик вызывает метод контроллера
  → контроллер обращается к другим компонентам через self.app.*
```

---

## Детерминированная деривация

Все идентификаторы (UUID, shortId, email) деривируются из топологии — без случайной генерации. Повторный запуск всегда даёт одинаковый результат для одинаковых `namespace` и имён.

Источник: `hexrift/components/derive/identity.py` — класс `Namespace`.

### Деривация UUID

| Идентификатор | Формула |
|---------------|---------|
| Namespace UUID | `UUID5(UUID(int=0), namespace)` |
| User UUID | `UUID5(namespace_uuid, username)` |
| Server UUID | `UUID5(user_uuid, "{username}-server")` |
| Guest UUID | `UUID5(user_uuid, guest_label)` |
| Portal UUID | `UUID5(user_uuid, "{label}-portal")` |
| Hub-Exit UUID | `UUID5(namespace_uuid, "{hub_id}-{exit_id}")` |
| Warp UUID | Hub-Exit UUID с заменой 3-го сегмента на `ffff` |

UUID пользователя можно переопределить в YAML через `users[].uuid`.

### Деривация ShortId

ShortId — первые 16 символов SHA-256 хеша в шестнадцатеричном виде:

| Идентификатор | Входная строка |
|---------------|---------------|
| Group shortId | `"{group_id}.{namespace}"` (или переопределение через `groups[].short_id`) |
| Hub shortId | `"{node_id}.hub.{namespace}"` |
| Exit shortId | `"{node_id}.exit.{namespace}"` |
| User shortId | `"{username}.user.{namespace}"` |

### Деривация Email

| Email | Формат |
|-------|--------|
| User | `{username}@{namespace}` |
| Server | `{username}-server@{username}` |
| Portal | `{label}-portal@{username}` |
| Guest | `{label}@{username}` |
| Hub-Exit | `{hub_id}-{exit_id}@{namespace}` |
| Warp | `warp-{hub_id}-{exit_id}@{namespace}` |

---

## Хранение ключей

Ключевые пары генерируются командой `gen-keys` и сохраняются в `keys/<nodeId>.yaml`.

Источник: `hexrift/components/keys/store.py`, `reality.py`, `decryption.py`.

### Формат файла

```yaml
reality_private_key: "<base64url-без-отступов>"   # приватный ключ x25519 (32 байта)
reality_public_key:  "<base64url-без-отступов>"   # публичный ключ x25519 (32 байта)
decryption: "mlkem768x25519plus.rprx_vision.12h.{private_key_b64}"   # server inbound
encryption: "mlkem768x25519plus.rprx_vision.0rtt.{public_key_b64}"   # client outbound
```

### Формат строки ключа

| Строка | Назначение | Формат |
|--------|-----------|--------|
| `decryption` | Xray server inbound | `{method}.{mode}.{session_time}[.{padding}].{private_key_b64}` |
| `encryption` | Клиентская ссылка | `{method}.{mode}.0rtt.{public_key_b64}` |

Права доступа к файлу устанавливаются в `0o600` (только чтение/запись владельцем).

!!! info "Общие ключи hub-узлов"
    Hub-узлы одного региона используют общую пару ключей. `gen-keys` определяет это автоматически и создаёт только один файл.

---

## Добавление нового компонента

Следуйте паттерну существующих четырёх компонентов:

### 1. Создайте структуру модуля

```bash
hexrift/components/myfeature/
├── __init__.py
├── component.py   # регистрация Click CLI
└── controller.py  # бизнес-логика
```

### 2. Определите контроллер

```python
# hexrift/components/myfeature/controller.py
from hexrift.core.controller import BaseController

class MyController(BaseController["HexRiftApp"]):
    def do_something(self) -> None:
        cfg = self.app.schema.config  # доступ к другим компонентам
        ...
```

### 3. Определите компонент

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
            """Краткое описание команды."""
            app.myfeature.do_something()
```

### 4. Зарегистрируйте в приложении

```python
# hexrift/app.py
from hexrift.components.myfeature.component import MyComponent

class HexRiftApp(BaseApplication["HexRiftApp"]):
    default_components = [..., MyComponent]
    myfeature: MyController
```

---

## Команды разработчика

```bash
uv run ruff check . --fix        # линтинг + автоисправление
uv run ruff format .             # форматирование (длина строки 120)
uv run ty check                  # проверка типов
uv run prek run --all-files      # запуск всех pre-commit хуков
```

### Договорённости по коммитам

```bash
<тип>[область]: <описание>

Примеры:
  feat(render): add CDN support
  fix(schema): validate unique vless_route values
  chore(release): bump version to 0.6.0
```
