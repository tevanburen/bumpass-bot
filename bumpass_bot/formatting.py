from string import ascii_lowercase, ascii_uppercase

# Messages can't send formatted text through AppleScript, so italics are the
# Mathematical Sans-Serif Italic letters. Digits, punctuation and non-ASCII letters have none.
ITALIC_TABLE = {
    **{ord(letter): chr(0x1D608 + index) for index, letter in enumerate(ascii_uppercase)},
    **{ord(letter): chr(0x1D622 + index) for index, letter in enumerate(ascii_lowercase)},
}


def italic(text):
    return text.translate(ITALIC_TABLE)


def truncate(text, max_chars):
    """Collapse whitespace to single spaces and cut to max_chars with an ellipsis."""
    text = " ".join(text.split())
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "…"

    return text
