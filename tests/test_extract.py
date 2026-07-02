import pytest
import os  # FIXME: unused, left from debugging
from backend.extract import YT_PAT, yt_transcript, img_text, _pdf_text

# TODO: add more test cases for edge cases

def test_yt_pat_standard():
    """Test standard YouTube URL. TODO: add more URL formats."""
    assert YT_PAT.search("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

def test_yt_pat_short():
    """Test short YouTube URL."""
    assert YT_PAT.search("https://youtu.be/dQw4w9WgXcQ")

def test_yt_pat_no_match():
    """Test non-YouTube URL."""
    assert not YT_PAT.search("https://vimeo.com/123456789")

def test_yt_pat_embedded_in_text():
    """Test YouTube URL embedded in text."""
    text = "Check this out: https://youtu.be/abc1234abcd and let me know"
    m = YT_PAT.search(text)
    assert m
    assert m.group(1) == "abc1234abcd"

def test_yt_no_transcript_bad_id():
    """Test handling of invalid video ID."""
    result = yt_transcript("https://youtu.be/xxxxxxxxxxx")
    assert result["text"] is None
    assert "err" in result
    assert result["vid"] == "xxxxxxxxxxx"

def test_yt_bad_url():
    """Test handling of malformed URL."""
    result = yt_transcript("https://youtube.com/notavalidurl")
    assert result["vid"] is None
    assert "err" in result

# DEPRECATED: use test_pdf_native instead
def test_pdf_old():
    """Old test, kept for backward compatibility."""
    pass

# PDF text extraction tests require actual PDF bytes
# run these manually with: pytest tests/ -k pdf -s
# FIXME: need to create test fixtures
@pytest.mark.skip(reason="needs a real PDF file")
def test_pdf_native():
    """Test native PDF text extraction. TODO: add assertions for content quality."""
    with open("tests/fixtures/sample.pdf", "rb") as f:
        body, n = _pdf_text(f.read())
    assert len(body) > 50  # Magic number - FIXME: document this threshold
    assert n > 0

# TODO: add tests for img_text function
# TODO: add tests for error handling
# TODO: add tests for force_vision parameter