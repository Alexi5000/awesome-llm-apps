"""Extract canonical Google Docs links from generated responses."""

import re
from urllib.parse import urlsplit, urlunsplit


def extract_google_doc_link(content):
    for candidate in re.findall(r"https://[^\s<>\"']+", content or ""):
        try:
            parsed = urlsplit(candidate.rstrip(").,;]"))
            if parsed.hostname != "docs.google.com" or parsed.username is not None or parsed.password is not None:
                continue
            if parsed.port not in {None, 443}:
                continue
            if not re.fullmatch(r"/document/d/[A-Za-z0-9_-]+(?:/(?:edit|view|preview))?/?", parsed.path):
                continue
            return urlunsplit(("https", "docs.google.com", parsed.path, "", ""))
        except ValueError:
            continue
    return None
