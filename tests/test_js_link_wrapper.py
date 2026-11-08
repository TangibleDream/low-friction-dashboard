import pytest

def test_link_wrapper_javascript_presence(client):
    """Verify that the auto-wrapping keydown event listener script is embedded in HTML_TEMPLATE."""
    test_client, _ = client

    response = test_client.get('/')
    assert response.status_code == 200

    html = response.get_data(as_text=True)

    # Verify keydown listener logic exists in JavaScript
    assert "e.key === '['" in html
    assert "target.selectionStart !== target.selectionEnd" in html
    assert "target.setSelectionRange" in html


def test_link_wrapper_targets_text_inputs(client):
    """Verify the script attaches event listeners to text input or textarea selectors."""
    test_client, _ = client

    response = test_client.get('/')
    assert response.status_code == 200

    html = response.get_data(as_text=True)

    # Verify script listens at document level for inputs/textareas
    assert "document.addEventListener('keydown'" in html or 'document.addEventListener("keydown"' in html
    assert "target.tagName === 'INPUT'" in html or 'target.tagName === "INPUT"' in html