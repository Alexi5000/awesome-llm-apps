"""Regression checks for URL ingestion and Beifong media confinement."""

import importlib.util
import io
import socket
import ssl
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch = load("rag_tutorials/multimodal_agentic_rag/backend/safe_fetch.py", "safe_fetch")
paths = load("advanced_ai_agents/multi_agent_apps/ai_news_and_podcast_agents/beifong/services/safe_paths.py", "safe_paths")


def resolution(address):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]


def response(status=200, body=b"<p>Public article</p>", location=None):
    result = Mock(status=status, headers=Message())
    result.read.side_effect = io.BytesIO(body).read
    result.getheader.return_value = location
    return result


class PublicFetchTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(fetch.os.environ, {"ALLOW_PRIVATE_URLS": "false"})
        environment.start()
        self.addCleanup(environment.stop)

    def test_admin_private_network_opt_in_keeps_pinned_ingestion(self):
        connection = Mock()
        connection.getresponse.return_value = response()
        with patch.dict(fetch.os.environ, {"ALLOW_PRIVATE_URLS": "true"}), patch.object(fetch.socket, "getaddrinfo", return_value=resolution("10.0.0.7")), patch.object(fetch, "_PinnedHTTPSConnection", return_value=connection) as factory:
            self.assertIn("Public article", fetch.fetch_public_html("https://intranet.example/article"))
        factory.assert_called_once_with("intranet.example", 443, "10.0.0.7")

    def test_rejects_nonpublic_dns_and_mixed_answers(self):
        for address in ["127.0.0.1", "10.0.0.1", "169.254.169.254", "100.64.0.1", "::1", "224.0.0.1", "0.0.0.0", "::ffff:127.0.0.1"]:
            with self.subTest(address=address), patch.object(fetch.socket, "getaddrinfo", return_value=resolution(address)):
                with self.assertRaises(ValueError):
                    fetch.fetch_public_html("https://example.com")
        with patch.object(fetch.socket, "getaddrinfo", return_value=resolution("8.8.8.8") + resolution("127.0.0.1")):
            with self.assertRaises(ValueError):
                fetch.fetch_public_html("https://example.com")

    def test_rejects_credentials_and_other_schemes(self):
        for url in ["file:///etc/passwd", "ftp://example.com", "https://user:pass@example.com", "http://example.com:99999"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                fetch.fetch_public_html(url)

    def test_fetches_public_content_with_original_host_and_path(self):
        connection = Mock()
        connection.getresponse.return_value = response()
        with patch.object(fetch.socket, "getaddrinfo", return_value=resolution("8.8.8.8")), patch.object(fetch, "_PinnedHTTPSConnection", return_value=connection) as factory:
            self.assertEqual(fetch.fetch_public_html("https://example.com/article?q=hello"), "<p>Public article</p>")
        factory.assert_called_once_with("example.com", 443, "8.8.8.8")
        self.assertEqual(connection.request.call_args.args[:2], ("GET", "/article?q=hello"))
        connection.close.assert_called_once()

    def test_redirect_to_private_address_is_blocked_before_connect(self):
        connection = Mock()
        connection.getresponse.return_value = response(302, location="http://169.254.169.254/latest/meta-data")
        with patch.object(fetch.socket, "getaddrinfo", side_effect=[resolution("8.8.8.8"), resolution("169.254.169.254")]), patch.object(fetch, "_PinnedHTTPSConnection", return_value=connection), patch.object(fetch, "_PinnedHTTPConnection") as private:
            with self.assertRaises(ValueError):
                fetch.fetch_public_html("https://example.com")
            private.assert_not_called()
        connection.close.assert_called_once()

    def test_public_relative_redirect_keeps_ingestion_working(self):
        first, second = Mock(), Mock()
        first.getresponse.return_value = response(302, location="/news")
        second.getresponse.return_value = response()
        with patch.object(fetch.socket, "getaddrinfo", return_value=resolution("8.8.8.8")), patch.object(fetch, "_PinnedHTTPSConnection", side_effect=[first, second]):
            self.assertIn("Public article", fetch.fetch_public_html("https://example.com/start"))
        self.assertEqual(second.request.call_args.args[1], "/news")
        first.close.assert_called_once()
        second.close.assert_called_once()

    def test_redirect_limit_and_body_limit(self):
        for remote in [response(302, location="/loop"), response(body=b"x" * (fetch.MAX_BYTES + 1))]:
            connection = Mock()
            connection.getresponse.return_value = remote
            with patch.object(fetch.socket, "getaddrinfo", return_value=resolution("8.8.8.8")), patch.object(fetch, "_PinnedHTTPSConnection", return_value=connection), self.assertRaises(ValueError):
                fetch.fetch_public_html("https://example.com")

    def test_connection_pins_dns_and_verifies_original_tls_hostname(self):
        context = Mock()
        sock = Mock()
        with patch.object(fetch.socket, "create_connection", return_value=sock) as connect, patch.object(fetch.ssl, "create_default_context", return_value=context), patch.object(fetch.socket, "getaddrinfo") as dns:
            connection = fetch._PinnedHTTPSConnection("example.com", 443, "8.8.8.8")
            connection.connect()
        connect.assert_called_once_with(("8.8.8.8", 443), 20)
        dns.assert_not_called()
        context.wrap_socket.assert_called_once_with(sock, server_hostname="example.com")

    def test_tls_validation_errors_are_not_ignored(self):
        context = Mock()
        context.wrap_socket.side_effect = ssl.SSLCertVerificationError("bad certificate")
        sock = Mock()
        with patch.object(fetch.socket, "create_connection", return_value=sock), patch.object(fetch.ssl, "create_default_context", return_value=context), self.assertRaises(ssl.SSLCertVerificationError):
            fetch._PinnedHTTPSConnection("example.com", 443, "8.8.8.8").connect()
        sock.close.assert_called_once()


class MediaPathTests(unittest.TestCase):
    def test_valid_downloads_and_nested_recordings(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(paths.media_path(root, "show.wav"), str(Path(root) / "show.wav"))
            self.assertEqual(paths.media_path(root, "session-123", "recording.webm"), str(Path(root) / "session-123/recording.webm"))

    def test_rejects_traversal_absolute_and_header_control_characters(self):
        for name in ["..", ".", "../secret", "/etc/passwd", "folder/file", "..\\secret", "x\r\nInjected: value", "x\x00"]:
            with self.subTest(name=name), self.assertRaises(paths.HTTPException):
                paths.media_path("podcasts/audio", name)

    def test_rejects_symlinks_leading_outside_root(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            (Path(root) / "escape").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(paths.HTTPException):
                paths.media_path(root, "escape", "secret.wav")


if __name__ == "__main__":
    unittest.main()
