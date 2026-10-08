#!/usr/bin/env python3
"""verify_contract.py — acceptance verifier for the app-quality-polish contract.

Reads <config-dir>/contract.yml and evaluates every clause. Static clauses are
machine-checked against the config graph; evidence clauses require a fresh,
passing evidence record. A blocking clause that is UNVERIFIED counts as a
failure, because acceptance rule is all_blocking_clauses_pass.

Usage:
    python3 verify_contract.py <config-dir> [--report out.md]

Exit codes:
    0  ACCEPTED      every blocking clause PASS
    1  NOT ACCEPTED  at least one blocking clause FAIL/UNVERIFIED
    2  usage or contract/parse error
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("error: PyYAML is required (pip install pyyaml)", file=sys.stderr)
    raise SystemExit(2)

HEX_RE = re.compile(r"(?<![\w#])#[0-9a-fA-F]{3,8}(?![\w])")
ERROR_STATE_RE = re.compile(r"error|fail|offline|timeout|denied|restricted", re.I)
REQUIRED_ENTITY_TYPES = {
    "app", "page", "component", "element", "token", "motion",
    "copy", "data", "net", "perm", "theme", "a11y",
}
REQUIRED_PAGE_STATES = {"loading", "success", "empty", "error", "offline", "noAuth"}
REQUIRED_P0_SCENES = {"S01", "S02", "S04", "S06", "S07", "S08", "S10", "S11", "S12", "S13", "S14", "S15"}
REQUIRED_MUST_TEST = {"slow_network", "dark_mode", "large_text", "a11y"}
REQUIRED_BUDGETS = {
    "cold_start_p90_ms", "first_screen_ttl_ms", "click_response_p90_ms",
    "scroll_fps_min", "crash_rate", "anr_rate",
}
REQUIRED_COPY_SCENES = {"empty", "error", "offline", "auth", "permission", "success", "confirm", "list"}
CONTRACT_CLAUSE_FIELDS = {"id", "dim", "level", "enforcement", "requirement", "verify"}


class ConfigError(Exception):
    """A config file is missing or cannot be parsed."""


class Ctx:
    """Lazily loaded config graph."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._cache: dict[str, Any] = {}

    def _raw(self, name: str) -> str:
        path = self.root / name
        if not path.is_file():
            raise ConfigError(f"{name} not found")
        return path.read_text(encoding="utf-8")

    def raw(self, name: str) -> str:
        return self._raw(name)

    def yml(self, name: str) -> Any:
        if name not in self._cache:
            try:
                self._cache[name] = yaml.safe_load(self._raw(name)) or {}
            except yaml.YAMLError as exc:
                raise ConfigError(f"{name} does not parse: {exc}") from exc
        return self._cache[name]

    def js(self, name: str) -> Any:
        if name not in self._cache:
            try:
                self._cache[name] = json.loads(self._raw(name))
            except json.JSONDecodeError as exc:
                raise ConfigError(f"{name} does not parse: {exc}") from exc
        return self._cache[name]

    def configured_files(self) -> list[Path]:
        return sorted(
            p for p in self.root.iterdir()
            if p.is_file() and p.suffix in {".yml", ".yaml", ".json"}
        )


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def dig(data: Any, dotted: str) -> Any:
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def compare(actual: Any, op: str, expected: Any) -> bool:
    try:
        if op == ">=":
            return actual >= expected
        if op == "<=":
            return actual <= expected
        if op == ">":
            return actual > expected
        if op == "<":
            return actual < expected
        if op == "==":
            return actual == expected
        if op == "!=":
            return actual != expected
    except TypeError:
        return False
    raise ConfigError(f"unsupported operator: {op}")


def color_leaves(node: Any, path: str = "") -> list[tuple[str, dict]]:
    """Find leaf colour nodes (dicts exposing light/dark)."""
    out: list[tuple[str, dict]] = []
    if isinstance(node, dict):
        if "light" in node or "dark" in node:
            out.append((path, node))
        else:
            for key, val in node.items():
                out.extend(color_leaves(val, f"{path}.{key}" if path else key))
    return out


