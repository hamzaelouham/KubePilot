from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAt, PrimaryKey


class AssistantProposal(Base):
    __tablename__ = "assistant_proposals"

    id: Mapped[PrimaryKey]
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    cluster_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    precondition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    created_at: Mapped[CreatedAt]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id: Mapped[PrimaryKey]
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="operator", server_default="operator")
    created_at: Mapped[CreatedAt]
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now().astimezone(),
        server_default=text("now()"),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    audit_actions: Mapped[list["AuditAction"]] = relationship(
        back_populates="actor", foreign_keys="AuditAction.actor_id"
    )
    preferences: Mapped["UserPreference | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[PrimaryKey]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    issued_at: Mapped[CreatedAt]
    expires_at: Mapped[datetime]
    restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    user: Mapped[UserAccount] = relationship(back_populates="sessions")
    __table_args__ = (Index("ix_sessions_active_expiry", "user_id", "expires_at"),)


class ClusterConnection(Base):
    __tablename__ = "cluster_connections"

    id: Mapped[PrimaryKey]
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    endpoint: Mapped[str] = mapped_column(String(2048), nullable=False)
    kubeconfig_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    kubeconfig_content: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", server_default="unknown")
    created_at: Mapped[CreatedAt]

    namespaces: Mapped[list["Namespace"]] = relationship(back_populates="cluster", cascade="all, delete-orphan")
    installations: Mapped[list["InstallationJob"]] = relationship(back_populates="cluster", passive_deletes=True)
    __table_args__ = (Index("ix_cluster_connections_status", "status"),)


class HelmRepository(Base):
    __tablename__ = "helm_repositories"

    id: Mapped[PrimaryKey]
    name: Mapped[str] = mapped_column(String(63), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now().astimezone(),
        server_default=text("now()"),
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_helm_repositories_name"),
        UniqueConstraint("url", name="uq_helm_repositories_url"),
        Index("ix_helm_repositories_name", "name"),
    )


class Namespace(Base):
    __tablename__ = "namespaces"

    id: Mapped[PrimaryKey]
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cluster_connections.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(253), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", server_default="unknown")
    created_at: Mapped[CreatedAt]

    cluster: Mapped[ClusterConnection] = relationship(back_populates="namespaces")
    __table_args__ = (UniqueConstraint("cluster_id", "name", name="uq_namespaces_cluster_name"), Index("ix_namespaces_cluster_status", "cluster_id", "status"))


class Workload(Base):
    __tablename__ = "workloads"

    id: Mapped[PrimaryKey]
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cluster_connections.id", ondelete="CASCADE"), nullable=False)
    namespace: Mapped[str] = mapped_column(String(253), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(253), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    labels: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    image: Mapped[str | None] = mapped_column(String(2048))

    __table_args__ = (UniqueConstraint("cluster_id", "namespace", "kind", "name", name="uq_workloads_identity"), Index("ix_workloads_cluster_namespace", "cluster_id", "namespace"))


class Pod(Base):
    __tablename__ = "pods"

    id: Mapped[PrimaryKey]
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cluster_connections.id", ondelete="CASCADE"), nullable=False)
    namespace: Mapped[str] = mapped_column(String(253), nullable=False)
    name: Mapped[str] = mapped_column(String(253), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    restarts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    age: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (UniqueConstraint("cluster_id", "namespace", "name", name="uq_pods_identity"), Index("ix_pods_cluster_namespace_status", "cluster_id", "namespace", "status"))


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[PrimaryKey]
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cluster_connections.id", ondelete="CASCADE"), nullable=False)
    namespace: Mapped[str] = mapped_column(String(253), nullable=False)
    name: Mapped[str] = mapped_column(String(253), nullable=False)
    replicas: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    image: Mapped[str | None] = mapped_column(String(2048))

    __table_args__ = (UniqueConstraint("cluster_id", "namespace", "name", name="uq_deployments_identity"), Index("ix_deployments_cluster_namespace_status", "cluster_id", "namespace", "status"))


class Service(Base):
    __tablename__ = "services"

    id: Mapped[PrimaryKey]
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cluster_connections.id", ondelete="CASCADE"), nullable=False)
    namespace: Mapped[str] = mapped_column(String(253), nullable=False)
    name: Mapped[str] = mapped_column(String(253), nullable=False)
    selector: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ports: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (UniqueConstraint("cluster_id", "namespace", "name", name="uq_services_identity"), Index("ix_services_cluster_namespace", "cluster_id", "namespace"))


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[PrimaryKey]
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cluster_connections.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(253), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (UniqueConstraint("cluster_id", "name", name="uq_nodes_identity"), Index("ix_nodes_cluster_status", "cluster_id", "status"))


class Event(Base):
    __tablename__ = "events"

    id: Mapped[PrimaryKey]
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cluster_connections.id", ondelete="CASCADE"), nullable=False)
    namespace: Mapped[str | None] = mapped_column(String(253))
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(253), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[CreatedAt]

    __table_args__ = (Index("ix_events_cluster_namespace_created", "cluster_id", "namespace", "created_at"),)


class AuditAction(Base):
    __tablename__ = "audit_actions"

    id: Mapped[PrimaryKey]
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(512), nullable=False)
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    result: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    context: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]

    actor: Mapped[UserAccount | None] = relationship(back_populates="audit_actions", foreign_keys="AuditAction.actor_id")
    __table_args__ = (Index("ix_audit_actions_created", "created_at"),)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[PrimaryKey]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    default_namespace: Mapped[str | None] = mapped_column(String(253))
    view_settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    user: Mapped[UserAccount] = relationship(back_populates="preferences")


class ApplicationSetting(Base):
    __tablename__ = "application_settings"

    id: Mapped[PrimaryKey]
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now().astimezone(),
        server_default=text("now()"),
    )


