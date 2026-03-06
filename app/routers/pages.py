from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.sql import func

from app.config import settings
from app.database import async_session
from app.models import CostSnapshot
from app.services.cost_calculator import DAYS_PER_MONTH, latest_cost_info
from app.services.whatif import compare_providers

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main dashboard page."""
    configured_apps = list(settings.get_app_boundaries().keys())

    async with async_session() as session:
        # Get latest snapshots per app
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
        current_snapshots = result.scalars().all()

        # Get 7-day history for trend chart
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        history_query = (
            select(CostSnapshot)
            .where(CostSnapshot.app_name.in_(configured_apps), CostSnapshot.timestamp >= cutoff)
            .order_by(CostSnapshot.timestamp.asc())
        )

        history_result = await session.execute(history_query)
        history_snapshots = history_result.scalars().all()

    # Group history by app for Chart.js
    history_by_app: dict[str, list[dict]] = {}
    for snap in history_snapshots:
        if snap.app_name not in history_by_app:
            history_by_app[snap.app_name] = []
        history_by_app[snap.app_name].append({
            "timestamp": snap.timestamp.isoformat(),
            "total_cost": snap.total_cost,
            "droplet_cost": snap.droplet_cost,
            "cloudflare_cost": snap.cloudflare_cost,
            "domain_cost": snap.domain_cost,
            "cpu_share": snap.cpu_share,
            "memory_share": snap.memory_share,
        })

    # Compute droplet-level aggregate
    droplet: dict | None = None
    if current_snapshots:
        total_cost = sum(s.total_cost for s in current_snapshots)
        droplet_cost = sum(s.droplet_cost for s in current_snapshots)
        cloudflare_cost = sum(s.cloudflare_cost for s in current_snapshots)
        domain_cost = sum(s.domain_cost for s in current_snapshots)
        droplet = {
            "total_cost": total_cost,
            "droplet_cost": droplet_cost,
            "cloudflare_cost": cloudflare_cost,
            "domain_cost": domain_cost,
        }

    boundaries = settings.get_app_boundaries()
    all_containers = [c for containers in boundaries.values() for c in containers]

    if droplet and all_containers:
        droplet["container_count"] = len(all_containers)

    # Calculate the per-period interval label and monthly extrapolation
    calc_interval = settings.calculation_interval_minutes
    periods_per_month = DAYS_PER_MONTH * 24 * 60 / calc_interval

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "snapshots": current_snapshots,
            "droplet": droplet,
            "all_containers": all_containers,
            "history_by_app": history_by_app,
            "app_names": configured_apps,
            "cost_info": latest_cost_info,
            "display_names": settings.get_app_display_names(),
            "boundaries": boundaries,
            "calc_interval_minutes": calc_interval,
            "periods_per_month": periods_per_month,
            "settings": settings,
        },
    )


@router.get("/what-if", response_class=HTMLResponse)
async def what_if(request: Request):
    """Render the What-If cloud pricing comparison page."""
    initial_data = compare_providers()

    return templates.TemplateResponse(
        "whatif.html",
        {
            "request": request,
            "settings": settings,
            "initial_data": initial_data,
        },
    )


@router.get("/methodology", response_class=HTMLResponse)
async def methodology(request: Request):
    """Render the methodology transparency page."""
    return templates.TemplateResponse(
        "methodology.html",
        {
            "request": request,
            "settings": settings,
            "boundaries": settings.get_app_boundaries(),
            "display_names": settings.get_app_display_names(),
        },
    )
