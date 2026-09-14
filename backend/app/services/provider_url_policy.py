from dataclasses import dataclass
import ipaddress
import re
from urllib.parse import urlsplit


class ProviderURLPolicyError(ValueError):
    """Raised when a provider URL cannot be used safely by the server."""


_HOSTNAME = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$"
)
_INTERNAL_SUFFIXES = (".internal", ".local", ".cluster.local", ".svc")
_BLOCKED_HOSTNAMES = frozenset({"localhost", "broadcasthost", "ip6-allnodes", "ip6-allrouters"})


@dataclass(frozen=True)
class ProviderURLPolicy:
    allowed_hosts: frozenset[str] = frozenset()

    @classmethod
    def from_hosts(cls, hosts: tuple[str, ...] | list[str] | set[str]) -> "ProviderURLPolicy":
        return cls(frozenset(_normalize_allowlist_host(host) for host in hosts))

    @classmethod
    def from_settings(cls, settings: object) -> "ProviderURLPolicy":
        return cls.from_hosts(getattr(settings, "provider_allowed_hosts", ()))

    def validate(self, url: str) -> str:
        if not isinstance(url, str) or not url or len(url) > 2048:
            raise ProviderURLPolicyError("Provider URL is malformed")
        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as error:
            raise ProviderURLPolicyError("Provider URL is malformed") from error

        if parsed.scheme.lower() not in {"http", "https"}:
            raise ProviderURLPolicyError("Provider URL must use HTTP or HTTPS")
        if not parsed.netloc or not hostname:
            raise ProviderURLPolicyError("Provider URL must include a hostname")
        if parsed.username is not None or parsed.password is not None:
            raise ProviderURLPolicyError("Provider URL must not include credentials")
        if parsed.query or parsed.fragment:
            raise ProviderURLPolicyError("Provider URL must not include a query or fragment")
        if port is not None and not 1 <= port <= 65535:
            raise ProviderURLPolicyError("Provider URL port is invalid")

        normalized_host = hostname.lower().rstrip(".")
        if normalized_host != hostname.lower() or not _HOSTNAME.fullmatch(normalized_host):
            raise ProviderURLPolicyError("Provider URL hostname is malformed")
        try:
            ipaddress.ip_address(normalized_host)
        except ValueError:
            pass
        else:
            raise ProviderURLPolicyError("Provider URL must use an approved hostname, not an IP literal")

        if normalized_host in _BLOCKED_HOSTNAMES:
            raise ProviderURLPolicyError("Provider URL targets a blocked local hostname")
        if normalized_host in self.allowed_hosts:
            return url
        if normalized_host.endswith(_INTERNAL_SUFFIXES) or "." not in normalized_host:
            raise ProviderURLPolicyError("Private or internal provider hosts require an explicit allowlist")
        return url

    def validate_redirect(self, url: str) -> str:
        """Apply the same policy to every redirect target before following it."""
        return self.validate(url)


def _normalize_allowlist_host(host: str) -> str:
    normalized = host.strip().lower().rstrip(".")
    if not normalized or not _HOSTNAME.fullmatch(normalized):
        raise ProviderURLPolicyError("Provider host allowlist contains a malformed hostname")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        return normalized
    raise ProviderURLPolicyError("Provider host allowlist must contain hostnames, not IP literals")
