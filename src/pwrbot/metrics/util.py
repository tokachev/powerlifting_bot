"""Shared helpers for metrics computation."""

from __future__ import annotations

from datetime import date


def iso_week_label(d: date) -> str:
    """Return ISO week string like '2026-W15'."""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"
