from pathlib import Path
import pytest
from pytest_bdd import scenario, given, when, then, parsers

from board_etl import parse_tasks
from watcher import TaskFileHandler


@scenario('features/dashboard.feature', 'Categorize tasks with dates and standalone wait tags')
def test_task_categorization():
    """BDD scenario for testing real world task list structure."""
    pass


@scenario('features/dashboard.feature', 'Parse tasks with nested subtask breakdowns')
def test_subtask_parsing():
    """BDD scenario for testing subtask parsing."""
    pass


@scenario('features/dashboard.feature', 'Trigger dashboard refresh on file modification')
def test_file_watcher_trigger():
    """BDD scenario testing file watcher modification handling."""
    pass


@pytest.fixture
def task_file_path(tmp_path):
    return tmp_path / "tasks.txt"


@pytest.fixture
def parsed_tasks():
    return []


@given('a task file exists with the following content:')
def create_task_file(task_file_path, docstring):
    task_file_path.write_text(docstring)


@when('I process the task file')
def process_task_file(task_file_path, parsed_tasks):
    res = parse_tasks(str(task_file_path))
    active_tasks = res.get("today", res) if isinstance(res, dict) else res
    parsed_tasks.clear()
    parsed_tasks.extend(active_tasks)


@when('the task file is updated with new tasks')
def update_task_file(task_file_path):
    updated_content = (
        "! 09:00 Standup @work\n"
        "* Clean git branches @dev #quick\n"
    )
    task_file_path.write_text(updated_content)


@then(parsers.parse('I should identify {count:d} strongly scheduled task'))
@then(parsers.parse('I should identify {count:d} strongly scheduled tasks'))
def verify_strong_tasks(parsed_tasks, count):
    strong_tasks = [t for t in parsed_tasks if isinstance(t, dict) and t.get('symbol') == '!']
    assert len(strong_tasks) == count


@then(parsers.parse('I should identify {count:d} arbitrarily scheduled task with time "{expected_time}"'))
def verify_arbitrary_task_time(parsed_tasks, count, expected_time):
    arbitrary_tasks = [t for t in parsed_tasks if isinstance(t, dict) and t.get('symbol') == '?']
    assert len(arbitrary_tasks) == count
    assert arbitrary_tasks[0]['time'] == expected_time


@then(parsers.parse('I should find {count:d} gap filler task for standalone wait'))
def verify_standalone_wait(parsed_tasks, count):
    waiting_tasks = [
        t for t in parsed_tasks 
        if isinstance(t, dict) and any(tag == 'wait' or tag.startswith('wait:') for tag in t.get('tags', []))
    ]
    assert len(waiting_tasks) == count


@then(parsers.parse('the task "{task_title}" should have {count:d} subtasks'))
def verify_subtasks(parsed_tasks, task_title, count):
    target = next((t for t in parsed_tasks if isinstance(t, dict) and t.get('title') == task_title), None)
    assert target is not None
    assert len(target['subtasks']) == count


@then(parsers.parse('the task handler should parse {count:d} tasks'))
def verify_handler_parsing(task_file_path, count):
    handler = TaskFileHandler(task_file_path)
    res = parse_tasks(str(task_file_path))
    
    if isinstance(res, dict):
        # Total active tasks = today + future
        active_tasks = res.get("today", []) + res.get("future", [])
    else:
        active_tasks = res

    assert len(active_tasks) == count

def test_future_tasks_separation(tmp_path):
    test_file = tmp_path / "tasks.txt"
    test_file.write_text(
        "! 10:30 - 11:00 Today Sync @admin\n"
        "? 10/5 Visit Comcast @logistics #focus\n"
    )
    res = parse_tasks(str(test_file))
    
    # 10:30 - 11:00 is today, 10/5 is future
    assert len(res["today"]) == 1
    assert len(res["future"]) == 1
    assert res["today"][0]["title"] == "Today Sync"
    assert res["future"][0]["title"] == "Visit Comcast"