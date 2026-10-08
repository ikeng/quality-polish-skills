# Quality Polish Skills

Agent skills that turn subjective quality work into **verifiable acceptance contracts**.

This repo is a skills collection. It currently ships one skill:

| Skill | What it does |
|---|---|
| [`app-quality-polish`](app-quality-polish/) | Turns "make it feel good" into 51 machine-checkable clauses, per-platform profiles, and a verifier that returns `ACCEPTED` / `NOT ACCEPTED` |

---

## The problem

Quality work normally arrives as advice:

> Reduce motion to 150–250ms. Handle empty, error and offline states. Use semantic colours in dark mode.

None of that can be verified, so it degrades into a checklist someone ticks. The same review happens again next quarter, and the same defects ship.

`app-quality-polish` converts each piece of advice into a **clause with a threshold, a verification method, and an evidence artefact** — then enforces it.

```
subjective polish
  -> clause (MUST / MUST NOT)
  -> threshold
  -> verification method
  -> evidence
  -> ACCEPTED / NOT ACCEPTED
```

## Quick start

The scripts run on their own — no agent required, only Python 3 and PyYAML.

```bash
git clone https://github.com/ikeng/quality-polish-skills.git
cd quality-polish-skills

# 1. Emit a contract package for your project, declaring the axes you ship
python3 app-quality-polish/scripts/scaffold_configs.py ./my-app \
  --platforms ios,android,flutter

# 2. Fill in the config graph, then verify
python3 app-quality-polish/scripts/verify_contract.py ./my-app/quality
```

Exit codes are the interface, so it drops straight into CI:

| Exit | Meaning |
|---|---|
| `0` | `ACCEPTED` — every blocking clause passed |
| `1` | `NOT ACCEPTED` — at least one blocking clause failed or is unverified |
| `2` | Usage or parse error |

A fresh scaffold exits `1` by design: static clauses pass, evidence clauses are `UNVERIFIED` until you produce the evidence.

```
CLAUSE   LEVEL    ENFORCE   STATUS      DETAIL
ENT-01   MUST     blocking  PASS        all entities complete
STA-03   MUST     blocking  FAIL        dead-end: button.error
PRF-02   MUST     blocking  UNVERIFIED  evidence/PRF-02.yml stale: 45d old (max 7d)
PLT-07   MUST     blocking  FAIL        flutter: hosts do not intersect targets ['miniprogram']
GAT-03   MUST     blocking  PASS        51 clauses well-formed

VERDICT: NOT ACCEPTED — 3 blocking clause(s) not passed
```

Add `--report report.md` for a Markdown conformance report to keep as the release record.

## What a clause looks like

`contract.yml` is the single normative source of truth. Each clause names its own verification:

```yaml
- id: FLW-02
  dim: flow
  level: MUST
  enforcement: blocking
  requirement: Non-terminal nodes must have at least one outgoing edge; terminal nodes must have none.
  verify: { method: static, check: flows_no_dead_end }
```

Two verification methods:

- **`static`** (44 clauses) — machine-checked against the config graph. Real algorithms, not string matching: DFS cycle detection over the relation graph, out-degree analysis on flow graphs, BFS reachability, token reference resolution, hex-literal scanning.
- **`evidence`** (7 clauses) — requires a record that is `status: pass`, names an `artifact`, and satisfies an assertion within a freshness window.

```
Clause   Method    What it actually does
REL-01   static    DFS cycle detection over the relation graph
FLW-02   static    builds the flow graph, enforces out-degree per node
FLW-05   static    BFS reachability from the first step
STA-03   static    finds error-class states with out-degree 0 (dead ends)
MOT-04   static    resolves every token.* against design-token.json
TOK-04   static    rejects hex literals outside the token file
PRF-02   evidence  measured cold start P90 < 2000ms, expires in 7 days
```

Evidence expires on purpose. Performance evidence dies in 7 days, device matrices in 14, state and accessibility records in 30. A stale record cannot hold a release open — which stops "we tested it last time" from standing in for "we tested it this time".

## Two orthogonal axes

A project only owes obligations for what it declares. Per-axis rules live in **profiles**, not in the contract, so adding a platform adds obligations without editing any clause.

```
platforms.yml               targets (OS surfaces) + runtimes (host frameworks)
platforms/ios.yml           HIG and UIKit behaviours
platforms/android.yml       Material 3 and Android behaviours
platforms/harmonyos.yml     ArkTS/ArkUI, HAP packaging, atomic services
platforms/web.yml           WCAG 2.2 AA and Core Web Vitals
platforms/h5.yml            viewport, safe area, host container realities
platforms/miniprogram.yml   package size, setData, capsule safe area, rpx
platforms/desktop.yml       window resize, keyboard, HiDPI, cursor
platforms/flutter.yml       (kind: runtime) frame budget, repaint scope, host feel
platforms/react-native.yml  (kind: runtime) JS-thread stalls, list memory
```

| Axis | kind | Unit | Capabilities |
|---|---|---|---|
| iOS | platform | pt | 7 |
| Android | platform | dp | 6 |
| HarmonyOS | platform | vp | 8 |
| Web | platform | px | 7 |
| H5 | platform | px | 8 |
| Mini program | platform | rpx | 9 |
| Desktop | platform | px | 9 |
| Flutter | runtime | logical_px | 8 |
| React Native | runtime | logical_px | 8 |

