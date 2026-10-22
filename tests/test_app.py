import app


def test_split_queue_line():
    rows = app.split_queues("QUEUE(INT.TEST.ERR) CURDEPTH(3)")
    assert rows == [
        {
            "name": "INT.TEST.ERR",
            "curdepth": 3,
            "source": "QUEUE(INT.TEST.ERR) CURDEPTH(3)",
        }
    ]


def test_split_wrapped_queue_line():
    rows = app.split_queues("QUEUE(\nINT.TEST.ERR\n) CURDEPTH(4)")
    assert rows[0]["name"] == "INT.TEST.ERR"
    assert rows[0]["curdepth"] == 4


def test_split_plain_names():
    rows = app.split_queues("ONE, TWO; THREE")
    assert [row["name"] for row in rows] == ["ONE", "TWO", "THREE"]
    assert all(row["curdepth"] is None for row in rows)


def test_classification_follows_np_rules():
    rules = app.load_rules()
    raw = "\n".join(
        [
            "QUEUE(INT.TEST.ERR) CURDEPTH(3)",
            "QUEUE(FOO.SIGNAL) CURDEPTH(2)",
            "QUEUE(BAR.CALLBACK) CURDEPTH(1)",
            "QUEUE(BAZ.DEADLETTER) CURDEPTH(1)",
            "QUEUE(INT.STORE.OP1.Q) CURDEPTH(9)",
        ]
    )
    grouped = app.classify_queues(app.split_queues(raw), rules)

    assert grouped["move_if_returned_delete"] == ["QUEUE(INT.TEST.ERR) CURDEPTH(3)"]
    assert grouped["delete"] == ["QUEUE(FOO.SIGNAL) CURDEPTH(2)"]
    assert grouped["move_with_analysis"] == ["QUEUE(BAR.CALLBACK) CURDEPTH(1)"]
    assert grouped["dead_letter_export"] == ["QUEUE(BAZ.DEADLETTER) CURDEPTH(1)"]
    assert grouped["skipped"] == ["QUEUE(INT.STORE.OP1.Q) CURDEPTH(9)"]
    assert grouped["unmatched"] == []


def test_high_volume_ignores_main_queues():
    queues = app.split_queues(
        "QUEUE(FOO.ERR) CURDEPTH(25)\nQUEUE(INT.STORE.OP1.Q) CURDEPTH(100)"
    )
    assert app.collect_high_volume(queues) == ["QUEUE(FOO.ERR) CURDEPTH(25)"]


def test_generate_letter(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "SIGNATURE_PATH", tmp_path / "signature.txt")
    client = app.app.test_client()
    response = client.post(
        "/generate",
        json={
            "queues": "QUEUE(INT.TEST.ERR) CURDEPTH(3)\nQUEUE(FOO.SIGNAL) CURDEPTH(25)",
            "signature": "Test Signature",
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 2
    assert "Переложить если вернуться удалить:" in data["letter"]
    assert "Удалить:" in data["letter"]
    assert "Test Signature" in data["letter"]
    assert data["high_volume"] == ["QUEUE(FOO.SIGNAL) CURDEPTH(25)"]
    assert "!!!ОЧЕРЕДИ С БОЛЬШИМ КОЛ-ВОМ СООБЩЕНИЙ!!!" in data["high_volume_block"]


def test_empty_generate(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "SIGNATURE_PATH", tmp_path / "signature.txt")
    client = app.app.test_client()
    data = client.post("/generate", json={"queues": ""}).get_json()
    assert data["total"] == 0
    assert data["letter"].startswith("Коллеги добрый день!")
    assert data["unmatched"] == []


def test_signature_is_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "SIGNATURE_PATH", tmp_path / "signature.txt")
    client = app.app.test_client()
    saved = client.post("/signature", json={"signature": "Новая подпись"})
    assert saved.status_code == 200
    assert client.get("/signature").get_json()["signature"] == "Новая подпись"


def test_index_page():
    response = app.app.test_client().get("/")
    assert response.status_code == 200
    assert "Генератор письма" in response.get_data(as_text=True)
