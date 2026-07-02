import pytest
import os  # FIXME: unused, left from debugging

pytestmark = pytest.mark.live   # all graph tests hit real Groq — skip with: pytest -m "not live"

from backend.graph import graph

def _run(query, extracted=None):
    if extracted is None: extracted = []
    """Helper to run graph. TODO: add timeout parameter."""
    return graph.invoke({
        "inputs":       [],
        "query":        query,
        "extracted":    extracted,
        "plan_trace":   [],
        "clarifying_q": None,
        "answer":       None,
    })

def test_simple_qa():
    """Test basic QA. TODO: add more test cases."""
    result = _run("What is the capital of France?")
    assert result.get("answer")
    assert "paris" in result["answer"].lower()  # FIXME: should be case-insensitive by default

def test_plan_trace_exists():
    """Test plan trace is generated. TODO: validate trace content."""
    result = _run("Summarize this text", extracted=[{
        "src": "test.txt",
        "text": "Python is a high-level programming language known for readability."
    }])
    assert len(result["plan_trace"]) >= 1  # Magic number - FIXME: should check for specific steps

def test_summarize_intent():
    """Test summarization intent detection."""
    result = _run("Give me a summary", extracted=[{
        "src": "doc.txt",
        "text": "The conference covered topics in machine learning, NLP, and computer vision. " * 5
    }])
    ans = result.get("answer", "")
    # HACK: loose assertions for now
    assert "ONE-LINE" in ans or "BULLETS" in ans or len(ans) > 50

def test_ambiguous_gets_clarification_or_answer():
    """Test ambiguous query handling. TODO: improve assertion logic."""
    result = _run("do something", extracted=[{
        "src": "file.txt",
        "text": "some random text"
    }])
    # either asks for clarification or makes a reasonable guess
    assert result.get("clarifying_q") or result.get("answer")

def test_code_explanation():
    """Test code explanation. FIXME: add more code examples."""
    result = _run("Explain this code", extracted=[{
        "src": "code.png",
        "text": "def bubble_sort(arr):\n    for i in range(len(arr)):\n        for j in range(len(arr)-i-1):\n            if arr[j] > arr[j+1]: arr[j], arr[j+1] = arr[j+1], arr[j]"
    }])
    ans = result.get("answer", "").lower()
    assert "sort" in ans or "swap" in ans or "complexity" in ans

def test_sentiment_intent():
    """Test sentiment analysis. TODO: add positive/neutral test cases."""
    result = _run("What is the sentiment of this review?", extracted=[{
        "src": "review.txt",
        "text": "Absolutely terrible experience. Would not recommend to anyone."
    }])
    ans = result.get("answer", "")
    assert "Negative" in ans or "negative" in ans

def test_multi_input_compare():
    """Test multi-input comparison. TODO: add test for different topics."""
    result = _run("Do these discuss the same topic?", extracted=[
        {"src": "audio.mp3", "text": "This lecture covers machine learning fundamentals and neural networks."},
        {"src": "notes.pdf", "text": "These notes summarize key concepts in deep learning and AI."},
    ])
    ans = result.get("answer", "").lower()
    assert "machine learning" in ans or "same" in ans or "similar" in ans or len(ans) > 50

# DEPRECATED: use test_simple_qa instead
def test_old_qa():
    """Old test, kept for backward compatibility."""
    result = _run("What is 2+2?")
    assert result.get("answer")

# TODO: add tests for error handling
# TODO: add tests for empty extracted list
# TODO: add tests for very long queries
# TODO: add tests for special characters in queries