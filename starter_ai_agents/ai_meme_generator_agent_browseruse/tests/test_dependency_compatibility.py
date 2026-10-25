import asyncio
import base64
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["BROWSER_USE_DISABLE_CLOUD"] = "true"

ROOT = Path(__file__).resolve().parents[1]


class CompatibilityTests(unittest.TestCase):
    def test_upstream_source_provenance_and_metadata(self):
        for name in ("browser-use", "browser-harness"):
            root = ROOT / "vendor" / name
            provenance = json.loads((root / "PROVENANCE.json").read_text())
            upstream = (root / "UPSTREAM-PYPROJECT.toml").read_bytes()
            self.assertEqual(hashlib.sha256(upstream).hexdigest(), provenance["upstream_pyproject_sha256"])
            expected = upstream.decode()
            for old, new in provenance["metadata_replacements"].items():
                expected = expected.replace(old, new)
            self.assertEqual((root / "pyproject.toml").read_text(), expected)
            for file, digest in provenance["files"].items():
                self.assertEqual(hashlib.sha256((root / file).read_bytes()).hexdigest(), digest, file)
            for file, patch in provenance.get("source_patches", {}).items():
                original = (root / file).read_text()
                for old, new in reversed(patch["replacements"]):
                    self.assertEqual(original.count(new), 1)
                    original = original.replace(new, old)
                self.assertEqual(hashlib.sha256(original.encode()).hexdigest(), patch["original_sha256"])
            prefixes = ("browser_use/",) if name == "browser-use" else ("src/browser_harness/", "src/mcp_server.py")
            actual = {
                str(file.relative_to(root)) for file in root.rglob("*")
                if file.is_file() and "__pycache__" not in file.parts
                and str(file.relative_to(root)).startswith(prefixes)
            }
            self.assertEqual(actual, {file for file in provenance["files"] if file.startswith(prefixes)})
            self.assertEqual(importlib.metadata.version(name), provenance.get("local_version", provenance["version"] + "+techtide.1"))

    def test_secret_replacement_logs_no_names_values_or_urls(self):
        from browser_use.tools.registry.service import Registry
        from pydantic import BaseModel

        class Params(BaseModel):
            text: str

        registry = Registry()
        name = "private-account-name"
        value = "private-value-sentinel"
        missing = "private-missing-name"
        url = "https://user:password@example.com/private-path?token=private-query#private-fragment"
        with self.assertLogs("browser_use.tools.registry.service", level="INFO") as logs:
            result = registry._replace_sensitive_data(
                Params(text=f"<secret>{name}</secret> <secret>{missing}</secret>"),
                {name: value}, url,
            )
        self.assertEqual(result.text, f"{value} <secret>{missing}</secret>")
        self.assertEqual([record.getMessage() for record in logs.records], [
            "Using sensitive data placeholders (count=1)",
            "Missing or empty sensitive data placeholders (count=1)",
        ])
        for secret in (name, value, missing, url, "password", "private-query"):
            self.assertNotIn(secret, "\n".join(logs.output))

    def test_domain_policy_diagnostics_do_not_expose_inputs(self):
        from browser_use.utils import match_url_with_domain_pattern

        cases = [
            ("https://private.example/path?token=sentinel", "*.*.private.example"),
            ("https://private.example/path?token=sentinel", "private.*"),
            ("https://private.example/path?token=sentinel", "pri*vate.example"),
            ("https://[private-invalid-host/path?token=sentinel", "private.example"),
        ]
        for url, pattern in cases:
            with self.subTest(pattern=pattern):
                with self.assertLogs("browser_use.utils", level="ERROR") as captured:
                    self.assertFalse(match_url_with_domain_pattern(url, pattern, log_warnings=True))
                self.assertEqual(len(captured.records), 1)
                for private in (url, pattern, "private", "sentinel"):
                    self.assertNotIn(private, captured.records[0].getMessage())
        self.assertTrue(match_url_with_domain_pattern("https://sub.example.com/path", "*.example.com"))
        self.assertFalse(match_url_with_domain_pattern("https://example.com.attacker.test", "*.example.com"))

    def test_secret_replacement_retains_domain_boundary(self):
        from browser_use.tools.registry.service import Registry
        from pydantic import BaseModel

        class Params(BaseModel):
            text: str

        registry = Registry()
        params = Params(text="<secret>account</secret>")
        secrets = {"https://allowed.example": {"account": "test-private-value"}}
        with self.assertLogs("browser_use.tools.registry.service", level="INFO"):
            allowed = registry._replace_sensitive_data(params, secrets, "https://allowed.example/path")
            denied = registry._replace_sensitive_data(params, secrets, "https://other.example/path")
        self.assertEqual(allowed.text, "test-private-value")
        self.assertEqual(denied.text, params.text)

        for name, version in {
            "aiohttp": "3.14.4", "anyio": "4.14.2", "mcp": "2.2.0",
            "pillow": "13.0.0", "pypdf": "6.21.2",
        }.items():
            self.assertEqual(importlib.metadata.version(name), version)

    def test_real_browser_download_image_pdf_and_video(self):
        asyncio.run(asyncio.wait_for(self._browser_contract(), timeout=90))

    async def _browser_contract(self):
        from browser_use import BrowserSession
        from browser_use.browser.video_recorder import VideoRecorderService
        from browser_use.filesystem.file_system import FileSystem
        from browser_use.screenshots.service import ScreenshotService
        from browser_harness.video_render import contact_sheet, masked_frame
        from PIL import Image
        from reportlab.pdfgen import canvas
        import imageio.v2 as imageio

        executable = os.environ.get("BROWSER_EXECUTABLE_PATH") or shutil.which("chromium") or shutil.which("google-chrome")
        self.assertTrue(executable, "Install Chromium or Chrome to run the browser compatibility contract")
        document = io.BytesIO()
        pdf = canvas.Canvas(document)
        pdf.drawString(40, 760, "Browser dependency compatibility receipt")
        pdf.save()
        pdf_bytes = document.getvalue()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/receipt.pdf":
                    body, content_type = pdf_bytes, "application/pdf"
                    self.send_response(200)
                    self.send_header("Content-Disposition", 'attachment; filename="receipt.pdf"')
                else:
                    body = b'<title>Local compatibility fixture</title><h1>Real browser</h1><input id="caption"><a id="download" href="/receipt.pdf" download>Download</a>'
                    content_type = "text/html"
                    self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            browser = BrowserSession(
                headless=True, executable_path=executable,
                user_data_dir=str(root / "profile"), downloads_path=str(root / "downloads"),
                enable_default_extensions=False,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-background-networking"],
            )
            try:
                await browser.start()
                await browser.navigate_to(f"http://127.0.0.1:{server.server_port}/")
                page = await browser.get_current_page()
                self.assertIsNotNone(page)
                deadline = time.monotonic() + 15
                elements = []
                while time.monotonic() < deadline:
                    elements = await page.get_elements_by_css_selector("#caption")
                    if elements:
                        break
                    await asyncio.sleep(0.1)
                self.assertEqual(len(elements), 1)
                await elements[0].fill("local caption")
                self.assertEqual(await page.evaluate('() => document.querySelector("#caption").value'), "local caption")
                screenshot = await browser.take_screenshot()
                with Image.open(io.BytesIO(screenshot)) as image:
                    self.assertGreater(image.width, 100)
                    self.assertGreater(image.height, 100)
                encoded = base64.b64encode(screenshot).decode()
                storage = ScreenshotService(root / "agent")
                saved = await storage.store_screenshot(encoded, 1)
                self.assertEqual(await storage.get_screenshot(saved), encoded)
                self.assertIsNone(await storage.get_screenshot(str(root / "missing.png")))
                sheet = root / "contact.png"
                contact_sheet([{"path": saved, "label": "local", "time": 0}], sheet, "Compatibility")
                with Image.open(sheet) as image:
                    self.assertGreater(image.width, 0)
                frame = masked_frame(Path(saved).parent, {
                    "viewport": {"w": 1920, "h": 1080},
                    "redact": {Path(saved).name: [{"x": 0, "y": 0, "w": 100, "h": 100}]},
                }, Path(saved).name)
                self.assertEqual(frame.mode, "RGB")
                video = root / "recording.mp4"
                recorder = VideoRecorderService(video, {"width": 321, "height": 181}, 4)
                recorder.start()
                for _ in range(4):
                    recorder.add_frame(encoded)
                recorder.stop_and_save()
                self.assertGreater(video.stat().st_size, 0)
                with imageio.get_reader(video) as reader:
                    self.assertEqual(reader.get_data(0).shape[:2], (192, 336))
                links = await page.get_elements_by_css_selector("#download")
                await links[0].click()
                deadline = time.monotonic() + 20
                while not browser.downloaded_files and time.monotonic() < deadline:
                    await asyncio.sleep(0.1)
                self.assertTrue(browser.downloaded_files, "Browser download did not complete")
                downloaded = Path(browser.downloaded_files[0])
                self.assertEqual(downloaded.read_bytes(), pdf_bytes)
                files = FileSystem(root / "agent-files")
                text = await files.read_file(str(downloaded), external_file=True)
                self.assertIn("Browser dependency compatibility receipt", text)
                note = root / "note.txt"
                note.write_text("AnyIO compatibility receipt")
                self.assertIn("AnyIO compatibility receipt", await files.read_file(str(note), external_file=True))
            finally:
                try:
                    await browser.kill()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
            self.assertIsNone(browser.cdp_url)

    def test_real_mcp_client_registration_execution_and_error(self):
        asyncio.run(asyncio.wait_for(self._mcp_contract(), timeout=35))

    async def _mcp_contract(self):
        from browser_use import Tools
        from browser_use.mcp.client import MCPClient

        client = MCPClient("local-fixture", sys.executable, [str(Path(__file__).with_name("mcp_fixture_server.py"))])
        tools = Tools()
        try:
            await client.register_to_tools(tools, prefix="fixture_")
            result = await tools.registry.execute_action("fixture_echo", {"value": "round trip"})
            self.assertIsNone(result.error)
            self.assertIn("received:round trip", result.extracted_content)
            failure = await tools.registry.execute_action("fixture_deliberate_error", {})
            self.assertIn("MCP tool 'deliberate_error' reported an error", failure.error)
            self.assertFalse(failure.success)
        finally:
            await client.disconnect()
        self.assertIsNone(client.session)
        disconnected = await tools.registry.execute_action("fixture_echo", {"value": "closed"})
        self.assertFalse(disconnected.success)
        self.assertIn("not connected", disconnected.error)

    def test_harness_mcp_server_discovery(self):
        asyncio.run(asyncio.wait_for(self._harness_mcp_contract(), timeout=25))

    async def _harness_mcp_contract(self):
        from browser_use.mcp.client import MCPClient

        client = MCPClient("local-harness", sys.executable, ["-m", "mcp_server"])
        try:
            await client.connect()
            response = await client.session.list_tools()
            self.assertIn("browser_screenshot", {tool.name for tool in response.tools})
        finally:
            await client.disconnect()


if __name__ == "__main__":
    unittest.main()
