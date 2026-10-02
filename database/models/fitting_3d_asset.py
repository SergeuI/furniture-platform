from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


class Fitting3DAssetModel(Base):
    __tablename__ = "fitting_3d_assets"
    __table_args__ = (Index("uq_fitting_3d_assets_fitting_id", "fitting_id", unique=True),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    fitting_id = Column(Integer, ForeignKey("fittings.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="draft")
    canonical_format = Column(String(16), nullable=False, default="glb")
    canonical_file_url = Column(Text, nullable=True)
    canonical_file_size = Column(Integer, nullable=True)
    canonical_sha256 = Column(String(64), nullable=True)
    units = Column(String(16), nullable=True)
    dimensions_x = Column(Float, nullable=True)
    dimensions_y = Column(Float, nullable=True)
    dimensions_z = Column(Float, nullable=True)
    bbox_min_x = Column(Float, nullable=True)
    bbox_min_y = Column(Float, nullable=True)
    bbox_min_z = Column(Float, nullable=True)
    bbox_max_x = Column(Float, nullable=True)
    bbox_max_y = Column(Float, nullable=True)
    bbox_max_z = Column(Float, nullable=True)
    axis_up = Column(String(8), nullable=True)
    axis_forward = Column(String(8), nullable=True)
    origin_x = Column(Float, nullable=True)
    origin_y = Column(Float, nullable=True)
    origin_z = Column(Float, nullable=True)
    rotation_x = Column(Float, nullable=True)
    rotation_y = Column(Float, nullable=True)
    rotation_z = Column(Float, nullable=True)
    coordinate_system_configured = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    validated_at = Column(DateTime, nullable=True)

    fitting = relationship("FittingModel", back_populates="three_d_asset")
    sources = relationship("Fitting3DAssetSourceModel", back_populates="asset", cascade="all, delete-orphan", order_by="Fitting3DAssetSourceModel.order_index")


class Fitting3DAssetSourceModel(Base):
    __tablename__ = "fitting_3d_asset_sources"
    __table_args__ = (Index("ix_fitting_3d_asset_sources_asset_order", "asset_id", "order_index"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("fitting_3d_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    file_role = Column(String(32), nullable=False)
    file_format = Column(String(16), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=True)
    file_size = Column(Integer, nullable=True)
    sha256 = Column(String(64), nullable=True)
    order_index = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    asset = relationship("Fitting3DAssetModel", back_populates="sources")
