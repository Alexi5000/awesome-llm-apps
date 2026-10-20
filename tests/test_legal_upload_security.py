"""Exercise the production document handler without contacting model providers."""

import ast
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "advanced_ai_agents/multi_agent_apps/agent_teams/ai_legal_agent_team/local_ai_legal_agent_team/local_legal_agent.py"


class LegalUploadTests(unittest.TestCase):
    def run_upload(self, filename, fail=False):
        observed = []

        class Knowledge:
            def __init__(self, vector_db):
                self.vector_db = vector_db

            def add_content(self, path):
                observed.append(Path(path))
                self_test.assertEqual(Path(path).read_bytes(), b"%PDF-test")
                if fail:
                    raise RuntimeError("loader failure")

        self_test = self
        function = next(node for node in ast.parse(SOURCE.read_text()).body
                        if isinstance(node, ast.FunctionDef) and node.name == "process_document")
        namespace = {"tempfile": tempfile, "os": os, "Qdrant": object,
                     "Knowledge": Knowledge, "st": SimpleNamespace(write=lambda *args: None)}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), namespace)
        upload = SimpleNamespace(name=filename, getbuffer=lambda: b"%PDF-test")
        if fail:
            with self.assertRaisesRegex(Exception, "loader failure"):
                namespace["process_document"](upload, "database")
        else:
            result = namespace["process_document"](upload, "database")
            self.assertEqual(result.vector_db, "database")
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0].suffix, ".pdf")
        self.assertFalse(observed[0].exists())
        self.assertFalse(observed[0].parent.exists())

    def test_normal_document_is_loaded_and_cleaned(self):
        self.run_upload("contract.pdf")

    def test_client_filename_cannot_overwrite_outside_file(self):
        with tempfile.TemporaryDirectory() as outside:
            sentinel = Path(outside) / "private.pdf"
            sentinel.write_bytes(b"keep")
            for name in [str(sentinel), os.path.relpath(sentinel, tempfile.gettempdir()),
                         "../../private.pdf", r"C:\private.pdf", r"..\private.pdf"]:
                with self.subTest(name=name):
                    self.run_upload(name)
                    self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_failed_loader_cleans_up_document(self):
        self.run_upload("contract.pdf", fail=True)


if __name__ == "__main__":
    unittest.main()
