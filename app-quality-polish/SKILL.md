---
name: app-quality-polish
description: Enforce app quality as a verifiable acceptance contract instead of advice. Use for perceived quality work (polish, premium feel, craft), UI quality audits, quality gates and release blocking criteria, cross-platform consistency, per-platform design-system adaptation, design-token rules, component state matrices, motion specs, performance budgets, empty/error/slow-network/dark-mode/large-text coverage, or the five-dimension method (entity, attribute/state, relation, scenario, flow). Covers iOS, Android, HarmonyOS, Web, H5, mini program, desktop, and the Flutter / React Native runtimes. Produces a machine-checkable contract.yml with MUST/MUST NOT clauses, per-axis profiles (HIG, Material 3, ArkUI, WCAG, H5 viewport, mini program packaging, desktop windowing, Flutter frame budget, RN lists), thresholds, evidence artefacts, and a verifier returning ACCEPTED or NOT ACCEPTED. NOT for product strategy, backend performance, or brand identity creation.
---

# App Quality Polish — Acceptance Contract

This skill does not produce recommendations. It produces **a contract and a verifier**, so
quality is decided by clauses and measurements rather than by opinion.

```
subjective polish -> clause (MUST/MUST NOT) -> threshold -> verification method -> evidence -> verdict
```

Normative language follows RFC 2119: **MUST**, **MUST NOT**, **SHOULD**.

**Authority order.** `contract.yml` is normative. This file and everything in `references/`
are informative. If they disagree, `contract.yml` wins. Never restate a threshold in prose
when it can live in a clause.

## Quick start

```bash
# Any combination of platforms and runtimes; the tool classifies them by kind
python3 scripts/scaffold_configs.py ./my-app --platforms ios,android,harmonyos,web,h5,miniprogram,desktop,flutter,react-native
python3 scripts/scaffold_configs.py ./my-app --platforms ios,android,flutter   # Flutter app, two platforms
python3 scripts/scaffold_configs.py ./my-app --platforms harmonyos,web         # HarmonyOS plus web
# fill entities.yml -> states.yml -> relations.yml -> scenarios.yml -> flows.yml
# then declare every capability in platforms.yml
python3 scripts/verify_contract.py ./my-app/quality   # verdict plus exit code
```

Exit codes are the interface: `0` = ACCEPTED, `1` = NOT ACCEPTED, `2` = usage or parse
error. Wire it into CI and the contract enforces itself.

## Two axes: platforms and runtimes

A project owes obligations only for what it declares. Per-axis rules live in **profiles**,
not in the contract:

```
platforms.yml               targets (OS surfaces) plus runtimes (host frameworks)
platforms/ios.yml           HIG and UIKit behaviours
platforms/android.yml       Material 3 and Android behaviours
platforms/harmonyos.yml     ArkTS/ArkUI, HAP packaging, atomic services
platforms/web.yml           WCAG 2.2 AA and Core Web Vitals
platforms/h5.yml            viewport, safe area, host container realities
platforms/miniprogram.yml   package size, setData, capsule safe area, rpx
platforms/desktop.yml       window resize, keyboard, HiDPI, cursor
platforms/flutter.yml       (kind: runtime) frame budget, repaint scope, host feel
platforms/react-native.yml  (kind: runtime) JS-thread stalls, list memory, host feel
```

**A runtime is not a platform.** Flutter and React Native render onto iOS, Android, Web,
H5 and desktop; they are an implementation axis orthogonal to the OS axis. Declaring
`flutter` does not mean you ship Flutter — it means you owe Flutter's obligations *on the
platforms you do ship*, which `PLT-07` enforces by intersecting the runtime's `hosts` with
your declared `targets`.

The contract's `PLT-*` clauses iterate whatever is declared, so adding an axis adds
obligations without editing the contract:

