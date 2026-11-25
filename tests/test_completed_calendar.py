from datetime import datetime, timedelta
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


def test_completed_calendar_groups_reverse_chronologically_with_counts(client):
    """Verify completed_calendar groups tasks by month and day descending with accurate counts."""
    test_client, test_file = client
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    prev_month_day = today.replace(day=1) - timedelta(days=5)

    test_file.write_text(
        "# Done\n"
        f"x {prev_month_day.month}/{prev_month_day.day} Older Month Task\n"
        f"x {yesterday.month}/{yesterday.day} Yesterday Task\n"
        f"x {today.month}/{today.day} Today First\n"
        f"x {today.month}/{today.day} Today Second\n"
    )

    data = parse_tasks(str(test_file))
    cal = data["completed_calendar"]

    assert len(cal) == 2
    assert cal[0]["short_label"] == today.strftime("%B")
    assert cal[0]["count"] == 3
    assert cal[0]["days"][0]["label"] == "Today"
    assert cal[0]["days"][0]["tasks"] == [
        f"{today.month}/{today.day} Today Second",
        f"{today.month}/{today.day} Today First",
    ]
    assert cal[1]["short_label"] == prev_month_day.strftime("%B")
    assert cal[1]["count"] == 1

    res = test_client.get("/")
    html = res.get_data(as_text=True)
    assert 'id="completedMonthsAccordion"' in html
    assert f">{today.strftime('%B')}</span>" in html

from datetime import datetime, timedelta
import web_app
from utils.board_etl import parse_tasks


def test_undated_subtasks_inherit_preceding_done_date(tmp_path):
    """Verify historical undated subtasks inherit the date of the preceding # Done entry."""
    test_file = tmp_path / "tasks.txt"
    today = datetime.now().date()
    older = today - timedelta(days=5)

    test_file.write_text(
        "# Done\n"
        f"x 11/{older.day} Guitar Practice #preserve_subtasks\n"
        "x Sound Of Silence vs She's Got a Way\n"
        "✓ Tereza\n"
        f"x {today.month}/{today.day} Brush Teeth #daily\n"
    )

    data = parse_tasks(str(test_file))
    cal = data["completed_calendar"]

    # Today should only contain Brush Teeth, not the 5-day-old subtasks
    today_bucket = next(d for m in cal for d in m["days"] if d["label"] == "Today")
    assert len(today_bucket["tasks"]) == 1
    assert f"{today.month}/{today.day} Brush Teeth #daily" in today_bucket["tasks"]

    older_bucket = next(d for m in cal for d in m["days"] if d["date_iso"] == older.strftime("%Y-%m-%d"))
    assert len(older_bucket["tasks"]) == 3