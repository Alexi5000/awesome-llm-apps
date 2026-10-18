"""Exercise actual link parsers without importing provider-backed applications."""

import ast
import importlib.util
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = "dQw4w9WgXcQ"
source = ROOT / "advanced_ai_agents/single_agent_apps/earnings_call_analyst_agent/youtube_ingest.py"
module = ast.parse(source.read_text())
function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "extract_video_id")
namespace = {"VIDEO_ID_RE": re.compile(r"^[A-Za-z0-9_-]{11}$"), "urlparse": urlparse, "parse_qs": parse_qs}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
extract_video_id = namespace["extract_video_id"]
source = ROOT / "advanced_ai_agents/multi_agent_apps/agent_teams/ai_teaching_agent_team/google_doc_links.py"
spec = importlib.util.spec_from_file_location("google_doc_links", source)
links = importlib.util.module_from_spec(spec)
spec.loader.exec_module(links)


class ExternalLinkTests(unittest.TestCase):
    def test_supported_youtube_forms(self):
        for url in [VIDEO_ID, f"https://www.youtube.com/watch?v={VIDEO_ID}", f"https://m.youtube.com/shorts/{VIDEO_ID}", f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}", f"https://youtu.be/{VIDEO_ID}"]:
            with self.subTest(url=url):
                self.assertEqual(extract_video_id(url), VIDEO_ID)

    def test_rejects_deceptive_youtube_hosts(self):
        for url in [f"https://notyoutube.com/watch?v={VIDEO_ID}", f"https://evilyoutube-nocookie.com/embed/{VIDEO_ID}", f"https://youtube.com.evil.test/watch?v={VIDEO_ID}", f"https://evil.test@youtube.com/watch?v={VIDEO_ID}", f"javascript://youtube.com/watch?v={VIDEO_ID}"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                extract_video_id(url)

    def test_google_docs_markdown_links(self):
        self.assertEqual(links.extract_google_doc_link("See [document](https://docs.google.com/document/d/abc_123/edit?usp=sharing)."), "https://docs.google.com/document/d/abc_123/edit")

    def test_rejects_deceptive_google_doc_links(self):
        for url in ["https://docs.google.com.evil.test/document/d/123/edit", "https://docs.google.com@evil.test/document/d/123/edit", "https://evil.test@docs.google.com/document/d/123/edit", "https://docs.google.com:444/document/d/123/edit", "https://docs.google.com/redirect?url=https://evil.test"]:
            with self.subTest(url=url):
                self.assertIsNone(links.extract_google_doc_link(url))


if __name__ == "__main__":
    unittest.main()
