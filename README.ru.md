# InstaPost - Автоматизация Instagram

<img width="2912" height="1632" alt="InstaPost Screenshot" src="instapost.png" />

Автоматическая публикация в Instagram через удаленную VM с планированием на основе cron.

## Архитектура

```
Локально (Mac/PC)                 Удаленно (AWS EC2)
┌─────────────────┐              ┌─────────────────────────────┐
│ instapost CLI   │◄── SSH ─────►│ Cron Jobs                   │
│                 │              │ ├─ watcher (каждые 5 мин)   │
│ Команды:        │              │ └─ scheduler (каждую 1 мин) │
│ - status        │              │                             │
│ - upload        │              │ S3 Bucket ◄─► /mnt/s3       │
│ - queue         │              │                             │
│ - logs          │              │ Angie ──► Cloudflare Tunnel │
│ - account       │              │ instapost.celestialtech.io  │
└─────────────────┘              └─────────────────────────────┘
```

## Возможности

- **Удаленная работа**: CLI работает локально, вся обработка на VM
- **Cron планирование**: Надежные cron задачи с flock блокировкой
- **Собственный хостинг**: Angie + Cloudflare tunnel (без Dropbox)
- **S3 хранилище**: Изображения хранятся в S3 Express bucket
- **AI подписи**: Опциональная генерация подписей через Claude CLI
- **Управление очередью**: Просмотр, отмена, перепланирование постов

## Быстрый старт

```bash
# Установка
uv sync

# Настройка (один раз)
cp .env.vm.example .env.vm
# Отредактируйте .env.vm с вашими API credentials
instapost init              # Загрузить credentials на VM
instapost deploy            # Развернуть код

# Повседневное использование
instapost upload photo.jpg  # Загрузить изображение
instapost status            # Проверить статус
instapost queue             # Просмотр расписания
instapost logs -f           # Следить за логами
```

## CLI команды

### Статус и мониторинг
| Команда | Описание |
|---------|----------|
| `instapost status` | Подключение к VM, cron задачи, статистика очереди |
| `instapost health` | Полная проверка здоровья |
| `instapost logs [-j watcher\|scheduler] [-f]` | Просмотр/следить за логами |

### Управление очередью
| Команда | Описание |
|---------|----------|
| `instapost queue` | Просмотр запланированных постов |
| `instapost history` | Просмотр истории публикаций |
| `instapost cancel <file>` | Отменить запланированный пост |
| `instapost reschedule <file> <time>` | Изменить время поста |
| `instapost rebalance [--apply]` | Заполнить пропуски в расписании |

### Изображения
| Команда | Описание |
|---------|----------|
| `instapost images` | Список ожидающих изображений на VM |
| `instapost upload <path> [-c caption]` | Загрузить изображение на VM |

### Ручное выполнение
| Команда | Описание |
|---------|----------|
| `instapost run watcher` | Запустить watcher вручную |
| `instapost run scheduler` | Запустить scheduler вручную |

### Instagram API
| Команда | Описание |
|---------|----------|
| `instapost account` | Информация об аккаунте |
| `instapost media [-n N]` | Последние посты |
| `instapost token-info` | Статус токена |

### Деплой
| Команда | Описание |
|---------|----------|
| `instapost init [file]` | Загрузить .env на VM |
| `instapost deploy` | Развернуть код на VM |
| `instapost ssh` | Открыть SSH сессию |

## Конфигурация

### Локально (.env)
```bash
VM_HOST=instapost-deploy
VM_INSTAPOST_DIR=/home/ironsirens/instapost
VM_IMAGES_DIR=/mnt/s3/images
VM_PROCESSED_DIR=/mnt/s3/processed
```

### Удаленно (.env.vm)
```bash
IMAGE_BASE_URL=https://instapost.celestialtech.io
FACEBOOK_APP_ID=...
FACEBOOK_APP_SECRET=...
FACEBOOK_ACCESS_TOKEN=...
INSTAGRAM_BUSINESS_ACCOUNT_ID=...
TIMEZONE=America/New_York
WEEKLY_SCHEDULE="0:07:00,2:11:00,4:17:00,5:09:00,6:18:00"
CAPTION_PROMPT="..."
```

## Cron задачи

Устанавливаются через `crontab crontab.example` на VM:

```cron
# Watcher: сканирование новых изображений каждые 5 минут
*/5 * * * * flock -n /tmp/instapost-watcher.lock -c "..."

# Scheduler: публикация готовых постов каждую минуту
* * * * * flock -n /tmp/instapost-scheduler.lock -c "..."
```

- `flock -n` предотвращает параллельный запуск
- Логи пишутся в `~/instapost/logs/`
- Ротация логов настроена через `/etc/logrotate.d/instapost`

## Как это работает

1. **Загрузка**: `instapost upload photo.jpg` копирует изображение в `/mnt/s3/images/`
2. **Watcher**: Cron задача сканирует новые изображения, валидирует, планирует на следующий слот
3. **Scheduler**: Cron задача проверяет готовые посты, публикует через Instagram API
4. **Перемещение**: После публикации изображение перемещается в `/mnt/s3/processed/{date}/`

## Подписи

Три метода (в порядке приоритета):

1. **IPTC метаданные**: Подпись хранится в метаданных изображения
2. **.txt файл**: `photo.txt` рядом с `photo.jpg`
3. **AI генерация**: Claude CLI генерирует подпись (если установлен)

## Настройка VM

Для настройки EC2 инстанса:
- Настройка EC2 инстанса
- Монтирование S3 bucket
- Веб-сервер Angie
- Cloudflare tunnel
- Установка cron задач

## Требования

- Python 3.13+
- uv package manager
- SSH доступ к VM
- Facebook App с Instagram разрешениями

## Формат недельного расписания

Формат: `WEEKLY_SCHEDULE="0:07:00,2:11:00,4:17:00,5:09:00,6:18:00"`

- Дни: 0=Понедельник, 1=Вторник, ..., 6=Воскресенье
- Время в 24-часовом формате (ЧЧ:ММ:СС)
- Пример расписания:
  - Понедельник (0): 07:00
  - Среда (2): 11:00
  - Пятница (4): 17:00
  - Суббота (5): 09:00
  - Воскресенье (6): 18:00

## Ребалансировка расписания

Автоматическая оптимизация расписания публикаций путем заполнения пропусков:

```bash
# Предпросмотр изменений (dry-run)
instapost rebalance

# Применить ребалансировку
instapost rebalance --apply
```

**Когда использовать:**
- После отмены или удаления постов
- Когда система была выключена и пропустила время публикации
- Для уплотнения расписания

## Лицензия

MIT
