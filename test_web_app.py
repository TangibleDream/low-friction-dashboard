import pytest
from web_app import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    test_file = tmp_path / "tasks.txt"
    initial_content = (
        "* 6 guitar net 2 pieces @skill-building\n"
        "    * We Sing Hallelujah vs Uncle John's Band\n"
        "* Put away laundry @home #focus\n"
    )
    test_file.write_text(initial_content)
    
    monkeypatch.setattr("web_app.TASK_FILE", test_file)
    
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client, test_file

def test_complete_subtask_with_single_quote(client):
    test_client, test_file = client

    # Completing the subtask with an apostrophe/single quote
    response = test_client.post('/complete_subtask', json={
        "parent_title": "6 guitar net 2 pieces",
        "subtask": "We Sing Hallelujah vs Uncle John's Band"
    })

    assert response.status_code == 200
    
    # Since it was the last subtask under 6 guitar, the parent task auto-completes
    file_content = test_file.read_text()
    assert "# Done" in file_content
    assert "x * 6 guitar net 2 pieces @skill-building" in file_content

def test_complete_main_task(client):
    test_client, test_file = client

    response = test_client.post('/complete_task', json={
        "raw_line": "* Put away laundry @home #focus"
    })

    assert response.status_code == 200
    file_content = test_file.read_text()
    assert "x * Put away laundry @home #focus" in file_content