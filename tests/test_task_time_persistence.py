import pytest
import web_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_file = tmp_path / "tasks.txt"
    test_file.write_text("! 11/17 18:00 Piprins #6-days #focus #fib:2\n")
    monkeypatch.setattr(web_app, "TASK_FILE", test_file)
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c, test_file


def test_edit_modal_prefills_data_time_and_renders_time_inputs(client):
    """Verify Create and Edit modals have time inputs and edit buttons expose data-time."""
    test_client, _ = client
    res = test_client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert 'id="task-time"' in html
    assert 'id="edit-task-time"' in html
    assert 'data-time="11/17 18:00"' in html or 'data-time="18:00"' in html


def test_edit_task_preserves_time_when_description_updated(client):
    """Verify editing a task's title/tags preserves its scheduled time in tasks.txt."""
    test_client, test_file = client
    res = test_client.post(
        "/edit_task",
        json={
            "old_raw": "! 11/17 18:00 Piprins #6-days #focus #fib:2",
            "date": "2026-11-17",
            "time": "18:00",
            "symbol": "!",
            "description": "Piprins Madrigal",
            "tags": ["7-days", "focus", "fib:2"],
            "subtasks": [],
        },
    )
    assert res.status_code == 200
    content = test_file.read_text()
    assert "! 11/17 18:00 Piprins Madrigal #7-days #focus #fib:2" in content


def test_add_task_persists_dedicated_time_field(client):
    """Verify /add_task writes the dedicated time field cleanly into tasks.txt."""
    test_client, test_file = client
    res = test_client.post(
        "/add_task",
        json={
            "date": "2026-11-19",
            "time": "09:30",
            "symbol": "*",
            "description": "Standup",
            "tags": ["work"],
            "subtasks": [],
        },
    )
    assert res.status_code == 200
    content = test_file.read_text()
    assert "* 11/19 09:30 Standup #work" in content

def test_frontend_serializes_time_and_all_edit_buttons_expose_data_time(client):
    """Ensure JS fetch payloads include time: timeVal and every rendered edit button exposes data-time."""
    test_client, _ = client
    res = test_client.get("/")
    html = res.get_data(as_text=True)

    # Both save and update JS payloads must send time: timeVal
    assert "body: JSON.stringify({ date: dateVal, time: timeVal," in html
    assert "time: timeVal," in html

    # Every rendered edit button (excluding the JS closest('.btn-edit-task') selector) must carry data-time
    edit_button_count = html.count("btn-edit-task") - html.count("closest('.btn-edit-task')")
    assert edit_button_count >= 1
    assert edit_button_count == html.count("data-time=")