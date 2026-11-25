from datetime import datetime
import pytest
import web_app
from utils.board_etl import parse_tasks


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_file = tmp_path / "tasks.txt"
    test_file.write_text("# Done\n")
    monkeypatch.setattr(web_app, "TASK_FILE", test_file)
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c, test_file


def test_zero_fib_option_in_modals_and_low_hanging_fruit_rendering(client):
    """Verify #fib:0 is selectable in create/edit modals and surfaces in Low-Hanging Fruit."""
    test_client, test_file = client
    now = datetime.now()
    today_iso = now.strftime("%Y-%m-%d")

    res = test_client.post("/add_task", json={
        "date": today_iso,
        "symbol": "*",
        "description": "Quick zero-effort check",
        "tags": ["fib:0"],
        "subtasks": []
    })
    assert res.status_code == 200
    assert "#fib:0" in test_file.read_text()

    data = parse_tasks(str(test_file))
    assert data["today"][0]["fib_score"] == "0"
    assert data["today_fib_remaining"] == 0

    html = test_client.get("/").get_data(as_text=True)
    assert '<option value="0">0 pts</option>' in html
    # Appears in both Today's schedule and Low-Hanging Fruit card
    assert html.count("Quick zero-effort check") == 4
