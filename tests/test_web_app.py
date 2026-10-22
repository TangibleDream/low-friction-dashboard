import pytest
from datetime import datetime
from utils.board_etl import complete_task

today_str = f"{datetime.now().month}/{datetime.now().day}"

@pytest.fixture
def client(tmp_path, monkeypatch):
    test_file = tmp_path / "tasks.txt"
    test_file.write_text(
        "* 6 guitar net 2 pieces @skill-building\n"
        "    * We Sing Hallelujah vs Uncle John's Band\n"
        "* Put away laundry @home #focus\n"
    )
    
    import web_app
    monkeypatch.setattr(web_app, 'TASK_FILE', test_file)
    web_app.app.config['TESTING'] = True
    
    with web_app.app.test_client() as test_client:
        yield test_client, test_file

def test_add_task_defaults_to_today_when_date_omitted(client):
    test_client, test_file = client

    response = test_client.post('/add_task', json={
        "symbol": "*",
        "description": "Inspect garden soil",
        "tags": ["home"]
    })

    assert response.status_code == 200

    content = test_file.read_text()
    today_dt = datetime.now()
    today_str = f"{today_dt.month}/{today_dt.day}"

    assert f"* {today_str} Inspect garden soil #home" in content
    
def test_add_task_does_not_leak_subtasks_from_edit_modal(client):
    test_client, test_file = client

    # 1. Edit an existing task to attach subtasks
    edit_response = test_client.post('/edit_task', json={
        "old_raw": "* Put away laundry @home #focus",
        "date": "2026-10-20",
        "symbol": "*",
        "description": "Put away laundry",
        "tags": ["home"],
        "subtasks": ["Fold shirts", "Match socks", "Hang jackets"]
    })
    assert edit_response.status_code == 200

    # 2. Post a new task without subtasks
    add_response = test_client.post('/add_task', json={
        "date": "2026-10-20",
        "symbol": "*",
        "description": "Clean kitchen counters",
        "tags": ["home"],
        "subtasks": []
    })
    assert add_response.status_code == 200

    # 3. Verify the new task block in tasks.txt does not inherit edit subtasks
    content = test_file.read_text()
    lines = content.splitlines()

    new_task_idx = None
    for idx, line in enumerate(lines):
        if "Clean kitchen counters" in line:
            new_task_idx = idx
            break

    assert new_task_idx is not None, "New task was not written to file"

    # Inspect lines directly under the new task to confirm no leaked subtasks
    following_lines = lines[new_task_idx + 1:new_task_idx + 4]
    for follow_line in following_lines:
        assert "Fold shirts" not in follow_line
        assert "Match socks" not in follow_line
        assert "Hang jackets" not in follow_line
        
def test_complete_daily_task_route(client):
    test_client, test_file = client
    test_file.write_text("* 10/17 Check for ripe figs #Daily #focus\n\n# Done\n")

    response = test_client.post('/complete_task', json={
        "raw_line": "* 10/17 Check for ripe figs #Daily #focus"
    })

    assert response.status_code == 200

    content = test_file.read_text()
    tomorrow = datetime.now()
    tomorrow_str = f"{datetime.now().month}/{datetime.now().day + 1}"

    # Confirm recurring task spawned for tomorrow
    assert f"* {tomorrow_str} Check for ripe figs #Daily" in content
    # Confirm completed entry moved under # Done without #focus
    assert "x * 10/17 Check for ripe figs #Daily" in content

def test_complete_main_task(client):
    test_client, test_file = client

    response = test_client.post('/complete_task', json={
        "raw_line": "* Put away laundry @home #focus"
    })

    assert response.status_code == 200
    file_content = test_file.read_text()
    # Confirm task moved under # Done and #focus was stripped
    assert f"x * {today_str} Put away laundry @home" in file_content

def test_complete_subtask_with_single_quote(client):
    test_client, test_file = client

    response = test_client.post('/complete_subtask', json={
        "parent_title": "6 guitar net 2 pieces",
        "subtask": "We Sing Hallelujah vs Uncle John's Band"
    })

    assert response.status_code == 200

    file_content = test_file.read_text()
    assert "# Done" in file_content
    assert f"x * {today_str} 6 guitar net 2 pieces @skill-building" in file_content

def test_edit_future_task_route(client):
    test_client, test_file = client
    test_file.write_text("* 11/15 Board sync @admin #3rd-Sunday\n\n# Done\n")

    response = test_client.post('/edit_task', json={
        "old_raw": "* 11/15 Board sync @admin #3rd-Sunday",
        "date": "2026-11-22",
        "symbol": "!",
        "description": "Executive Board sync",
        "tags": ["admin", "4th-Sunday"],
        "subtasks": ["Review Q4 metrics"]
    })

    assert response.status_code == 200

    content = test_file.read_text()
    assert "Board sync @admin" not in content
    assert "! 11/22 Executive Board sync #admin #4th-Sunday" in content
    assert "  * Review Q4 metrics" in content
    
def test_edit_task_route(client):
    test_client, test_file = client
    test_file.write_text("* 10/19 Old description @admin #focus\n\n# Done\n")

    response = test_client.post('/edit_task', json={
        "old_raw": "* 10/19 Old description @admin #focus",
        "date": "2026-10-20",
        "symbol": "!",
        "description": "Updated description",
        "tags": ["priority", "work"],
        "subtasks": ["Subtask A"]
    })

    assert response.status_code == 200

    content = test_file.read_text()
    # Confirm old task is replaced by new formatted entry
    assert "Old description" not in content
    assert "! 10/20 Updated description #priority #work" in content
    assert "  * Subtask A" in content