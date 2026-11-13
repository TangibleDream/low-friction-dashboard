from datetime import datetime
from utils.board_etl import parse_tasks
import pytest


def test_parse_tasks_extracts_historical_tags(tmp_path):
    """Verify parse_tasks collects unique tags across active and completed tasks while filtering system tags."""
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    task_file = tmp_path / "tasks.txt"
    task_file.write_text(
        f"* {today_str} Write unit tests #coding #python #focus #priority\n"
        f"* {today_str} Water figs #garden #2-days\n"
        "\n# Done\n"
        f"x {today_str} Practice fingerstyle #guitar #music\n"
    )

    data = parse_tasks(str(task_file))
    tags = data["all_tags"]

    assert "coding" in tags
    assert "python" in tags
    assert "garden" in tags
    assert "2-days" in tags
    assert "guitar" in tags
    assert "music" in tags

    # System state tags should be excluded
    assert "focus" not in tags
    assert "priority" not in tags
    assert "Done" not in tags


def test_historical_tags_datalist_renders_in_modals(client):
    """Verify historical tags datalist and input list bindings render in the HTML."""
    test_client, test_file = client

    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    test_file.write_text(
        f"* {today_str} Morning routine #daily #health\n"
        "\n# Done\n"
        f"x {today_str} Old task #archived_tag\n"
    )

    response = test_client.get("/")
    assert response.status_code == 200

    html = response.get_data(as_text=True)

    # Verify datalist and input bindings exist
    assert 'id="historical-tags-list"' in html
    assert 'list="historical-tags-list"' in html

    # Verify extracted tags appear as <option> values
    assert '<option value="daily"></option>' in html
    assert '<option value="health"></option>' in html
    assert '<option value="archived_tag"></option>' in html