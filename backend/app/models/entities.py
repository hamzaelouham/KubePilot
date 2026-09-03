from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAt, PrimaryKey


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id: Mapped[PrimaryKey]
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="operator", server_default="operator")
    created_at: Mapped[CreatedAt]

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    audit_actions: Mapped[list["AuditAction"]] = relationship(back_populates="actor")
    preferences: Mapped["UserPreference | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[PrimaryKey]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    issued_at: Mapped[CreatedAt]
    expires_at: Mapped[datetime]

    user: Mapped[UserAccount] = relationship(back_populates="sessions")
    __table_args__ = (Index("ix_sessions_active_expiry", "user_id", "expires_at"),)


class ClusterConnection(Base):
    __tablename__ = "cluster_connections"

    id: Mapped[PrimaryKey]
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    endpoint: Mapped[str] = mapped_column(String(2048), nullable=False)
    kubeconfig_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", server_default="unknown")
    created_at: Mapped[CreatedAt]

    namespaces: Mapped[list["Namespace"]] = relationship(back_populates="cluster", cascade="all, delete-orphan")
    __table_args__ = (Index("ix_cluster_connections_status", "status"),)


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
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[CreatedAt]

    actor: Mapped[UserAccount] = relationship(back_populates="audit_actions")
    __table_args__ = (Index("ix_audit_actions_created", "created_at"),)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[PrimaryKey]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    default_namespace: Mapped[str | None] = mapped_column(String(253))
    view_settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    user: Mapped[UserAccount] = relationship(back_populates="preferences")
