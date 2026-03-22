# 🤖 Telegram AI Bot на базе Venice.ai

Полноценный Telegram-бот с uncensored нейросетями через Venice.ai API, с FastAPI-админ-панелью, PostgreSQL и Redis.

---

## 📋 Содержание

1. [Требования](#1-требования)
2. [Клонирование репозитория](#2-клонирование-репозитория)
3. [Создание виртуального окружения](#3-создание-виртуального-окружения)
4. [Установка зависимостей](#4-установка-зависимостей)
5. [Настройка переменных окружения](#5-настройка-переменных-окружения)
6. [Запуск Docker (PostgreSQL + Redis)](#6-запуск-docker-postgresql--redis)
7. [Запуск миграций](#7-запуск-миграций)
8. [Запуск бота](#8-запуск-бота)
9. [Запуск админ-панели](#9-запуск-админ-панели)
10. [Проверка работы](#10-проверка-работы)
11. [Команды бота](#11-команды-бота)
12. [Переменные окружения](#12-переменные-окружения)
13. [Тарифные планы и модели](#13-тарифные-планы-и-модели)
14. [FAQ](#14-faq)

---

## 1. Требования

| Компонент | Версия |
|-----------|--------|
| Python    | 3.11+  |
| Docker Desktop | последняя |
| Git | любая |

- **Telegram Bot Token** — получить у [@BotFather](https://t.me/BotFather)
- **Venice.ai API Key** — зарегистрироваться на [venice.ai](https://venice.ai) и получить ключ в настройках аккаунта

---

## 2. Клонирование репозитория

```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

---

## 3. Создание виртуального окружения

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3.11 -m venv venv
source venv/bin/activate
```

---

## 4. Установка зависимостей

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Настройка переменных окружения

```bash
cp .env.example .env
```

Откройте `.env` и заполните все переменные (подробнее в разделе [12](#12-переменные-окружения)):

```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
ADMIN_IDS=123456789
VENICE_API_KEY=vn-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DATABASE_URL=postgresql+asyncpg://aibot_user:password@localhost/aibot_db
REDIS_URL=redis://localhost:6379
ADMIN_SECRET_KEY=my_super_secret_password
ADMIN_PORT=8080
```

---

## 6. Запуск Docker (PostgreSQL + Redis)

```bash
docker compose up -d
```

Проверьте, что контейнеры запущены:

```bash
docker compose ps
```

Ожидаемый результат:
```
NAME               STATUS    PORTS
aibot_postgres     running   0.0.0.0:5432->5432/tcp
aibot_redis        running   0.0.0.0:6379->6379/tcp
```

---

## 7. Запуск миграций

```bash
alembic upgrade head
```

Если база данных создана впервые, Alembic создаст все таблицы.

> **Примечание:** бот также автоматически создаёт таблицы при первом запуске через `Base.metadata.create_all`, поэтому миграции нужны в первую очередь для последующих изменений схемы.

---

## 8. Запуск бота

```bash
python bot/main.py
```

В терминале вы увидите:
```
HH:MM:SS | INFO | Database tables ensured
HH:MM:SS | INFO | Bot started: @YourBotName
HH:MM:SS | INFO | Starting polling...
```

---

## 9. Запуск админ-панели

В **отдельном терминале** (с активированным venv):

```bash
python admin/app.py
```

Панель будет доступна по адресу: **http://localhost:8080/admin/login**

Введите пароль из `ADMIN_SECRET_KEY`.

---

## 10. Проверка работы

1. Откройте Telegram и найдите вашего бота
2. Отправьте `/start` — должно появиться приветствие с кнопками
3. Напишите любое сообщение — бот должен ответить через Venice.ai
4. Откройте `http://localhost:8080/admin/dashboard` и проверьте статистику

---

## 11. Команды бота

### Пользовательские команды

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню и регистрация |
| `/help` | Список всех команд |
| `/account` | Информация об аккаунте (план, токены, модель) |
| `/clear` | Очистить историю диалога |
| `/setprompt` | Установить системный промпт для AI |

### Команды администратора

| Команда | Описание |
|---------|----------|
| `/admin` | Панель администратора (статистика) |
| `/stats` | Подробная статистика использования |
| `/ban {user_id}` | Забанить пользователя |
| `/unban {user_id}` | Разбанить пользователя |
| `/addtokens {user_id} {amount}` | Добавить токены пользователю |
| `/setplan {user_id} {plan}` | Изменить тарифный план |
| `/broadcast` | Рассылка сообщений всем пользователям |

---

## 12. Переменные окружения

| Переменная | Обязательная | Описание |
|------------|:-----------:|----------|
| `BOT_TOKEN` | ✅ | Токен Telegram-бота от @BotFather |
| `ADMIN_IDS` | ✅ | Telegram ID администраторов через запятую |
| `VENICE_API_KEY` | ✅ | API ключ Venice.ai |
| `DATABASE_URL` | ✅ | URL PostgreSQL (asyncpg формат) |
| `REDIS_URL` | ✅ | URL Redis |
| `ADMIN_SECRET_KEY` | ✅ | Пароль для входа в веб-панель |
| `ADMIN_PORT` | ❌ | Порт веб-панели (по умолчанию: 8080) |

---

## 13. Тарифные планы и модели

### Тарифные планы

| Тариф | Токенов | История | Доступные модели |
|-------|--------:|:-------:|:----------------:|
| **Free** | 10 000 | 10 сообщений | Venice Uncensored, Llama 3.2 3B |
| **Basic** | 500 000 | 30 сообщений | Все модели |
| **Premium** | 3 000 000 | 50 сообщений | Все модели |
| **Unlimited** | ∞ | 100 сообщений | Все модели |

### Доступные модели Venice.ai

| ID модели | Название | Минимальный план |
|-----------|----------|:----------------:|
| `venice-uncensored` | Venice Uncensored | Free |
| `llama-3.2-3b` | Llama 3.2 3B | Free |
| `llama-3.3-70b` | Llama 3.3 70B | Basic |
| `deepseek-v3` | DeepSeek V3 | Basic |
| `hermes-3-llama-3.1-405b` | Hermes 3 Llama 3.1 405B | Basic |
| `qwen3-235b-a22b-instruct` | Qwen3 235B | Basic |

---

## 14. FAQ

### ❓ Ошибка "Cannot connect to database"

1. Убедитесь, что Docker запущен: `docker compose ps`
2. Проверьте `DATABASE_URL` в `.env`
3. Попробуйте подключиться напрямую: `docker exec -it aibot_postgres psql -U aibot_user -d aibot_db`

### ❓ Ошибка "Invalid API key Venice.ai"

- Проверьте `VENICE_API_KEY` в `.env`
- Убедитесь, что ключ активен в личном кабинете Venice.ai
- Ключ должен начинаться с `vn-`

### ❓ Бот не отвечает на сообщения

- Проверьте, что `BOT_TOKEN` правильный
- Убедитесь, что бот запущен (`python bot/main.py`)
- Проверьте логи в папке `logs/bot.log`

### ❓ Redis недоступен

- Бот продолжит работу без rate limiting если Redis недоступен
- Запустите Redis через Docker: `docker compose up -d redis`

### ❓ Ошибка при alembic upgrade head

```bash
# Проверьте, что DATABASE_URL в .env правильный
# Убедитесь, что PostgreSQL запущен
docker compose up -d postgres
alembic upgrade head
```

### ❓ Как изменить лимиты запросов (rate limiting)?

Откройте `bot/middlewares/auth.py` и измените константы:
```python
RATE_LIMIT = 10  # запросов в минуту
RATE_WINDOW = 60  # окно в секундах
```

### ❓ Как добавить нового администратора?

Добавьте Telegram ID через запятую в `ADMIN_IDS` в `.env`:
```env
ADMIN_IDS=123456789,987654321
```
Перезапустите бота.

### ❓ Где хранятся логи?

- **Бот:** `logs/bot.log` (ротация каждые 10 МБ, хранение 7 дней)
- **Консоль:** уровень INFO

### ❓ Как запустить в production?

Используйте process manager, например `systemd` или `supervisor`:

```bash
# Пример с nohup
nohup python bot/main.py > /dev/null 2>&1 &
nohup python admin/app.py > /dev/null 2>&1 &
```

Или настройте Docker Compose для всех сервисов.

---

## 📁 Структура проекта

```
├── bot/
│   ├── main.py                  # Точка входа бота
│   ├── handlers/
│   │   ├── start.py             # /start, /help, /account, /clear
│   │   ├── chat.py              # Основной чат с AI
│   │   ├── settings.py          # Настройки пользователя
│   │   └── admin.py             # Команды администратора
│   ├── middlewares/
│   │   └── auth.py              # Проверка бана, rate limiting
│   └── keyboards/
│       ├── main_kb.py           # Главное меню
│       ├── models_kb.py         # Выбор модели
│       └── settings_kb.py       # Меню настроек
├── api/
│   └── venice.py                # Интеграция Venice.ai API
├── admin/
│   ├── app.py                   # FastAPI админ-панель
│   ├── templates/               # HTML шаблоны (тёмная тема)
│   └── static/style.css         # CSS стили
├── database/
│   ├── db.py                    # SQLAlchemy engine
│   ├── models.py                # ORM модели
│   └── crud.py                  # CRUD операции
├── alembic/
│   ├── env.py                   # Конфигурация Alembic
│   └── versions/                # Миграции
├── config.py                    # Конфигурация, планы, модели
├── requirements.txt
├── .env.example
├── alembic.ini
├── docker-compose.yml
└── README.md
```

---

*Сделано с ❤️ на Python + aiogram 3 + Venice.ai*