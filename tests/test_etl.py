import pytest
from datetime import datetime, timedelta
from utils.board_etl import (
    complete_task,
    delete_line,
    get_next_month_date,
    insert_date_at_front,
    make_line_today,
    move_line_to_bottom,
    parse_tasks,
    shift_line_to_tomorrow,
    toggle_line_focus,
)
def test_capitalized_priority_tag_sorting(tmp_path):
    task_file = tmp_path / "tasks.txt"
    task_file.write_text(
        "* 10/21 Cut pokeweed\n"
        "* 10/21 Marnie Grow @Fooda #Priority\n"
    )

    data = parse_tasks(str(task_file))
    
    # Assert #Priority item rises to index 0 and contexts/tags are cleaned from title
    assert data["today"][0]["title"] == "Marnie Grow"
    assert "priority" in data["today"][0]["tags"]

def test_complete_capitalized_daily_recurring_task(tmp_path):
    task_file = tmp_path / "tasks.txt"
    task_file.write_text("! 10/17 10:00 Walk 11K steps #Daily #focus\n\n# Done\n")

    complete_task(str(task_file), "! 10/17 10:00 Walk 11K steps #Daily #focus")

    content = task_file.read_text()
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_str = f"{tomorrow.month}/{tomorrow.day}"

    # Verify tomorrow's recurring instance is present and focus is stripped
    assert f"! {tomorrow_str} 10:00 Walk 11K steps #Daily" in content
    assert f"! {tomorrow_str} 10:00 Walk 11K steps #Daily #focus" not in content
    # Verify completion entry exists under # Done
    assert "x ! 10/17 10:00 Walk 11K steps #Daily" in content

def test_complete_daily_task_not_found_fails_gracefully(tmp_path):
    task_file = tmp_path / "tasks.txt"
    # File has lowercase #daily
    task_file.write_text("! 10/17 10:00 Walk 11K steps #daily #focus\n\n# Done\n")

    # Front-end sends uppercase #Daily
    complete_task(str(task_file), "! 10/17 10:00 Walk 11K steps #Daily #focus")

    content = task_file.read_text()
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_str = f"{tomorrow.month}/{tomorrow.day}"

    # THIS ASSERTION WILL FAIL currently because line matching is case-sensitive
    assert f"! {tomorrow_str} 10:00 Walk 11K steps" in content
    assert "x !" in content
   
def test_complete_daily_task_with_html_escaped_payload(tmp_path):
    task_file = tmp_path / "tasks.txt"
    task_file.write_text("- 10/17 Check for ripe figs & herbs #Daily #focus\n\n# Done\n")

    # Simulate HTML-escaped string sent from Jinja template via fetch POST
    escaped_raw = "- 10/17 Check for ripe figs &amp; herbs #Daily #focus"
    complete_task(str(task_file), escaped_raw)

    content = task_file.read_text()
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_str = f"{tomorrow.month}/{tomorrow.day}"

    assert f"- {tomorrow_str} Check for ripe figs & herbs #Daily" in content
    assert "x - 10/17 Check for ripe figs & herbs #Daily" in content

def test_complete_monthly_task(tmp_path):
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"
    
    next_month_dt = get_next_month_date(now)
    expected_next_str = f"{next_month_dt.month}/{next_month_dt.day}"

    task_file = tmp_path / "tasks.txt"
    task_file.write_text(f"* {today_str} Pay mortgage #Monthly #focus\n\n# Done\n")

    complete_task(str(task_file), f"* {today_str} Pay mortgage #Monthly #focus")

    content = task_file.read_text()
    
    # Dynamic assertions relative to datetime.now()
    assert f"* {expected_next_str} Pay mortgage #Monthly" in content
    assert f"x * {today_str} Pay mortgage #Monthly" in content

def test_complete_not_sunday_task_midweek(tmp_path, monkeypatch):
    # Simulate current day as Wednesday (2026-10-21)
    wednesday = datetime(2026, 10, 21)
    class FixedDatetime(datetime):
        @classmethod
        def now(cls):
            return wednesday

    monkeypatch.setattr("utils.board_etl.datetime", FixedDatetime)

    task_file = tmp_path / "tasks.txt"
    task_file.write_text("* 10/21 Daily routine #Not-Sunday #focus\n\n# Done\n")

    complete_task(str(task_file), "* 10/21 Daily routine #Not-Sunday #focus")

    content = task_file.read_text()
    # On Wednesday, next instance should be Thursday (10/22)
    assert "* 10/22 Daily routine #Not-Sunday" in content

