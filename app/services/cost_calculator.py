import logging
from datetime import datetime, timezone

from app.config import settings
from app.database import async_session
from app.models import CostSnapshot
from app.services.prometheus import PrometheusClient

logger = logging.getLogger(__name__)

# Cached latest cost info for dashboard access
latest_cost_info: dict = {}

# Average days per month for cost allocation
DAYS_PER_MONTH = 30.44


async def calculate_all_costs() -> list[CostSnapshot]:
    """Run the full cost allocation pipeline for all configured apps.

    Queries Prometheus for CPU, memory, and network usage per app group,
    then allocates the fixed monthly costs proportionally.
    """
    period_seconds = settings.calculation_interval_minutes * 60
    boundaries = settings.get_app_boundaries()

    prom_client = PrometheusClient()

    # All container names across all apps
    all_containers = [c for containers in boundaries.values() for c in containers]

    # Step 1: Query Prometheus for all containers at once
    cpu_by_container = await prom_client.get_container_cpu_seconds(all_containers, period_seconds)
    mem_by_container = await prom_client.get_container_memory_avg(all_containers, period_seconds)
    net_by_container = await prom_client.get_container_network_bytes(all_containers, period_seconds)

    # Step 2: Aggregate per app
    app_cpu: dict[str, float] = {}
    app_mem: dict[str, float] = {}
    app_net: dict[str, float] = {}

    for app_name, container_names in boundaries.items():
        app_cpu[app_name] = sum(cpu_by_container.get(c, 0) for c in container_names)
        app_mem[app_name] = sum(mem_by_container.get(c, 0) for c in container_names)
        app_net[app_name] = sum(net_by_container.get(c, 0) for c in container_names)

    # Step 3: Calculate shares
    total_cpu = sum(app_cpu.values())
    total_mem = sum(app_mem.values())
    total_net = sum(app_net.values())

    app_count = len(boundaries)

    # Per-period cost (monthly cost prorated to this interval)
    periods_per_month = DAYS_PER_MONTH * 24 * 3600 / period_seconds
    period_droplet = settings.droplet_cost / periods_per_month
    period_cloudflare = settings.cloudflare_cost / periods_per_month
    period_domain = settings.domain_cost / periods_per_month

    snapshots: list[CostSnapshot] = []
    now = datetime.now(timezone.utc)

    for app_name in boundaries:
        cpu_share = app_cpu[app_name] / total_cpu if total_cpu > 0 else 1.0 / app_count
        mem_share = app_mem[app_name] / total_mem if total_mem > 0 else 1.0 / app_count
        net_share = app_net[app_name] / total_net if total_net > 0 else 1.0 / app_count

        # Droplet cost: weighted by CPU and memory shares
        resource_share = settings.cpu_weight * cpu_share + settings.memory_weight * mem_share
        droplet_cost = resource_share * period_droplet

        # Cloudflare cost: weighted by network share
        cloudflare_cost = net_share * period_cloudflare

        # Domain cost: split evenly
        domain_cost = period_domain / app_count

        total_cost = droplet_cost + cloudflare_cost + domain_cost

        snapshot = CostSnapshot(
            app_name=app_name,
            timestamp=now,
            cpu_seconds=app_cpu[app_name],
            memory_bytes_avg=app_mem[app_name],
            network_bytes=app_net[app_name],
            cpu_share=cpu_share,
            memory_share=mem_share,
            network_share=net_share,
            droplet_cost=droplet_cost,
            cloudflare_cost=cloudflare_cost,
            domain_cost=domain_cost,
            total_cost=total_cost,
            calculation_period_seconds=period_seconds,
        )
        snapshots.append(snapshot)

        logger.info(
            "Cost [%s]: $%.4f | CPU=%.1f%% MEM=%.1f%% NET=%.1f%% | cpu=%.1fs mem=%.0fMB",
            app_name,
            total_cost,
            cpu_share * 100,
            mem_share * 100,
            net_share * 100,
            app_cpu[app_name],
            app_mem[app_name] / 1024 / 1024,
        )

    # Step 4: Store results in database
    if snapshots:
        async with async_session() as session:
            session.add_all(snapshots)
            await session.commit()

    # Step 5: Update Prometheus gauges
    _update_prometheus_gauges(snapshots)

    # Cache for dashboard access
    latest_cost_info.clear()
    latest_cost_info.update({
        "total_monthly": settings.total_monthly_cost,
        "droplet_monthly": settings.droplet_cost,
        "cloudflare_monthly": settings.cloudflare_cost,
        "domain_monthly": settings.domain_cost,
    })

    return snapshots


def _update_prometheus_gauges(snapshots: list[CostSnapshot]) -> None:
    """Update custom Prometheus gauges with latest cost results."""
    try:
        from app.metrics import (
            COST_PER_APP_GAUGE,
            CPU_SHARE_GAUGE,
            MEMORY_SHARE_GAUGE,
            TOTAL_MONTHLY_COST_GAUGE,
        )

        TOTAL_MONTHLY_COST_GAUGE.set(settings.total_monthly_cost)

        for snapshot in snapshots:
            COST_PER_APP_GAUGE.labels(app=snapshot.app_name).set(snapshot.total_cost)
            CPU_SHARE_GAUGE.labels(app=snapshot.app_name).set(snapshot.cpu_share)
            MEMORY_SHARE_GAUGE.labels(app=snapshot.app_name).set(snapshot.memory_share)

    except Exception:
        logger.exception("Failed to update Prometheus gauges")
