from unittest.mock import MagicMock, patch

from my_agent.tools.advanced_search import (
    check_eligibility_semantic,
    get_competitor_intelligence,
)

# --- Test Data ---

# Mock HTML for a grant that IS restricted to non-profits
RESTRICTED_HTML = """
<html>
<body>
    <h1>Grant Opportunity 123</h1>
    <div id="eligibility">
        <h2>Eligibility Information</h2>
        <p>Eligible Applicants: Non-profit organizations only. 501(c)(3) status is required.</p>
    </div>
</body>
</html>
"""

# Mock HTML for a grant that IS OPEN to for-profits
OPEN_HTML = """
<html>
<body>
    <h1>Grant Opportunity 456</h1>
    <div id="eligibility">
        <h2>Who May Apply</h2>
        <p>State governments, Small businesses, For-profit organizations other than small businesses.</p>
    </div>
</body>
</html>
"""

# --- Tests ---


def test_check_eligibility_semantic_knockout():
    """Test that the tool correctly flags a non-profit restricted grant."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = RESTRICTED_HTML.encode("utf-8")
        mock_get.return_value = mock_response

        # Run the tool
        result = check_eligibility_semantic("http://fake-url.com/restricted")

        # Assertions
        assert "❌ ELIGIBILITY WARNINGS" in result
        assert "KNOCKOUT: Seems restricted to Non-Profits/501(c)(3)" in result


def test_check_eligibility_semantic_pass():
    """Test that the tool passes a grant open to businesses."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = OPEN_HTML.encode("utf-8")
        mock_get.return_value = mock_response

        # Run the tool
        result = check_eligibility_semantic("http://fake-url.com/open")

        # Assertions
        assert "✅ ELIGIBILITY CHECK PASSED" in result
        assert "not in result" not in result  # Double negative check


def test_get_competitor_intelligence_success():
    """Test that we can parse a valid response from USAspending."""
    mock_api_response = {
        "results": [
            {"Recipient Name": "Big Defense Corp", "Award Amount": 5000000},
            {"Recipient Name": "University of Tech", "Award Amount": 120000},
        ]
    }

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_response
        mock_post.return_value = mock_response

        # Run tool with a fake CFDA
        result = get_competitor_intelligence(cfda_number="12.345")

        # Assertions
        assert "Big Defense Corp" in result
        assert "$5,000,000.00" in result
        assert "University of Tech" in result


def test_get_competitor_intelligence_no_results():
    """Test handling of empty API results."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_post.return_value = mock_response

        result = get_competitor_intelligence(keyword="SimulatedUnobtainium")

        assert "No direct competitor data found" in result


if __name__ == "__main__":
    # Manually running tests if executed as script
    print("Running Manual Tests...")
    try:
        test_check_eligibility_semantic_knockout()
        print("PASS: Restricted Grant Check")
        test_check_eligibility_semantic_pass()
        print("PASS: Open Grant Check")
        test_get_competitor_intelligence_success()
        print("PASS: Competitor Data Parse")
        test_get_competitor_intelligence_no_results()
        print("PASS: Empty Competitor Data")
        print("ALL TESTS PASSED!")
    except AssertionError as e:
        print(f"FAILED: {e}")
    except Exception as e:
        print(f"ERROR: {e}")
