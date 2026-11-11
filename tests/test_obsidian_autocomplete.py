import html as html_lib
import pytest
from datetime import datetime
from utils.board_etl import parse_tasks

def test_all_subtask_inputs_bind_obsidian_datalist(client):
    """Verify subtask input template includes list attribute for autocomplete."""
    test_client, test_file = client

    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    test_file.write_text(
        f"* {today_str} Practice Set #focus\n"
        "  * [Song A](obsidian://open?vault=Music&file=SongA)\n"
        "  * [Song B](obsidian://open?vault=Music&file=SongB)\n"
        "\n# Done\n"
    )

    response = test_client.get('/')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'list="historical-obsidian-links"' in html

def test_extracts_obsidian_links_from_completed_section(client):
    """Verify parse_tasks collects unique Obsidian links from completed tasks."""
    test_client, test_file = client

    test_file.write_text(
        "* 11/10 Practice Guitar\n"
        "\n# Done\n"
        "x 11/09 Played [Blackbird](obsidian://open?vault=Music&file=Blackbird) #guitar\n"
        "x 11/08 Played [Dust in the Wind](obsidian://open?vault=Music&file=DustInTheWind)\n"
    )

    data = parse_tasks(str(test_file))
    links = data["obsidian_links"]

    assert len(links) == 2
    assert "[Blackbird](obsidian://open?vault=Music&file=Blackbird)" in links
    assert "[Dust in the Wind](obsidian://open?vault=Music&file=DustInTheWind)" in links

def test_obsidian_link_datalist_renders_in_dom(client):
    """Verify historical obsidian links datalist is rendered into modal templates."""
    test_client, test_file = client

    test_file.write_text(
        "* 11/10 Practice Fingerstyle\n"
        "\n# Done\n"
        "x 11/09 [Anji](obsidian://open?vault=Music&file=Anji)\n"
    )

    response = test_client.get('/')
    assert response.status_code == 200

    html_content = response.get_data(as_text=True)
    assert 'id="historical-obsidian-links"' in html_content
    
    # Verify option value is present in rendered datalist
    expected_link = "[Anji](obsidian://open?vault=Music&file=Anji)"
    assert expected_link in html_content or html_lib.escape(expected_link) in html_content