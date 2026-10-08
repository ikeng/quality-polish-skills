# Pipeline milestones (informative)

The pipeline is the order in which the contract is satisfied. Each milestone's **exit
criterion is a set of passing clauses**, not a feeling that the work is done. Normative
content lives in `contract.yml`.

| Milestone | Action | Artefacts | Exit criteria (clauses) |
|---|---|---|---|
| M0 Baseline audit | Real-device slow-motion review of core paths, collecting real numbers | issue list, baseline score | none (method in verification.md) |
| M1 Token normalisation | Build semantic tokens with paired light and dark values | design-token.json | TOK-01..05 |
| M2 Entities and states | Inventory entities, complete state machines | entities.yml, states.yml | ENT-01..03, STA-01..03, STA-05 |
| M3 Relations and pages | Constrain the relation graph, assemble page states | relations.yml, page-state.yml, component-state.yml | REL-01..04, STA-02 |
| M4 Scenarios and flows | Build the scenario library and flow state machines | scenarios.yml, flows.yml | SCN-01..03, FLW-01..05 |
| M5 Motion and copy | Unify motion, complete copy | motion.json, copy.yml | MOT-01..04, CPY-01..04 |
| M6 Performance and accessibility | Set budgets, run the accessibility audit | perf-budget.yml, a11y.yml | PRF-01, A11Y-01..03 |
| M6.5 Platform adaptation | Declare axes, then capability status and thresholds per axis | platforms.yml, platforms/*.yml | PLT-01..04, PLT-07 |
| M7 Gate and evidence | Wire CI, produce per-axis evidence | release-gate.yml, evidence/* | GAT-01..03, STA-04, SCN-04, PRF-02, PRF-03, A11Y-04, PLT-05, PLT-06 |
| M8 Monitoring | Watch production metrics, turn regressions into items | dashboard, reports | all clauses stay PASS |

Indicative schedule: M0 week 1; M1-M2 weeks 2-3; M3 weeks 4-5; M4-M5 week 6; M6 week 7;
M6.5 and M7 week 8; M8 continuous.

Platform adaptation sits at M6.5 rather than M0 on purpose. Only once shared tokens and a
shared state model exist does "how should each axis express this one thing" become a
meaningful question. Splitting per axis first produces five unrelated implementations.

## Mapping to the dimensions

| Milestone | Dimension focus |
|---|---|
| M1 | Token (an entity's attributes) |
| M2 | Entity + Attribute/State |
| M3 | Entity + Relation |
| M4 | Scenario + Flow |
| M5 | Attribute/State + Flow |
| M6 | Flow + Attribute/State |
| M6.5 | Platform (one entity's behaviour per axis) |
| M7 | Scenario + Flow -> gate |
| M8 | Flow feedback |

## Weekly verification record

Run this at the end of every milestone:

```bash
python3 scripts/verify_contract.py quality --report reports/M<n>-<date>.md
```

Keep the reports. Progress is the **clause pass rate**, not a subjective assessment:

- at the end of M2, ENT and STA should be fully PASS;
- at the end of M4, FLW-01..05 should be fully PASS, since dead ends and unreachable nodes
  are structural defects and the cheapest time to expose them is now;
- at the end of M6.5, PLT-01..04 and PLT-07 should be fully PASS, because capability
  declarations and thresholds are checked at declaration time;
- at the end of M7, only evidence clauses may still be UNVERIFIED, and each must have a
  concrete artefact plan.

## Structural defects cost more than the others

The ordering is not arbitrary. Cycles, dead ends and unreachable nodes are structural:
fixing them during M2-M4 is a config edit, and fixing them at M7 is an architecture
change. The contract makes them static clauses precisely so they fail at the moment the
config is written.
