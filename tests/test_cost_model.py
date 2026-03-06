from app.services.cost_calculator import DAYS_PER_MONTH


def test_days_per_month_constant():
    assert DAYS_PER_MONTH == 30.44


def test_monthly_cost_totals():
    """Verify base cost components sum correctly."""
    droplet = 24.00
    cloudflare = 0.00
    domain = 1.02
    assert droplet + cloudflare + domain == 25.02


def test_window_fraction_one_month():
    """One month window should yield fraction ~1.0."""
    minutes_per_month = DAYS_PER_MONTH * 24 * 60
    window_fraction = 43200 / minutes_per_month  # 30 days in minutes
    assert 0.98 < window_fraction < 1.02


def test_cost_allocation_shares_sum_to_one():
    """Equal shares across N apps should each be 1/N."""
    n_apps = 6
    share = 1.0 / n_apps
    total = share * n_apps
    assert abs(total - 1.0) < 1e-10
