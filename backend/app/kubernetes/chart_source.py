"""Fetch chart sources without giving Helm arbitrary network targets."""

from contextlib import contextmanager
import http.client
import ipaddress
import socket
import ssl
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import yaml

from app.services.provider_url_policy import ProviderURLPolicy, ProviderURLPolicyError


class ChartSourceError(ValueError):
    pass


def _public_addresses(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ChartSourceError("Chart source resolves to a non-public address")
    return addresses


def _request(url, limit):
    parsed = urlsplit(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = _public_addresses(parsed.hostname, port)
    # Connect to the checked address directly, retaining hostname TLS verification.
    family, socktype, proto, _, address = addresses[0]
    sock = socket.socket(family, socktype, proto)
    connection = http.client.HTTPConnection(parsed.hostname, port, timeout=15)
    try:
        sock.settimeout(15)
        sock.connect(address)
        if parsed.scheme == "https":
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname)
        connection.sock = sock
        connection.request("GET", parsed.path or "/", headers={"Accept-Encoding": "identity"})
        response = connection.getresponse()
        if response.status in {301, 302, 303, 307, 308}:
            return response.status, response.getheader("Location"), b""
        if response.status != 200:
            raise ChartSourceError("Chart source is unavailable")
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ChartSourceError("Chart source exceeds the size limit")
        return response.status, None, body
    finally:
        connection.close()
        sock.close()


def fetch_public(url, *, limit):
    try:
        for _ in range(6):
            ProviderURLPolicy().validate(url)
            status, location, body = _request(url, limit)
            if status == 200:
                return body
            if not location:
                raise ChartSourceError("Chart redirect has no target")
            target = urljoin(url, location)
            if urlsplit(url).scheme == "https" and urlsplit(target).scheme != "https":
                raise ChartSourceError("Chart redirect cannot downgrade TLS")
            url = target
        raise ChartSourceError("Too many chart redirects")
    except (ProviderURLPolicyError, OSError, http.client.HTTPException, ValueError) as error:
        raise ChartSourceError("Chart source is invalid or unavailable") from error


@contextmanager
def chart_archive(repository_url, chart_name, version):
    try:
        ProviderURLPolicy().validate(repository_url)
        index_url = repository_url.rstrip("/") + "/index.yaml"
        index = yaml.safe_load(fetch_public(index_url, limit=2 * 1024 * 1024))
        entries = index["entries"][chart_name]
        entry = next(item for item in entries if str(item.get("version")) == version)
        archive_url = urljoin(index_url, entry["urls"][0])
        archive = fetch_public(archive_url, limit=50 * 1024 * 1024)
        if not archive.startswith(b"\x1f\x8b"):
            raise ChartSourceError("Chart archive must use gzip")
    except (ProviderURLPolicyError, yaml.YAMLError, KeyError, TypeError, AttributeError, IndexError, StopIteration) as error:
        raise ChartSourceError("Selected chart version is unavailable") from error
    with tempfile.TemporaryDirectory(prefix="kubepilot-chart-") as directory:
        path = Path(directory) / "chart.tgz"
        path.write_bytes(archive)
        yield str(path)