| Axis | kind | Unit | Hard constraints specific to this axis (full list in the profile) |
|---|---|---|---|
| iOS | platform | pt | 44pt, safe area, Dynamic Type, Reduce Motion, semantic dark colour, haptics, swipe back, VoiceOver |
| Android | platform | dp | 48dp, edge-to-edge insets, text in sp, predictive back, dynamic colour, ripple and focus, TalkBack |
| HarmonyOS | platform | vp | avoidArea, vp/fp units, semantic colour resources, HAP size, LazyForEach, atomic-service cards, accessibilityText |
| Web | platform | px | keyboard reachability, visible focus ring, hover, prefers-reduced-motion, semantic HTML, 200% zoom |
| H5 | platform | px | viewport-fit=cover, env(safe-area-inset-*), no 100vh, tap highlight, no sticky hover, host containers |
| Mini program | platform | rpx | main package 2MB, batched setData, rpx, capsule safe area, image domain whitelist, hover-class, virtual list, darkmode |
| Desktop | platform | px | menu bar and shortcuts, window resize, visible focus ring, HiDPI multi-monitor, hover and cursor, context menu and drag-drop, custom title bar, large-screen density |
| Flutter | runtime | logical_px | 8ms UI and raster frame budget, jank ratio, const subtrees, RepaintBoundary, MediaQuery insets, platform-adaptive transitions, Semantics |
| React Native | runtime | logical_px | JS frame budget, bundle size, virtualized lists, useNativeDriver, Pressable and hitSlop, SafeArea, image caching, Fabric migration state |

Rules that keep the axes honest:

- **Thresholds may be tightened, never loosened.** `PLT-04` fails if any declared value is
  looser than its profile floor or ceiling.
- **Every profile capability must be declared** as `implemented` (with `where`) or
  `not_applicable` (with `reason`). Silence is a failure, not a default.
- **A runtime must land somewhere.** `PLT-07` fails on `flutter` with only `miniprogram`,
  or mainline `flutter` with only `harmonyos`, because shipping a fork is a decision that
  has to be recorded in `hosts`.
- **Adding an axis is additive.** Drop in a profile, add the entry, and existing clauses
  re-evaluate. Removing one must be a deliberate edit to `platforms.yml`, recorded like any
  other contract change.

## The clause set

51 clauses across 12 dimensions. Each declares `level` (MUST / MUST NOT), `enforcement`
(blocking / advisory), a measurable `requirement`, a `verify` method, and the `evidence` it
consumes.

- **`method: static`** — machine-checked against the config graph by `verify_contract.py`.
  Platform clauses iterate `platforms.yml`.
- **`method: evidence`** — requires a record in `evidence/<CLAUSE-ID>.yml` that is
  `status: pass` and, where declared, satisfies an assertion within `max_age_days`.
  Axis-scoped clauses use `file_pattern: evidence/PLT-05-{platform}.yml` and must pass for
  **every** declared axis.

