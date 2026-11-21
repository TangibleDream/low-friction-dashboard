import calendar
from datetime import datetime
import pytest
import web_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_file = tmp_path / "tasks.txt"
    test_file.write_text("# Done\n")
    monkeypatch.setattr(web_app, "TASK_FILE", test_file)
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c, test_file


def test_monthly_water_consistency_excludes_current_month_and_deduplicates_days(client):
    """Verify /api/fib_velocity scrapes 'Drink Water', deduplicates same-day entries, and excludes active month."""
    test_client, test_file = client

    now = datetime.now()
    prev_month = 12 if now.month == 1 else now.month - 1
    prev_year = now.year - 1 if now.month == 1 else now.year
    days_in_prev_month = calendar.monthrange(prev_year, prev_month)[1]

    test_file.write_text(
        "# Done\n"
        f"x ! {prev_month}/1 09:00 Drink Water #daily\n"
        f"x ! {prev_month}/1 17:00 Drink Water #daily\n"
        f"x ! {prev_month}/4 10:00 drink water #health\n"
        f"x ! {prev_month}/10 12:00 Drink Water\n"
        f"x ! {now.month}/1 10:00 Drink Water #daily\n"
    )

    response = test_client.get("/api/fib_velocity")
    assert response.status_code == 200

    payload = response.get_json()
    monthly_water = payload["monthly_water"]

    current_ym = f"{now.year}-{now.month:02d}"
    assert all(m["month"] != current_ym for m in monthly_water)

    assert len(monthly_water) == 1
    entry = monthly_water[0]
    assert entry["yes_days"] == 3
    assert entry["total_days"] == days_in_prev_month
    assert entry["percentage"] == round((3 / days_in_prev_month) * 100, 1)


def test_monthly_water_ribbon_markup_and_js_present(client):
    """Verify #statsModal renders the Monthly Water Consistency ribbon and roller."""
    test_client, _ = client
    res = test_client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert "Monthly Water Consistency" in html
    assert 'id="waterMonthsBackInput"' in html
    assert 'id="waterMonthLabel"' in html
    assert 'id="waterFractionText"' in html
    assert 'id="waterMonthlyPct"' in html
    assert "renderMonthlyWaterRibbon" in html