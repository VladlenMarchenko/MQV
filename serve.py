"""Production entry point for Windows Server (Waitress)."""

import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from waitress import serve

from app import EXE_DIR, app

CONFIG_PATH = EXE_DIR / "server.json"
LOG_DIR = EXE_DIR / "logs"
PID_PATH = LOG_DIR / "queuemail.pid"


def load_config() -> dict:
    config = {"host": "0.0.0.0", "port": 8000, "threads": 8}
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"server.json должен быть объектом: {CONFIG_PATH}")
        for key in ("host", "port", "threads"):
            if key in data:
                config[key] = data[key]

    if os.environ.get("QUEUEMAIL_HOST"):
        config["host"] = os.environ["QUEUEMAIL_HOST"]
    if os.environ.get("QUEUEMAIL_PORT"):
        config["port"] = int(os.environ["QUEUEMAIL_PORT"])
    if os.environ.get("QUEUEMAIL_THREADS"):
        config["threads"] = int(os.environ["QUEUEMAIL_THREADS"])

    config["port"] = int(config["port"])
    config["threads"] = int(config["threads"])
    if config["port"] < 1 or config["port"] > 65535:
        raise ValueError(f"Некорректный порт: {config['port']}")
    if config["threads"] < 1:
        raise ValueError(f"Некорректное число потоков: {config['threads']}")
    return config


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(
        LOG_DIR / "queuemail.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    app.logger.setLevel(logging.INFO)


def main() -> None:
    setup_logging()
    log = logging.getLogger("queuemail")
    config = load_config()
    PID_PATH.write_text(str(os.getpid()), encoding="ascii")
    log.info("Queue Mail Generator listening on http://%s:%s", config["host"], config["port"])
    try:
        serve(
            app,
            host=config["host"],
            port=config["port"],
            threads=config["threads"],
            ident="QueueMail",
        )
    except OSError:
        log.exception("Не удалось занять %s:%s", config["host"], config["port"])
        raise SystemExit(1)
    finally:
        if PID_PATH.exists():
            try:
                PID_PATH.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    main()