def test_complete_not_sunday_task_saturday(tmp_path, monkeypatch):
    # Simulate current day as Saturday (2026-10-24)
    saturday = datetime(2026, 10, 24)
    class FixedDatetime(datetime):
        @classmethod
        def now(cls):
            return saturday

    monkeypatch.setattr("utils.board_etl.datetime", FixedDatetime)

    task_file = tmp_path / "tasks.txt"
    task_file.write_text("* 10/24 Daily routine #Not-Sunday #focus\n\n# Done\n")

    complete_task(str(task_file), "* 10/24 Daily routine #Not-Sunday #focus")

    content = task_file.read_text()
    # On Saturday, next instance should skip Sunday (10/25) to Monday (10/26)
    assert "* 10/26 Daily routine #Not-Sunday" in content
    
def test_complete_nth_weekday_task(tmp_path, monkeypatch):
    # Simulate current date as 3rd Sunday of October 2026 (2026-10-18)
    oct_18_2026 = datetime(2026, 10, 18)
    class FixedDatetime(datetime):
        @classmethod
        def now(cls):
            return oct_18_2026

    monkeypatch.setattr("utils.board_etl.datetime", FixedDatetime)

    task_file = tmp_path / "tasks.txt"
    task_file.write_text("* 10/18 Board sync #3rd-Sunday #focus\n\n# Done\n")

    complete_task(str(task_file), "* 10/18 Board sync #3rd-Sunday #focus")

    content = task_file.read_text()
    # 3rd Sunday of November 2026 is 11/15
    assert "* 11/15 Board sync #3rd-Sunday" in content

def test_complete_task_end_to_end_daily(tmp_path):
    task_file = tmp_path / "tasks.txt"
    # Exact file contents as used in live testing
    task_file.write_text("10/17 Check for ripe figs #Daily #focus\n\n# Done\n")

    # Call complete_task with exact raw string
    complete_task(str(task_file), "10/17 Check for ripe figs #Daily #focus")

    content = task_file.read_text()
    lines = content.splitlines()

    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_str = f"{tomorrow.month}/{tomorrow.day}"

    # 1. Assert recurring line was generated for tomorrow before # Done
    assert f"* {tomorrow_str} Check for ripe figs #Daily" in content or f"{tomorrow_str} Check for ripe figs #Daily" in content
    
    # 2. Assert original task was moved below # Done
    assert "x 10/17 Check for ripe figs #Daily" in content

def test_complete_weekdays_task_midweek(tmp_path, monkeypatch):
    # Simulate current day as Wednesday (2026-10-21)
    wednesday = datetime(2026, 10, 21)
    class FixedDatetime(datetime):
        @classmethod
        def now(cls):
            return wednesday

    monkeypatch.setattr("utils.board_etl.datetime", FixedDatetime)

    task_file = tmp_path / "tasks.txt"
    task_file.write_text("* 10/21 Standup sync #Weekdays #focus\n\n# Done\n")

    complete_task(str(task_file), "* 10/21 Standup sync #Weekdays #focus")

    content = task_file.read_text()
    # On Wednesday, next instance should be Thursday (10/22)
    assert "* 10/22 Standup sync #Weekdays" in content

def test_complete_weekdays_task_friday(tmp_path, monkeypatch):
    # Simulate current day as Friday (2026-10-23)
    friday = datetime(2026, 10, 23)
    class FixedDatetime(datetime):
        @classmethod
        def now(cls):
            return friday

    monkeypatch.setattr("utils.board_etl.datetime", FixedDatetime)

    task_file = tmp_path / "tasks.txt"
    task_file.write_text("* 10/23 Submit weekly report #Weekdays #focus\n\n# Done\n")

    complete_task(str(task_file), "* 10/23 Submit weekly report #Weekdays #focus")

    content = task_file.read_text()
    # On Friday, next instance should skip the weekend to Monday (10/26)
    assert "* 10/26 Submit weekly report #Weekdays" in content

