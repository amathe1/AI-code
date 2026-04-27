def citation_score(answer: str, chunk_text: str) -> float:
    ans_words = set(answer.lower().split())
    chunk_words = set(chunk_text.lower().split())

    if not ans_words:
        return 0.0

    return len(ans_words & chunk_words) / len(ans_words)