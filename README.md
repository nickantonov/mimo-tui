# MiMo TUI v1.0

Автономний AI-асистент для програмування. Працює на Windows та Linux.

**Без Bun, без opencode, без SolidJS** — просто Python + Rich + MiMo free-tier API.

## Швидкий старт

### Windows
```bat
install.bat
run.bat
```

### Linux (Fedora/Ubuntu)
```bash
chmod +x install.sh run.sh
./install.sh
./run.sh
```

## Що всередині

| Компонент | Джерело | Призначення |
|-----------|---------|-------------|
| Brain (streaming + tool calling) | JARVIS | LLM engine з MiMo API + Ollama fallback |
| 13 Tools | JARVIS | Файли, git, python, shell, система |
| Memory (SQLite) | JARVIS | Граф знань, діалоги, бібліотека коду |
| VibeCoder | JARVIS | Авто-повтор генерації коду |
| Planner | JARVIS | Декомпозиція задач |
| Cerebro | NATASHA7 | Особистість та навчання |
| AST Analyzer | Predator | Аналіз якості Python коду |
| Auth | Наша робота | MiMo free-tier bootstrap + fingerprint |

## Команди

- `/help` — Довідка
- `/mode [назва]` — Режим (auto|code|plan|local|fast)
- `/model s|f` — Модель (smart/fast)
- `/plan <ціль>` — Додати задачу в планувальник
- `/plans` — Черга планів
- `/memory` — Статистика пам'яті
- `/fact k=v` — Запам'ятати факт
- `/ast <файл>` — AST перевірка Python файлу
- `/cwd [шлях]` — Змінити робочу директорію
- `/tokens` — Статистика токенів
- `/status` — Системний статус (CPU/RAM)
- `exit` — Вихід

## Режими

- **AUTO** — Розумний автоматичний (за замовчуванням)
- **CODE** — Вайбкодинг з авто-повтором
- **PLAN** — Автономне планування задач
- **LOCAL** — Тільки Ollama (офлайн)
- **FAST** — Мала модель, економія токенів

## Залежності

- Python 3.10+
- rich, psutil
- Опціонально: Ollama (для локального fallback)

## API

Використовує MiMo free-tier через opencode.ai:
- Auth: device fingerprint (SHA-256)
- Endpoint: `https://opencode.ai/zen/v1/chat/completions`
- Моделі: mimo-auto, hy3-free, mimo-v2.5-free

## Credits

Borodachamba Studio © 2026
