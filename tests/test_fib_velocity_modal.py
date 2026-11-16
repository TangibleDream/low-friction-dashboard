import pytest
from datetime import datetime, timedelta

def test_fib_velocity_api_empty_file(client):
    """Test API response when tasks.txt has no completed tasks."""
    test_client, test_file = client
    test_file.write_text("* 10/31 Uncompleted task #fib:3\n\n# Done\n")

    response = test_client.get('/api/fib_velocity')
    assert response.status_code == 200
    
    data = response.get_json()
    assert "weeks" in data
    assert "points" in data
    assert len(data["weeks"]) == 0
    assert len(data["points"]) == 0

def test_fib_velocity_api_calculates_sunday_buckets(client):
    """Test that completed fib tasks are grouped correctly into Sunday-ending weeks."""
    test_client, test_file = client
    
    # Generate past Sunday dates
    today = datetime.now().date()
    days_since_sunday = (today.weekday() + 1) % 7
    last_closed_sunday = today - timedelta(days=days_since_sunday if days_since_sunday > 0 else 7)
    prev_sunday = last_closed_sunday - timedelta(weeks=1)

    # Format dates as M/D strings
    date1_str = f"{prev_sunday.month}/{prev_sunday.day}"
    date2_str = f"{last_closed_sunday.month}/{last_closed_sunday.day}"

    # Write completed tasks under # Done
    test_file.write_text(
        f"* Active task\n\n# Done\n"
        f"x * {date1_str} Guitar practice #fib:3\n"
        f"x * {date1_str} Code review #fib:5\n"
        f"x * {date2_str} Mandolin practice #fib:2\n"
    )

    response = test_client.get('/api/fib_velocity')
    assert response.status_code == 200

    data = response.get_json()
    assert len(data["weeks"]) >= 2
    
    # Verify points were aggregated for the Sunday buckets
    assert 8 in data["points"]  # 3 + 5 from prev_sunday
    assert 2 in data["points"]  # 2 from last_closed_sunday

def test_fib_velocity_returns_daily_bars_per_sunday_week(client):
    """Verify /api/fib_velocity returns 7 daily totals per week aligned to each Sunday."""
    test_client, test_file = client

    today = datetime.now().date()
    days_since_sunday = (today.weekday() + 1) % 7
    last_sunday = today - timedelta(days=days_since_sunday)
    monday_of_that_week = last_sunday - timedelta(days=6)
    wednesday_of_that_week = last_sunday - timedelta(days=4)

    mon_str = f"{monday_of_that_week.month}/{monday_of_that_week.day}"
    wed_str = f"{wednesday_of_that_week.month}/{wednesday_of_that_week.day}"
    sun_str = f"{last_sunday.month}/{last_sunday.day}"

    test_file.write_text(
        "# Done\n"
        f"x {mon_str} Monday Task #fib:3\n"
        f"x {wed_str} Wednesday Task #fib:5\n"
        f"x {sun_str} Sunday Task #fib:2\n"
    )

    response = test_client.get("/api/fib_velocity")
    assert response.status_code == 200

    payload = response.get_json()
    assert "daily_points" in payload
    assert len(payload["daily_points"]) >= 1

    last_week_days = payload["daily_points"][-1]
    assert len(last_week_days) == 7
    assert last_week_days[0] == 3  # Monday
    assert last_week_days[2] == 5  # Wednesday
    assert last_week_days[6] == 2  # Sunday
    assert sum(last_week_days) == payload["points"][-1]

def test_stats_button_and_modal_markup_present(client):
    """Test that the main page renders the Stats button, modal markup, and SVG chart elements."""
    test_client, _ = client

    response = test_client.get('/')
    assert response.status_code == 200

    html = response.get_data(as_text=True)

    # Verify Stats trigger button
    assert 'data-bs-target="#statsModal"' in html
    assert '📊 Stats' in html

    # Verify Modal container
    assert 'id="statsModal"' in html
    assert 'Weekly Fibonacci Velocity' in html

    # Verify Rolling Window Input with default value of 2
    assert 'id="rollingWeeksInput"' in html
    assert 'value="2"' in html

    # Verify SVG Chart Container
    assert 'id="velocitySvgChart"' in html
    assert 'id="chartContainer"' in html

def test_stats_modal_javascript_hooks(client):
    """Test that client-side JavaScript functions for fetching and rendering the velocity chart are embedded."""
    test_client, _ = client

    response = test_client.get('/')
    assert response.status_code == 200

    html = response.get_data(as_text=True)

    # Verify key JS lifecycle functions and keys
    assert '/api/fib_velocity' in html
    assert 'fib_velocity_rolling_weeks' in html
    assert 'renderVelocityChart' in html

def test_stats_modal_renders_dual_weekly_and_daily_charts(client):
    """Verify stats modal contains both weekly and daily SVG charts with weeks-back roller."""
    test_client, _ = client

    response = test_client.get("/")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'id="velocitySvgChart"' in html
    assert 'id="dailyVelocitySvgChart"' in html
    assert 'id="dailyWeeksBackInput"' in html
    assert 'value="1"' in html