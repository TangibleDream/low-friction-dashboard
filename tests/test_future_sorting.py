from datetime import datetime, timedelta
from utils.board_etl import parse_tasks


def test_future_tasks_sorted_chronologically_by_date_and_time(tmp_path):
    """Verify future tasks sort by date ascending, then time ascending, then priority/#ord."""
    now = datetime.now()
    in_1_day = now + timedelta(days=1)
    in_2_days = now + timedelta(days=2)
    in_5_days = now + timedelta(days=5)

    d1 = f"{in_1_day.month}/{in_1_day.day}"
    d2 = f"{in_2_days.month}/{in_2_days.day}"
    d5 = f"{in_5_days.month}/{in_5_days.day}"

    task_file = tmp_path / "tasks.txt"
    task_file.write_text(
        f"* {d5} Far Future Low Ord #ord:100\n"
        f"* {d1} Tomorrow Untimed Priority #priority #ord:200\n"
        f"* {d2} Two Days Out #ord:150\n"
        f"* {d1} 16:00 Tomorrow Afternoon #ord:859\n"
        f"* {d1} 09:30 Tomorrow Morning #ord:900\n"
        f"* {d1} Tomorrow Untimed Regular #ord:300\n"
    )

    data = parse_tasks(str(task_file))
    titles = [t["title"] for t in data["future"]]

    assert titles == [
        "Tomorrow Morning",
        "Tomorrow Afternoon",
        "Tomorrow Untimed Priority",
        "Tomorrow Untimed Regular",
        "Two Days Out",
        "Far Future Low Ord",
    ]