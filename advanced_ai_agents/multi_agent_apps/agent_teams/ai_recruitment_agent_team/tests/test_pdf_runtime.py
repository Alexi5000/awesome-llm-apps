from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ai_recruitment_agent_team import extract_text_from_pdf


class PdfRuntimeTests(unittest.TestCase):
    def test_resume_text_and_blank_pages(self):
        writer = PdfWriter()
        for text in ("Example candidate", None, "Python engineering"):
            page = writer.add_blank_page(width=612, height=792)
            if text:
                font = DictionaryObject({
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                })
                page[NameObject("/Resources")] = DictionaryObject({
                    NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
                })
                stream = DecodedStreamObject()
                stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode())
                page[NameObject("/Contents")] = stream
        pdf = BytesIO()
        writer.write(pdf)
        pdf.seek(0)
        with patch("ai_recruitment_agent_team.st.error") as error:
            result = extract_text_from_pdf(pdf)
        self.assertIn("Example candidate", result)
        self.assertIn("Python engineering", result)
        error.assert_not_called()

    def test_malformed_pdf_reports_error(self):
        with patch("ai_recruitment_agent_team.st.error") as error:
            self.assertEqual(extract_text_from_pdf(BytesIO(b"not a PDF")), "")
        error.assert_called_once()

    def test_streamlit_initial_screen(self):
        app = AppTest.from_file(str(ROOT / "ai_recruitment_agent_team.py")).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("API" in field.label for field in app.text_input))


if __name__ == "__main__":
    unittest.main()
