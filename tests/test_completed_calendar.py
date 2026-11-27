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

def test_cooking_fractions_not_parsed_as_dates(tmp_path):
    """Verify fractions like 1/4c or 2 3/4c do not trigger false date parsing or reset last_seen_done_date."""
    test_file = tmp_path / "tasks.txt"
    test_file.write_text(
        "* 11/26 Bake Bread with 1/4c sugar and 2 3/4c flour\n"
        "\n# Done\n"
        "x * 11/26 Bake Bread #preserve_subtasks\n"
        "✓ Add 1/4c sugar, 1tsp salt, mix well till dough is firm\n"
        "✓ Add 2 3/4c bread flour, 1 1/4 yeast\n"
    )

    data = parse_tasks(str(test_file))
    # Active task retains full description and stays in today
    assert data["today"][0]["title"] == "Bake Bread with 1/4c sugar and 2 3/4c flour"

    # Completed calendar has only November (no false January 4th bucket)
    cal = data["completed_calendar"]
    assert len(cal) == 1
    assert cal[0]["short_label"] == "November"
    assert cal[0]["count"] == 3

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
    