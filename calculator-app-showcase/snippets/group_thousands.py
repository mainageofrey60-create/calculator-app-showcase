"""Illustrative snippet written for this showcase (not copied from the private source).

Idea: add thousands separators only when drawing text, and never store them.
The stored expression stays comma-free, so it can always be parsed again.
"""
import re

_NUMBER = re.compile(r"(\d+)(\.?)(\d*)")


def group_thousands(display_text: str) -> str:
    """'1234+5678.9' -> '1,234+5,678.9'. Display only; never feed this back into the parser."""
    def add_commas(match):
        whole, dot, fraction = match.groups()
        return f"{int(whole):,}{dot}{fraction}"
    return _NUMBER.sub(add_commas, display_text)


if __name__ == "__main__":
    stored = "1234567+0.5"          # what the session keeps
    print(group_thousands(stored))  # 1,234,567+0.5  (what the screen shows)