def test_complete_x_days_recurring_task(tmp_path):
    task_file = tmp_path / "tasks.txt"
    task_file.write_text("* 10/17 Check fig tree soil #2-Days #focus\n\n# Done\n")

    complete_task(str(task_file), "* 10/17 Check fig tree soil #2-Days #focus")

    content = task_file.read_text()
    two_days_out = datetime.now() + timedelta(days=2)
    expected_date = f"{two_days_out.month}/{two_days_out.day}"

    # Confirm dynamic date incremented by 2 days
    assert f"* {expected_date} Check fig tree soil #2-Days" in content
    assert "x * 10/17 Check fig tree soil #2-Days" in content

def test_delete_line_with_subtasks(tmp_path):
    task_file = tmp_path / "tasks.txt"
    task_file.write_text(
        "* Parent task to delete #focus\n"
        "  * Subtask 1\n"
        "  * Subtask 2\n"
        "* Keep this task\n"
    )

    delete_line(str(task_file), "* Parent task to delete #focus")

    content = task_file.read_text()
    assert "Parent task to delete" not in content
    assert "Subtask 1" not in content
    assert "* Keep this task" in content

def test_insert_date_at_front():
    # Test task with symbol
    res_symbol = insert_date_at_front("* Dry Whites", "10/17")
    assert res_symbol == "* 10/17 Dry Whites"

    # Test task without symbol
    res_no_symbol = insert_date_at_front("Review pull requests", "10/17")
    assert res_no_symbol == "10/17 Review pull requests"

def test_make_line_today():
    # Replace existing M/D date with today's date
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    res = make_line_today("* 12/25 Future task")
    assert res == f"* {today_str} Future task"

    # Append today's date if none present
    res_no_date = make_line_today("* Undated task")
    assert res_no_date == f"* Undated task {today_str}"

def test_move_line_to_bottom(tmp_path):
    task_file = tmp_path / "tasks.txt"
    task_file.write_text(
        "* First task #focus\n"
        "* Second task\n"
        "* Third task\n\n"
        "# Done\n"
    )

    move_line_to_bottom(str(task_file), "* First task #focus")

    content = task_file.read_text()
    lines = [line.strip() for line in content.splitlines() if line.strip()]

    # Verify #focus was stripped and task was reordered to bottom before # Done
    assert lines == [
        "* Second task",
        "* Third task",
        "* First task",
        "# Done"
    ]

def test_parse_dated_or_hyphenated_tasks(tmp_path):
    task_file = tmp_path / "tasks.txt"
    task_file.write_text(
        "10/18 Check for ripe figs #Daily\n"
        "- 10/17 Water fig trees #Daily\n"
    )

    data = parse_tasks(str(task_file))
    total_parsed = len(data["today"]) + len(data["future"])
    assert total_parsed == 2

def test_parse_hyphen_and_dated_tasks(tmp_path):
    task_file = tmp_path / "tasks.txt"
    task_file.write_text(
        "- 10/17 Check for ripe figs #Daily\n"
        "10/18 Water fig trees #Daily\n"
    )

    data = parse_tasks(str(task_file))
    assert len(data["today"]) + len(data["future"]) == 2

def test_parse_task_with_obsidian_markdown_link(tmp_path):
    task_file = tmp_path / "tasks.txt"
    obsidian_uri = "obsidian://open?vault=obsidian&file=300%20Music%20MOC%2F360%20Instruments%20MOC%2F310%20Guitar%20MOC%2FApril%20Come%20She%20Will"
    
    task_file.write_text(f"* 10/23 Practiced ({obsidian_uri})[April Come She Will] #guitar\n")

    data = parse_tasks(str(task_file))
    task = data["today"][0]

    # Verify link parsing retains markdown syntax or renders cleanly
    assert "April Come She Will" in task["title"]
    assert "obsidian://" in task["raw"]

def test_shift_line_to_tomorrow():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    tomorrow_str = f"{tomorrow.month}/{tomorrow.day}"

    shifted = shift_line_to_tomorrow(f"* {now.month}/{now.day} Scheduled item")
    assert shifted == f"* {tomorrow_str} Scheduled item"

def test_toggle_line_focus(tmp_path):
    task_file = tmp_path / "tasks.txt"
    task_file.write_text("* Task A\n* Task B #focus\n")

    # Toggle focus onto Task A (should clear focus from Task B)
    toggle_line_focus(str(task_file), "* Task A")

    content = task_file.read_text()
    assert "* Task A #focus" in content
    assert "* Task B #focus" not in content