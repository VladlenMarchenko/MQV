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
