from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, BigInteger, Boolean,
    UniqueConstraint, Index, ForeignKey, JSON,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    real_name = Column(String(100))
    email = Column(String(200))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_roles = relationship("UserRole", back_populates="user")


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    description = Column(String(500))


class UserRole(Base):
    __tablename__ = "user_roles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    user = relationship("User", back_populates="user_roles")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    created_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class UploadBatch(Base):
    __tablename__ = "upload_batches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_no = Column(String(50), nullable=False, unique=True)
    project_id = Column(Integer, nullable=False)
    ym = Column(String(7), nullable=False)
    uploaded_by = Column(Integer)
    file_name = Column(String(500))
    file_size = Column(BigInteger)
    status = Column(String(20), default="processing")
    created_at = Column(DateTime, default=datetime.utcnow)


class UploadLog(Base):
    __tablename__ = "upload_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, nullable=False)
    sheet_name = Column(String(200))
    template_id = Column(String(100))
    action = Column(String(20), default="matched")
    total_rows = Column(Integer, default=0)
    success_rows = Column(Integer, default=0)
    error_rows = Column(Integer, default=0)
    error_msg = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (Index("idx_batch", "batch_id"),)


class TemplateConfig(Base):
    __tablename__ = "template_configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(String(100), nullable=False, unique=True)
    description = Column(String(500))
    config_yaml = Column(Text, nullable=False)
    data_table = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