| Dimension | Clause | Requirement (summary; thresholds are normative in contract.yml) |
|---|---|---|
| Entity | ENT-01 | Every entity must declare type, owner, lifecycle, source and gate |
| | ENT-02 | MUST NOT leave orphan components: every component must be referenced by a scenario |
| | ENT-03 | entity_types must cover app/page/component/element/token/motion/copy/data/net/perm/theme/a11y |
| Attribute / State | STA-01 | Every state machine must declare attrs, states and transitions together |
| | STA-02 | The page state machine must cover loading/success/empty/error/offline/noAuth |
| | STA-03 | Every error-class state must have an outgoing edge, i.e. a recovery path |
| | STA-04 | Every implemented state must have an entry/exit/visual/copy/feedback record — evidence |
| | STA-05 | MUST NOT render loading and error together; an excludes declaration is required |
| Relation | REL-01 | The relation graph must be acyclic |
| | REL-02 | MUST NOT place raw colour values in component or page configs |
| | REL-03 | Every page entity must have an entry in page-state.yml |
| | REL-04 | scenes_must_cover must include slow_network, dark_mode and large_text |
| Scenario | SCN-01 | Every scenario must declare entities, states, expect, exception and gate |
| | SCN-02 | The P0 scenario set must be complete (S01,S02,S04,S06,S07,S08,S10-S14,S15) |
| | SCN-03 | must_test must include slow_network, dark_mode, large_text and a11y |
| | SCN-04 | All P0 scenarios must have been executed — evidence |
| Flow | FLW-01 | Every flow must declare terminal_states and paths (normal/error/recovery) |
| | FLW-02 | Non-terminal nodes must have an outgoing edge; terminal nodes must have none |
| | FLW-03 | MUST NOT declare an error-class state terminal |
| | FLW-04 | feedback_within_ms must be at most 100 |
| | FLW-05 | Every node in a flow must be reachable from the first step |
| Token | TOK-01 | Every colour token must define both light and dark |
| | TOK-02 | contrast.min must be at least 4.5 |
| | TOK-03 | Touch targets at least 44pt on iOS and 48dp on Android |
| | TOK-04 | MUST NOT allow raw colour values outside the token file |
| | TOK-05 | The type scale must not exceed five levels |
| Motion | MOT-01 | Non-loop animations at most 350ms |
| | MOT-02 | honorReducedMotion must be declared and respected |
| | MOT-03 | Entrance animations must use the enter curve or a spring |
| | MOT-04 | Every token.* reference in motion.json must resolve |
| Copy | CPY-01 | A non-empty forbidden-string list must be declared |
| | CPY-02 | MUST NOT let a forbidden string appear in the copy body |
| | CPY-03 | Copy must exist for empty/error/offline/auth/permission/success/confirm/list |
| | CPY-04 | The delete confirmation must be destructive and state the consequence |
| Performance | PRF-01 | All six budgets must be declared: cold start, first screen, click response, frame rate, crash, ANR |
| | PRF-02 | Measured cold start P90 under 2000ms — evidence (7 days) |
| | PRF-03 | Measured crash and ANR rate under 0.1% — evidence (7 days) |
| Accessibility | A11Y-01 | Must be blocking with all three contrast tiers declared |
| | A11Y-02 | Touch targets at least 44pt on iOS and 48dp on Android |
| | A11Y-03 | Dynamic type supported, layout scrolls rather than clips |
| | A11Y-04 | Accessibility scan reports zero violations — evidence (30 days) |
| Platform | PLT-01 | Targets and runtimes declared; every profile exists, parses, matches platform and kind, and declares capabilities |
| | PLT-02 | Every axis has a unit mapping matching its profile |
| | PLT-03 | Every profile capability declared as implemented (+where) or not_applicable (+reason) |
| | PLT-04 | Declared thresholds never looser than the profile; no threshold omitted |
| | PLT-05 | Every axis has a core-page visual baseline — evidence (30 days) |
| | PLT-06 | Every axis device matrix run with zero failures — evidence (14 days) |
| | PLT-07 | A runtime must cover at least one declared platform |
| Gate | GAT-01 | The P0 gate must be blocking with at least seven checks |
| | GAT-02 | CI fail_build_on must include P0 and P1 |
| | GAT-03 | Contract self-consistency: every clause declares id, dim, level, enforcement, requirement, verify |

## Acceptance procedure

1. **Scaffold** — `scaffold_configs.py <project> --platforms <ids>` writes `contract.yml`,
   `platforms.yml` (targets plus runtimes), one profile per axis, the config graph, and one
   pending evidence stub per evidence clause (**per axis** for `file_pattern` clauses).
   Axes are classified automatically by each profile's `kind`.
2. **Populate** — fill the five dimension files in dependency order: `entities.yml` →
   `states.yml` → `relations.yml` → `scenarios.yml` → `flows.yml`. Then the audit files:
   `design-token.json`, `motion.json`, `copy.yml`, `component-state.yml`, `page-state.yml`,
   `perf-budget.yml`, `a11y.yml`, `release-gate.yml`.
3. **Verify** — run `verify_contract.py`. Static clauses resolve immediately; evidence
   clauses stay UNVERIFIED until evidence exists.
4. **Evidence** — produce one `evidence/<CLAUSE-ID>.yml` per evidence clause. Evidence is
   not a checkbox: it carries an `artifact` and an assertion that the verifier re-checks.
5. **Judge** — the acceptance rule is `all_blocking_clauses_pass`. A blocking clause that is
   FAIL **or UNVERIFIED** is not accepted. There is no partial credit and no waiver path
   that bypasses the file.

