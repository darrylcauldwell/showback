"""What-If cloud pricing comparison service.

Compares the current Digital Ocean droplet cost against equivalent
offerings from AWS, Azure, GCP, and other DO plans.
"""

import json
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

PRICING_PATH = Path(__file__).parent.parent / "static" / "data" / "cloud_pricing.json"

CURRENT_PROVIDER = "DO"
CURRENT_PLAN = "s-2vcpu-4gb"


def load_cloud_pricing() -> list[dict]:
    """Load cloud pricing data from the bundled JSON file."""
    with open(PRICING_PATH) as f:
        return json.load(f)


def compare_providers() -> dict:
    """Compare current droplet cost against equivalent cloud offerings.

    Returns comparison data including current plan details and alternatives
    sorted by monthly cost ascending (cheapest first).
    """
    plans = load_cloud_pricing()
    current_cost = settings.droplet_cost + settings.cloudflare_cost + settings.domain_cost

    results = []
    for plan in plans:
        monthly = plan["monthly_cost"]
        # Add domain cost to make comparison fair (you'd need it on any provider)
        total_monthly = monthly + settings.domain_cost

        is_current = plan["provider"] == CURRENT_PROVIDER and plan["plan"] == CURRENT_PLAN

        if is_current:
            delta_percent = 0.0
        elif current_cost > 0:
            delta_percent = ((total_monthly - current_cost) / current_cost) * 100
        else:
            delta_percent = 0.0

        results.append({
            "provider": plan["provider"],
            "plan": plan["plan"],
            "location": plan["location"],
            "vcpus": plan["vcpus"],
            "memory_gb": plan["memory_gb"],
            "disk_gb": plan["disk_gb"],
            "monthly_cost": monthly,
            "total_monthly": total_monthly,
            "is_current": is_current,
            "delta_percent": round(delta_percent, 1),
            "notes": plan.get("notes", ""),
        })

    # Filter to plans that meet or exceed current spec
    results = [
        r for r in results
        if r["vcpus"] >= settings.host_vcpus
        and r["memory_gb"] >= settings.host_memory_gb
        and r["disk_gb"] >= settings.host_disk_gb
    ]

    # Sort by total monthly cost ascending
    results.sort(key=lambda r: r["total_monthly"])

    # Find cheapest non-current option that meets or exceeds current spec
    cheapest = None
    for r in results:
        if (
            not r["is_current"]
            and r["vcpus"] >= settings.host_vcpus
            and r["memory_gb"] >= settings.host_memory_gb
            and r["disk_gb"] >= settings.host_disk_gb
        ):
            cheapest = r
            break

    return {
        "current_cost": current_cost,
        "current_provider": CURRENT_PROVIDER,
        "current_plan": CURRENT_PLAN,
        "host_vcpus": settings.host_vcpus,
        "host_memory_gb": settings.host_memory_gb,
        "host_disk_gb": settings.host_disk_gb,
        "cheapest": cheapest,
        "plans": results,
    }
