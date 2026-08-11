#!/usr/bin/env python3
"""Small, model-neutral coach harness with deterministic safety and evidence gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta

from state_layers import multidomain_state, raw_signal_snapshot


TASK_ACTIONS = {
    "daily_guidance": {"ask", "maintain", "reduce", "rest", "suggest_session",
                       "seek_professional_help", "seek_emergency_help"},
    "post_workout": {"ask", "maintain", "reduce", "rest", "protective_activity",
                     "seek_professional_help", "seek_emergency_help"},
    "weekly_review": {"ask", "maintain", "reduce", "rest", "draft_plan",
                      "seek_professional_help", "seek_emergency_help"},
    "pain_followup": {"ask", "rest", "protective_activity", "seek_professional_help",
                      "seek_emergency_help"},
}
TOKEN_BUDGETS = {"daily_guidance": 3500, "post_workout": 3500,
                 "weekly_review": 5000, "pain_followup": 3000}
RED_FLAGS = {"chest_pain", "palpitations", "fainting", "joint_deformity",
             "cannot_bear_weight", "severe_breathing_difficulty"}
LEVEL = {"green": 0, "yellow": 1, "red": 2}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _compact_date(value):
    return datetime.strptime(value.replace("-", ""), "%Y%m%d").strftime("%Y%m%d")


def _recent_events(events, as_of, days=14):
    start = (datetime.strptime(as_of, "%Y%m%d") - timedelta(days=days - 1)).strftime("%Y%m%d")
    return [event for event in events if isinstance(event, dict)
            and start <= str(event.get("date", "")).replace("-", "") <= as_of]


def safety_gate(events, as_of):
    recent = _recent_events(events, as_of)
    red = []
    yellow = []
    for index, event in enumerate(recent):
        flags = set(event.get("red_flags") or [])
        matched = sorted(flags.intersection(RED_FLAGS))
        if matched:
            red.append({"event_index": index, "signals": matched})
        pain = event.get("pain")
        if isinstance(pain, (int, float)) and pain > 0:
            yellow.append({"event_index": index, "signal": "pain", "value": pain})
        if event.get("illness"):
            yellow.append({"event_index": index, "signal": "illness", "value": True})
        if event.get("function_limited") or event.get("worsening"):
            yellow.append({"event_index": index, "signal": "function_or_trend", "value": True})
    if red:
        return {"level": "red", "reasons": red, "training_actions_blocked": True,
                "required_action_types": ["seek_emergency_help"]}
    if yellow:
        return {"level": "yellow", "reasons": yellow, "training_actions_blocked": True,
                "required_action_types": ["protective_activity", "reduce", "rest",
                                          "seek_professional_help"]}
    return {"level": "green", "reasons": [], "training_actions_blocked": False,
            "required_action_types": []}


def build_context(payload, task, query=""):
    if task not in TASK_ACTIONS:
        raise ValueError("unknown task: %s" % task)
    week = payload.get("week") or {}
    mon = _compact_date(week["mon"])
    as_of = _compact_date(week["as_of"])
    daily = list(payload.get("history_daily") or []) + list(payload.get("daily") or [])
    daily = sorted(daily, key=lambda row: row.get("date", ""))
    events = _recent_events(payload.get("subjective_events") or [], as_of)
    state = multidomain_state(daily, mon, as_of)
    if task != "weekly_review":
        state = {
            "kind": state["kind"], "schema_version": state["schema_version"],
            "status": state["status"], "as_of": state["as_of"], "anchor": state["anchor"],
            "axes": [{key: axis.get(key) for key in
                      ("id", "label", "available", "index", "reliability", "meaning", "reason")
                      if key in axis} for axis in state["axes"]],
            "change_points": {"candidate_count": state["change_points"]["candidate_count"]},
            "warnings": state["warnings"],
        }
    recent_days = 14 if task == "weekly_review" else 7
    context = {
        "kind": "coach_context", "schema_version": 2, "task": task, "as_of": as_of,
        "query": query,
        "policy": {"allowed_action_types": sorted(TASK_ACTIONS[task]),
                   "medical_diagnosis": "forbidden", "plan_change_requires_confirmation": True,
                   "experimental_only_prescription": "forbidden"},
        "views": {
            "raw_signals": raw_signal_snapshot(daily, mon, as_of),
            "state": state,
            "recent_daily": daily[-recent_days:],
            "activities": payload.get("activities") or [],
            "current_plan": payload.get("current_plan"),
        },
        "recent_events": events,
        "safety_gate": safety_gate(events, as_of),
        "data_status": {"partial_week": bool(week.get("partial") or as_of < _compact_date(week["sun"])),
                        "missing_inputs": []},
    }
    if not events:
        context["data_status"]["missing_inputs"].append("subjective_events")
    unsigned = dict(context)
    context["content_sha256"] = stable_hash(unsigned)
    characters = len(_canonical(context))
    budget = TOKEN_BUDGETS[task]
    context["context_metrics"] = {"characters": characters,
                                  "approx_tokens": (characters + 1) // 2,
                                  "budget_tokens": budget,
                                  "within_budget": (characters + 1) // 2 <= budget}
    return context


def resolve_pointer(document, pointer):
    if pointer == "":
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("pointer must be a JSON Pointer")
    current = document
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise ValueError("pointer traverses a scalar")
    return current


def _same(first, second):
    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        return abs(float(first) - float(second)) <= 1e-9
    return first == second


def _expected_layer(pointer):
    if pointer.startswith("/views/raw_signals") or pointer.startswith("/views/recent_daily"):
        return "raw_signal"
    if pointer.startswith("/views/state"):
        return "experimental_model"
    if pointer.startswith("/recent_events"):
        return "user_event"
    if pointer.startswith("/safety_gate"):
        return "deterministic_metric"
    if pointer.startswith("/views/current_plan"):
        return "plan"
    return None


def _evidence_errors(item, path, context, require_value):
    errors = []
    if not isinstance(item, dict):
        return [{"code": "evidence", "path": path, "message": "evidence must be an object"}]
    if item.get("source") != "coach_context":
        errors.append({"code": "source", "path": path + ".source",
                       "message": "source must be coach_context"})
    pointer = item.get("pointer")
    if not isinstance(pointer, str):
        errors.append({"code": "pointer", "path": path + ".pointer",
                       "message": "pointer is required"})
        return errors
    expected = _expected_layer(pointer)
    if expected and item.get("layer") != expected:
        errors.append({"code": "layer", "path": path + ".layer",
                       "message": "expected layer %s" % expected})
    try:
        actual = resolve_pointer(context, pointer)
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        errors.append({"code": "pointer", "path": path + ".pointer", "message": str(exc)})
        return errors
    if require_value and "observed_value" not in item:
        errors.append({"code": "observed_value", "path": path + ".observed_value",
                       "message": "observed_value is required"})
    elif "observed_value" in item and not _same(item["observed_value"], actual):
        errors.append({"code": "value_mismatch", "path": path + ".observed_value",
                       "message": "observed_value does not match the pointer"})
    return errors


def validate_response(response, context):
    errors = []
    unsigned_context = {key: value for key, value in context.items()
                        if key not in {"content_sha256", "context_metrics"}}
    if stable_hash(unsigned_context) != context.get("content_sha256"):
        errors.append({"code": "context_hash", "path": "$context.content_sha256",
                       "message": "context content hash does not match"})
    if response.get("kind") != "coach_response" or response.get("schema_version") != 2:
        errors.append({"code": "contract", "path": "$", "message": "Response v2 is required"})
    if response.get("task") != context.get("task") or response.get("as_of") != context.get("as_of"):
        errors.append({"code": "context", "path": "$", "message": "task/as_of mismatch"})
    observations = response.get("observations") if isinstance(response.get("observations"), list) else []
    recommendations = response.get("recommendations") if isinstance(response.get("recommendations"), list) else []
    risks = response.get("risks") if isinstance(response.get("risks"), list) else []
    for index, observation in enumerate(observations):
        evidence = observation.get("evidence") if isinstance(observation, dict) else None
        if not evidence:
            errors.append({"code": "evidence", "path": "$.observations[%d]" % index,
                           "message": "observation needs evidence"})
            continue
        layers = {item.get("layer") for item in evidence if isinstance(item, dict)}
        for evidence_index, item in enumerate(evidence):
            errors.extend(_evidence_errors(item, "$.observations[%d].evidence[%d]" %
                                           (index, evidence_index), context, True))
        if observation.get("confidence") == "high" and "experimental_model" in layers:
            errors.append({"code": "experimental_confidence",
                           "path": "$.observations[%d].confidence" % index,
                           "message": "experimental evidence cannot be high confidence"})
    allowed = TASK_ACTIONS.get(context.get("task"), set())
    for index, recommendation in enumerate(recommendations):
        path = "$.recommendations[%d]" % index
        action = recommendation.get("action_type") if isinstance(recommendation, dict) else None
        if action not in allowed:
            errors.append({"code": "permission", "path": path + ".action_type",
                           "message": "action is not allowed for this task"})
        if recommendation.get("changes_plan") and not recommendation.get("requires_confirmation"):
            errors.append({"code": "confirmation", "path": path,
                           "message": "plan changes require confirmation"})
        evidence = recommendation.get("evidence") or []
        if not evidence:
            errors.append({"code": "evidence", "path": path, "message": "recommendation needs evidence"})
        layers = {item.get("layer") for item in evidence if isinstance(item, dict)}
        for evidence_index, item in enumerate(evidence):
            errors.extend(_evidence_errors(item, path + ".evidence[%d]" % evidence_index,
                                           context, False))
        if layers and layers <= {"experimental_model"} and action not in {"ask", "maintain"}:
            errors.append({"code": "experimental_only", "path": path,
                           "message": "experimental-only evidence cannot prescribe"})
    gate = (context.get("safety_gate") or {}).get("level", "green")
    response_level = max((LEVEL.get(item.get("level"), -1) for item in risks
                          if isinstance(item, dict)), default=0)
    if response_level < LEVEL.get(gate, 0):
        errors.append({"code": "safety_gate", "path": "$.risks",
                       "message": "response cannot downgrade the deterministic safety gate"})
    actions = {item.get("action_type") for item in recommendations if isinstance(item, dict)}
    if gate == "red":
        if "seek_emergency_help" not in actions or actions - {"seek_emergency_help"}:
            errors.append({"code": "safety_action", "path": "$.recommendations",
                           "message": "red gate requires emergency escalation and blocks training actions"})
    elif gate == "yellow" and actions.intersection({"maintain", "suggest_session", "draft_plan"}):
        errors.append({"code": "safety_action", "path": "$.recommendations",
                       "message": "yellow gate blocks normal training progression"})
    return {"valid": not errors, "errors": errors,
            "receipt": {"context_sha256": context.get("content_sha256"),
                        "response_sha256": stable_hash(response)}}


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(path, value):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Model-neutral coach harness demo")
    commands = parser.add_subparsers(dest="command", required=True)
    context = commands.add_parser("context")
    context.add_argument("input")
    context.add_argument("--task", required=True, choices=sorted(TASK_ACTIONS))
    context.add_argument("--query", default="")
    context.add_argument("--output", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("response")
    validate.add_argument("context")
    args = parser.parse_args(argv)
    if args.command == "context":
        result = build_context(_read(args.input), args.task, args.query)
        _write(args.output, result)
        print(json.dumps({"ok": True, "output": args.output,
                          "context_metrics": result["context_metrics"]}, ensure_ascii=False))
        return 0
    result = validate_response(_read(args.response), _read(args.context))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
