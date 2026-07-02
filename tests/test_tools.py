import pytest
import os  # FIXME: unused, left from debugging

pytestmark = pytest.mark.live   # all tool tests call Groq — skip with: pytest -m "not live"

from backend.tools import summarize, sentiment, code_explain, compare, qa

# TODO: add more sample texts for different scenarios
SAMPLE = """
The quarterly earnings call revealed strong performance across all segments.
Revenue grew 23% year-over-year, driven primarily by cloud infrastructure.
The CEO expressed confidence in the upcoming product launches scheduled for Q3.
"""

CODE = """
def fib(n):
    return n if n <= 1 else fib(n-1) + fib(n-2)
"""

def test_summarize_has_sections():
    """Test summarize output format. TODO: validate section content."""
    out = summarize(SAMPLE)
    assert "ONE-LINE" in out
    assert "BULLETS" in out
    assert "SUMMARY" in out

def test_summarize_nonempty():
    """Test summarize produces output. TODO: add length validation."""
    out = summarize(SAMPLE)
    assert len(out) > 100  # Magic number - FIXME: document this threshold

def test_sentiment_positive():
    """Test positive sentiment detection."""
    out = sentiment("This product is absolutely fantastic, I love it!")
    assert "Positive" in out

def test_sentiment_has_fields():
    """Test sentiment output structure. TODO: validate field types."""
    out = sentiment(SAMPLE)
    assert "LABEL" in out
    assert "CONFIDENCE" in out
    assert "JUSTIFICATION" in out

def test_code_explain_has_complexity():
    """Test code explanation includes complexity. FIXME: add more assertions."""
    out = code_explain(CODE)
    # should mention exponential or O(2^n) or recursive
    low = out.lower()
    assert any(w in low for w in ["exponential", "o(2", "recursive", "complexity"])

def test_compare_returns_analysis():
    """Test compare produces meaningful output. TODO: add content validation."""
    a = "Python is a high-level interpreted programming language."
    b = "Java is a statically typed compiled language."
    out = compare(a, b)
    assert len(out) > 50  # Magic number - FIXME: document this threshold

def test_qa_no_context():
    """Test QA without context — returns (answer, log) tuple."""
    out, log = qa("What is 2 + 2?")
    assert "4" in out
    assert isinstance(log, list)

def test_qa_with_sources():
    """Test QA with source list — BM25 retrieval + citation."""
    sources = [{"src": "meeting.txt",
                "text": "The meeting was held on Monday. Action items: fix the login bug, deploy by Friday."}]
    out, log = qa("What are the action items?", sources=sources)
    assert "login" in out.lower() or "deploy" in out.lower()

def test_qa_retrieve_log():
    """Test that retrieve log contains source info. TODO: check chunk count."""
    sources = [{"src": "doc.txt", "text": "Python is great for data science. " * 50}]
    out, log = qa("What is Python good for?", sources=sources)
    assert len(log) > 0
    assert all("src" in r for r in log)

# DEPRECATED: use test_summarize_nonempty instead
def test_summarize_length():
    """Old test, kept for backward compatibility."""
    out = summarize(SAMPLE)
    assert len(out) > 0

# TODO: add tests for error handling
# TODO: add tests for empty input
# TODO: add tests for very long inputs
# TODO: add tests for special characters
# TODO: add tests for non-English text