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


def test_add_and_parse_next_year_task_lands_in_future_sorted_chronologically(client):
    """Scheduling a task for next year (e.g., Jan 27, 2027) must write /27, route to future, and sort after Dec."""
    test_client, test_file = client
    now = datetime.now()
    next_year = now.year + 1

    # Add a next-year January task first, then a current-year December task
    res_jan = test_client.post(
        "/add_task",
        json={
            "date": f"{next_year}-01-27",
            "symbol": "!",
            "description": "Dentist Appointment",
            "tags": ["health"],
            "subtasks": [],
        },
    )
    assert res_jan.status_code == 200

    res_dec = test_client.post(
        "/add_task",
        json={
            "date": f"{now.year}-12-15",
            "symbol": "*",
            "description": "Year-End Review",
            "tags": [],
            "subtasks": [],
        },
    )
    assert res_dec.status_code == 200

    raw_text = test_file.read_text()
    assert f"! 1/27/{str(next_year)[-2:]} Dentist Appointment #health" in raw_text

    parsed = parse_tasks(str(test_file))
    today_titles = [t["title"] for t in parsed["today"]]
    future_titles = [t["title"] for t in parsed["future"]]

    assert "Dentist Appointment" not in today_titles
    assert future_titles == ["Year-End Review", "Dentist Appointment"]