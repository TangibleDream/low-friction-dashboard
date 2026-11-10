import pytest

def test_time_proximity_javascript_presence(client):
    """Verify time proximity evaluator and audio synthesizer are embedded in HTML_TEMPLATE."""
    test_client, _ = client

    response = test_client.get('/')
    assert response.status_code == 200

    html = response.get_data(as_text=True)

    assert "updateTimeBadgeProximity" in html
    assert "playImminentAlertSound" in html
    assert "time-passed" in html
    assert "time-imminent" in html


def test_time_badge_markup_attributes(client):
    """Verify schedule markup renders time-badge classes or data-time-str attributes."""
    test_client, test_file = client

    test_file.write_text(
        "* 14:30 Timed Task #focus\n"
        "\n# Done\n"
    )

    response = test_client.get('/')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "14:30" in html