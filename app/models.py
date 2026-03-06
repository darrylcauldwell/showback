from datetime import datetime

from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CostSnapshot(Base):
    __tablename__ = "cost_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_name: Mapped[str] = mapped_column(String(100), index=True)
    timestamp: Mapped[datetime] = mapped_column(index=True)

    # Resource usage (raw values for the period)
    cpu_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    memory_bytes_avg: Mapped[float] = mapped_column(Float, default=0.0)
    network_bytes: Mapped[float] = mapped_column(Float, default=0.0)

    # Resource shares (0.0 to 1.0)
    cpu_share: Mapped[float] = mapped_column(Float, default=0.0)
    memory_share: Mapped[float] = mapped_column(Float, default=0.0)
    network_share: Mapped[float] = mapped_column(Float, default=0.0)

    # Cost breakdown (USD for the period)
    droplet_cost: Mapped[float] = mapped_column(Float, default=0.0)
    cloudflare_cost: Mapped[float] = mapped_column(Float, default=0.0)
    domain_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)

    # Period length
    calculation_period_seconds: Mapped[int] = mapped_column(Integer, default=900)

    __table_args__ = (
        Index("ix_cost_app_timestamp", "app_name", "timestamp"),
    )
