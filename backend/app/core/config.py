from dataclasses import dataclass
import os
import re
from urllib.parse import unquote, urlsplit


class ConfigurationError(RuntimeError):
    """Raised when required backend configuration is absent or invalid."""


@dataclass(frozen=True)
class Settings:
    auth_secret: str
    database_url: str
    encryption_key: str | None = None
    public_url: str | None = None
    provider_allowed_hosts: tuple[str, ...] = ()
    service_name: str = "kubepilot-api"
    cluster_name: str = "primary"
    admin_email: str = "ops@kubepilot.io"
    admin_password: str = "kubepilot"
    password_ttl_days: int = 15
    password_min_length: int = 10
    worker_enabled: bool = True
    worker_poll_seconds: int = 5
    helm_binary: str = "helm"
    helm_install_timeout_seconds: int = 600
    host_namespace: str = "kubepilot"

    def __post_init__(self) -> None:
        if len(self.host_namespace) > 63 or not re.fullmatch(
            r"[a-z0-9](?:[-a-z0-9]*[a-z0-9])?", self.host_namespace
        ):
            raise ConfigurationError("KUBEPILOT_HOST_NAMESPACE must be a valid namespace name")

    @classmethod
    def from_env(cls) -> "Settings":
        auth_secret = os.getenv("KUBEPILOT_AUTH_SECRET", "")
        database_url = os.getenv("KUBEPILOT_DATABASE_URL", "")
        service_name = os.getenv("KUBEPILOT_SERVICE_NAME", "kubepilot-api").strip()
        cluster_name = os.getenv("KUBEPILOT_CLUSTER_NAME", "primary").strip()
        admin_email = os.getenv("KUBEPILOT_ADMIN_EMAIL", "ops@kubepilot.io").strip().lower()
        local_development = cls._env_bool("KUBEPILOT_LOCAL_DEVELOPMENT", False)
        admin_password = os.getenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot" if local_development else "")
        password_ttl_days = cls._positive_int("KUBEPILOT_PASSWORD_TTL_DAYS", 15)
        password_min_length = cls._positive_int("KUBEPILOT_PASSWORD_MIN_LENGTH", 10)
        worker_enabled = cls._env_bool("KUBEPILOT_WORKER_ENABLED", True)
        worker_poll_seconds = cls._positive_int("KUBEPILOT_WORKER_POLL_SECONDS", 5)
        helm_binary = cls._non_empty("KUBEPILOT_HELM_BINARY", "helm")
        helm_install_timeout_seconds = cls._positive_int(
            "KUBEPILOT_HELM_INSTALL_TIMEOUT_SECONDS", 600
        )
        raw_encryption_key = os.getenv("KUBEPILOT_ENCRYPTION_KEY")
        encryption_key = raw_encryption_key.strip() if raw_encryption_key else None
        raw_public_url = os.getenv("KUBEPILOT_PUBLIC_URL")
        public_url = raw_public_url.strip().rstrip("/") if raw_public_url else None
        provider_allowed_hosts = tuple(
            host.strip().lower().rstrip(".")
            for host in os.getenv("KUBEPILOT_PROVIDER_ALLOWED_HOSTS", "").split(",")
            if host.strip()
        )

        missing = [
            name
            for name, value in (
                ("KUBEPILOT_AUTH_SECRET", auth_secret),
                ("KUBEPILOT_DATABASE_URL", database_url),
            )
            if not value.strip()
        ]
        if missing:
            raise ConfigurationError(
                "Missing required backend configuration: " + ", ".join(missing)
            )
        if len(auth_secret) < 32:
            raise ConfigurationError("KUBEPILOT_AUTH_SECRET must be at least 32 characters")
        if not service_name:
            raise ConfigurationError("KUBEPILOT_SERVICE_NAME must not be empty")
        if not cluster_name:
            raise ConfigurationError("KUBEPILOT_CLUSTER_NAME must not be empty")
        if not admin_email or not admin_password:
            raise ConfigurationError("KUBEPILOT_ADMIN_EMAIL and KUBEPILOT_ADMIN_PASSWORD must not be empty")
        if not local_development:
            if len(admin_password) < password_min_length or admin_password.lower() in {"kubepilot", "change-me", "password"}:
                raise ConfigurationError("Configure a non-default administrator password")
            if auth_secret.startswith(("local-", "replace-with-")) or len(set(auth_secret)) < 8:
                raise ConfigurationError("Configure a random, non-development authentication secret")
            try:
                db_password = urlsplit(database_url).password
                if db_password is not None:
                    db_password = unquote(db_password)
            except ValueError:
                raise ConfigurationError("Database URL is invalid") from None
            if db_password is not None and (len(db_password) < 10 or db_password.lower() in {"change-me", "kubepilot", "password"}):
                raise ConfigurationError("Configure a non-default database password")
        if public_url and not public_url.startswith(("http://", "https://")):
            raise ConfigurationError("KUBEPILOT_PUBLIC_URL must use http:// or https://")

        return cls(
            auth_secret=auth_secret,
            database_url=database_url,
            encryption_key=encryption_key,
            public_url=public_url,
            provider_allowed_hosts=provider_allowed_hosts,
            service_name=service_name,
            cluster_name=cluster_name,
            admin_email=admin_email,
            admin_password=admin_password,
            password_ttl_days=password_ttl_days,
            password_min_length=password_min_length,
            worker_enabled=worker_enabled,
            worker_poll_seconds=worker_poll_seconds,
            helm_binary=helm_binary,
            helm_install_timeout_seconds=helm_install_timeout_seconds,
            host_namespace=os.getenv("KUBEPILOT_HOST_NAMESPACE", "kubepilot").strip(),
        )

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name, "").strip().lower()
        if not raw:
            return default
        if raw in {"true", "1", "yes", "on"}:
            return True
        if raw in {"false", "0", "no", "off"}:
            return False
        raise ConfigurationError(f"{name} must be true or false")

    @staticmethod
    def _non_empty(name: str, default: str) -> str:
        value = os.getenv(name, "").strip()
        if not value:
            return default
        return value

    @staticmethod
    def _positive_int(name: str, default: int) -> int:
        raw = os.getenv(name, "")
        if not raw.strip():
            return default
        try:
            value = int(raw)
        except ValueError:
            raise ConfigurationError(f"{name} must be a positive integer")
        if value < 1:
            raise ConfigurationError(f"{name} must be a positive integer")
        return value
