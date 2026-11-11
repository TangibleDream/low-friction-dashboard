import pytest
from utils.board_etl import parse_tasks

def test_daily_fibonacci_completion_and_remaining_calculation(client):
    """Verify today_fib_completed and today_fib_remaining aggregation."""
    test_client, test_file = client

    test_file.write_text(
        "* 11/10 Active Task 1 #fib:3\n"
        "* 11/10 Active Task 2 #fib:5\n"
        "\n# Done\n"
        "x 11/10 Completed Task #fib:2\n"
    )

    data = parse_tasks(str(test_file))
    assert data["today_fib_remaining"] == 8
    assert data["today_fib_completed"] == 2

def test_daily_fibonacci_badges_render_in_header(client):
    """Verify daily fibonacci badges render in the header bar."""
    test_client, test_file = client

    test_file.write_text(
        "* 11/10 Active Task #fib:8\n"
        "\n# Done\n"
        "x 11/10 Finished Task #fib:5\n"
    )

    response = test_client.get('/')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "Done:" in html
    assert "Remaining:" in html


from utils.board_etl import parse_tasks
from datetime import datetime

def test_daily_fibonacci_completed_only_counts_today(client):
    """Verify today_fib_completed ignores items completed on prior dates."""
    test_client, test_file = client

    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    test_file.write_text(
        "* 11/10 Active Task #fib:5\n"
        "\n# Done\n"
        f"x {today_str} Completed Today #fib:3\n"
        "x 10/15 Completed Past Month #fib:13\n"
        "x 11/01 Completed Last Week #fib:8\n"
    )

    data = parse_tasks(str(test_file))
    assert data["today_fib_completed"] == 3
    assert data["today_fib_remaining"] == 5