class ApplicationCredential(Base):
    __tablename__ = "application_credentials"

    id: Mapped[PrimaryKey]
    credential_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now().astimezone(),
        server_default=text("now()"),
    )


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"

    id: Mapped[PrimaryKey]
    provider: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_connected", server_default="not_connected")
    external_account_id: Mapped[str | None] = mapped_column(String(512))
    external_account_label: Mapped[str | None] = mapped_column(String(512))
    granted_scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    access_token_ciphertext: Mapped[str | None] = mapped_column(Text)
    refresh_token_ciphertext: Mapped[str | None] = mapped_column(Text)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(128))
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now().astimezone(),
        server_default=text("now()"),
    )

    __table_args__ = (Index("ix_integration_connections_status", "status"),)


class IntegrationOAuthState(Base):
    __tablename__ = "integration_oauth_states"

    id: Mapped[PrimaryKey]
    state_digest: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]

    __table_args__ = (Index("ix_integration_oauth_states_provider_expiry", "provider", "expires_at"),)


class AIModelConfig(Base):
    __tablename__ = "ai_model_configs"

    id: Mapped[PrimaryKey]
    provider_id: Mapped[str] = mapped_column(String(32), nullable=False)
    external_model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    friendly_name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    supports_streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    supports_tools: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    supports_reasoning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    supports_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    supports_large_context: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    availability: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", server_default="unknown")
    availability_message: Mapped[str | None] = mapped_column(String(512))
    availability_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now().astimezone(),
        server_default=text("now()"),
    )

    __table_args__ = (
        UniqueConstraint("provider_id", "external_model_id", name="uq_ai_model_configs_provider_external"),
        Index(
            "uq_ai_model_configs_global_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default = 1"),
        ),
        Index("ix_ai_model_configs_provider", "provider_id"),
        Index("ix_ai_model_configs_eligibility", "enabled", "availability"),
    )


class InstallationJob(Base):
    __tablename__ = "installation_jobs"

    id: Mapped[PrimaryKey]
    package_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    package_name: Mapped[str | None] = mapped_column(String(253), nullable=True)
    chart_name: Mapped[str | None] = mapped_column(String(253), nullable=True)
    chart_repository: Mapped[str | None] = mapped_column(String(253), nullable=True)
    chart_repository_url: Mapped[str | None] = mapped_column(String(2048))
    chart_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cluster_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    namespace: Mapped[str] = mapped_column(String(253), nullable=False)
    release_name: Mapped[str] = mapped_column(String(253), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", server_default="queued"
    )
    action: Mapped[str] = mapped_column(
        String(32), nullable=False, default="install", server_default="install"
    )
    revision: Mapped[int | None] = mapped_column(Integer())
    error_message: Mapped[str | None] = mapped_column(Text())
    log_output: Mapped[str | None] = mapped_column(Text())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]

    cluster: Mapped[ClusterConnection] = relationship(back_populates="installations")
    __table_args__ = (Index("ix_installation_jobs_cluster_status", "cluster_id", "status"),)
