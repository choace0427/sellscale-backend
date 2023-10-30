from decorators import use_app_context
from src.ml.spam_detection import run_algorithmic_spam_detection
from test_utils import test_app
from app import app

@use_app_context
def test_run_algorithmic_spam_detection():
    text = """This is a sample email that should not pass the spam detection algorithm.

Hello friend, let me tell you about this great opportunity to make $$$ fast!

You can make $1000 in 1 day!

Just click this link to get started.
"""
    results = run_algorithmic_spam_detection(text=text)
    print(results)
    assert len(results.get("spam_words")) > 0
    assert results.get("read_minutes") > 0
    assert results.get("spam_word_score") == 75
    assert results.get("read_minutes_score") == 100
    assert results.get("total_score") == 87.5
