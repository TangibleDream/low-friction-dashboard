import pytest
from datetime import datetime, timedelta
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

def test_add_task_with_fibonacci_score(client):
    test_client, test_file = client

    response = test_client.post('/add_task', json={
        "symbol": "*",
        "description": "Implement fibonacci points",
        "tags": ["feature", "fib:8"]
    })

    assert response.status_code == 200

    content = test_file.read_text()
    assert "#fib:8" in content
    assert "Implement fibonacci points" in content

def test_add_task_with_preserve_subtasks_tag(client):
    test_client, test_file = client

    response = test_client.post('/add_task', json={
        "symbol": "*",
        "description": "Practice Guitar Repertoire",
        "tags": ["music", "preserve_subtasks"],
        "subtasks": ["Bakers Street"]
    })

    assert response.status_code == 200
    content = test_file.read_text()
    assert "#preserve_subtasks" in content

def test_edit_modal_template_has_preserve_subtasks_control(client):
    test_client, test_file = client

    response = test_client.get('/')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    # Check that the checkbox and script references exist cleanly in rendered index HTML
    assert 'id="edit-task-preserve-subtasks"' in html
    assert 'edit-task-preserve-subtasks' in html

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

def test_completing_last_subtask_keeps_main_task_open(client):
    test_client, test_file = client
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    # Setup parent task with exactly 1 subtask
    test_file.write_text(f"* {today_str} Mandolin practice\n  * Practice fingerpicking pattern\n\n# Done\n")

    response = test_client.post('/complete_subtask', json={
        "parent_title": "Mandolin practice",
        "subtask": "Practice fingerpicking pattern",
        "preserve_subtasks": False  # Explicitly disable retention for raw removal assertion
    })

    assert response.status_code == 200

    content = test_file.read_text()

    # Subtask should be completely removed from file
    assert "Practice fingerpicking pattern" not in content

    # Main parent task MUST remain active and NOT be moved under # Done
    assert f"* {today_str} Mandolin practice" in content
    assert f"x * {today_str} Mandolin practice" not in content
    
    # Subtask should be removed
    assert "Practice fingerpicking pattern" not in content
    
    # Main parent task MUST remain active and NOT be moved under # Done
    assert f"* {today_str} Mandolin practice" in content
    assert f"x * {today_str} Mandolin practice" not in content

def test_complete_main_task(client):
    test_client, test_file = client

    response = test_client.post('/complete_task', json={
        "raw_line": "* Put away laundry @home #focus"
    })

    assert response.status_code == 200
    file_content = test_file.read_text()
    # Confirm task moved under # Done and #focus was stripped
    assert f"x * {today_str} Put away laundry @home" in file_content

@pytest.mark.parametrize("toggle_state,expected_moved", [
    (True, True),   # Yes -> Moved to Done
    (False, False)  # No -> Not Moved to Done
])
def test_complete_subtask_toggle_behavior(client, toggle_state, expected_moved):
    test_client, test_file = client
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    test_file.write_text(f"* {today_str} Job Applications @career\n  * Senior SDET at Acme\n\n# Done\n")

    response = test_client.post('/complete_subtask', json={
        "parent_title": "Job Applications",
        "subtask": "Senior SDET at Acme",
        "preserve_subtasks": toggle_state
    })

    assert response.status_code == 200
    content = test_file.read_text()

    # Active parent subtask list should no longer contain the subtask
    assert "  * Senior SDET at Acme" not in content

    if expected_moved:
        # Appended under # Done as a recorded completed subtask entry
        assert "✓ Senior SDET at Acme" in content
    else:
        # Not moved to # Done
        assert "✓ Senior SDET at Acme" not in content

def test_complete_subtask_with_embedded_markdown_link(client):
    test_client, test_file = client
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    parent_line = f"* {today_str} Google @home"
    sub_line = "Review [Google](https://www.google.com)"
    test_file.write_text(f"{parent_line}\n  * {sub_line}\n\n# Done\n")

    response = test_client.post('/complete_subtask', json={
        "parent_title": "Google",
        "subtask": sub_line,
        "preserve_subtasks": False
    })

    assert response.status_code == 200
    content = test_file.read_text()

    # Subtask line must be removed from tasks.txt
    assert "https://www.google.com" not in content

@pytest.mark.parametrize("toggle_state,expected_moved", [
    (True, True),   # Yes -> #preserve_subtasks tag present, subtasks moved to Done
    (False, False)  # No -> Tag omitted, subtasks discarded
])
def test_complete_main_task_with_incomplete_subtasks_toggle_behavior(client, toggle_state, expected_moved):
    test_client, test_file = client
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    tag_suffix = " #preserve_subtasks" if toggle_state else ""
    raw_parent = f"* {today_str} Guitar practice @music{tag_suffix}"
    test_file.write_text(f"{raw_parent}\n  * Bakers Street vs Wish You Were Here\n  * White Rabbit vs Whats Up\n\n# Done\n")

    response = test_client.post('/complete_task', json={
        "raw_line": raw_parent
    })

    assert response.status_code == 200
    content = test_file.read_text()

    if expected_moved:
        assert f"x {raw_parent}" in content
        assert "x * Bakers Street vs Wish You Were Here" in content
        assert "x * White Rabbit vs Whats Up" in content
    else:
        assert f"x {raw_parent}" in content
        assert "Bakers Street vs Wish You Were Here" not in content
        assert "White Rabbit vs Whats Up" not in content

