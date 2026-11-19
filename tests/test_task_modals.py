import pytest
import web_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    test_file = tmp_path / "tasks.txt"
    test_file.write_text("! 11/18 Sample task #daily\n")
    monkeypatch.setattr(web_app, "TASK_FILE", test_file)
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c, test_file


def test_create_task_modal_has_all_required_form_fields(client):
    """Prevent regression where #addTaskModal was truncated to only the subtasks field."""
    test_client, _ = client
    res = test_client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    required_create_ids = [
        'id="addTaskModal"',
        'id="create-task-form"',
        'id="task-preserve-subtasks"',
        'id="task-date"',
        'id="task-type"',
        'id="task-desc"',
        'id="task-tags-input"',
        'id="task-fib-score"',
        'id="subtasks-container"',
        'id="btn-save-task"',
    ]
    for element_id in required_create_ids:
        assert element_id in html, f"Missing {element_id} in Create Task Modal"


def test_add_subtask_buttons_and_handlers_present_for_create_and_edit(client):
    """Verify both Create and Edit modals have functional + Add Subtask buttons and JS handlers."""
    test_client, _ = client
    res = test_client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Buttons in markup
    assert 'id="btn-add-subtask-field"' in html
    assert 'id="btn-add-edit-subtask-field"' in html
    assert 'id="btn-calc-steps-add"' in html
    assert 'id="btn-calc-steps-edit"' in html

    # Click listener wiring for both + Add Subtask buttons
    assert "e.target.id === 'btn-add-subtask-field'" in html
    assert "e.target.id === 'btn-add-edit-subtask-field'" in html
    assert "createSubtaskInputRow" in html