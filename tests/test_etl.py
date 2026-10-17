from datetime import datetime, timedelta
from utils.board_etl import (
    insert_date_at_front,
    complete_task,
    delete_line,
    make_line_today,
    move_line_to_bottom,
    parse_tasks,
    shift_line_to_tomorrow,
    toggle_line_focus,
)

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