def test_complete_subtask_with_single_quote(client):
    test_client, test_file = client

    # Setup parent task with single-quote subtask
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"
    test_file.write_text(f"* {today_str} 6 guitar net 2 pieces\n  * We Sing Hallelujah vs Uncle John's Band\n\n# Done\n")

    response = test_client.post('/complete_subtask', json={
        "parent_title": "6 guitar net 2 pieces",
        "subtask": "We Sing Hallelujah vs Uncle John's Band",
        "preserve_subtasks": False
    })

    assert response.status_code == 200

    file_content = test_file.read_text()

    # Subtask is completely removed
    assert "We Sing Hallelujah vs Uncle John's Band" not in file_content

    # Parent task stays open in place
    assert "6 guitar net 2 pieces" in file_content
    assert "x * " not in file_content

def test_complete_subtask_with_markdown_link(client):
    test_client, test_file = client
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    parent_line = f"* {today_str} Documentation Work"
    sub_line = "Review [Google](https://www.google.com)"
    test_file.write_text(f"{parent_line}\n  * {sub_line}\n\n# Done\n")

    response = test_client.post('/complete_subtask', json={
        "parent_title": "Documentation Work",
        "subtask": sub_line,
        "preserve_subtasks": False
    })

    assert response.status_code == 200
    content = test_file.read_text()
    assert sub_line not in content

def test_future_task_renders_links_and_does_not_spill(client):
    test_client, test_file = client
    
    # Seed a future task with a link to trigger the future tasks template block
    test_file.write_text("* 12/31 Future Task [Google](https://www.google.com)\n\n# Done\n")

    response = test_client.get('/')
    assert response.status_code == 200
    html_content = response.get_data(as_text=True)

    # Confirm truncation class and parsed link are present in the rendered HTML
    assert "text-truncate" in html_content
    assert "https://www.google.com" in html_content

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

    def test_render_obsidian_link_in_partial(client):
        test_client, test_file = client
        obsidian_uri = "obsidian://open?vault=obsidian&file=300%20Music%20MOC%2F360%20Instruments%20MOC%2F310%20Guitar%20MOC%2FApril%20Come%20She%20Will"
        
        test_file.write_text(f"* 10/23 Practiced ({obsidian_uri})[April Come She Will] #guitar\n")

        response = test_client.get('/partial')
        assert response.status_code == 200
        
        html = response.get_data(as_text=True)

        expected_anchor = f'<a href="{obsidian_uri}" target="_blank" class="text-info text-decoration-underline" onclick="event.stopPropagation();">April Come She Will</a>'
        
        # Verify exact anchor renders and raw syntax is removed
        assert expected_anchor in html
        assert f"({obsidian_uri})[April Come She Will]" not in html

def test_long_task_description_and_subtasks_have_truncation_classes(client):
    test_client, test_file = client
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"
    long_title = "A" * 150
    long_subtask = "B" * 150

    test_file.write_text(f"* {today_str} {long_title}\n  * {long_subtask}\n")

    response = test_client.get('/partial')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'task-title-cell' in html
    assert 'subtask-text-container' in html
    assert 'action-cell' in html

def test_partial_endpoint_serves_fresh_day_data(client):
    test_client, test_file = client
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    test_file.write_text(f"* {today_str} Morning routine #focus\n\n# Done\n")

    response = test_client.get('/partial')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "Morning routine" in html
    assert f"{now.month}/{now.day}" in html

def test_recurring_task_copies_preserve_subtasks_tag(client):
    test_client, test_file = client
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    raw_parent = f"* {today_str} Daily Songs #daily #preserve_subtasks"
    test_file.write_text(f"{raw_parent}\n  * Song A\n\n# Done\n")

    response = test_client.post('/complete_task', json={
        "raw_line": raw_parent,
        "preserve_subtasks": True
    })

    assert response.status_code == 200
    content = test_file.read_text()

    # Confirm recurring copy created for tomorrow retains #preserve_subtasks
    next_dt = now + timedelta(days=1)
    next_date_str = f"{next_dt.month}/{next_dt.day}"
    assert f"* {next_date_str} Daily Songs #daily #preserve_subtasks" in content

def test_render_obsidian_link_in_subtask(client):
    test_client, test_file = client
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"
    obsidian_uri = "obsidian://open?vault=obsidian&file=300%20Music%20MOC%2F360%20Instruments%20MOC%2F310%20Guitar%20MOC%2F16%20Military%20Wives"
    
    # Standard Markdown link order: [Label](URL) with dynamic today's date
    test_file.write_text(f"* {today_str} Guitar practice\n  * [16 Wives]({obsidian_uri}) vs. Yours\n")

    response = test_client.get('/partial')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)
    assert '<a href="obsidian://' in html
    assert '>16 Wives</a>' in html

def test_render_standard_markdown_link_order(client):
    test_client, test_file = client
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"
    obsidian_uri = "obsidian://open?vault=obsidian&file=test_note"
    
    test_file.write_text(f"* {today_str} Review [16 Wives]({obsidian_uri}) notes\n")

    response = test_client.get('/partial')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)

    # Verify anchor tag structure and label text are present in rendered HTML
    assert '<a href="obsidian://open?vault=obsidian' in html
    assert '>16 Wives</a>' in html
    assert f"[{obsidian_uri}]" not in html

def test_subtasks_render_with_aligned_action_container(client):
    test_client, test_file = client
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    test_file.write_text(f"* {today_str} Guitar practice\n  * Bakers Street vs Wish You Were Here\n")

    response = test_client.get('/partial')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'subtask-action-container' in html
    assert 'btn-complete-subtask' in html