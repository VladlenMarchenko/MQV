import json
import os
import re
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

if getattr(sys, "frozen", False):
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    EXE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
    EXE_DIR = BASE_DIR

_data_dir = os.environ.get("QUEUEMAIL_DATA", "").strip()
DATA_DIR = Path(_data_dir) if _data_dir else EXE_DIR

RULES_PATH = BASE_DIR / "np_rules.json"
SIGNATURE_PATH = DATA_DIR / "signature.txt"

HIGH_VOLUME_THRESHOLD = 20

MOVE_WITH_ANALYSIS_HEADER = (
    "Переложить с анализом, если вернутся, то просьба приложить логи и тела "
    "в ответном письме, а затем удалить"
)
DEAD_LETTER_HEADER = (
    "Выгрузить тела сообщений и направить в ответном письме, а затем удалить"
)
HIGH_VOLUME_HEADER = "!!!ОЧЕРЕДИ С БОЛЬШИМ КОЛ-ВОМ СООБЩЕНИЙ!!!"

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024


def load_signature() -> str:
    if SIGNATURE_PATH.exists():
        return SIGNATURE_PATH.read_text(encoding="utf-8")
    return ""


def save_signature(text: str) -> None:
    SIGNATURE_PATH.write_text(text, encoding="utf-8")


def load_rules() -> dict:
    rules_path = RULES_PATH
    if not rules_path.exists():
        alt_path = EXE_DIR / "np_rules.json"
        if alt_path.exists():
            rules_path = alt_path

    if not rules_path.exists():
        raise FileNotFoundError(
            f"Не найден файл правил: {rules_path}. Заполните его по NP документу."
        )

    with rules_path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def split_queues(raw_text: str) -> list[dict]:
    normalized = raw_text.replace("\r", "")
    normalized = re.sub(r"_(?:\s*\n)\s*_", "_", normalized)
    normalized = re.sub(r"QUEUE\(\s*\n\s*", "QUEUE(", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\)\s*\n\s*CURDEPTH\(", ") CURDEPTH(", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s*\n\s*", "\n", normalized)

    queue_records = []
    for m in re.finditer(r"QUEUE\(([^)]+)\)(?:\s*CURDEPTH\((\d+)\))?", normalized, flags=re.IGNORECASE):
        queue_name = m.group(1).strip()
        curdepth_raw = m.group(2)
        curdepth = int(curdepth_raw) if curdepth_raw is not None else None
        source = f"QUEUE({queue_name})"
        if curdepth is not None:
            source += f" CURDEPTH({curdepth})"
        queue_records.append({"name": queue_name, "curdepth": curdepth, "source": source})

    if queue_records:
        return queue_records

    parts = re.split(r"[\n,;]+", normalized)
    return [{"name": p.strip(), "curdepth": None, "source": p.strip()} for p in parts if p.strip()]


def match_rule(queue: dict, rule: dict) -> bool:
    queue_name = queue["name"]
    curdepth = queue["curdepth"]
    mode = rule.get("mode")
    pattern = rule.get("pattern", "")

    if mode == "regex":
        base_match = re.search(pattern, queue_name, flags=re.IGNORECASE) is not None
    elif mode == "contains":
        base_match = pattern.lower() in queue_name.lower()
    elif mode == "always":
        base_match = True
    else:
        raise ValueError(f"Неподдерживаемый mode: {mode}")

    if not base_match:
        return False

    all_keywords = [k.lower() for k in rule.get("all_keywords", [])]
    any_keywords = [k.lower() for k in rule.get("any_keywords", [])]
    exclude_keywords = [k.lower() for k in rule.get("exclude_keywords", [])]
    queue_name_l = queue_name.lower()

    if all_keywords and not all(k in queue_name_l for k in all_keywords):
        return False
    if any_keywords and not any(k in queue_name_l for k in any_keywords):
        return False
    if exclude_keywords and any(k in queue_name_l for k in exclude_keywords):
        return False

    min_curdepth = rule.get("min_curdepth")
    max_curdepth = rule.get("max_curdepth")
    exact_curdepth = rule.get("exact_curdepth")

    if exact_curdepth is not None and curdepth != exact_curdepth:
        return False
    if min_curdepth is not None and (curdepth is None or curdepth < min_curdepth):
        return False
    if max_curdepth is not None and (curdepth is None or curdepth > max_curdepth):
        return False

    return True


def is_dead_letter_queue(queue_name: str) -> bool:
    name = queue_name.upper()
    return "DEAD_LETTER" in name or "DEADLETTER" in name


