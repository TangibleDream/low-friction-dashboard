import pytest

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
