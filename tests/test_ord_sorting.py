import pytest
from utils.board_etl import parse_line_ord, parse_tasks

def test_parse_line_ord_extraction():
    """Verify numeric extraction from #ord tags."""
    assert parse_line_ord("* 11/05 Task A #ord:10") == 10.0
    assert parse_line_ord("* 11/05 Task B #ord:15.5") == 15.5
    assert parse_line_ord("* 11/05 Task C #ord:0") == float('inf')
    assert parse_line_ord("* 11/05 Task D #daily") == float('inf')


def test_ord_sorting_hierarchy(client):
    """Test that Priority > Low #ord > High #ord > Unordered items."""
    test_client, test_file = client

    test_file.write_text(
        "* 11/05 Standard Unordered B\n"
        "* 11/05 Step 2 #ord:20\n"
        "! 11/05 Priority Commitment #priority\n"
        "* 11/05 Step 1 #ord:10\n"
        "* 11/05 Intermediate Step #ord:15\n"
        "* 11/05 Standard Unordered A\n"
        "\n# Done\n"
    )

    data = parse_tasks(str(test_file))
    today_titles = [t["title"] for t in data["today"]]

    # Expected order:
    # 1. Priority Commitment
    # 2. Step 1 (#ord:10)
    # 3. Intermediate Step (#ord:15)
    # 4. Step 2 (#ord:20)
    # 5. Standard Unordered B (preserved order)
    # 6. Standard Unordered A (preserved order)
    
    assert today_titles[0] == "Priority Commitment"
    assert today_titles[1] == "Step 1"
    assert today_titles[2] == "Intermediate Step"
    assert today_titles[3] == "Step 2"
    assert "Standard Unordered B" in today_titles[4:]
    assert "Standard Unordered A" in today_titles[4:]


def test_fractional_ord_insertion(client):
    """Verify inserting a fractional #ord:15 places it between #ord:10 and #ord:20."""
    test_client, test_file = client

    test_file.write_text(
        "* 11/05 Task 20 #ord:20\n"
        "* 11/05 Task 10 #ord:10\n"
        "* 11/05 Task 15 #ord:15\n"
        "\n# Done\n"
    )

    data = parse_tasks(str(test_file))
    titles = [t["title"] for t in data["today"]]

    assert titles == ["Task 10", "Task 15", "Task 20"]