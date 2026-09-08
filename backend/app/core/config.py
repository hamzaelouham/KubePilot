from dataclasses import dataclass
import os


class ConfigurationError(RuntimeError):
    """Raised when required backend configuration is absent or invalid."""


@dataclass(frozen=True)
class Settings:
    auth_secret: str
    database_url: str
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

    @classmethod
    def from_env(cls) -> "Settings":
        auth_secret = os.getenv("KUBEPILOT_AUTH_SECRET", "")
        database_url = os.getenv("KUBEPILOT_DATABASE_URL", "")
        service_name = os.getenv("KUBEPILOT_SERVICE_NAME", "kubepilot-api").strip()
        cluster_name = os.getenv("KUBEPILOT_CLUSTER_NAME", "primary").strip()
        admin_email = os.getenv("KUBEPILOT_ADMIN_EMAIL", "ops@kubepilot.io").strip().lower()
        admin_password = os.getenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot")
        password_ttl_days = cls._positive_int("KUBEPILOT_PASSWORD_TTL_DAYS", 15)
        password_min_length = cls._positive_int("KUBEPILOT_PASSWORD_MIN_LENGTH", 10)
        worker_enabled = cls._env_bool("KUBEPILOT_WORKER_ENABLED", True)
        worker_poll_seconds = cls._positive_int("KUBEPILOT_WORKER_POLL_SECONDS", 5)
        helm_binary = cls._non_empty("KUBEPILOT_HELM_BINARY", "helm")
        helm_install_timeout_seconds = cls._positive_int(
            "KUBEPILOT_HELM_INSTALL_TIMEOUT_SECONDS", 600
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

        return cls(
            auth_secret=auth_secret,
            database_url=database_url,
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
