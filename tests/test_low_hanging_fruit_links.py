from datetime import datetime

def test_low_hanging_fruit_renders_markdown_links(client):
    """Verify markdown links in quick/low_energy tasks are converted to clickable HTML links."""
    test_client, test_file = client

    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    test_file.write_text(
        f"* {today_str} [Google Time!](https://www.google.com) #quick #focus\n"
        "\n# Done\n"
    )

    response = test_client.get('/')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert '<a href="https://www.google.com"' in html
    assert 'Google Time!</a>' in html