def is_skippable_main_queue(queue_name: str) -> bool:
    name = queue_name.upper()

    # Main business queues must be ignored.
    # We process only technical/error/service queues.
    actionable_keywords = [
        ".ERR",
        "CALLBACK",
        "INVOKE",
        "DEADLETTER",
        "DEAD_LETTER",
        "ROUTERUNAV",
        "IFPSSTATUS",
        "SIGNAL",
        "TRG",
        "OW_RESP",
    ]
    if any(k in name for k in actionable_keywords):
        return False

    if name.startswith("INT.RMMB_") or name.startswith("RMMB_"):
        return True

    # Основные очереди (*_STORE.OP1.Q и т.п.) — не трогаем.
    if name.endswith(".Q"):
        return True

    return False


def collect_high_volume(queues: list[dict]) -> list[str]:
    return [
        queue["source"]
        for queue in queues
        if queue["curdepth"] is not None
        and queue["curdepth"] > HIGH_VOLUME_THRESHOLD
        and not is_skippable_main_queue(queue["name"])
    ]


def classify_queues(queues: list[dict], rules: dict) -> dict:
    buckets = {
        "move_if_returned_delete": [],
        "delete": [],
        "dead_letter_export": [],
        "move_with_analysis": [],
        "unmatched": [],
        "skipped": [],
    }

    categories = rules.get("categories", {})
    for queue in queues:
        if is_skippable_main_queue(queue["name"]):
            buckets["skipped"].append(queue["source"])
            continue

        if is_dead_letter_queue(queue["name"]):
            buckets["dead_letter_export"].append(queue["source"])
            continue

        assigned = False
        # NP.pdf: сначала удаление (SIGNAL/TRG/OW_RESP), затем анализ (CALLBACK/INVOKE/глубина>10).
        for category_name in ["delete", "move_with_analysis", "move_if_returned_delete"]:
            for rule in categories.get(category_name, []):
                if match_rule(queue, rule):
                    buckets[category_name].append(queue["source"])
                    assigned = True
                    break
            if assigned:
                break

        if not assigned:
            buckets["unmatched"].append(queue["source"])

    return buckets


def format_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def build_high_volume_block(items: list[str]) -> str:
    if not items:
        return ""
    return f"{HIGH_VOLUME_HEADER}\n{format_list(items)}"


def build_letter(grouped: dict, signature: str = "") -> str:
    lines = ["Коллеги добрый день!", "Просьба:"]

    if grouped["move_if_returned_delete"]:
        lines.extend([
            "Переложить если вернуться удалить:",
            format_list(grouped["move_if_returned_delete"]),
            "",
        ])

    if grouped["delete"]:
        lines.extend(["Удалить:", format_list(grouped["delete"]), ""])

    if grouped["dead_letter_export"]:
        lines.extend([
            f"{DEAD_LETTER_HEADER}:",
            format_list(grouped["dead_letter_export"]),
            "",
        ])

    if grouped["move_with_analysis"]:
        lines.extend([
            f"{MOVE_WITH_ANALYSIS_HEADER}:",
            format_list(grouped["move_with_analysis"]),
        ])

    while lines and lines[-1] == "":
        lines.pop()

    signature = signature.strip()
    if signature:
        lines.append("")
        lines.extend(signature.splitlines())

    return "\n".join(lines)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/signature", methods=["GET"])
def get_signature():
    return jsonify({"signature": load_signature()})


@app.route("/signature", methods=["POST"])
def post_signature():
    payload = request.get_json(silent=True) or {}
    save_signature(payload.get("signature", ""))
    return jsonify({"ok": True})


@app.route("/generate", methods=["POST"])
def generate():
    payload = request.get_json(silent=True) or {}
    raw_queues = payload.get("queues", "")
    signature = payload.get("signature")
    if signature is None:
        signature = load_signature()

    queues = split_queues(raw_queues)
    rules = load_rules()
    grouped = classify_queues(queues, rules)
    high_volume = collect_high_volume(queues)
    letter = build_letter(grouped, signature)

    return jsonify({
        "letter": letter,
        "high_volume": high_volume,
        "high_volume_block": build_high_volume_block(high_volume),
        "unmatched": grouped["unmatched"],
        "total": len(queues),
    })


@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(_exc):
    return jsonify({"error": "Слишком большой текст очередей"}), 413


@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    if isinstance(exc, HTTPException):
        return exc
    app.logger.exception("request failed")
    return jsonify({"error": "Внутренняя ошибка сервера"}), 500


if __name__ == "__main__":
    # Локальная проверка. На Windows Server запускайте serve.py.
    app.run(host="127.0.0.1", port=8000, debug=False)
