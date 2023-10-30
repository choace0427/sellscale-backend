import csv

spam_words_path = r"src/../datasets/spam_words.csv"

def run_algorithmic_spam_detection(text: str) -> dict:
    """Runs an algorithmic spam detection approach by using a list of spam words.

    Args:
        text (str): The text to be checked for spam.

    Returns:
        tuple[bool, ]: _description_
    """
    detected_spam = []

    spam_words = []
    with open(spam_words_path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            spam_words.append(row[0])

    text = text.split()
    for word in text:
        if word in spam_words:
            detected_spam.append(word)

    text_length = len(text)
    read_minutes = (text_length // 130) + 1

    spam_word_score = max(100 - (25 * len(detected_spam)), 0)
    read_minutes_score = max(125 - (25 * read_minutes), 0)
    total_score = (spam_word_score + read_minutes_score) / 2

    results = {
        "spam_words": detected_spam,
        "read_minutes": read_minutes,
        "spam_word_score": spam_word_score,
        "read_minutes_score": read_minutes_score,
        "total_score": total_score,
    }

    return results
