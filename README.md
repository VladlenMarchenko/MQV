# Queue Mail Generator

Python backend + web frontend for generating a letter from queue names.

## Run locally

```powershell
python app.py
```

Open: <http://127.0.0.1:8000>

This starts the development server on localhost only. To publish the site, use Docker or the Windows service below.

## Docker

Нужны Docker Engine и Docker Compose. В каталоге с `docker-compose.yml`:

```powershell
docker compose up -d --build
```

Сайт: <http://localhost:8000>

```powershell
docker compose logs -f
docker compose restart
docker compose down
```

Подпись хранится в томе `queuemail-data` и сохраняется при пересборке образа. Правила читаются из `np_rules.json` рядом с compose-файлом; после правки выполните `docker compose restart`. Другой внешний порт задаётся слева в `ports`, например `"8080:8000"`. Страницы входа нет.

## GitHub Actions

Файл `.github/workflows/ci.yml` запускается на каждый push и pull request.

- Тесты: `pytest`
- Сборка Docker-образа
- Push в ветку `main` или `master` публикует образ в GitHub Container Registry: `ghcr.io/<владелец>/<репозиторий>:latest`

Локально те же проверки:

```powershell
pip install -r requirements.txt pytest
pytest
```

Автоматическое обновление сервера включается в настройках репозитория: Settings, Secrets and variables, Actions. Сервер должен быть с Docker и SSH, а вход по ключу должен попадать в bash.

Variables:

- `DEPLOY_ENABLED` = `true`
- `DEPLOY_HOST` — адрес сервера
- `DEPLOY_USER` — пользователь SSH
- `DEPLOY_PATH` — каталог на сервере, например `/opt/queuemail`

Secret:

- `DEPLOY_SSH_KEY` — приватный ключ, публичная часть которого добавлена этому пользователю

Пока `DEPLOY_ENABLED` не равен `true`, пайплайн только проверяет код и публикует образ. На сервере пользователь должен иметь право запускать Docker. Подпись в томе `queuemail-data` при обновлении не стирается.

## Windows Server

Сайт слушает все интерфейсы через Waitress и поднимается при загрузке Windows задачей `QueueMailGenerator` от имени `SYSTEM`. Адрес и порт задаются в `server.json`.

Скопируйте `release\QueueMail-deploy.zip` на сервер и распакуйте в локальную папку, например `C:\Apps\QueueMail`. Не кладите приложение в OneDrive и не запускайте его с сетевого диска. На сервере заранее нужен Python 3.10 или новее в `PATH`.

В PowerShell от имени администратора:

```powershell
cd C:\Apps\QueueMail
powershell -ExecutionPolicy Bypass -File .\deploy\install.ps1
```

Установщик создаёт `.venv`, ставит зависимости, открывает порт в брандмауэре для текущего профиля сети и запускает сайт.

Адрес по умолчанию: `http://<имя-сервера>:8000`

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\status.ps1
powershell -ExecutionPolicy Bypass -File .\deploy\stop.ps1
powershell -ExecutionPolicy Bypass -File .\deploy\start.ps1
powershell -ExecutionPolicy Bypass -File .\deploy\uninstall.ps1
```

Другой порт:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\install.ps1 -Port 8080
```

Журнал: `logs\queuemail.log`. Подпись хранится в `signature.txt` рядом с `app.py`. Страницы входа нет, порт должен быть доступен только во внутренней сети.

Собрать архив для выгрузки заново:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\package.ps1
```

## Important

Queue classification must strictly follow `NP.pdf`.
All mapping logic is configured in `np_rules.json`.

## Rules format

`np_rules.json`:

- `categories.move_if_returned_delete`
- `categories.delete`
- `categories.move_with_analysis`

Each item:

- `mode`: `regex` or `contains`
- `pattern`: pattern string

Priority is fixed:

1. `move_if_returned_delete`
2. `delete`
3. `move_with_analysis`

If no rule matched, queue appears in `unmatched` warning.
