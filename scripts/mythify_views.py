"""Read-only dashboard and progress surfaces for the Mythify CLI."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from mythify_io import read_json, read_jsonl, read_jsonl_since, write_json_atomic
from mythify_outcomes import (
    get_active_outcome_slug,
    list_outcomes,
    load_outcome,
    outcome_iterations_path,
)

WORKSPACE_DIR_NAME = ".mythify"
REPORT_SINCE_MODES = ("last", "start")
REPORT_FORMATS = ("chat", "json")
DEFAULT_REPORT_RECENT = 8
DEFAULT_REPORT_ATTENTION = 5


def _missing_dependency(*_args, **_kwargs):
    raise RuntimeError("mythify_views dependencies are not configured")


get_active_slug = _missing_dependency
load_plan = _missing_dependency
plan_progress = _missing_dependency
next_pending_step = _missing_dependency
load_memory = _missing_dependency
load_lessons = _missing_dependency
global_lessons_dir = _missing_dependency
list_plan_slugs = _missing_dependency
format_step_line = _missing_dependency
timestamp_sort_key = _missing_dependency
timestamp_after = _missing_dependency
now_iso = _missing_dependency
slugify = _missing_dependency


def fail(message):
    print(message, file=sys.stderr)


def configure_views(
    *,
    get_active_slug_func=None,
    load_plan_func=None,
    plan_progress_func=None,
    next_pending_step_func=None,
    load_memory_func=None,
    load_lessons_func=None,
    global_lessons_dir_func=None,
    list_plan_slugs_func=None,
    format_step_line_func=None,
    timestamp_sort_key_func=None,
    timestamp_after_func=None,
    now_iso_func=None,
    slugify_func=None,
    fail_func=None,
):
    global get_active_slug, load_plan, plan_progress, next_pending_step
    global load_memory, load_lessons, global_lessons_dir, list_plan_slugs
    global format_step_line, timestamp_sort_key, timestamp_after, now_iso, slugify
    global fail
    if get_active_slug_func is not None:
        get_active_slug = get_active_slug_func
    if load_plan_func is not None:
        load_plan = load_plan_func
    if plan_progress_func is not None:
        plan_progress = plan_progress_func
    if next_pending_step_func is not None:
        next_pending_step = next_pending_step_func
    if load_memory_func is not None:
        load_memory = load_memory_func
    if load_lessons_func is not None:
        load_lessons = load_lessons_func
    if global_lessons_dir_func is not None:
        global_lessons_dir = global_lessons_dir_func
    if list_plan_slugs_func is not None:
        list_plan_slugs = list_plan_slugs_func
    if format_step_line_func is not None:
        format_step_line = format_step_line_func
    if timestamp_sort_key_func is not None:
        timestamp_sort_key = timestamp_sort_key_func
    if timestamp_after_func is not None:
        timestamp_after = timestamp_after_func
    if now_iso_func is not None:
        now_iso = now_iso_func
    if slugify_func is not None:
        slugify = slugify_func
    if fail_func is not None:
        fail = fail_func


def _contains_any(text, needles):
    lower = str(text or "").lower()
    return any(needle in lower for needle in needles)


def current_in_progress_step(plan):
    for step in plan.get("steps", []):
        if step.get("status") == "in_progress":
            return step
    return None


def recent_records(records, limit):
    if limit <= 0:
        return []
    return records[-limit:]


def build_dashboard(state, recent=3):
    active = get_active_slug(state)
    active_plan = None
    if active:
        plan = load_plan(state, active)
        if plan is not None:
            done, total = plan_progress(plan)
            active_plan = {
                "slug": active,
                "goal": plan.get("goal", ""),
                "completed_steps": done,
                "total_steps": total,
                "current_step": current_in_progress_step(plan),
                "next_pending_step": next_pending_step(plan),
                "steps": plan.get("steps", []),
            }
    active_outcome_slug = get_active_outcome_slug(state)
    active_outcome = None
    if active_outcome_slug:
        slug, goal = load_outcome(state, active_outcome_slug)
        if goal is not None:
            iterations = read_jsonl(outcome_iterations_path(state, slug))
            active_outcome = {
                "slug": slug,
                "goal": goal.get("goal", ""),
                "status": goal.get("status", "active"),
                "iteration_count": goal.get("iteration_count", 0),
                "max_iterations": goal.get("max_iterations", 1),
                "last_iteration": iterations[-1] if iterations else None,
            }
    memory = load_memory(state)
    project_lessons = load_lessons(state / "lessons", "project")
    global_lessons = load_lessons(global_lessons_dir(), "global")
    verifications = read_jsonl(state / "verifications.jsonl")
    executed = [record for record in verifications if record.get("kind") == "executed"]
    reflections = read_jsonl(state / "reflections.jsonl")
    return {
        "state_dir": str(state),
        "active_plan": active_plan,
        "active_outcome": active_outcome,
        "counts": {
            "memory": len(memory["entries"]),
            "project_lessons": len(project_lessons),
            "global_lessons": len(global_lessons),
            "verifications": len(verifications),
            "reflections": len(reflections),
        },
        "verification_summary": {
            "executed": len(executed),
            "executed_passed": sum(1 for record in executed if record.get("verified") is True),
            "executed_failed": sum(1 for record in executed if record.get("verified") is False),
            "attested": sum(1 for record in verifications if record.get("kind") == "attested"),
            "recent": recent_records(verifications, recent),
        },
        "reflection_summary": {
            "total": len(reflections),
            "recent": recent_records(reflections, recent),
        },
    }


def format_dashboard(dashboard):
    lines = ["[OK] Workflow dashboard: {0}".format(dashboard["state_dir"])]
    plan = dashboard.get("active_plan")
    if plan:
        lines.append(
            "Active plan: {0} ({1}/{2} completed)".format(
                plan["slug"], plan["completed_steps"], plan["total_steps"]
            )
        )
        lines.append("Goal: {0}".format(plan.get("goal", "")))
        current = plan.get("current_step")
        if current:
            lines.append("Current step: {0}".format(format_step_line(current, "").strip()))
        next_step = plan.get("next_pending_step")
        if next_step:
            lines.append(
                "Next pending: {0}. {1} (criteria: {2})".format(
                    next_step.get("id"),
                    next_step.get("title"),
                    next_step.get("success_criteria") or "none",
                )
            )
        elif not current:
            lines.append("Next pending: none")
    else:
        lines.append("Active plan: none")
    outcome = dashboard.get("active_outcome")
    if outcome:
        lines.append(
            "Active outcome: {0} ({1}, {2}/{3} iterations)".format(
                outcome["slug"],
                outcome["status"],
                outcome["iteration_count"],
                outcome["max_iterations"],
            )
        )
    else:
        lines.append("Active outcome: none")
    counts = dashboard["counts"]
    lines.append(
        "Counts: memory {0}, lessons {1} project + {2} global, verifications {3}, reflections {4}".format(
            counts["memory"],
            counts["project_lessons"],
            counts["global_lessons"],
            counts["verifications"],
            counts["reflections"],
        )
    )
    verification = dashboard["verification_summary"]
    lines.append(
        "Evidence: {0} executed ({1} passed, {2} failed), {3} attested".format(
            verification["executed"],
            verification["executed_passed"],
            verification["executed_failed"],
            verification["attested"],
        )
    )
    if verification["recent"]:
        lines.append("Recent verification:")
        for record in verification["recent"]:
            if record.get("kind") == "executed":
                verdict = "passed" if record.get("verified") is True else "failed"
                label = record.get("claim") or record.get("command") or "executed check"
                lines.append(
                    "  - {0}: {1} (exit {2})".format(
                        verdict, label, record.get("exit_code")
                    )
                )
            else:
                lines.append(
                    "  - attested: {0}".format(record.get("claim") or "claim")
                )
    reflections = dashboard["reflection_summary"]
    if reflections["recent"]:
        lines.append("Recent reflection:")
        for record in reflections["recent"]:
            lines.append(
                "  - {0}: {1}; next {2}".format(
                    record.get("outcome", "unknown"),
                    record.get("action", ""),
                    record.get("next", ""),
                )
            )
    return "\n".join(lines)


def cmd_dashboard(args, state):
    dashboard = build_dashboard(state, args.recent)
    if args.json_output:
        print(json.dumps(dashboard, indent=2))
    else:
        print(format_dashboard(dashboard))
    return 0


VERIFICATION_HISTORY_ICONS = {
    "passed": "[x]",
    "failed": "[!]",
    "attested": "[~]",
    "unknown": "[ ]",
}


def verification_verdict(record):
    if record.get("kind") == "attested":
        return "attested"
    if record.get("kind") == "executed" and record.get("verified") is True:
        return "passed"
    if record.get("kind") == "executed" and record.get("verified") is False:
        return "failed"
    return "unknown"


def summarize_verification_record(record, index):
    kind = record.get("kind", "unknown")
    verdict = verification_verdict(record)
    summary = {
        "index": index,
        "kind": kind,
        "verdict": verdict,
        "timestamp": record.get("timestamp", ""),
        "claim": record.get("claim"),
        "verified": record.get("verified"),
        "plan": record.get("plan"),
        "step_id": record.get("step_id"),
        "step_title": record.get("step_title"),
        "step_status": record.get("step_status"),
    }
    if kind == "executed":
        summary.update(
            {
                "command": record.get("command", ""),
                "exit_code": record.get("exit_code"),
                "duration_seconds": record.get("duration_seconds", 0),
                "stdout_tail_bytes": len(record.get("stdout_tail", "") or ""),
                "stderr_tail_bytes": len(record.get("stderr_tail", "") or ""),
            }
        )
    elif kind == "attested":
        summary.update(
            {
                "evidence": record.get("evidence", ""),
            }
        )
    return summary


def build_verification_history_view(state, recent=10):
    records = read_jsonl(state / "verifications.jsonl")
    rows = [
        summarize_verification_record(record, index + 1)
        for index, record in enumerate(records)
    ]
    executed = [row for row in rows if row["kind"] == "executed"]
    counts = {
        "total": len(rows),
        "executed": len(executed),
        "executed_passed": sum(1 for row in executed if row["verdict"] == "passed"),
        "executed_failed": sum(1 for row in executed if row["verdict"] == "failed"),
        "attested": sum(1 for row in rows if row["kind"] == "attested"),
        "unknown": sum(1 for row in rows if row["verdict"] == "unknown"),
    }
    if recent <= 0:
        recent_rows = []
    else:
        recent_rows = list(reversed(rows[-recent:]))
    return {
        "state_dir": str(state),
        "records": recent_rows,
        "counts": counts,
        "guardrail": (
            "history displays recorded evidence only; it does not rerun checks "
            "or upgrade attested claims"
        ),
    }


def verification_label(row):
    return compact_label(
        row.get("claim") or row.get("command") or row.get("evidence"),
        "verification",
    )


def format_verification_history_row(row):
    icon = VERIFICATION_HISTORY_ICONS.get(row.get("verdict"), "[ ]")
    label = verification_label(row)
    prefix = "  {0} {1} #{2} {3}: {4}".format(
        icon,
        row.get("timestamp") or "unknown-time",
        row.get("index"),
        row.get("verdict"),
        label,
    )
    details = []
    if row.get("kind") == "executed":
        details.append("exit {0}".format(row.get("exit_code")))
        details.append("{0}s".format(row.get("duration_seconds", 0)))
        if row.get("stdout_tail_bytes"):
            details.append("stdout {0} bytes".format(row.get("stdout_tail_bytes")))
        if row.get("stderr_tail_bytes"):
            details.append("stderr {0} bytes".format(row.get("stderr_tail_bytes")))
    elif row.get("kind") == "attested":
        details.append("self-reported")
    if row.get("plan"):
        step = row.get("step_id")
        if step is not None:
            details.append("plan {0} step {1}".format(row.get("plan"), step))
        else:
            details.append("plan {0}".format(row.get("plan")))
    if details:
        prefix += " ({0})".format("; ".join(details))
    return prefix


def format_verification_history_view(view):
    lines = ["[OK] Verification history: {0}".format(view["state_dir"])]
    counts = view["counts"]
    lines.append(
        "Evidence: {0} executed ({1} passed, {2} failed), {3} attested, {4} total".format(
            counts["executed"],
            counts["executed_passed"],
            counts["executed_failed"],
            counts["attested"],
            counts["total"],
        )
    )
    if view["records"]:
        lines.append("Recent verification:")
        for row in view["records"]:
            lines.append(format_verification_history_row(row))
    else:
        lines.append("No verification records found.")
    lines.append("Guardrail: {0}.".format(view["guardrail"]))
    return "\n".join(lines)


def cmd_history(args, state):
    view = build_verification_history_view(state, args.recent)
    if args.json_output:
        print(json.dumps(view, indent=2))
    else:
        print(format_verification_history_view(view))
    return 0


def reports_dir(state):
    return state / "reports"


def report_cursor_name(name):
    return slugify(name or "default") or "default"


def report_cursor_path(state, cursor):
    return reports_dir(state) / (report_cursor_name(cursor) + ".json")


def report_event_sort_key(event):
    return (
        timestamp_sort_key(event.get("timestamp", "")),
        event.get("order", 0),
        event.get("key", ""),
    )


def compact_report_detail(text):
    value = str(text or "").strip()
    return value if len(value) <= 140 else value[:137] + "..."


def report_attention_level(event):
    kind = event.get("kind", "")
    if (
        event.get("verified") is False
        or kind == "step_failed"
        or kind == "reflection_failure"
    ):
        return "issue"
    if kind == "verification_attested":
        return "warning"
    return ""


def build_report_attention_events(events):
    items = []
    for event in events:
        level = report_attention_level(event)
        if not level:
            continue
        items.append(
            {
                "level": level,
                "key": event.get("key", ""),
                "timestamp": event.get("timestamp", ""),
                "kind": event.get("kind", ""),
                "summary": event.get("summary", "Event recorded"),
                "detail": event.get("detail", ""),
                "plan": event.get("plan"),
                "step_id": event.get("step_id"),
                "verified": event.get("verified"),
            }
        )
    return items


def build_report_events(state, log_lower_bound=""):
    events = []
    for slug in list_plan_slugs(state):
        plan = load_plan(state, slug)
        if plan is None:
            continue
        created = plan.get("created") or plan.get("last_updated") or ""
        steps = plan.get("steps", [])
        events.append(
            {
                "key": "plan:{0}:created".format(slug),
                "timestamp": created,
                "order": 10,
                "kind": "plan_created",
                "summary": "Plan created: {0} ({1} steps)".format(slug, len(steps)),
                "detail": plan.get("goal", ""),
                "plan": slug,
                "step_id": None,
                "verified": None,
            }
        )
        for step in steps:
            updated = step.get("updated_at")
            if not updated:
                continue
            status = step.get("status", "pending")
            detail = step.get("result") or step.get("success_criteria") or ""
            events.append(
                {
                    "key": "step:{0}:{1}:{2}:{3}".format(
                        slug, step.get("id"), status, updated
                    ),
                    "timestamp": updated,
                    "order": 20,
                    "kind": "step_" + status,
                    "summary": "Step {0}: {1}. {2}".format(
                        status, step.get("id"), step.get("title")
                    ),
                    "detail": detail,
                    "plan": slug,
                    "step_id": step.get("id"),
                    "verified": None,
                }
            )
    verifications = read_jsonl_since(state / "verifications.jsonl", log_lower_bound)
    for index, record in enumerate(verifications, start=1):
        kind = record.get("kind", "unknown")
        if kind == "executed":
            passed = record.get("verified") is True
            verdict = "passed" if passed else "failed"
            label = record.get("claim") or record.get("command") or "executed check"
            summary = "Verification {0}: {1}".format(verdict, compact_report_detail(label))
            detail = "exit {0}".format(record.get("exit_code"))
            verified = passed
        elif kind == "attested":
            label = record.get("claim") or "claim"
            summary = "Verification attested: {0}".format(compact_report_detail(label))
            detail = "self-reported, not machine-checked"
            verified = None
        else:
            summary = "Verification recorded"
            detail = ""
            verified = None
        events.append(
            {
                "key": "verification:{0}:{1}".format(index, record.get("timestamp", "")),
                "timestamp": record.get("timestamp", ""),
                "order": 30,
                "kind": "verification_" + verification_verdict(record),
                "summary": summary,
                "detail": detail,
                "plan": record.get("plan"),
                "step_id": record.get("step_id"),
                "verified": verified,
            }
        )
    reflections = read_jsonl_since(state / "reflections.jsonl", log_lower_bound)
    for index, record in enumerate(reflections, start=1):
        summary = "Reflection {0}: {1}".format(
            record.get("outcome", "unknown"),
            compact_report_detail(record.get("action", "action")),
        )
        events.append(
            {
                "key": "reflection:{0}:{1}".format(index, record.get("timestamp", "")),
                "timestamp": record.get("timestamp", ""),
                "order": 40,
                "kind": "reflection_" + str(record.get("outcome", "unknown")),
                "summary": summary,
                "detail": "next: {0}".format(record.get("next", "")),
                "plan": None,
                "step_id": None,
                "verified": None,
            }
        )
    return sorted(events, key=report_event_sort_key)


def events_after_marker(events, marker):
    last_event = marker.get("last_event") if isinstance(marker, dict) else None
    if not isinstance(last_event, dict):
        return events
    last_key = last_event.get("key")
    if last_key:
        for index, event in enumerate(events):
            if event.get("key") == last_key:
                return events[index + 1:]
    last_timestamp = last_event.get("timestamp") or ""
    if last_timestamp:
        return [
            event for event in events
            if timestamp_after(event.get("timestamp", ""), last_timestamp)
        ]
    return events


def build_work_report(
    state,
    since="last",
    recent=DEFAULT_REPORT_RECENT,
    cursor="default",
    peek=False,
    mark=False,
):
    if recent < 0:
        fail("[FAIL] Invalid --recent: use 0 or a positive integer.")
        return None
    if mark and peek:
        fail("[FAIL] --mark cannot be combined with --peek.")
        return None
    cursor_name = report_cursor_name(cursor)
    marker_path = report_cursor_path(state, cursor_name)
    marker = read_json(marker_path, {})
    if not isinstance(marker, dict):
        marker = {}
    lower_bound = ""
    if since == "last" and not mark:
        last_event = marker.get("last_event") if isinstance(marker, dict) else None
        if isinstance(last_event, dict):
            lower_bound = last_event.get("timestamp") or ""
    all_events = build_report_events(state, lower_bound)
    if mark:
        candidate_events = []
    elif since == "last":
        candidate_events = events_after_marker(all_events, marker)
    else:
        candidate_events = all_events
    if recent == 0:
        visible_events = []
    else:
        visible_events = candidate_events[-recent:]
    omitted = max(0, len(candidate_events) - len(visible_events))
    attention_candidates = build_report_attention_events(candidate_events)
    attention_events = attention_candidates[-DEFAULT_REPORT_ATTENTION:]
    attention_omitted = max(0, len(attention_candidates) - len(attention_events))
    if mark or not peek:
        last_event = all_events[-1] if all_events else marker.get("last_event")
        write_json_atomic(
            marker_path,
            {
                "cursor": cursor_name,
                "updated_at": now_iso(),
                "last_event": last_event,
            },
        )
    return {
        "state_dir": str(state),
        "cursor": cursor_name,
        "since": since,
        "format": "chat",
        "peek": peek,
        "mark": mark,
        "events": visible_events,
        "new_event_count": len(candidate_events),
        "shown_event_count": len(visible_events),
        "omitted_new_events": omitted,
        "attention_events": attention_events,
        "attention_event_count": len(attention_candidates),
        "omitted_attention_events": attention_omitted,
        "cursor_updated": not peek,
        "last_event": all_events[-1] if all_events else None,
        "guardrail": (
            "report summarizes durable Mythify state only; it does not rerun "
            "checks or prove work beyond recorded evidence"
        ),
    }


def format_work_report(view):
    lines = ["[OK] Live work report: {0}".format(view["state_dir"])]
    if view.get("mark"):
        lines.append(
            "Scope: mark cursor {0}, {1} new events ({2} shown, {3} omitted)".format(
                view["cursor"],
                view["new_event_count"],
                view["shown_event_count"],
                view["omitted_new_events"],
            )
        )
    else:
        lines.append(
            "Scope: since {0}, cursor {1}, {2} new events ({3} shown, {4} omitted)".format(
                view["since"],
                view["cursor"],
                view["new_event_count"],
                view["shown_event_count"],
                view["omitted_new_events"],
            )
        )
    if view.get("attention_event_count", 0):
        lines.append("Attention:")
        for event in view.get("attention_events", []):
            detail = event.get("detail")
            line = "- {0}: {1}".format(
                event.get("level", "notice"),
                event.get("summary", "Event recorded"),
            )
            if detail:
                line += ", {0}".format(compact_report_detail(detail))
            lines.append(line)
        if view.get("omitted_attention_events", 0):
            lines.append(
                "- {0} older attention events omitted".format(
                    view["omitted_attention_events"]
                )
            )
    else:
        lines.append("Attention: none in this report window.")
    if view["events"]:
        for event in view["events"]:
            detail = event.get("detail")
            line = "- {0}".format(event.get("summary", "Event recorded"))
            if detail:
                line += ", {0}".format(compact_report_detail(detail))
            lines.append(line)
    elif view.get("mark"):
        lines.append(
            "Cursor is ready. Future reports with --since last will show only new events."
        )
    else:
        lines.append("No new Mythify events to report.")
    if view.get("mark"):
        lines.append("Cursor marked at latest event: {0}".format(view["cursor"]))
    elif view["cursor_updated"]:
        lines.append("Cursor advanced: {0}".format(view["cursor"]))
    else:
        lines.append("Cursor unchanged: --peek")
    lines.append("Guardrail: {0}.".format(view["guardrail"]))
    return "\n".join(lines)


def cmd_report(args, state):
    if args.mark and args.since is not None:
        fail(
            "[FAIL] --mark cannot be combined with --since. Use --mark to set "
            "a cursor, then run report --since last to read new events."
        )
        return 1
    view = build_work_report(
        state,
        since=args.since or "last",
        recent=args.recent,
        cursor=args.cursor,
        peek=args.peek,
        mark=args.mark,
    )
    if view is None:
        return 1
    if args.report_format == "json":
        payload = dict(view)
        payload["format"] = "json"
        print(json.dumps(payload, indent=2))
    else:
        print(format_work_report(view))
    return 0


BACKGROUND_STATUS_ICONS = {
    "active": "[>]",
    "running": "[>]",
    "pending": "[ ]",
    "completed": "[x]",
    "succeeded": "[x]",
    "failed": "[!]",
    "interrupted": "[~]",
    "stopped": "[~]",
    "empty": "[ ]",
}


def background_recent(items, limit):
    if limit <= 0:
        return []
    return list(reversed(items[-limit:]))


def fanout_root_dir(state):
    return state / "fanout"


def count_statuses(items, statuses):
    counts = {status: 0 for status in statuses}
    for item in items:
        status = item.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def summarize_fanout_job(job):
    tasks = job.get("tasks") if isinstance(job.get("tasks"), list) else []
    counts = count_statuses(
        tasks, ("pending", "running", "completed", "failed", "interrupted")
    )
    if counts.get("pending", 0) or counts.get("running", 0):
        status = "active"
    elif counts.get("failed", 0):
        status = "failed"
    elif counts.get("interrupted", 0):
        status = "interrupted"
    elif tasks:
        status = "completed"
    else:
        status = "empty"
    return {
        "id": job.get("id", ""),
        "status": status,
        "created": job.get("created", ""),
        "last_updated": job.get("last_updated", ""),
        "purpose": job.get("purpose", ""),
        "engine": job.get("engine", ""),
        "model": job.get("model", ""),
        "visibility": job.get("visibility", "summary"),
        "task_counts": counts,
        "task_total": len(tasks),
        "tasks": [
            {
                "id": task.get("id"),
                "title": task.get("title", ""),
                "status": task.get("status", "pending"),
                "role": task.get("role", "worker"),
                "engine": task.get("engine", ""),
                "model": task.get("model", ""),
                "started_at": task.get("started_at", ""),
                "finished_at": task.get("finished_at", ""),
                "duration_seconds": task.get("duration_seconds", 0),
                "error": task.get("error"),
                "output_file": task.get("output_file"),
                "output_bytes": task.get("output_bytes", 0),
            }
            for task in tasks
        ],
    }


def list_fanout_summaries(state):
    root = fanout_root_dir(state)
    if not root.exists():
        return []
    jobs = []
    for path in sorted(root.iterdir()):
        if not path.is_dir() or not re.match(r"^fo-\d{14}-[0-9a-f]{4}$", path.name):
            continue
        job = read_json(path / "job.json", None)
        if isinstance(job, dict):
            summary = summarize_fanout_job(job)
            if not summary["id"]:
                summary["id"] = path.name
            jobs.append(summary)
    return sorted(jobs, key=lambda item: (item.get("created") or "", item.get("id") or ""))


def summarize_outcome(state, slug, goal):
    iterations = read_jsonl(outcome_iterations_path(state, slug))
    last_iteration = iterations[-1] if iterations else None
    return {
        "id": slug,
        "goal": goal.get("goal", ""),
        "status": goal.get("status", "active"),
        "iteration_count": goal.get("iteration_count", 0),
        "max_iterations": goal.get("max_iterations", 1),
        "visibility": goal.get("visibility", "summary"),
        "created": goal.get("created", ""),
        "updated": goal.get("updated", ""),
        "last_verified": goal.get("last_verified"),
        "last_iteration": last_iteration,
        "next_action": last_iteration.get("next_action") if last_iteration else (
            "make a bounded attempt, then run outcome check"
        ),
    }


def list_outcome_summaries(state):
    items = []
    for slug, goal in list_outcomes(state):
        items.append(summarize_outcome(state, slug, goal))
    return sorted(items, key=lambda item: (item.get("updated") or item.get("created") or "", item.get("id") or ""))


def build_background_view(state, recent=5):
    outcomes = list_outcome_summaries(state)
    fanout_jobs = list_fanout_summaries(state)
    active_outcome_slug = get_active_outcome_slug(state)
    outcome_counts = count_statuses(
        outcomes, ("active", "succeeded", "failed", "stopped")
    )
    fanout_counts = count_statuses(
        fanout_jobs, ("active", "completed", "failed", "interrupted", "empty")
    )
    task_counts = {
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "interrupted": 0,
    }
    for job in fanout_jobs:
        for status, count in job.get("task_counts", {}).items():
            task_counts[status] = task_counts.get(status, 0) + count
    active_outcome = None
    for outcome in outcomes:
        if outcome.get("id") == active_outcome_slug:
            active_outcome = outcome
            break
    return {
        "state_dir": str(state),
        "active_outcome": active_outcome,
        "outcomes": background_recent(outcomes, recent),
        "fanout_jobs": background_recent(fanout_jobs, recent),
        "counts": {
            "outcomes": {"total": len(outcomes), **outcome_counts},
            "fanout_jobs": {"total": len(fanout_jobs), **fanout_counts},
            "fanout_tasks": task_counts,
        },
    }


def compact_label(text, fallback):
    value = str(text or "").strip()
    if not value:
        return fallback
    return value if len(value) <= 80 else value[:77] + "..."


def format_background_view(view):
    lines = ["[OK] Background tasks: {0}".format(view["state_dir"])]
    counts = view["counts"]
    outcomes = counts["outcomes"]
    lines.append(
        "Outcomes: {0} total; {1} active, {2} succeeded, {3} failed, {4} stopped".format(
            outcomes["total"],
            outcomes.get("active", 0),
            outcomes.get("succeeded", 0),
            outcomes.get("failed", 0),
            outcomes.get("stopped", 0),
        )
    )
    active_outcome = view.get("active_outcome")
    if active_outcome:
        lines.append(
            "Active outcome: {0} ({1}, {2}/{3} iterations)".format(
                active_outcome["id"],
                active_outcome["status"],
                active_outcome["iteration_count"],
                active_outcome["max_iterations"],
            )
        )
    else:
        lines.append("Active outcome: none")
    if view["outcomes"]:
        lines.append("Recent outcomes:")
        for outcome in view["outcomes"]:
            icon = BACKGROUND_STATUS_ICONS.get(outcome["status"], "[ ]")
            lines.append(
                "  {0} {1}: {2} ({3}, {4}/{5} iterations, last verified={6})".format(
                    icon,
                    outcome["id"],
                    compact_label(outcome["goal"], "outcome"),
                    outcome["status"],
                    outcome["iteration_count"],
                    outcome["max_iterations"],
                    outcome["last_verified"],
                )
            )
            if outcome.get("next_action"):
                lines.append("      next: {0}".format(outcome["next_action"]))
    fanout = counts["fanout_jobs"]
    tasks = counts["fanout_tasks"]
    lines.append(
        "Fanout jobs: {0} total; {1} active, {2} completed, {3} failed, {4} interrupted".format(
            fanout["total"],
            fanout.get("active", 0),
            fanout.get("completed", 0),
            fanout.get("failed", 0),
            fanout.get("interrupted", 0),
        )
    )
    lines.append(
        "Fanout tasks: {0} running, {1} pending, {2} completed, {3} failed, {4} interrupted".format(
            tasks.get("running", 0),
            tasks.get("pending", 0),
            tasks.get("completed", 0),
            tasks.get("failed", 0),
            tasks.get("interrupted", 0),
        )
    )
    if view["fanout_jobs"]:
        lines.append("Recent fanout jobs:")
        for job in view["fanout_jobs"]:
            icon = BACKGROUND_STATUS_ICONS.get(job["status"], "[ ]")
            task_counts = job["task_counts"]
            lines.append(
                "  {0} {1}: {2} ({3}; {4} tasks, {5} completed, {6} failed, {7} running, {8} pending)".format(
                    icon,
                    job["id"],
                    compact_label(job["purpose"], "fanout job"),
                    job["status"],
                    job["task_total"],
                    task_counts.get("completed", 0),
                    task_counts.get("failed", 0),
                    task_counts.get("running", 0),
                    task_counts.get("pending", 0),
                )
            )
            lines.append(
                "      visibility: {0}; engine: {1}; created: {2}".format(
                    job["visibility"] or "summary",
                    job["engine"] or "unknown",
                    job["created"] or "unknown",
                )
            )
            for task in job["tasks"]:
                task_icon = BACKGROUND_STATUS_ICONS.get(task["status"], "[ ]")
                detail = "      {0} {1}. {2} ({3})".format(
                    task_icon,
                    task["id"],
                    compact_label(task["title"], "task"),
                    task["status"],
                )
                if task.get("error"):
                    detail += ": {0}".format(compact_label(task["error"], "error"))
                lines.append(detail)
    if not view["outcomes"] and not view["fanout_jobs"]:
        lines.append("No background tasks found.")
    return "\n".join(lines)


def cmd_background(args, state):
    view = build_background_view(state, args.recent)
    if args.json_output:
        print(json.dumps(view, indent=2))
    else:
        print(format_background_view(view))
    return 0


def summarize_outcome_progress(state, slug, goal):
    iterations = read_jsonl(outcome_iterations_path(state, slug))
    last_iteration = iterations[-1] if iterations else None
    iteration_count = int(goal.get("iteration_count", 0) or 0)
    max_iterations = int(goal.get("max_iterations", 1) or 1)
    remaining = max(0, max_iterations - iteration_count)
    last_check = None
    if last_iteration:
        verify = last_iteration.get("verify") or {}
        metric = last_iteration.get("metric") or {}
        last_check = {
            "iteration": last_iteration.get("iteration"),
            "timestamp": last_iteration.get("timestamp", ""),
            "verified": last_iteration.get("verified"),
            "status_after": last_iteration.get("status_after", ""),
            "notes": last_iteration.get("notes", ""),
            "verify_exit_code": verify.get("exit_code"),
            "verify_duration_seconds": verify.get("duration_seconds", 0),
            "verify_verified": verify.get("verified"),
            "metric_exit_code": metric.get("exit_code") if metric else None,
            "metric_score": metric.get("score") if metric else None,
            "metric_verified": metric.get("verified") if metric else None,
        }
    return {
        "id": slug,
        "goal": goal.get("goal", ""),
        "success_criteria": goal.get("success_criteria", ""),
        "status": goal.get("status", "active"),
        "iteration_count": iteration_count,
        "max_iterations": max_iterations,
        "iterations_remaining": remaining,
        "progress_percent": round((iteration_count / max_iterations) * 100, 1)
        if max_iterations
        else 0,
        "visibility": goal.get("visibility", "summary"),
        "created": goal.get("created", ""),
        "updated": goal.get("updated", ""),
        "last_verified": goal.get("last_verified"),
        "last_check": last_check,
        "next_action": (
            last_iteration.get("next_action")
            if last_iteration
            else "make a bounded attempt, then run outcome check"
        ),
        "verify_command": goal.get("verify_command", ""),
        "metric_command": goal.get("metric_command", ""),
        "best_metric_score": goal.get("best_metric_score"),
        "allowed_paths": goal.get("allowed_paths") or [],
        "stop_reason": goal.get("stop_reason"),
    }


def list_outcome_progress_rows(state):
    rows = [
        summarize_outcome_progress(state, slug, goal)
        for slug, goal in list_outcomes(state)
    ]
    return sorted(
        rows,
        key=lambda item: (
            item.get("updated") or item.get("created") or "",
            item.get("id") or "",
        ),
    )


def build_outcome_progress_view(state, recent=5):
    rows = list_outcome_progress_rows(state)
    active_slug = get_active_outcome_slug(state)
    counts = count_statuses(rows, ("active", "succeeded", "failed", "stopped"))
    return {
        "state_dir": str(state),
        "active_outcome": next(
            (row for row in rows if row.get("id") == active_slug),
            None,
        ),
        "outcomes": background_recent(rows, recent),
        "counts": {"total": len(rows), **counts},
        "guardrail": (
            "progress displays recorded outcome verifier results only; it does "
            "not run checks, make attempts, stop loops, or treat notes as verification"
        ),
    }


def format_outcome_progress_row(row):
    icon = BACKGROUND_STATUS_ICONS.get(row.get("status"), "[ ]")
    lines = [
        "  {0} {1}: {2} ({3}, {4}/{5} iterations, {6} remaining)".format(
            icon,
            row.get("id"),
            compact_label(row.get("goal"), "outcome"),
            row.get("status"),
            row.get("iteration_count"),
            row.get("max_iterations"),
            row.get("iterations_remaining"),
        )
    ]
    last = row.get("last_check")
    if last:
        lines.append(
            "      verifier: iteration {0}, exit {1}, verified={2}, at {3}".format(
                last.get("iteration"),
                last.get("verify_exit_code"),
                last.get("verify_verified"),
                last.get("timestamp") or "unknown-time",
            )
        )
        if last.get("metric_exit_code") is not None:
            metric_line = "      metric: exit {0}".format(
                last.get("metric_exit_code")
            )
            if last.get("metric_score") is not None:
                metric_line += ", score {0}".format(last.get("metric_score"))
            lines.append(metric_line)
    else:
        lines.append("      verifier: no recorded iterations yet")
    if row.get("next_action"):
        lines.append("      next: {0}".format(row.get("next_action")))
    return lines


def format_outcome_progress_view(view):
    lines = ["[OK] Outcome progress: {0}".format(view["state_dir"])]
    counts = view["counts"]
    lines.append(
        "Outcomes: {0} total; {1} active, {2} succeeded, {3} failed, {4} stopped".format(
            counts["total"],
            counts.get("active", 0),
            counts.get("succeeded", 0),
            counts.get("failed", 0),
            counts.get("stopped", 0),
        )
    )
    active = view.get("active_outcome")
    if active:
        lines.append(
            "Active outcome: {0} ({1}, {2}/{3} iterations, {4} remaining)".format(
                active.get("id"),
                active.get("status"),
                active.get("iteration_count"),
                active.get("max_iterations"),
                active.get("iterations_remaining"),
            )
        )
    else:
        lines.append("Active outcome: none")
    if view["outcomes"]:
        lines.append("Recent outcomes:")
        for row in view["outcomes"]:
            lines.extend(format_outcome_progress_row(row))
    else:
        lines.append("No outcome loops found.")
    lines.append("Guardrail: {0}.".format(view["guardrail"]))
    return "\n".join(lines)


def cmd_progress(args, state):
    view = build_outcome_progress_view(state, args.recent)
    if args.json_output:
        print(json.dumps(view, indent=2))
    else:
        print(format_outcome_progress_view(view))
    return 0


RELEASE_READINESS_GATES = (
    {
        "id": "python_tests",
        "label": "Python test suite",
        "required": True,
        "sources": ["tests/"],
        "match_any": [
            "python3 -m unittest discover -s tests",
            "Python suite passes",
        ],
    },
    {
        "id": "node_mcp_tests",
        "label": "Node MCP suite",
        "required": True,
        "sources": ["mcp-server/test/"],
        "match_any": [
            "npm test --prefix mcp-server",
            "Node MCP suite passes",
        ],
    },
    {
        "id": "surface_manifest",
        "label": "Surface manifest check",
        "required": True,
        "sources": [
            "protocol/surface-manifest.json",
            "mcp-server/protocol/surface-manifest.json",
            "scripts/check_surface_manifest.mjs",
        ],
        "match_any": [
            "node scripts/check_surface_manifest.mjs",
            "surface manifest",
        ],
    },
    {
        "id": "classification_rules_manifest",
        "label": "Runtime manifest mirror check",
        "required": True,
        "sources": [
            "protocol/classification-rules.json",
            "mcp-server/protocol/classification-rules.json",
            "protocol/operation-registry.json",
            "mcp-server/protocol/operation-registry.json",
            "scripts/check_classification_rules_manifest.mjs",
        ],
        "match_any": [
            "node scripts/check_classification_rules_manifest.mjs",
            "classification rules manifest",
        ],
    },
    {
        "id": "registry_docs",
        "label": "Generated registry docs check",
        "required": True,
        "sources": ["scripts/build_registry_docs.mjs", "docs/adapter-candidates.md"],
        "match_any": [
            "node scripts/build_registry_docs.mjs --check",
            "registry docs",
            "generated docs",
        ],
    },
    {
        "id": "protocol_check",
        "label": "Protocol variants check",
        "required": True,
        "sources": ["protocol/PROTOCOL.md", "AGENTS.md", "CLAUDE.md", ".cursorrules"],
        "match_any": [
            "python3 scripts/mythify.py protocol check",
            "protocol check",
        ],
    },
    {
        "id": "variant_idempotence",
        "label": "Generated variants idempotence",
        "required": True,
        "sources": ["scripts/build_variants.py", "AGENTS.md", "CLAUDE.md", ".cursorrules"],
        "match_any": [
            "scripts/build_variants.py",
            "generated variants",
            "variant idempotence",
        ],
    },
    {
        "id": "whitespace",
        "label": "Whitespace check",
        "required": True,
        "sources": ["git diff --check"],
        "match_any": [
            "git diff --check",
            "whitespace",
        ],
    },
    {
        "id": "forbidden_dash_scan",
        "label": "Forbidden dash scan",
        "required": True,
        "sources": ["AGENTS.md", "docs/design.md"],
        "match_any": [
            "forbidden dash",
            "dash scan",
        ],
    },
    {
        "id": "emoji_scan",
        "label": "Emoji scan",
        "required": True,
        "sources": ["AGENTS.md", "docs/design.md"],
        "match_any": [
            "emoji scan",
            "emoji-like",
        ],
    },
)


RELEASE_READINESS_ICONS = {
    "passed": "[x]",
    "failed": "[!]",
    "missing": "[ ]",
    "unknown": "[~]",
    "clean": "[x]",
    "dirty": "[!]",
    "present": "[x]",
}


def project_root_for_state(state):
    return state.parent if state.name == WORKSPACE_DIR_NAME else Path.cwd()


def verification_search_text(record):
    return "\n".join(
        str(record.get(key) or "")
        for key in ("claim", "command", "stdout_tail", "stderr_tail")
    ).lower()


def latest_matching_verification(records, gate):
    needles = [item.lower() for item in gate["match_any"]]
    matches = [
        record
        for record in records
        if record.get("kind") == "executed"
        and any(needle in verification_search_text(record) for needle in needles)
    ]
    return matches[-1] if matches else None


def summarize_release_gate(gate, records):
    record = latest_matching_verification(records, gate)
    status = "missing"
    if record is not None:
        status = "passed" if record.get("verified") is True else "failed"
    return {
        "id": gate["id"],
        "label": gate["label"],
        "required": gate["required"],
        "sources": list(gate["sources"]),
        "status": status,
        "latest_record": None
        if record is None
        else {
            "timestamp": record.get("timestamp", ""),
            "claim": record.get("claim"),
            "command": record.get("command", ""),
            "exit_code": record.get("exit_code"),
            "verified": record.get("verified"),
            "plan": record.get("plan"),
            "step_id": record.get("step_id"),
        },
    }


def git_status_summary(root):
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "status", "--short", "--branch"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "unknown",
            "branch": "",
            "clean": None,
            "detail": str(exc),
        }
    output = result.stdout or ""
    if result.returncode != 0:
        return {
            "status": "unknown",
            "branch": "",
            "clean": None,
            "detail": (result.stderr or output or "git status failed").strip(),
        }
    lines = [line for line in output.splitlines() if line.strip()]
    branch = ""
    if lines and lines[0].startswith("## "):
        branch = lines[0][3:].strip()
    dirty_lines = [line for line in lines if not line.startswith("## ")]
    clean = len(dirty_lines) == 0
    return {
        "status": "clean" if clean else "dirty",
        "branch": branch,
        "clean": clean,
        "detail": "working tree clean" if clean else "{0} changed paths".format(len(dirty_lines)),
        "changed_paths": dirty_lines[:20],
    }


def roadmap_summary(root):
    path = root / "roadmap.md"
    if not path.is_file():
        return {
            "status": "unknown",
            "path": str(path),
            "active_now": "",
            "detail": "roadmap.md not found",
        }
    text = path.read_text(encoding="utf-8")
    active_now = ""
    match = re.search(r"(?ms)^## Active Now\n\n(.*?)(?:\n## |\Z)", text)
    if match:
        for line in match.group(1).splitlines():
            stripped = line.strip()
            if stripped.startswith("- ["):
                active_now = stripped
                break
    return {
        "status": "present" if active_now else "unknown",
        "path": str(path),
        "active_now": active_now,
        "detail": "active slice found" if active_now else "no active slice found",
    }


def release_readiness_status(gates, git_state):
    failed = sum(1 for gate in gates if gate["status"] == "failed")
    missing = sum(1 for gate in gates if gate["status"] == "missing")
    if failed or git_state.get("status") == "dirty":
        return "blocked"
    if missing:
        return "needs_evidence"
    if git_state.get("status") == "unknown":
        return "needs_review"
    return "ready_for_release_review"


def build_release_readiness_view(state):
    records = read_jsonl(state / "verifications.jsonl")
    gates = [
        summarize_release_gate(gate, records)
        for gate in RELEASE_READINESS_GATES
    ]
    root = project_root_for_state(state)
    git_state = git_status_summary(root)
    roadmap = roadmap_summary(root)
    counts = count_statuses(gates, ("passed", "failed", "missing", "unknown"))
    return {
        "state_dir": str(state),
        "project_root": str(root),
        "status": release_readiness_status(gates, git_state),
        "gates": gates,
        "counts": {"total": len(gates), **counts},
        "project_state": {
            "git": git_state,
            "roadmap": roadmap,
        },
        "guardrail": (
            "readiness summarizes recorded evidence and project state only; it "
            "does not rerun gates or declare a release safe"
        ),
    }


def format_release_gate(row):
    icon = RELEASE_READINESS_ICONS.get(row["status"], "[ ]")
    line = "  {0} {1}: {2}".format(icon, row["label"], row["status"])
    record = row.get("latest_record")
    if record:
        line += " (exit {0}, {1})".format(
            record.get("exit_code"),
            record.get("timestamp") or "unknown-time",
        )
    else:
        line += " (no recorded executed verifier)"
    line += "; sources: {0}".format(", ".join(row["sources"]))
    return line


def format_release_readiness_view(view):
    lines = ["[OK] Release readiness: {0}".format(view["state_dir"])]
    counts = view["counts"]
    lines.append("Readiness: {0}".format(view["status"]))
    lines.append(
        "Recorded gates: {0} total; {1} passed, {2} failed, {3} missing".format(
            counts["total"],
            counts.get("passed", 0),
            counts.get("failed", 0),
            counts.get("missing", 0),
        )
    )
    lines.append("Gates:")
    for gate in view["gates"]:
        lines.append(format_release_gate(gate))
    git_state = view["project_state"]["git"]
    git_icon = RELEASE_READINESS_ICONS.get(git_state.get("status"), "[~]")
    lines.append(
        "Project git: {0} {1}; branch={2}; {3}".format(
            git_icon,
            git_state.get("status", "unknown"),
            git_state.get("branch") or "unknown",
            compact_label(git_state.get("detail"), "no detail"),
        )
    )
    roadmap = view["project_state"]["roadmap"]
    roadmap_icon = RELEASE_READINESS_ICONS.get(roadmap.get("status"), "[~]")
    lines.append(
        "Roadmap: {0} {1}; {2}".format(
            roadmap_icon,
            roadmap.get("status", "unknown"),
            compact_label(roadmap.get("active_now"), roadmap.get("detail")),
        )
    )
    lines.append("Guardrail: {0}.".format(view["guardrail"]))
    return "\n".join(lines)


def cmd_readiness(args, state):
    view = build_release_readiness_view(state)
    if args.json_output:
        print(json.dumps(view, indent=2))
    else:
        print(format_release_readiness_view(view))
    return 0


TIMELINE_EVENT_ICONS = {
    "job_created": "[ ]",
    "task_started": "[>]",
    "task_pending": "[ ]",
    "task_finished": "[x]",
    "task_failed": "[!]",
    "task_interrupted": "[~]",
}


def selected_recent_fanout_jobs(fanout_jobs, recent):
    if recent <= 0:
        return []
    return list(reversed(fanout_jobs[-recent:]))


def timeline_event_time(job, task, event):
    if event == "task_started":
        return task.get("started_at") or job.get("created", "")
    if event in ("task_finished", "task_failed", "task_interrupted"):
        return task.get("finished_at") or job.get("last_updated", "")
    return job.get("created", "")


def add_timeline_event(events, job, task, event):
    status = task.get("status", "pending") if task else job.get("status", "unknown")
    item = {
        "time": timeline_event_time(job, task or {}, event),
        "event": event,
        "job_id": job.get("id", ""),
        "job_purpose": job.get("purpose", ""),
        "task_id": task.get("id") if task else None,
        "task_title": task.get("title", "") if task else "",
        "status": status,
        "engine": (task.get("engine") if task else None) or job.get("engine", ""),
        "model": (task.get("model") if task else None) or job.get("model", ""),
        "duration_seconds": task.get("duration_seconds", 0) if task else 0,
        "error": task.get("error") if task else None,
        "output_file": task.get("output_file") if task else None,
        "output_bytes": task.get("output_bytes", 0) if task else 0,
    }
    events.append(item)


def build_fanout_timeline_events(job):
    events = []
    events.append(
        {
            "time": job.get("created", ""),
            "event": "job_created",
            "job_id": job.get("id", ""),
            "job_purpose": job.get("purpose", ""),
            "task_id": None,
            "task_title": "",
            "status": job.get("status", "unknown"),
            "engine": job.get("engine", ""),
            "model": job.get("model", ""),
            "duration_seconds": 0,
            "error": None,
            "output_file": None,
            "output_bytes": 0,
        }
    )
    for task in job.get("tasks", []):
        status = task.get("status", "pending")
        if status == "pending" and not task.get("started_at"):
            add_timeline_event(events, job, task, "task_pending")
            continue
        add_timeline_event(events, job, task, "task_started")
        if status == "failed":
            add_timeline_event(events, job, task, "task_failed")
        elif status == "interrupted":
            add_timeline_event(events, job, task, "task_interrupted")
        elif status == "completed":
            add_timeline_event(events, job, task, "task_finished")
    return events


def sort_timeline_events(events):
    return sorted(
        events,
        key=lambda item: (
            item.get("time") or "9999-12-31T23:59:59Z",
            item.get("job_id") or "",
            item.get("task_id") or 0,
            item.get("event") or "",
        ),
    )


def build_fanout_timeline_view(state, recent=5):
    fanout_jobs = list_fanout_summaries(state)
    selected_jobs = selected_recent_fanout_jobs(fanout_jobs, recent)
    selected_ids = {job.get("id") for job in selected_jobs}
    events = []
    for job in fanout_jobs:
        if job.get("id") in selected_ids:
            events.extend(build_fanout_timeline_events(job))
    task_counts = {
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "interrupted": 0,
    }
    for job in fanout_jobs:
        for status, count in job.get("task_counts", {}).items():
            task_counts[status] = task_counts.get(status, 0) + count
    job_counts = count_statuses(
        fanout_jobs, ("active", "completed", "failed", "interrupted", "empty")
    )
    return {
        "state_dir": str(state),
        "jobs": selected_jobs,
        "events": sort_timeline_events(events),
        "counts": {
            "fanout_jobs": {"total": len(fanout_jobs), **job_counts},
            "fanout_tasks": task_counts,
            "timeline_events": len(events),
        },
        "guardrail": (
            "timeline summarizes durable fanout state only; worker output is "
            "material, not verification evidence"
        ),
    }


def format_timeline_event(event):
    icon = TIMELINE_EVENT_ICONS.get(event.get("event"), "[ ]")
    stamp = event.get("time") or "unknown-time"
    job_id = event.get("job_id") or "unknown-job"
    task_id = event.get("task_id")
    if event.get("event") == "job_created":
        return "  {0} {1} {2}: job created ({3})".format(
            icon,
            stamp,
            job_id,
            compact_label(event.get("job_purpose"), "fanout job"),
        )
    title = compact_label(event.get("task_title"), "task")
    prefix = "  {0} {1} {2} task {3}: {4}".format(
        icon,
        stamp,
        job_id,
        task_id,
        title,
    )
    detail = " ({0}; engine={1}".format(
        event.get("status", "unknown"),
        event.get("engine") or "unknown",
    )
    if event.get("model"):
        detail += "; model={0}".format(event.get("model"))
    if event.get("duration_seconds"):
        detail += "; duration={0}s".format(event.get("duration_seconds"))
    if event.get("output_bytes"):
        detail += "; output={0} bytes".format(event.get("output_bytes"))
    detail += ")"
    if event.get("error"):
        detail += ": {0}".format(compact_label(event.get("error"), "error"))
    return prefix + detail


def format_fanout_timeline_view(view):
    lines = ["[OK] Fanout timeline: {0}".format(view["state_dir"])]
    jobs = view["counts"]["fanout_jobs"]
    tasks = view["counts"]["fanout_tasks"]
    lines.append(
        "Fanout jobs: {0} total; {1} active, {2} completed, {3} failed, {4} interrupted".format(
            jobs["total"],
            jobs.get("active", 0),
            jobs.get("completed", 0),
            jobs.get("failed", 0),
            jobs.get("interrupted", 0),
        )
    )
    lines.append(
        "Fanout tasks: {0} running, {1} pending, {2} completed, {3} failed, {4} interrupted".format(
            tasks.get("running", 0),
            tasks.get("pending", 0),
            tasks.get("completed", 0),
            tasks.get("failed", 0),
            tasks.get("interrupted", 0),
        )
    )
    if view["events"]:
        lines.append("Timeline events:")
        for event in view["events"]:
            lines.append(format_timeline_event(event))
    else:
        lines.append("No fanout timeline events found.")
    lines.append("Guardrail: {0}.".format(view["guardrail"]))
    return "\n".join(lines)


def cmd_timeline(args, state):
    view = build_fanout_timeline_view(state, args.recent)
    if args.json_output:
        print(json.dumps(view, indent=2))
    else:
        print(format_fanout_timeline_view(view))
    return 0


PHASE_CONFIG = (
    {
        "id": "understand",
        "label": "Understand",
        "keywords": (
            "understand",
            "map",
            "inspect",
            "research",
            "audit",
            "classify",
            "discover",
            "probe",
            "investigate",
            "analyze",
            "orient",
        ),
    },
    {
        "id": "design",
        "label": "Design",
        "keywords": (
            "design",
            "plan",
            "spec",
            "contract",
            "architecture",
            "outline",
            "docs design",
        ),
    },
    {
        "id": "build",
        "label": "Build",
        "keywords": (
            "implement",
            "build",
            "add",
            "create",
            "update",
            "write",
            "edit",
            "refactor",
            "wire",
        ),
    },
    {
        "id": "judge",
        "label": "Judge",
        "keywords": (
            "judge",
            "review",
            "evaluate",
            "assess",
            "reflect",
            "decide",
        ),
    },
    {
        "id": "verify",
        "label": "Verify",
        "keywords": (
            "verify",
            "test",
            "check",
            "gate",
            "lint",
            "suite",
        ),
    },
)

PHASE_STATUS_ICONS = {
    "empty": "[ ]",
    "pending": "[ ]",
    "in_progress": "[>]",
    "completed": "[x]",
    "failed": "[!]",
    "skipped": "[~]",
}


def phase_id_for_step(step):
    title = step.get("title", "")
    for phase in PHASE_CONFIG:
        if _contains_any(title, phase["keywords"]):
            return phase["id"]
    criteria = step.get("success_criteria", "")
    for phase in PHASE_CONFIG:
        if _contains_any(criteria, phase["keywords"]):
            return phase["id"]
    return "build"


def summarize_phase_step(step):
    return {
        "id": step.get("id"),
        "title": step.get("title", ""),
        "status": step.get("status", "pending"),
        "success_criteria": step.get("success_criteria", ""),
        "result": step.get("result"),
    }


def phase_step_counts(steps):
    return {
        "total": len(steps),
        "pending": sum(1 for step in steps if step.get("status") == "pending"),
        "in_progress": sum(1 for step in steps if step.get("status") == "in_progress"),
        "completed": sum(1 for step in steps if step.get("status") == "completed"),
        "failed": sum(1 for step in steps if step.get("status") == "failed"),
        "skipped": sum(1 for step in steps if step.get("status") == "skipped"),
    }


def phase_status(steps):
    if not steps:
        return "empty"
    statuses = [step.get("status", "pending") for step in steps]
    if "in_progress" in statuses:
        return "in_progress"
    if "failed" in statuses:
        return "failed"
    if all(status == "completed" for status in statuses):
        return "completed"
    if all(status == "skipped" for status in statuses):
        return "skipped"
    return "pending"


def phase_next_action(steps):
    for status in ("in_progress", "pending"):
        for step in steps:
            if step.get("status") == status:
                return "continue step {0}: {1}".format(
                    step.get("id"),
                    step.get("title", ""),
                )
    return None


def build_phase_evidence(phase_id, dashboard, background):
    plan = dashboard.get("active_plan")
    counts = dashboard["counts"]
    verification = dashboard["verification_summary"]
    reflections = dashboard["reflection_summary"]
    evidence = []
    if phase_id == "understand":
        if plan:
            evidence.append("active plan goal: {0}".format(plan.get("goal", "")))
        else:
            evidence.append("active plan: none")
        evidence.append(
            "memory {0}, lessons {1} project + {2} global".format(
                counts["memory"],
                counts["project_lessons"],
                counts["global_lessons"],
            )
        )
    elif phase_id == "design":
        if plan:
            evidence.append(
                "plan progress {0}/{1} completed".format(
                    plan["completed_steps"],
                    plan["total_steps"],
                )
            )
            next_step = plan.get("next_pending_step")
            if next_step:
                evidence.append(
                    "next pending step {0}: {1}".format(
                        next_step.get("id"),
                        next_step.get("title", ""),
                    )
                )
        else:
            evidence.append("no active plan")
    elif phase_id == "build":
        outcomes = background["counts"]["outcomes"]
        tasks = background["counts"]["fanout_tasks"]
        evidence.append(
            "outcomes {0} total, {1} active".format(
                outcomes["total"],
                outcomes.get("active", 0),
            )
        )
        evidence.append(
            "fanout tasks {0} running, {1} pending, {2} completed".format(
                tasks.get("running", 0),
                tasks.get("pending", 0),
                tasks.get("completed", 0),
            )
        )
    elif phase_id == "judge":
        evidence.append("reflections {0} total".format(reflections["total"]))
        if reflections["recent"]:
            latest = reflections["recent"][-1]
            evidence.append(
                "latest reflection: {0}; next {1}".format(
                    latest.get("outcome", "unknown"),
                    latest.get("next", ""),
                )
            )
    elif phase_id == "verify":
        evidence.append(
            "executed checks {0} total, {1} passed, {2} failed".format(
                verification["executed"],
                verification["executed_passed"],
                verification["executed_failed"],
            )
        )
        evidence.append("attested claims {0}".format(verification["attested"]))
        outcome = dashboard.get("active_outcome")
        if outcome:
            evidence.append(
                "active outcome {0} is {1}".format(
                    outcome["slug"],
                    outcome["status"],
                )
            )
    return evidence


def build_phase_view(state, recent=3):
    dashboard = build_dashboard(state, recent)
    background = build_background_view(state, recent)
    plan = dashboard.get("active_plan")
    step_buckets = {phase["id"]: [] for phase in PHASE_CONFIG}
    if plan:
        for step in plan.get("steps", []):
            step_buckets[phase_id_for_step(step)].append(summarize_phase_step(step))
    phases = []
    for phase in PHASE_CONFIG:
        steps = step_buckets[phase["id"]]
        status = phase_status(steps)
        phases.append(
            {
                "id": phase["id"],
                "label": phase["label"],
                "status": status,
                "steps": steps,
                "step_counts": phase_step_counts(steps),
                "evidence": build_phase_evidence(phase["id"], dashboard, background),
                "next_action": phase_next_action(steps),
            }
        )
    return {
        "state_dir": str(state),
        "active_plan": dashboard.get("active_plan"),
        "active_outcome": dashboard.get("active_outcome"),
        "phases": phases,
        "counts": {
            "memory": dashboard["counts"]["memory"],
            "project_lessons": dashboard["counts"]["project_lessons"],
            "global_lessons": dashboard["counts"]["global_lessons"],
            "verifications": dashboard["counts"]["verifications"],
            "reflections": dashboard["counts"]["reflections"],
            "outcomes": background["counts"]["outcomes"],
            "fanout_jobs": background["counts"]["fanout_jobs"],
            "fanout_tasks": background["counts"]["fanout_tasks"],
        },
        "guardrail": (
            "phase view summarizes durable state only; verification still "
            "requires executed checks"
        ),
    }


def format_phase_view(view):
    lines = ["[OK] Phase view: {0}".format(view["state_dir"])]
    plan = view.get("active_plan")
    if plan:
        lines.append(
            "Active plan: {0} ({1}/{2} completed)".format(
                plan["slug"],
                plan["completed_steps"],
                plan["total_steps"],
            )
        )
        lines.append("Goal: {0}".format(plan.get("goal", "")))
    else:
        lines.append("Active plan: none")
    lines.append("Phases:")
    for phase in view["phases"]:
        counts = phase["step_counts"]
        icon = PHASE_STATUS_ICONS.get(phase["status"], "[ ]")
        lines.append(
            "  {0} {1}: {2}; {3} plan steps ({4} completed, {5} in progress, {6} pending)".format(
                icon,
                phase["label"],
                phase["status"],
                counts["total"],
                counts["completed"],
                counts["in_progress"],
                counts["pending"],
            )
        )
        for item in phase["evidence"]:
            lines.append("      evidence: {0}".format(item))
        for step in phase["steps"]:
            lines.append(
                "      step: {0} {1}. {2}".format(
                    PHASE_STATUS_ICONS.get(step["status"], "[ ]"),
                    step["id"],
                    step["title"],
                )
            )
        if phase.get("next_action"):
            lines.append("      next: {0}".format(phase["next_action"]))
    lines.append("Guardrail: {0}.".format(view["guardrail"]))
    return "\n".join(lines)


def cmd_phase(args, state):
    view = build_phase_view(state, args.recent)
    if args.json_output:
        print(json.dumps(view, indent=2))
    else:
        print(format_phase_view(view))
    return 0


