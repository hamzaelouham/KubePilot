import gzip
import socket
from types import SimpleNamespace

import pytest

from app.kubernetes import chart_source, helm
from app.kubernetes.chart_source import ChartSourceError, chart_archive, fetch_public
from app.jobs import worker
from app.core.config import Settings


@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://169.254.169.254", "http://localhost", "http://service.svc", "http://[::1]", "https://user:pass@example.com"])
def test_bad_targets_are_rejected_before_requests(monkeypatch, url):
    monkeypatch.setattr(chart_source, "_request", lambda *args: pytest.fail("network request forbidden"))
    with pytest.raises(ChartSourceError):
        fetch_public(url, limit=100)


def test_public_dns_name_pointing_to_private_ip_is_denied(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))])
    monkeypatch.setattr(socket, "socket", lambda *args: pytest.fail("socket must not be created"))
    with pytest.raises(ChartSourceError):
        fetch_public("https://public.example.com", limit=100)


def test_redirect_to_metadata_is_denied_before_second_request(monkeypatch):
    calls = []
    def request(url, limit):
        calls.append(url)
        return 302, "http://169.254.169.254/latest/meta-data", b""
    monkeypatch.setattr(chart_source, "_request", request)
    with pytest.raises(ChartSourceError):
        fetch_public("https://charts.example.com", limit=100)
    assert calls == ["https://charts.example.com"]


def test_index_archive_urls_and_tempfile_lifecycle(monkeypatch):
    calls = []
    payload = gzip.compress(b"chart")
    def request(url, limit):
        calls.append(url)
        if url.endswith("index.yaml"):
            return 200, None, b"entries:\n  demo:\n    - version: '1.0'\n      urls: ['demo-1.0.tgz']\n"
        return 200, None, payload
    monkeypatch.setattr(chart_source, "_request", request)
    from pathlib import Path
    with chart_archive("https://charts.example.com/repo", "demo", "1.0") as path:
        assert Path(path).read_bytes() == payload
    assert not Path(path).exists()
    assert calls[-1] == "https://charts.example.com/repo/demo-1.0.tgz"


def test_archive_can_never_redirect_to_a_private_source(monkeypatch):
    def request(url, limit):
        return 200, None, b"entries:\n  demo:\n    - version: '1.0'\n      urls: ['http://localhost/private.tgz']\n"
    monkeypatch.setattr(chart_source, "_request", request)
    with pytest.raises(ChartSourceError), chart_archive("https://charts.example.com", "demo", "1.0"):
        pytest.fail("archive must not be yielded")


def test_queued_install_cannot_bypass_source_policy(monkeypatch):
    monkeypatch.setattr(worker, "_run_single_command", lambda *args: pytest.fail("helm must not run"))
    job = SimpleNamespace(chart_name="demo", chart_version="1.0", chart_repository="demo", release_name="demo", namespace="default")
    with pytest.raises(worker.HelmInstallError):
        worker._run_helm_install(Settings("x" * 32, "sqlite://"), job, "http://localhost", None)


def test_malformed_index_returns_a_safe_source_error(monkeypatch):
    monkeypatch.setattr(chart_source, "fetch_public", lambda *args, **kwargs: b"entries:\n  demo: ['not a chart entry']\n")
    with pytest.raises(ChartSourceError), chart_archive("https://charts.example.com", "demo", "1.0"):
        pytest.fail("archive must not be yielded")


def test_socket_connects_to_validated_ip_without_second_dns_lookup(monkeypatch):
    from unittest.mock import MagicMock
    lookups, connections = [], []
    def resolve(host, port, **kwargs):
        lookups.append((host, port))
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
    sock = MagicMock()
    sock.connect.side_effect = lambda address: connections.append(address)
    response = MagicMock(status=200)
    response.read.return_value = b"content"
    connection = MagicMock()
    connection.getresponse.return_value = response
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(socket, "socket", lambda *args: sock)
    monkeypatch.setattr(chart_source.http.client, "HTTPConnection", lambda *args, **kwargs: connection)
    assert fetch_public("http://charts.example.com/index.yaml", limit=100) == b"content"
    assert lookups == [("charts.example.com", 80)]
    assert connections == [("93.184.216.34", 80)]
    assert connection.sock is sock
    response.read.return_value = b"x" * 101
    with pytest.raises(ChartSourceError):
        fetch_public("http://charts.example.com/index.yaml", limit=100)
