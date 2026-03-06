from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.sql import func

from app.config import settings
from app.database import async_session
from app.models import CostSnapshot
from app.schemas import (
    AggregatedAppCost,
    AggregatedCostResponse,
    CostComponent,
    CostCurrentResponse,
    CostHistoryResponse,
    DropletSummary,
)
from app.services.cost_calculator import DAYS_PER_MONTH

router = APIRouter(prefix="/api/cost", tags=["cost"])


@router.get("/current", response_model=CostCurrentResponse)
async def get_current_cost():
    """Get the latest cost snapshot for each monitored app."""
    configured_apps = list(settings.get_app_boundaries().keys())

    async with async_session() as session:
        latest_subq = (
            select(CostSnapshot.app_name, func.max(CostSnapshot.timestamp).label("max_ts"))
            .where(CostSnapshot.app_name.in_(configured_apps))
            .group_by(CostSnapshot.app_name)
            .subquery()
        )

        query = select(CostSnapshot).join(
            latest_subq,
            (CostSnapshot.app_name == latest_subq.c.app_name)
            & (CostSnapshot.timestamp == latest_subq.c.max_ts),
        )

        result = await session.execute(query)
        scores = result.scalars().all()

    return CostCurrentResponse(
        scores=[CostComponent.model_validate(s) for s in scores],
        total_monthly_cost=settings.total_monthly_cost,
        droplet_monthly=settings.droplet_cost,
        cloudflare_monthly=settings.cloudflare_cost,
        domain_monthly=settings.domain_cost,
        calculated_at=scores[0].timestamp if scores else datetime.now(timezone.utc),
    )


@router.get("/history", response_model=CostHistoryResponse)
async def get_cost_history(
    app_name: str = Query(..., description="App name to get history for"),
    hours: int = Query(24, ge=1, le=8760, description="Hours of history to return"),
):
    """Get historical cost snapshots for trend charts."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    async with async_session() as session:
        query = (
            select(CostSnapshot)
            .where(CostSnapshot.app_name == app_name, CostSnapshot.timestamp >= cutoff)
            .order_by(CostSnapshot.timestamp.asc())
        )

        result = await session.execute(query)
        scores = result.scalars().all()

    return CostHistoryResponse(
        app_name=app_name,
        scores=[CostComponent.model_validate(s) for s in scores],
        hours=hours,
    )


@router.get("/aggregated", response_model=AggregatedCostResponse)
async def get_aggregated_cost(
    minutes: int = Query(1440, ge=15, le=525960, description="Time window in minutes"),
):
    """Get aggregated cost data over a time window.

    Supported windows: 1440 (1 day), 10080 (1 week), 43200 (1 month), 525960 (1 year).
    """
    configured_apps = list(settings.get_app_boundaries().keys())
    boundaries = settings.get_app_boundaries()
    display_names = settings.get_app_display_names()

    # Window as a fraction of one month (e.g. 43200 min ≈ 1.0 month)
    minutes_per_month = DAYS_PER_MONTH * 24 * 60
    window_fraction = minutes / minutes_per_month
    app_count = len(configured_apps)

    async with async_session() as session:
        # Get average resource shares over the window (or latest snapshot)
        if minutes <= settings.calculation_interval_minutes:
            latest_subq = (
                select(CostSnapshot.app_name, func.max(CostSnapshot.timestamp).label("max_ts"))
                .where(CostSnapshot.app_name.in_(configured_apps))
                .group_by(CostSnapshot.app_name)
                .subquery()
            )
            query = select(CostSnapshot).join(
                latest_subq,
                (CostSnapshot.app_name == latest_subq.c.app_name)
                & (CostSnapshot.timestamp == latest_subq.c.max_ts),
            )
            result = await session.execute(query)
            rows = result.scalars().all()
            share_rows = [
                {
                    "app_name": r.app_name,
                    "cpu_share": r.cpu_share,
                    "memory_share": r.memory_share,
                    "network_share": r.network_share,
                    "cpu_seconds": r.cpu_seconds,
                    "memory_bytes_avg": r.memory_bytes_avg,
                    "network_bytes": r.network_bytes,
                    "snapshot_count": 1,
                }
                for r in rows
            ]
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            query = (
                select(
                    CostSnapshot.app_name,
                    func.avg(CostSnapshot.cpu_share).label("cpu_share"),
                    func.avg(CostSnapshot.memory_share).label("memory_share"),
                    func.avg(CostSnapshot.network_share).label("network_share"),
                    func.sum(CostSnapshot.cpu_seconds).label("cpu_seconds"),
                    func.avg(CostSnapshot.memory_bytes_avg).label("memory_bytes_avg"),
                    func.sum(CostSnapshot.network_bytes).label("network_bytes"),
                    func.count().label("snapshot_count"),
                )
                .where(CostSnapshot.app_name.in_(configured_apps), CostSnapshot.timestamp >= cutoff)
                .group_by(CostSnapshot.app_name)
            )
            result = await session.execute(query)
            rows = result.all()
            share_rows = [
                {
                    "app_name": r.app_name,
                    "cpu_share": float(r.cpu_share),
                    "memory_share": float(r.memory_share),
                    "network_share": float(r.network_share),
                    "cpu_seconds": float(r.cpu_seconds),
                    "memory_bytes_avg": float(r.memory_bytes_avg),
                    "network_bytes": float(r.network_bytes),
                    "snapshot_count": int(r.snapshot_count),
                }
                for r in rows
            ]

    # Project costs for the window duration using average shares
    app_scores = []
    for r in share_rows:
        resource_share = (
            settings.cpu_weight * r["cpu_share"]
            + settings.memory_weight * r["memory_share"]
        )
        droplet_cost = resource_share * settings.droplet_cost * window_fraction
        cloudflare_cost = r["network_share"] * settings.cloudflare_cost * window_fraction
        domain_cost = (settings.domain_cost / app_count) * window_fraction
        total_cost = droplet_cost + cloudflare_cost + domain_cost

        app_scores.append(
            AggregatedAppCost(
                app_name=r["app_name"],
                cpu_seconds=r["cpu_seconds"],
                memory_bytes_avg=r["memory_bytes_avg"],
                network_bytes=r["network_bytes"],
                cpu_share=r["cpu_share"],
                memory_share=r["memory_share"],
                network_share=r["network_share"],
                droplet_cost=droplet_cost,
                cloudflare_cost=cloudflare_cost,
                domain_cost=domain_cost,
                total_cost=total_cost,
                snapshot_count=r["snapshot_count"],
            )
        )

    # Compute droplet-level aggregate
    droplet = None
    if app_scores:
        all_containers = [c for containers in boundaries.values() for c in containers]
        droplet = DropletSummary(
            total_cost=sum(s.total_cost for s in app_scores),
            droplet_cost=sum(s.droplet_cost for s in app_scores),
            cloudflare_cost=sum(s.cloudflare_cost for s in app_scores),
            domain_cost=sum(s.domain_cost for s in app_scores),
            container_count=len(all_containers),
        )

    return AggregatedCostResponse(
        window_minutes=minutes,
        scores=app_scores,
        droplet=droplet,
        display_names=display_names,
        boundaries=boundaries,
    )
