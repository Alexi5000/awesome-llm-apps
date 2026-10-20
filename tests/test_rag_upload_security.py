"""Run production upload functions with local loader and embedding doubles."""

import ast
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def load_function(relative, name, namespace):
    path = ROOT / relative
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    node.returns = None
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


class RagUploadTests(unittest.TestCase):
    def test_rag_chain_preserves_outside_file_and_cleans_up(self):
        observed = []
        stored = []
        test = self

        class Loader:
            def __init__(self, path):
                self.path = Path(path)
                observed.append(self.path)

            def load(self):
                test.assertEqual(self.path.read_bytes(), b"pdf")
                return [SimpleNamespace(page_content="text", metadata={"source": str(self.path)})]

        splitter = lambda **kw: SimpleNamespace(create_documents=lambda content, metadata: content)
        ns = {"os": os, "tempfile": tempfile, "st": SimpleNamespace(error=lambda *a: None),
              "PyPDFLoader": Loader, "SentenceTransformersTokenTextSplitter": splitter,
              "db": SimpleNamespace(add_documents=stored.extend)}
        process = load_function("rag_tutorials/rag_chain/app.py", "add_to_db", ns)
        with tempfile.TemporaryDirectory() as outside:
            sentinel = Path(outside) / "private.pdf"
            sentinel.write_bytes(b"keep")
            process([SimpleNamespace(name=str(sentinel), getbuffer=lambda: b"pdf")])
            self.assertEqual(sentinel.read_bytes(), b"keep")
            self.assertEqual(stored, ["text"])
            self.assertFalse(observed[0].exists())
            self.assertFalse(observed[0].parent.exists())

    def test_image_paths_ignore_client_names_and_deduplicate_content(self):
        ns = {"os": os, "hashlib": hashlib}
        path_for = load_function("rag_tutorials/vision_rag/vision_rag.py", "upload_image_path", ns)
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for name in ["photo.png", "/tmp/outside.png", "../../outside.png", r"C:\outside.png"]:
                paths.append(Path(path_for(SimpleNamespace(name=name, type="image/png", getbuffer=lambda: b"png"), folder)))
            self.assertEqual(len(set(paths)), 1)
            self.assertEqual(paths[0].parent, Path(folder))
            self.assertEqual(paths[0].suffix, ".png")
            with self.assertRaises(ValueError):
                path_for(SimpleNamespace(name="bad", type="text/html", getbuffer=lambda: b"html"), folder)

    def test_pdf_page_directory_ignores_absolute_filename(self):
        class Document:
            def __len__(self):
                return 1

            def pages(self):
                return [SimpleNamespace(get_pixmap=lambda **kw: SimpleNamespace(width=1, height=1, samples=b"rgb"))]

            def close(self):
                pass

        image = SimpleNamespace(save=lambda path, fmt: Path(path).write_bytes(b"page"))
        ns = {"os": os, "hashlib": hashlib, "fitz": SimpleNamespace(open=lambda **kw: Document()),
              "Image": SimpleNamespace(frombytes=lambda *a: image), "pil_to_base64": lambda img: "image",
              "compute_image_embedding": lambda *a, **kw: [1.0],
              "st": SimpleNamespace(write=lambda *a: None, warning=lambda *a: None, error=lambda *a: None,
                                    progress=lambda *a: SimpleNamespace(progress=lambda *a: None, empty=lambda: None))}
        process = load_function("rag_tutorials/vision_rag/vision_rag.py", "process_pdf_file", ns)
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as outside:
            upload = SimpleNamespace(name=str(Path(outside) / "escaped.pdf"), getbuffer=lambda: b"pdf", read=lambda: b"pdf")
            paths, embeddings = process(upload, None, folder)
            self.assertEqual(len(paths), 1)
            self.assertEqual(Path(paths[0]).parents[1], Path(folder))
            self.assertEqual(Path(paths[0]).read_bytes(), b"page")
            self.assertEqual(embeddings, [[1.0]])
            self.assertEqual(list(Path(outside).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