**A runtime is not a platform.** Flutter and React Native render onto iOS, Android, Web, H5 and desktop; they are an implementation axis orthogonal to the OS axis. Declaring `flutter` does not mean "we ship Flutter" — it means you accept Flutter's obligations *on the platforms you do ship*. `PLT-07` enforces this by intersecting a runtime's `hosts` with your declared `targets`:

```
platforms: [ios, android] + runtime: flutter   -> PASS  (flutter->android,ios)
platforms: [miniprogram]  + runtime: flutter   -> FAIL  (Flutter cannot run in a mini program)
platforms: [harmonyos]    + runtime: flutter   -> FAIL  (mainline Flutter does not host HarmonyOS)
```

That last failure is deliberate. Shipping a fork to HarmonyOS is a legitimate decision, but it has to be recorded — add `harmonyos` to the profile's `hosts` and the contract holds you to it.

Three further invariants:

- **Thresholds may be tightened, never loosened.** `PLT-04` fails if any declared value is weaker than its profile floor or ceiling.
- **Every capability must be declared** as `implemented` (with `where`) or `not_applicable` (with `reason`). Silence is a failure, not a default.
- **Loosening a threshold to make a build pass voids the contract.** That is a false acceptance, not a waiver.

## The five-dimension model

The config graph is one model with five views, plus the platform axis:

> An entity is a node, an attribute/state is a field, a relation is an edge, a scenario is a query, and a flow is a state transition sequence.

| Dimension | Question | Config | Clauses |
|---|---|---|---|
| Entity | What exists? | `entities.yml` | 3 |
| Attribute / State | What can each thing become? | `states.yml`, `page-state.yml`, `component-state.yml` | 5 |
| Relation | What contains, depends on or triggers what? | `relations.yml` | 4 |
| Scenario | Under what conditions is it used? | `scenarios.yml` | 4 |
| Flow | How does state move? | `flows.yml` | 5 |
| Token / Motion / Copy / Perf / A11y | What are the measurable floors? | `design-token.json`, `motion.json`, `copy.yml`, `perf-budget.yml`, `a11y.yml` | 20 |
| Platform / Runtime | How does each axis differ? | `platforms.yml`, `platforms/*.yml` | 7 |
| Gate | What blocks the release? | `release-gate.yml` | 3 |

**51 clauses, 12 dimensions, 70 platform capabilities, 49 platform thresholds.**

## Repo layout

```
app-quality-polish/
├── SKILL.md                  entry point: scope, clause index, procedure, change control
├── scripts/
│   ├── scaffold_configs.py   emits the contract, config graph and evidence stubs
│   └── verify_contract.py    the verifier; exit code is the interface
├── references/               informative: model, schema, platforms, pipeline, verification
└── assets/templates/         contract.yml, 13 configs, 9 axis profiles, evidence template
```

`contract.yml` is **normative**. `SKILL.md` and everything in `references/` are **informative** — if they disagree, `contract.yml` wins. This is enforced in spirit by `GAT-03`, which checks the contract is self-consistent.

## Using this as an agent skill

`app-quality-polish` follows the standard skill convention: `SKILL.md` with `name` and `description` frontmatter, plus `references/`, `scripts/` and `assets/`. Drop the directory into your agent's skills folder and it is discoverable.

The agent-facing contract and the standalone scripts are the same artefact. There is no separate build step and no hidden state — `verify_contract.py` reads the config graph directly, so a human and an agent running the same command get the same verdict.

## Limitations

Worth knowing before you adopt this:

- **The profile values are opinionated defaults, not measurements.** iOS and Android numbers come from published platform guidance. The H5 and mini program thresholds (200KB first screen, 256KB setData payload) are engineering heuristics. If you have real numbers from your own product, they should replace mine — tightening is free, loosening requires a version bump and a recorded reason.
- **The contract proves you documented and measured, not that the product is good.** `STA-04` checks that a record of each state exists; it cannot tell whether the motion curve feels right. The verifier removes arguments about whether something was done — not judgement about whether it was done well.
- **`copy.yml` ships English examples and an English forbidden-word list.** If you localise, keep the forbidden list in the language of the shipped copy or `CPY-02` will check the wrong strings.
- **Adding a clause means bumping `contract.version`.** `GAT-03` will fail a malformed clause, but nothing stops you from loosening a threshold and bumping the version anyway. That is a discipline boundary, not a technical one.

## Contributing

Adding a platform or runtime means adding one profile file under `assets/templates/platforms/` and nothing else — the `PLT-*` clauses iterate whatever is declared.

Two naming rules make a profile work:

1. Threshold keys encode direction: floors end in `_min_<unit>`, ceilings in `_max_<unit>`. A leading `min_` is not recognised, so `min_body_font_pt` is wrong and should be `body_font_min_pt`.
2. A profile must declare `platform`, `kind`, `unit`, `thresholds` and a non-empty `capabilities` list. Runtimes must also declare `hosts`.

## License

[MIT](LICENSE)
