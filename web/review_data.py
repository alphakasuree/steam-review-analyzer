import re


def parts(text):
    """Split a Steam review into excerpts for classification."""
    return [
        excerpt.strip()
        for excerpt in re.split(r'[\n.!?。]+|\s+(?:근데|그런데|하지만)\s+', text)
        if excerpt.strip()
    ]
