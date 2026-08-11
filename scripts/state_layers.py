#!/usr/bin/env python3
"""Vendor-neutral personal baseline, multidomain state, and change candidates.

All outputs are descriptive. A score of 50 is the individual's historical
anchor, not a health threshold. Experimental layers must not independently
trigger training or medical decisions.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta


SIGNALS = (
    {"key": "sleep_duration_min", "label": "睡眠时长", "unit": "min",
     "axis": "sleep_circadian", "polarity": 1},
    {"key": "sleep_efficiency", "label": "睡眠效率", "unit": "%",
     "axis": "sleep_circadian", "polarity": 1},
    {"key": "hrv_rmssd", "label": "HRV RMSSD", "unit": "ms",
     "axis": "recovery_autonomic", "polarity": 1},
    {"key": "resting_hr", "label": "静息心率", "unit": "bpm",
     "axis": "recovery_autonomic", "polarity": -1},
    {"key": "training_load", "label": "训练负荷", "unit": "a.u.",
     "axis": None, "polarity": 0},
    {"key": "vo2max", "label": "VO₂max", "unit": "ml/kg/min",
     "axis": "running_performance", "polarity": 1},
    {"key": "running_ability", "label": "跑步能力", "unit": "a.u.",
     "axis": "running_performance", "polarity": 1},
    {"key": "stress", "label": "压力", "unit": "a.u.",
     "axis": "health_stress", "polarity": -1},
)

AXES = (
    ("recovery_autonomic", "自主神经与恢复"),
    ("sleep_circadian", "睡眠与昼夜节律"),
    ("training_load_fatigue", "训练负荷与残余疲劳"),
    ("running_performance", "跑步表现与能力"),
    ("health_stress", "日常压力与健康信号"),
)


def _finite(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _day(value):
    return datetime.strptime(value.replace("-", ""), "%Y%m%d")


def _median(values):
    values = sorted(values)
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2.0


def _sample_sd(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _scale(values, center=None):
    center = _median(values) if center is None else center
    deviations = [abs(value - center) for value in values]
    mad = _median(deviations) or 0.0
    return max(1.4826 * mad, _sample_sd(values), abs(center or 0.0) * 0.05, 1e-6)


def _score(z):
    return round(50.0 + 50.0 * math.tanh(max(-4.0, min(4.0, z)) / 2.0), 1)


def _records(daily):
    return [(index, row) for index, row in enumerate(daily)
            if isinstance(row, dict) and isinstance(row.get("date"), str)]


def raw_signal_snapshot(daily, mon, as_of, baseline_days=28):
    """Keep raw metrics separate from interpretation and model scores."""
    mon_day = _day(mon)
    baseline_start = (mon_day - timedelta(days=baseline_days)).strftime("%Y%m%d")
    baseline_end = (mon_day - timedelta(days=1)).strftime("%Y%m%d")
    cards = []
    rows = _records(daily)
    for spec in SIGNALS:
        current = [(index, row["date"], float(row[spec["key"]])) for index, row in rows
                   if mon <= row["date"] <= as_of and _finite(row.get(spec["key"]))]
        if not current:
            continue
        baseline = [float(row[spec["key"]]) for _, row in rows
                    if baseline_start <= row["date"] <= baseline_end
                    and _finite(row.get(spec["key"]))]
        current_values = [value for _, _, value in current]
        current_mean = sum(current_values) / len(current_values)
        baseline_mean = sum(baseline) / len(baseline) if baseline else None
        latest_index, latest_date, latest_value = current[-1]
        cards.append({
            "key": spec["key"], "label": spec["label"], "unit": spec["unit"],
            "latest_date": latest_date, "latest": round(latest_value, 2),
            "week_mean": round(current_mean, 2),
            "baseline_28d_mean": round(baseline_mean, 2) if baseline_mean is not None else None,
            "delta_vs_baseline": round(current_mean - baseline_mean, 2)
            if baseline_mean is not None else None,
            "n_week": len(current), "n_baseline": len(baseline),
            "source": "input", "pointer": "/daily/%d/%s" % (latest_index, spec["key"]),
        })
    return cards


def _axis_state(daily, axis_id, label, mon, as_of, baseline_days=42):
    mon_day = _day(mon)
    start = (mon_day - timedelta(days=baseline_days)).strftime("%Y%m%d")
    elapsed = max(1, (_day(as_of) - mon_day).days + 1)
    components = {}
    weighted = []
    weights = []
    for spec in (item for item in SIGNALS if item["axis"] == axis_id):
        baseline = [float(row[spec["key"]]) for _, row in _records(daily)
                    if start <= row["date"] < mon and _finite(row.get(spec["key"]))]
        current = [float(row[spec["key"]]) for _, row in _records(daily)
                   if mon <= row["date"] <= as_of and _finite(row.get(spec["key"]))]
        if len(baseline) < 7 or not current:
            continue
        center = _median(baseline)
        current_mean = sum(current) / len(current)
        oriented_z = spec["polarity"] * (current_mean - center) / _scale(baseline, center)
        reliability = min(1.0, len(baseline) / 28.0) * min(1.0, len(current) / elapsed)
        component_score = _score(oriented_z)
        components[spec["key"]] = {
            "score": component_score, "oriented_z": round(oriented_z, 2),
            "current_mean": round(current_mean, 2), "baseline_median": round(center, 2),
            "n_current": len(current), "n_baseline": len(baseline),
            "reliability": round(reliability, 3),
        }
        weighted.append(component_score * reliability)
        weights.append(reliability)
    if not weights or sum(weights) <= 0:
        return {"id": axis_id, "label": label, "available": False,
                "reason": "insufficient_history_or_current_data", "components": {}}
    index = sum(weighted) / sum(weights)
    return {"id": axis_id, "label": label, "available": True,
            "index": round(index, 1), "centered_delta": round(index - 50.0, 1),
            "reliability": round(sum(weights) / len(weights), 3),
            "components": components, "baseline_days": baseline_days}


def change_candidates(daily, as_of, recent_days=7, baseline_days=28):
    """Robust recent-vs-prior shifts; candidates are not alerts or causes."""
    as_of_day = _day(as_of)
    recent_start = (as_of_day - timedelta(days=recent_days - 1)).strftime("%Y%m%d")
    baseline_end = (as_of_day - timedelta(days=recent_days)).strftime("%Y%m%d")
    baseline_start = (as_of_day - timedelta(days=recent_days + baseline_days - 1)).strftime("%Y%m%d")
    signals = []
    for spec in SIGNALS:
        baseline = [float(row[spec["key"]]) for _, row in _records(daily)
                    if baseline_start <= row["date"] <= baseline_end
                    and _finite(row.get(spec["key"]))]
        recent = [float(row[spec["key"]]) for _, row in _records(daily)
                  if recent_start <= row["date"] <= as_of and _finite(row.get(spec["key"]))]
        if len(baseline) < 14 or len(recent) < 3:
            continue
        center = _median(baseline)
        recent_center = _median(recent)
        shift_z = (recent_center - center) / _scale(baseline, center)
        signals.append({
            "key": spec["key"], "baseline_median": round(center, 2),
            "recent_median": round(recent_center, 2),
            "robust_shift_z": round(shift_z, 2), "candidate": abs(shift_z) >= 2.5,
            "n_baseline": len(baseline), "n_recent": len(recent),
        })
    return {"kind": "change_candidates", "status": "descriptive_not_validated",
            "as_of": as_of, "candidate_count": sum(row["candidate"] for row in signals),
            "signals": signals,
            "warning": "Statistical shifts are not medical alerts, causes, or prescriptions."}


def multidomain_state(daily, mon, as_of):
    axes = [_axis_state(daily, axis_id, label, mon, as_of) for axis_id, label in AXES]
    available = [axis for axis in axes if axis["available"]]
    elapsed = max(1, (_day(as_of) - _day(mon)).days + 1)
    mean_reliability = (sum(axis["reliability"] for axis in available) / len(available)
                        if available else 0.0)
    confidence = round(100.0 * (0.6 * mean_reliability + 0.4 * len(available) / len(AXES))
                       * math.sqrt(min(1.0, elapsed / 7.0)), 1)
    axes.append({"id": "data_confidence", "label": "数据质量与模型可信度",
                 "available": True, "index": confidence,
                 "meaning": "Coverage and history sufficiency; not body state."})
    return {"kind": "multidomain_state", "schema_version": 1, "status": "experimental",
            "as_of": as_of, "anchor": 50, "axes": axes,
            "change_points": change_candidates(daily, as_of),
            "warnings": ["50 is a personal historical anchor, not a health threshold.",
                         "Shared inputs are not independent physiological evidence.",
                         "This layer must not independently trigger a prescription."]}