```
CLAUSE   LEVEL    ENFORCE   STATUS      DETAIL
ENT-01   MUST     blocking  PASS        all entities complete
STA-03   MUST     blocking  FAIL        dead-end: button.error
PRF-02   MUST     blocking  UNVERIFIED  evidence/PRF-02.yml stale: 45d old (max 7d)
PLT-07   MUST     blocking  FAIL        flutter: hosts [...] do not intersect targets ['miniprogram']
GAT-03   MUST     blocking  PASS        51 clauses well-formed

VERDICT: NOT ACCEPTED — 3 blocking clause(s) not passed
```

`--report <path>` emits a Markdown conformance report for the release record.

## Evidence contract

```yaml
clause: PRF-02
status: pass                # pass | fail | pending - only pass satisfies a clause
verified_by: ci             # who or what produced it
verified_at: 2026-01-31T09:20:00Z
artifact: reports/perf-2026-01-31.json   # the raw measurement, not a summary
measured:
  cold_start_p90_ms: 1830   # re-checked against the clause assertion
```

The verifier re-reads the numbers behind `artifact`, so evidence cannot silently rot.
`max_age_days` makes stale evidence expire: PRF-02 and PRF-03 expire in 7 days, PLT-06 and
SCN-04 in 14, STA-04, A11Y-04 and PLT-05 in 30. Expiry is deliberate — it turns a one-time
sign-off into a standing obligation.

## Remediation map

| Violation | Fix |
|---|---|
| `FAIL ... does not parse` | the config file is malformed; fix the syntax before anything else |
| `FAIL ... missing` | add the field, state or scenario the clause names |
| `FAIL dead-end: <machine>.<state>` | add an explicit recovery transition out of that state |
| `FAIL cycle:` | break the relation cycle; re-point the edge one layer up |
| `FAIL over budget: <path>` | lower the value, or replace the literal with a token reference |
| `FAIL ... looser than profile` | tighten the value in `platforms.yml` to meet or beat the profile |
| `FAIL <axis>.<capability>: undeclared` | declare it as `implemented` + `where`, or `not_applicable` + `reason` |
| `FAIL ... unit=dp but profile expects px` | fix the unit; Web/H5/desktop px, mini program rpx, iOS pt, Android dp, HarmonyOS vp, Flutter/RN logical_px |
| `FAIL <runtime>: hosts [...] do not intersect targets` | add the host platform, or, if shipping a fork, add it to the runtime profile's `hosts` as a recorded decision |
| `UNVERIFIED ... PLT-05-<axis>.yml missing` | produce the visual baseline for that specific axis |
| `UNVERIFIED ... missing` | produce the evidence record with its `artifact` |
| `UNVERIFIED ... stale` | re-run the measurement and refresh `verified_at` |
| `UNVERIFIED ... fails <op> <value>` | the measurement is out of contract; fix the product, not the record |

Full audit method for sourcing the initial numbers: [references/verification.md](references/verification.md).

## Change control

Thresholds are contract terms, not preferences.

1. Amending any threshold means editing `contract.yml` and bumping `contract.version`.
2. Adding a clause requires `id / dim / level / enforcement / requirement / verify`, or
   GAT-03 fails the build.
3. A project MAY tighten a threshold (for example `contrast.min: 7.0`) and MUST NOT loosen
   one below the template without a version bump and a recorded rationale in the contract
   file.
4. Loosening a threshold to make a build pass voids the contract: that is a false
   acceptance, not a waiver.

## Boundaries

- Informative material only: [references/model.md](references/model.md) (the five-dimension
  model), [references/schema.md](references/schema.md) (config schema),
  [references/platforms.md](references/platforms.md) (per-axis constraints),
  [references/pipeline.md](references/pipeline.md) (milestones),
  [references/verification.md](references/verification.md) (verification and evidence).
- Ask which platforms ship, which **runtime** implements them, and which is primary before
  filling values. The clause structure generalises; the concrete numbers do not. A
  cross-platform project with a primary platform should set that platform's profile
  thresholds as the target and treat the others as floors.
- This contract covers perceived quality and release gating. It does not cover product
  strategy, backend latency, or brand identity creation.
