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