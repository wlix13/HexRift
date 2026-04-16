# HexRift

![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)
![Build](https://img.shields.io/github/actions/workflow/status/wlix13/hexrift/ci-code-quality.yaml?label=build&logo=github)
![License](https://img.shields.io/badge/license-MIT-green)
![uv](https://img.shields.io/badge/package%20manager-uv-blueviolet?logo=astral)
![Ruff](https://img.shields.io/badge/linter-ruff-orange?logo=ruff)

**HexRift** — генератор конфигурации для распределённой прокси-сети **Conglomerate**. Принимает YAML-описание топологии и создаёт JSON-конфиги [Xray](https://github.com/XTLS/Xray-core) и конфиги HAProxy для каждого узла.

---

## Быстрый старт

```bash
# 1. Установка
uv tool install hexrift

# 2. Проверка топологии
hexrift --yaml conglomerate.yaml validate

# 3. Генерация ссылок
hexrift --yaml conglomerate.yaml share alice --cdn
```

---

<div class="grid cards" markdown>

- :material-rocket-launch: **[Начало работы](getting-started.md)**

    Установите HexRift, создайте первый YAML-файл топологии и запустите полный рабочий процесс за несколько минут.

- :material-console: **[Справочник CLI](cli-reference.md)**

    Полное описание каждой команды и каждого флага.

- :material-file-code: **[Схема топологии](topology-schema.md)**

    Подробный YAML-справочник — каждое поле, тип, значение по умолчанию и правила валидации.

- :material-cog: **[Архитектура](architecture.md)**

    Устройство компонентов/контроллеров, формулы детерминированной деривации, формат хранения ключей и руководство разработчика.

</div>
