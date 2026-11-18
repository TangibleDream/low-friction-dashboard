import pytest
import web_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_file = tmp_path / "tasks.txt"
    test_file.write_text("! 11/18 Walk 10000 steps #daily #steps\n")
    monkeypatch.setattr(web_app, "TASK_FILE", test_file)
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c, test_file


def test_step_calculator_buttons_rendered(client):
    """Verify the footprint Calculate Steps buttons exist in both Create and Edit modals."""
    test_client, _ = client
    res = test_client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert 'id="btn-calc-steps-add"' in html
    assert 'id="btn-calc-steps-edit"' in html
    assert 'generateStepSubtasks' in html


def test_edit_task_persists_calculated_step_subtasks(client):
    """Verify /edit_task saves the half-remaining step milestones under the updated task."""
    test_client, test_file = client
    res = test_client.post(
        "/edit_task",
        json={
            "old_raw": "! 11/18 Walk 10000 steps #daily #steps",
            "date": "2026-11-18",
            "symbol": "!",
            "description": "Walk 11000 steps",
            "tags": ["daily", "steps"],
            "subtasks": [
                "Walk 5500",
                "Walk 8250",
                "Walk 9625",
                "Walk 10312.5",
                "Walk 10656.2",
            ],
        },
    )
    assert res.status_code == 200
    content = test_file.read_text()
    assert "! 11/18 Walk 11000 steps #daily #steps" in content
    assert "  * Walk 5500" in content
    assert "  * Walk 10656.2" in content