def walk_strings(node: Any, path: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, val in node.items():
            out.extend(walk_strings(val, f"{path}.{key}" if path else str(key)))
    elif isinstance(node, list):
        for i, val in enumerate(node):
            out.extend(walk_strings(val, f"{path}[{i}]"))
    elif isinstance(node, str):
        out.append((path, node))
    return out


def flow_graph(flow: dict) -> tuple[set[str], dict[str, list[str]]]:
    nodes: set[str] = set(flow.get("steps") or [])
    out_edges: dict[str, list[str]] = {}
    for tr in flow.get("transitions") or []:
        src, dst = tr.get("from"), tr.get("to")
        if src is None or dst is None:
            continue
        nodes.add(src)
        nodes.add(dst)
        out_edges.setdefault(src, []).append(dst)
    return nodes, out_edges


# --------------------------------------------------------------------------- #
# platform axis
# --------------------------------------------------------------------------- #

def load_targets(ctx: Ctx) -> tuple[dict, list[dict]]:
    """Return (platforms.yml document, resolved axes with parsed profiles).

    Two axes share one mechanism:
      targets  = OS surfaces   (kind: platform)
      runtimes = host frameworks (kind: runtime, e.g. Flutter / React Native)
    A runtime is not a platform: it renders onto one or more host targets.
    """
    doc = ctx.yml("platforms.yml")
    resolved = []
    for group, default_kind in (("targets", "platform"), ("runtimes", "runtime")):
        for entry in doc.get(group) or []:
            pid = entry.get("id")
            if not pid:
                continue
            path = entry.get("profile") or f"platforms/{pid}.yml"
            try:
                profile = ctx.yml(path)
            except ConfigError as exc:
                profile, path = {}, str(exc)
            resolved.append({
                "id": pid,
                "kind": entry.get("kind") or default_kind,
                "group": group,
                "target": entry,
                "profile": profile,
                "path": path,
            })
    return doc, resolved


def declared_platform_ids(doc: dict) -> set[str]:
    return {t.get("id") for t in (doc.get("targets") or []) if t.get("id")}


def threshold_direction(key: str) -> str | None:
    """Floors vs ceilings, inferred from the key name."""
    if "_min" in key:
        return "floor"
    if "_max" in key:
        return "ceiling"
    return None


# --------------------------------------------------------------------------- #
# static checks  ->  (ok: bool, detail: str)
# --------------------------------------------------------------------------- #

def entities_have_required_fields(ctx: Ctx, _: dict):
    ents = ctx.yml("entities.yml").get("entities") or {}
    if not ents:
        return False, "entities.yml declares no entities"
    missing = []
    for eid, body in ents.items():
        if not isinstance(body, dict):
            missing.append(f"{eid}(not a mapping)")
            continue
        absent = [f for f in ("type", "owner", "lifecycle", "source", "gate") if f not in body]
        if absent:
            missing.append(f"{eid}: missing {','.join(absent)}")
    return (not missing), ("all entities complete" if not missing else "; ".join(missing))


def no_orphan_components(ctx: Ctx, _: dict):
    ents = ctx.yml("entities.yml").get("entities") or {}
    scenarios = ctx.yml("scenarios.yml").get("scenarios") or []
    referenced = {e for s in scenarios for e in (s.get("entities") or [])}
    components = [eid for eid, b in ents.items() if isinstance(b, dict) and b.get("type") == "component"]
    orphans = [c for c in components if c not in referenced]
    return (not orphans), ("no orphan components" if not orphans else f"orphans: {', '.join(orphans)}")


def entity_types_complete(ctx: Ctx, _: dict):
    declared = set(ctx.yml("entities.yml").get("entity_types") or [])
    missing = REQUIRED_ENTITY_TYPES - declared
    return (not missing), ("entity types complete" if not missing else f"missing: {', '.join(sorted(missing))}")


def state_machines_present(ctx: Ctx, _: dict):
    machines = ctx.yml("states.yml").get("state_machines") or {}
    if not machines:
        return False, "states.yml declares no state_machines"
    bad = [name for name, m in machines.items()
           if not (m.get("attrs") and m.get("states") and m.get("transitions"))]
    return (not bad), ("all state machines complete" if not bad else f"incomplete: {', '.join(bad)}")


def page_states_complete(ctx: Ctx, _: dict):
    required = set(ctx.yml("page-state.yml").get("required_states") or [])
    missing = REQUIRED_PAGE_STATES - required
    return (not missing), ("6/6 states declared" if not missing else f"missing: {', '.join(sorted(missing))}")


def error_states_have_recovery(ctx: Ctx, _: dict):
    machines = ctx.yml("states.yml").get("state_machines") or {}
    dead = []
    for name, m in machines.items():
        outgoing = {tr.get("from") for tr in (m.get("transitions") or [])}
        for state in (m.get("states") or []):
            if isinstance(state, str) and ERROR_STATE_RE.search(state) and state not in outgoing:
                dead.append(f"{name}.{state}")
    return (not dead), ("every error state has a recovery edge" if not dead else f"dead-end: {', '.join(dead)}")


def no_state_conflict(ctx: Ctx, _: dict):
    edges = ctx.yml("relations.yml").get("edges") or []
    has = any(e.get("relation") == "excludes" for e in edges)
    return has, ("excludes declared" if has else "no excludes edge between loading and error")


def relations_no_cycles(ctx: Ctx, _: dict):
    edges = ctx.yml("relations.yml").get("edges") or []
    graph: dict[str, set[str]] = {}
    for e in edges:
        graph.setdefault(e.get("source"), set()).add(e.get("target"))
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {n: WHITE for n in graph}
    cycles: list[str] = []

    def visit(node: str, stack: list[str]) -> None:
        colour[node] = GREY
        for nxt in graph.get(node, ()):
            if nxt not in colour:
                colour[nxt] = WHITE
            if colour.get(nxt) == GREY:
                cycles.append(" -> ".join(stack + [node, nxt]))
            elif colour.get(nxt) == WHITE:
                visit(nxt, stack + [node])
        colour[node] = BLACK

    for node in list(graph):
        if colour.get(node) == WHITE:
            visit(node, [])
    return (not cycles), ("acyclic" if not cycles else f"cycle: {cycles[0]}")


def no_raw_value_in_components(ctx: Ctx, _: dict):
    hits = []
    for name in ("component-state.yml", "page-state.yml"):
        for i, line in enumerate(ctx.raw(name).splitlines(), 1):
            if HEX_RE.search(line):
                hits.append(f"{name}:{i}")
    return (not hits), ("no raw colour values" if not hits else f"raw values at {', '.join(hits)}")


def pages_cover_all_states(ctx: Ctx, _: dict):
    ents = ctx.yml("entities.yml").get("entities") or {}
    pages = [eid for eid, b in ents.items() if isinstance(b, dict) and b.get("type") == "page"]
    declared = set((ctx.yml("page-state.yml").get("pages") or {}).keys())
    missing = [p for p in pages if p not in declared]
    return (not missing), ("all pages covered" if not missing else f"uncovered pages: {', '.join(missing)}")


def scenes_cover_required(ctx: Ctx, _: dict):
    cover = set(dig(ctx.yml("relations.yml"), "gates.scenes_must_cover") or [])
    missing = {"slow_network", "dark_mode", "large_text"} - cover
    return (not missing), ("required scenes covered" if not missing else f"missing: {', '.join(sorted(missing))}")


def scenarios_have_fields(ctx: Ctx, _: dict):
    scenarios = ctx.yml("scenarios.yml").get("scenarios") or []
    if not scenarios:
        return False, "scenarios.yml declares no scenarios"
    bad = [s.get("id", "?") for s in scenarios
           if not all(k in s for k in ("entities", "states", "expect", "exception", "gate"))]
    return (not bad), ("all scenarios complete" if not bad else f"incomplete: {', '.join(bad)}")


def p0_scenarios_defined(ctx: Ctx, _: dict):
    scenarios = ctx.yml("scenarios.yml").get("scenarios") or []
    p0 = {s.get("id") for s in scenarios if s.get("gate") == "P0"}
    missing = REQUIRED_P0_SCENES - p0
    return (not missing), (f"{len(p0)} P0 scenarios declared" if not missing else f"missing P0: {', '.join(sorted(missing))}")


def must_test_covers(ctx: Ctx, _: dict):
    must = set(dig(ctx.yml("scenarios.yml"), "gates.must_test") or [])
    missing = REQUIRED_MUST_TEST - must
    return (not missing), ("must_test complete" if not missing else f"missing: {', '.join(sorted(missing))}")


def flows_declare_terminal(ctx: Ctx, _: dict):
    flows = ctx.yml("flows.yml").get("flows") or []
    if not flows:
        return False, "flows.yml declares no flows"
    bad = []
    for f in flows:
        terminal = f.get("terminal_states")
        paths = set(f.get("paths") or [])
        missing_paths = {"normal", "error", "recovery"} - paths
        if not isinstance(terminal, list):
            bad.append(f"{f.get('id')}: no terminal_states")
        elif missing_paths:
            bad.append(f"{f.get('id')}: missing paths {','.join(sorted(missing_paths))}")
    return (not bad), ("all flows declare terminal_states + paths" if not bad else "; ".join(bad))


def flows_no_dead_end(ctx: Ctx, _: dict):
    flows = ctx.yml("flows.yml").get("flows") or []
    problems = []
    for f in flows:
        fid = f.get("id")
        steps = set(f.get("steps") or [])
        terminal = set(f.get("terminal_states") or [])
        nodes, out_edges = flow_graph(f)
        orphan_steps = steps - nodes
        if orphan_steps:
            problems.append(f"{fid}: steps absent from transitions {sorted(orphan_steps)}")
        for node in nodes:
            n_out = len(out_edges.get(node, []))
            if node in terminal and n_out:
                problems.append(f"{fid}: terminal {node} has {n_out} outgoing")
            if node not in terminal and n_out == 0:
                problems.append(f"{fid}: non-terminal {node} is a dead end")
    return (not problems), ("no dead ends" if not problems else "; ".join(problems[:4]))


def flows_no_terminal_error(ctx: Ctx, _: dict):
    flows = ctx.yml("flows.yml").get("flows") or []
    bad = [f"{f.get('id')}.{s}" for f in flows for s in (f.get("terminal_states") or [])
           if ERROR_STATE_RE.search(str(s))]
    return (not bad), ("no error state declared terminal" if not bad else f"terminal error states: {', '.join(bad)}")


def flows_feedback_budget(ctx: Ctx, _: dict):
    doc = ctx.yml("flows.yml")
    limit = dig(doc, "gates.feedback_within_ms")
    value = limit if isinstance(limit, (int, float)) else dig(doc, "gates.feedbackWithinMs")
    if value is None:
        return False, "feedback_within_ms not declared"
    ok = value <= 100
    return ok, f"feedback_within_ms={value} (limit 100)"


def flows_all_reachable(ctx: Ctx, _: dict):
    flows = ctx.yml("flows.yml").get("flows") or []
    problems = []
    for f in flows:
        steps = f.get("steps") or []
        if not steps:
            problems.append(f"{f.get('id')}: no steps")
            continue
        nodes, out_edges = flow_graph(f)
        seen, stack = set(), [steps[0]]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(out_edges.get(node, []))
        unreachable = nodes - seen
        if unreachable:
            problems.append(f"{f.get('id')}: unreachable {sorted(unreachable)}")
    return (not problems), ("all nodes reachable from first step" if not problems else "; ".join(problems))


def tokens_have_dark(ctx: Ctx, _: dict):
    leaves = color_leaves(ctx.js("design-token.json").get("color") or {})
    if not leaves:
        return False, "design-token.json declares no colour tokens"
    bad = [p for p, node in leaves if not ("light" in node and "dark" in node)]
    return (not bad), (f"{len(leaves)} colour tokens with light+dark" if not bad else f"missing light/dark: {', '.join(bad)}")


def token_contrast_min(ctx: Ctx, clause: dict):
    value = dig(ctx.js("design-token.json"), "contrast.min")
    if value is None:
        return False, "contrast.min not declared"
    v = clause["verify"]
    return compare(value, v.get("op", ">="), v.get("value", 4.5)), f"contrast.min={value}"


def token_touch_min(ctx: Ctx, _: dict):
    doc = ctx.js("design-token.json").get("touchTarget") or {}
    ios, android = doc.get("min"), doc.get("androidMin")
    if ios is None or android is None:
        return False, "touchTarget.min / androidMin not declared"
    ok = ios >= 44 and android >= 48
    return ok, f"ios={ios} (>=44), android={android} (>=48)"


def no_raw_hex_outside_token(ctx: Ctx, _: dict):
    hits = []
    for path in ctx.configured_files():
        if path.name == "design-token.json":
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if HEX_RE.search(line):
                hits.append(f"{path.name}:{i}")
    return (not hits), ("no raw colour values outside token file" if not hits else f"found at {', '.join(hits)}")


def font_levels_max(ctx: Ctx, clause: dict):
    font = ctx.js("design-token.json").get("font") or {}
    v = clause["verify"]
    ok = compare(len(font), v.get("op", "<="), v.get("value", 5))
    return ok, f"{len(font)} font levels"


def resolve_token(ctx: Ctx, ref: str) -> Any:
    parts = ref.split(".")
    if parts and parts[0] == "token":
        parts = parts[1:]
    return dig(ctx.js("design-token.json"), ".".join(parts))


def motion_max_duration(ctx: Ctx, clause: dict):
    doc = ctx.js("motion.json")
    limit = clause["verify"].get("value", 350)
    over = []
    for name, anim in (doc.get("animations") or {}).items():
        if not isinstance(anim, dict) or anim.get("loop") is True:
            continue  # loops declare themselves explicitly; exempt by clause MOT-01
        value = anim.get("duration")
        if value is None:
            continue
        actual = resolve_token(ctx, value) if isinstance(value, str) and value.startswith("token.") else value
        if not isinstance(actual, (int, float)):
            over.append(f"animations.{name}.duration unresolved ({value!r})")
        elif actual > limit:
            over.append(f"animations.{name}.duration={actual}")
    declared_max = dig(doc, "defaults.maxDuration")
    if isinstance(declared_max, (int, float)) and declared_max > limit:
        over.append(f"defaults.maxDuration={declared_max}")
    return (not over), (f"all non-loop durations <= {limit}ms" if not over else f"over budget: {', '.join(over)}")


def motion_reduced(ctx: Ctx, _: dict):
    ok = dig(ctx.js("motion.json"), "defaults.honorReducedMotion") is True
    return ok, ("honorReducedMotion: true" if ok else "defaults.honorReducedMotion must be true")


def motion_enter_easing(ctx: Ctx, _: dict):
    anims = ctx.js("motion.json").get("animations") or {}
    bad = []
    for name, a in anims.items():
        if not isinstance(a, dict) or "from" not in a:
            continue
        easing = str(a.get("easing", ""))
        if not ("enter" in easing or "spring" in easing):
            bad.append(f"{name}({easing or 'none'})")
    return (not bad), ("enter animations use enter/spring easing" if not bad else f"wrong easing: {', '.join(bad)}")


def motion_token_resolution(ctx: Ctx, _: dict):
    unresolved = []
    for path, value in walk_strings(ctx.js("motion.json")):
        if value.startswith("token.") and resolve_token(ctx, value) is None:
            unresolved.append(f"{path}={value}")
    return (not unresolved), ("all token refs resolve" if not unresolved else f"unresolved: {', '.join(unresolved)}")


def copy_forbidden_present(ctx: Ctx, _: dict):
    forbidden = dig(ctx.yml("copy.yml"), "tone.forbidden")
    ok = isinstance(forbidden, list) and len(forbidden) > 0
    return ok, (f"{len(forbidden)} forbidden strings" if ok else "tone.forbidden must be a non-empty list")


def copy_no_forbidden_values(ctx: Ctx, _: dict):
    doc = ctx.yml("copy.yml")
    forbidden = doc.get("tone", {}).get("forbidden") or []
    pruned = {k: v for k, v in doc.items() if k != "tone"}
    hits = []
    for path, value in walk_strings(pruned):
        for word in forbidden:
            if word and word in value:
                hits.append(f"{path} contains {word!r}")
    return (not hits), ("no forbidden strings in copy" if not hits else "; ".join(hits[:5]))


def copy_scenes_complete(ctx: Ctx, _: dict):
    doc = ctx.yml("copy.yml")
    missing = REQUIRED_COPY_SCENES - set(doc.keys())
    return (not missing), ("copy scenes complete" if not missing else f"missing scenes: {', '.join(sorted(missing))}")


def copy_destructive_delete(ctx: Ctx, _: dict):
    node = dig(ctx.yml("copy.yml"), "confirm.delete") or {}
    ok = node.get("destructive") is True and bool(node.get("text"))
    return ok, ("delete confirm is destructive with consequence text" if ok else "confirm.delete needs destructive: true")


def perf_budgets_declared(ctx: Ctx, _: dict):
    budgets = set((ctx.yml("perf-budget.yml").get("budgets") or {}).keys())
    missing = REQUIRED_BUDGETS - budgets
    return (not missing), ("all budgets declared" if not missing else f"missing: {', '.join(sorted(missing))}")


def a11y_contrast_scan_config(ctx: Ctx, _: dict):
    doc = ctx.yml("a11y.yml")
    if doc.get("blocking") is not True:
        return False, "a11y.yml must set blocking: true"
    contrast = doc.get("contrast") or {}
    missing = [k for k in ("body_text_min", "large_text_min", "ui_components_min") if k not in contrast]
    return (not missing), ("contrast thresholds declared" if not missing else f"missing: {', '.join(missing)}")


def a11y_touch(ctx: Ctx, _: dict):
    doc = ctx.yml("a11y.yml").get("touch") or {}
    ios, android = doc.get("ios_min_pt"), doc.get("android_min_dp")
    if ios is None or android is None:
        return False, "touch.ios_min_pt / android_min_dp not declared"
    ok = ios >= 44 and android >= 48
    return ok, f"ios={ios} (>=44), android={android} (>=48)"


def a11y_dynamic_type(ctx: Ctx, _: dict):
    doc = ctx.yml("a11y.yml").get("dynamic_type") or {}
    ok = doc.get("supported") is True and "scroll" in str(doc.get("layout", ""))
    return ok, ("dynamic type supported, layout scrolls" if ok else "dynamic_type.supported: true + layout: must_scroll_not_clip")


def platforms_have_profiles(ctx: Ctx, _: dict):
    doc, resolved = load_targets(ctx)
    if not resolved:
        return False, "platforms.yml declares no targets or runtimes"
    problems = []
    for t in resolved:
        pid = t["id"]
        if not isinstance(t["profile"], dict) or not t["profile"]:
            problems.append(f"{pid}: {t['path']}")
            continue
        declared = t["profile"].get("platform")
        if declared != pid:
            problems.append(f"{pid}: profile platform={declared!r}")
        pkind = t["profile"].get("kind")
        if pkind not in ("platform", "runtime"):
            problems.append(f"{pid}: profile kind={pkind!r}")
        elif pkind != t["kind"]:
            problems.append(f"{pid}: profile kind={pkind} but declared in {t['group']}")
        if not t["profile"].get("capabilities"):
            problems.append(f"{pid}: profile declares no capabilities")
    return (not problems), (f"{len(resolved)} profiles resolved" if not problems else "; ".join(problems[:4]))


def runtime_hosts_declared(ctx: Ctx, _: dict):
    doc, resolved = load_targets(ctx)
    platforms = declared_platform_ids(doc)
    problems = []
    seen_runtime = False
    for t in resolved:
        if t["kind"] != "runtime":
            continue
        seen_runtime = True
        pid = t["id"]
        if not platforms:
            problems.append(f"{pid}: runtime declared but no platform targets")
            continue
        hosts = set((t["profile"] or {}).get("hosts") or [])
        if not hosts:
            problems.append(f"{pid}: profile declares no hosts")
            continue
        if not (hosts & platforms):
            problems.append(f"{pid}: hosts {sorted(hosts)} do not intersect targets {sorted(platforms)}")
        else:
            t["hosts_shipped"] = sorted(hosts & platforms)
    if not seen_runtime:
        return True, "no runtimes declared (OK)"
    if problems:
        return False, "; ".join(problems[:4])
    shipped = ", ".join(f"{t['id']}->{','.join(t.get('hosts_shipped', []))}" for t in resolved if t["kind"] == "runtime")
    return True, f"runtimes cover declared targets ({shipped})"


def platform_units_declared(ctx: Ctx, _: dict):
    doc, resolved = load_targets(ctx)
    if not resolved:
        return False, "platforms.yml declares no targets"
    unit_map = doc.get("unit_map") or {}
    problems = []
    for t in resolved:
        pid = t["id"]
        want = (t["profile"] or {}).get("unit") if isinstance(t["profile"], dict) else None
        got = t["target"].get("unit") or unit_map.get(pid)
        if not got:
            problems.append(f"{pid}: no unit declared")
        elif want and got != want:
            problems.append(f"{pid}: unit={got} but profile expects {want}")
    return (not problems), (
        ", ".join(f"{t['id']}={t['target'].get('unit') or unit_map.get(t['id'])}" for t in resolved)
        if not problems else "; ".join(problems[:4])
    )


def platform_capabilities_declared(ctx: Ctx, _: dict):
    doc, resolved = load_targets(ctx)
    if not resolved:
        return False, "platforms.yml declares no targets"
    declared = doc.get("capabilities") or {}
    problems = []
    total = 0
    for t in resolved:
        pid = t["id"]
        profile = t["profile"] if isinstance(t["profile"], dict) else {}
        owned = declared.get(pid) or {}
        for cap in profile.get("capabilities") or []:
            cid = cap.get("id")
            if not cid:
                continue
            total += 1
            entry = owned.get(cid)
            if not isinstance(entry, dict):
                problems.append(f"{pid}.{cid}: undeclared")
                continue
            status = entry.get("status")
            if status == "implemented" and not entry.get("where"):
                problems.append(f"{pid}.{cid}: implemented but no where")
            elif status == "not_applicable" and not entry.get("reason"):
                problems.append(f"{pid}.{cid}: not_applicable but no reason")
            elif status not in ("implemented", "not_applicable"):
                problems.append(f"{pid}.{cid}: status={status!r}")
    return (not problems), (f"{total} platform capabilities declared" if not problems else "; ".join(problems[:4]))


def platform_thresholds_met(ctx: Ctx, _: dict):
    doc, resolved = load_targets(ctx)
    if not resolved:
        return False, "platforms.yml declares no targets"
    values = doc.get("thresholds") or {}
    problems = []
    checked = 0
    for t in resolved:
        pid = t["id"]
        profile = t["profile"] if isinstance(t["profile"], dict) else {}
        owned = values.get(pid) or {}
        for key, bound in (profile.get("thresholds") or {}).items():
            checked += 1
            got = owned.get(key)
            if got is None:
                problems.append(f"{pid}.{key}: undeclared")
                continue
            direction = threshold_direction(key)
            if direction == "floor" and got < bound:
                problems.append(f"{pid}.{key}={got} looser than profile {bound}")
            elif direction == "ceiling" and got > bound:
                problems.append(f"{pid}.{key}={got} looser than profile {bound}")
    return (not problems), (f"{checked} platform thresholds met" if not problems else "; ".join(problems[:4]))


def gate_p0_complete(ctx: Ctx, clause: dict):
    p0 = dig(ctx.yml("release-gate.yml"), "levels.P0") or {}
    items = p0.get("items") or []
    minimum = clause["verify"].get("value", 7)
    ok = p0.get("blocking") is True and len(items) >= minimum
    return ok, f"P0 blocking={p0.get('blocking')}, items={len(items)} (min {minimum})"


def gate_ci_fail_on(ctx: Ctx, _: dict):
    fail_on = set(dig(ctx.yml("release-gate.yml"), "ci.fail_build_on") or [])
    missing = {"P0", "P1"} - fail_on
    return (not missing), ("CI fails on P0+P1" if not missing else f"ci.fail_build_on missing: {', '.join(sorted(missing))}")


def contract_self_consistent(ctx: Ctx, _: dict):
    clauses = ctx.yml("contract.yml").get("clauses") or []
    if not clauses:
        return False, "contract.yml declares no clauses"
    bad = []
    for c in clauses:
        missing = CONTRACT_CLAUSE_FIELDS - set(c)
        if missing:
            bad.append(f"{c.get('id', '?')}: missing {','.join(sorted(missing))}")
        if c.get("enforcement") not in {"blocking", "advisory"}:
            bad.append(f"{c.get('id', '?')}: bad enforcement")
        if c.get("level") not in {"MUST", "MUST NOT", "SHOULD"}:
            bad.append(f"{c.get('id', '?')}: bad level")
    return (not bad), (f"{len(clauses)} clauses well-formed" if not bad else "; ".join(bad[:4]))


CHECKS = {
    "entities_have_required_fields": entities_have_required_fields,
    "no_orphan_components": no_orphan_components,
    "entity_types_complete": entity_types_complete,
    "state_machines_present": state_machines_present,
    "page_states_complete": page_states_complete,
    "error_states_have_recovery": error_states_have_recovery,
    "no_state_conflict": no_state_conflict,
    "relations_no_cycles": relations_no_cycles,
    "no_raw_value_in_components": no_raw_value_in_components,
    "pages_cover_all_states": pages_cover_all_states,
    "scenes_cover_required": scenes_cover_required,
    "scenarios_have_fields": scenarios_have_fields,
    "p0_scenarios_defined": p0_scenarios_defined,
    "must_test_covers": must_test_covers,
    "flows_declare_terminal": flows_declare_terminal,
    "flows_no_dead_end": flows_no_dead_end,
    "flows_no_terminal_error": flows_no_terminal_error,
    "flows_feedback_budget": flows_feedback_budget,
    "flows_all_reachable": flows_all_reachable,
    "tokens_have_dark": tokens_have_dark,
    "token_contrast_min": token_contrast_min,
    "token_touch_min": token_touch_min,
    "no_raw_hex_outside_token": no_raw_hex_outside_token,
    "font_levels_max": font_levels_max,
    "motion_max_duration": motion_max_duration,
    "motion_reduced": motion_reduced,
    "motion_enter_easing": motion_enter_easing,
    "motion_token_resolution": motion_token_resolution,
    "copy_forbidden_present": copy_forbidden_present,
    "copy_no_forbidden_values": copy_no_forbidden_values,
    "copy_scenes_complete": copy_scenes_complete,
    "copy_destructive_delete": copy_destructive_delete,
    "perf_budgets_declared": perf_budgets_declared,
    "a11y_contrast_scan_config": a11y_contrast_scan_config,
    "a11y_touch": a11y_touch,
    "a11y_dynamic_type": a11y_dynamic_type,
    "gate_p0_complete": gate_p0_complete,
    "platforms_have_profiles": platforms_have_profiles,
    "platform_units_declared": platform_units_declared,
    "platform_capabilities_declared": platform_capabilities_declared,
    "platform_thresholds_met": platform_thresholds_met,
    "runtime_hosts_declared": runtime_hosts_declared,
    "gate_ci_fail_on": gate_ci_fail_on,
    "contract_self_consistent": contract_self_consistent,
}


# --------------------------------------------------------------------------- #
# evidence
# --------------------------------------------------------------------------- #

def _verify_one(ctx: Ctx, rel: str, spec: dict) -> tuple[bool, str]:
    path = ctx.root / rel
    if not path.is_file():
        return False, f"{rel} missing"
    try:
        rec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return False, f"{rel} does not parse: {exc}"

    if rec.get("status") != "pass":
        return False, f"{rel} status={rec.get('status')!r} (needs pass)"
    if not rec.get("verified_by"):
        return False, f"{rel} missing verified_by"
    if not rec.get("artifact"):
        return False, f"{rel} missing artifact"

    max_age = spec.get("max_age_days")
    if max_age:
        stamp = rec.get("verified_at")
        if not stamp:
            return False, f"{rel} missing verified_at"
        try:
            when = dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except ValueError:
            return False, f"{rel} verified_at is not ISO-8601"
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        age = (dt.datetime.now(dt.timezone.utc) - when).days
        if age > max_age:
            return False, f"{rel} stale: {age}d old (max {max_age}d)"

    assertion = spec.get("assert")
    if assertion:
        actual = dig(rec, assertion["path"])
        if actual is None:
            return False, f"{rel} missing {assertion['path']}"
        if not compare(actual, assertion.get("op", "=="), assertion.get("value")):
            return False, f"{assertion['path']}={actual} fails {assertion.get('op')} {assertion.get('value')}"
        return True, f"{assertion['path']}={actual} OK ({rel})"

    return True, f"evidence OK ({rel})"


def check_evidence(ctx: Ctx, clause: dict):
    """Evidence clauses verify one file, or one file per declared platform."""
    spec = clause["verify"]
    pattern = spec.get("file_pattern")

    if pattern:
        _, resolved = load_targets(ctx)
        if not resolved:
            return False, "no platform targets to expand {platform}"
        failures = []
        passed = 0
        for target in resolved:
            rel = pattern.replace("{platform}", str(target["id"]))
            ok, detail = _verify_one(ctx, rel, spec)
            if ok:
                passed += 1
            else:
                failures.append(detail)
        if failures:
            return False, "; ".join(failures[:4])
        return True, f"{passed}/{len(resolved)} platform evidence OK"

    rel = spec.get("file") or f"evidence/{clause['id']}.yml"
    ok, detail = _verify_one(ctx, rel, spec)
    return ok, detail


# --------------------------------------------------------------------------- #
# runner
# --------------------------------------------------------------------------- #

def evaluate(ctx: Ctx, clause: dict) -> tuple[str, str]:
    spec = clause.get("verify") or {}
    method = spec.get("method")
    try:
        if method == "static":
            fn = CHECKS.get(spec.get("check"))
            if fn is None:
                return "FAIL", f"unknown check: {spec.get('check')}"
            ok, detail = fn(ctx, clause)
            return ("PASS" if ok else "FAIL"), detail
        if method == "evidence":
            ok, detail = check_evidence(ctx, clause)
            return ("PASS" if ok else "UNVERIFIED"), detail
        return "FAIL", f"unknown verify method: {method}"
    except ConfigError as exc:
        return "FAIL", str(exc)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("config_dir", help="directory containing contract.yml and the config graph")
    ap.add_argument("--report", help="write a markdown report to this path")
    ap.add_argument("--quiet", action="store_true", help="only print the verdict")
    args = ap.parse_args()

    root = Path(args.config_dir).expanduser()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    if not (root / "contract.yml").is_file():
        print(f"error: {root}/contract.yml not found", file=sys.stderr)
        return 2

    ctx = Ctx(root)
    try:
        contract = ctx.yml("contract.yml")
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    clauses = contract.get("clauses") or []
    if not clauses:
        print("error: contract.yml declares no clauses", file=sys.stderr)
        return 2

    rows = []
    for clause in clauses:
        status, detail = evaluate(ctx, clause)
        rows.append((clause, status, detail))

    blocking_failures = [
        (c, s, d) for c, s, d in rows
        if c.get("enforcement") == "blocking" and s != "PASS"
    ]
    accepted = not blocking_failures

    if not args.quiet:
        width = max(len(c["id"]) for c, _, _ in rows)
        print(f"contract {contract.get('contract', {}).get('id')} "
              f"v{contract.get('contract', {}).get('version')}")
        print(f"{'CLAUSE'.ljust(width)}  {'LEVEL':8} {'ENFORCE':9} STATUS      DETAIL")
        print("-" * (width + 50))
        for clause, status, detail in rows:
            print(f"{clause['id'].ljust(width)}  {clause['level']:8} "
                  f"{clause.get('enforcement', ''):9} {status:11} {detail[:110]}")
        print()

    counts: dict[str, int] = {}
    for _, status, _ in rows:
        counts[status] = counts.get(status, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))

    if accepted:
        print(f"VERDICT: ACCEPTED — all blocking clauses PASS ({summary})")
    else:
        print(f"VERDICT: NOT ACCEPTED — {len(blocking_failures)} blocking clause(s) not passed ({summary})")
        for clause, status, detail in blocking_failures:
            print(f"  {clause['id']}: {status} — {detail}")
        print(f"\n{len(blocking_failures)} clause(s) must be satisfied before release.")

    if args.report:
        out = Path(args.report).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        verdict = "ACCEPTED" if accepted else "NOT ACCEPTED"
        lines = [
            f"# Contract Verification Report",
            "",
            f"- contract: `{contract.get('contract', {}).get('id')}` "
            f"v{contract.get('contract', {}).get('version')}",
            f"- verified_at: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}",
            f"- verdict: **{verdict}**",
            f"- summary: {summary}",
            "",
            "| Clause | Level | Enforcement | Status | Detail |",
            "|---|---|---|---|---|",
        ]
        for clause, status, detail in rows:
            lines.append(f"| {clause['id']} | {clause['level']} | "
                         f"{clause.get('enforcement')} | {status} | {detail.replace('|', '/')} |")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"report: {out}")

    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
