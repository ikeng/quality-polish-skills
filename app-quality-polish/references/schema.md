# Config schema (informative)

Each config file, the fields it carries, and the clauses it satisfies. Thresholds are
normative in `contract.yml`; they are not repeated here.

| Config file | Responsibility | Key fields | Clauses |
|---|---|---|---|
| contract.yml | The normative clause list | contract, clauses[] | GAT-03 |
| entities.yml | Entity model | entity_types, entities{type,owner,lifecycle,source,gate} | ENT-01..03 |
| states.yml | State machines | state_machines{attrs,states,transitions} | STA-01, STA-03 |
| page-state.yml | Page states | required_states, rules, pages | STA-02, REL-03 |
| component-state.yml | Component state matrix | defaults, components{required_states,states} | REL-02 |
| relations.yml | Relation constraints | edges{source,relation,target,cardinality,gate}, gates | REL-01, REL-04, STA-05 |
| scenarios.yml | Scenario library | scenarios{entities,states,expect,exception,gate}, gates | SCN-01..04 |
| flows.yml | Flow state machines | flows{steps,terminal_states,paths,transitions}, gates | FLW-01..05 |
| design-token.json | Semantic tokens | color, space, radius, font, shadow, motion, easing, touchTarget, contrast | TOK-01..05, MOT-04 |
| motion.json | Motion spec | defaults{honorReducedMotion,maxDuration}, animations{duration,easing,from,loop} | MOT-01..04 |
| copy.yml | Copy templates | tone{voice,rules,forbidden}, empty, error, offline, auth, permission, success, confirm, list | CPY-01..04 |
| perf-budget.yml | Performance budgets | blocking, budgets{}, ci{fail_build_on} | PRF-01..03 |
| a11y.yml | Accessibility | blocking, contrast, touch, dynamic_type, screen_reader, focus, motion, ci | A11Y-01..04 |
| release-gate.yml | Release gate | levels{P0,P1,P2}, ci{run_on,fail_build_on} | GAT-01, GAT-02 |
| platforms.yml | Two-axis declaration: platforms and runtimes, units, capability status, project thresholds | version, targets[], runtimes[], unit_map, capabilities{axis:{cap:{status,where,reason}}}, thresholds{axis:{}} | PLT-01..04, PLT-07 |
| platforms/<id>.yml | Axis profile (kind: platform or runtime) | platform, kind, unit, hosts (runtime only), min_version, thresholds, capabilities[], evidence | PLT-01, PLT-03, PLT-04, PLT-07 |
| evidence/<ID>.yml | Evidence record | clause, platform, status, verified_by, verified_at, artifact, measured | all evidence clauses |

Axis profiles carry the per-axis knowledge; the contract itself never hardcodes an
iOS, Android or H5 number. Nine profiles ship with the skill:

| id | kind | unit | hosts |
|---|---|---|---|
| ios | platform | pt | - |
| android | platform | dp | - |
| harmonyos | platform | vp | - |
| web | platform | px | - |
| h5 | platform | px | - |
| miniprogram | platform | rpx | - |
| desktop | platform | px | macos / windows / linux |
| flutter | runtime | logical_px | ios / android / web / h5 / desktop |
| react-native | runtime | logical_px | ios / android / web / h5 / desktop |

A `kind: runtime` profile must declare `hosts`, and PLT-07 checks that they intersect the
declared `targets`. Adding an axis means adding a profile and one entry; the `PLT-*`
clauses pick it up automatically.

## Field rules

1. **Semantic first.** Token files use semantic names (`color.bg.base`), not visual ones
   (`color.white`). REL-02 and TOK-04 reject raw colour values.
2. **References must resolve.** Any `token.*` reference must resolve against
   `design-token.json`, otherwise MOT-04 fails.
3. **Declaring is obligating.** Any field written into a config is verified. A field with
   no corresponding verification should be deleted, not left as a comment.
4. **Platform differences stay in the platform layer.** Axis-specific numbers belong in
   `platforms/<id>.yml` or the axis block of `platforms.yml`. They must not be scattered
   into the shared `design-token.json` or guarded by `if (platform === ...)` in business code.

## Threshold direction

PLT-04 infers direction from the key name, so naming is semantics:

| Key contains | Direction | Project value must be |
|---|---|---|
| `_min` | floor | >= the profile value |
| `_max` | ceiling | <= the profile value |
| neither | no direction | declared, but not numerically compared |

For example a profile `touch_target_min_pt: 44` requires the project value to be `>= 44`,
and `cls_max: 0.1` requires `<= 0.1`. Omission always fails.

Profile authors must therefore keep naming consistent: write floors as `xxx_min_unit` and
ceilings as `xxx_max_unit`. A leading `min_` is not recognised as a floor, so
`min_body_font_pt` is wrong and should be `body_font_min_pt`.

## How a clause maps to fields

Clause `FLW-02` (non-terminal nodes must have an outgoing edge) reads `flows.yml`:

```yaml
flows:
  - id: F04
    steps: [idle, editing, error, submitting, success]
    terminal_states: [success]        # terminal: must have no outgoing edge
    paths: [normal, error, recovery]  # FLW-01
    transitions:
      - { from: submitting, event: fail, to: error,      path: error }
      - { from: error,      event: retry, to: submitting, path: recovery }  # keeps error off a dead end
```

The verifier builds a graph from `steps` plus `transitions` and checks that nodes in
`terminal_states` have out-degree zero while all others have out-degree at least one.
Delete the last transition and `error` becomes a dead end, failing both `FLW-02` and
`STA-03`.
