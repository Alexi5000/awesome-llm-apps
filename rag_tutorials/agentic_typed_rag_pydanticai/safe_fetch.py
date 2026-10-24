"""Fetch public web pages with DNS pinning and per-redirect validation."""

import http.client
import ipaddress
import os
import socket
import ssl
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 5


def _resolve_target(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only HTTP and HTTPS URLs are supported.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL credentials are not supported.")
    host = parsed.hostname.encode("idna").decode("ascii")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError("URL host did not resolve.")
    allow_private = False
    for entry in addresses:
        address = ipaddress.ip_address(entry[4][0])
        if address.is_multicast or address.is_unspecified or (not allow_private and not address.is_global):
            raise ValueError("Only public Internet addresses are allowed.")
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            if not allow_private and not address.ipv4_mapped.is_global:
                raise ValueError("Only public Internet addresses are allowed.")
    return parsed, host, port, addresses[0][4][0]


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, port, address):
        super().__init__(host, port, timeout=20)
        self.address = address

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)


class _PinnedHTTPSConnection(_PinnedHTTPConnection):
    def connect(self):
        super().connect()
        try:
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            self.sock = context.wrap_socket(self.sock, server_hostname=self.host)
        except Exception:
            self.sock.close()
            raise


def fetch_public_document(url):
    """Fetch bounded content without proxy inheritance or unchecked redirects."""
    for redirect in range(MAX_REDIRECTS + 1):
        parsed, host, port, address = _resolve_target(url)
        connection_type = _PinnedHTTPSConnection if parsed.scheme == "https" else _PinnedHTTPConnection
        connection = connection_type(host, port, address)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        try:
            connection.request("GET", path, headers={"Accept": "text/html,text/plain", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location or redirect == MAX_REDIRECTS:
                    raise ValueError("Invalid or excessive URL redirects.")
                url = urljoin(url, location)
                continue
            if response.status >= 400:
                raise ValueError(f"Remote server returned HTTP {response.status}.")
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "text/plain"}:
                raise ValueError(f"Unsupported URL content type: {content_type}")
            content = response.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise ValueError("Web page exceeds the 2 MB ingestion limit.")
            encoding = response.headers.get_content_charset() or "utf-8"
            return content.decode(encoding, errors="replace"), content_type
        finally:
            connection.close()
    raise ValueError("Too many redirects.")
