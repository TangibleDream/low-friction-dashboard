from datetime import datetime
from utils.board_etl import parse_tasks

def test_daily_fibonacci_completion_and_remaining_calculation(client):
    """Verify today_fib_completed and today_fib_remaining aggregation."""
    test_client, test_file = client

    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    test_file.write_text(
        f"* {today_str} Active Task 1 #fib:3\n"
        f"* {today_str} Active Task 2 #fib:5\n"
        "\n# Done\n"
        f"x {today_str} Completed Task #fib:2\n"
    )

    data = parse_tasks(str(test_file))
    assert data["today_fib_remaining"] == 8
    assert data["today_fib_completed"] == 2
    