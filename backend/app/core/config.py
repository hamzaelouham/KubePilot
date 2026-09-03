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

    @classmethod
    def from_env(cls) -> "Settings":
        auth_secret = os.getenv("KUBEPILOT_AUTH_SECRET", "")
        database_url = os.getenv("KUBEPILOT_DATABASE_URL", "")
        service_name = os.getenv("KUBEPILOT_SERVICE_NAME", "kubepilot-api").strip()
        cluster_name = os.getenv("KUBEPILOT_CLUSTER_NAME", "primary").strip()
        admin_email = os.getenv("KUBEPILOT_ADMIN_EMAIL", "ops@kubepilot.io").strip().lower()
        admin_password = os.getenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot")

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
        )
