import csv
import json
import os
from io import StringIO

import pytest

from alphavantage_mcp_server.api import fetch_earnings_calendar, fetch_earnings_call_transcript


@pytest.mark.asyncio
async def test_fetch_earnings_call_transcript():
    """Test fetching earnings call transcript with real API call."""
    data = await fetch_earnings_call_transcript(symbol="IBM", quarter="2024Q1")

    assert isinstance(data, dict), "API should return JSON data as string"


    assert "symbol" in data, "JSON should contain 'symbol' field"
    assert "quarter" in data, "JSON should contain 'quarter' field"
    assert "transcript" in data, "JSON should contain 'transcript' field"

    assert data["symbol"] == "IBM", "Should find IBM data in the response"
    assert data["transcript"], "Transcript should not be empty"

    first_entry = data["transcript"][0]
    required_fields = ["speaker", "title", "content", "sentiment"]
    for field in required_fields:
        assert field in first_entry, f"Field '{field}' missing from transcript entry"

    assert first_entry["content"], "Transcript content should not be empty"

@pytest.mark.asyncio
async def test_fetch_earnings_calendar():
    """Test fetching earnings calendar with real API call."""
    api_key = os.getenv('ALPHAVANTAGE_API_KEY')
    assert api_key, "ALPHAVANTAGE_API_KEY must be set in environment"

    result = await fetch_earnings_calendar(symbol="AAPL", horizon="3month")

    assert isinstance(result, str), "API should return CSV data as string"

    # Parse CSV data
    csv_reader = csv.DictReader(StringIO(result))
    rows = list(csv_reader)

    # Basic validation of structure
    assert rows, "CSV should contain at least one row"

    # Check required fields in first row
    first_row = rows[0]
    required_fields = ["symbol", "name", "reportDate"]
    for field in required_fields:
        assert field in first_row, f"Field '{field}' missing from CSV data"

    # Check if we found AAPL data
    apple_entries = [row for row in rows if row["symbol"] == "AAPL"]
    assert apple_entries, "Should find AAPL entries in the response"