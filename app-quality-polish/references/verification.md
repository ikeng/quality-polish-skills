# Verification and evidence (informative)

This file explains how clauses are verified, how evidence is produced, and how to wire
the verifier into CI. Normative content lives in `contract.yml`.

## Two verification methods

| Method | Executed by | Outcome | Failure state |
|---|---|---|---|
| `static` | `verify_contract.py`, against the config graph | PASS / FAIL | FAIL |
| `evidence` | evidence records produced by people or tools, re-checked by the verifier | PASS / UNVERIFIED | UNVERIFIED |
| `evidence` + `file_pattern` | as above, expanded once per declared axis | PASS / UNVERIFIED | UNVERIFIED |

`UNVERIFIED` and `FAIL` are equivalent for acceptance: the rule is
`all_blocking_clauses_pass`.

## Baseline audit method (M0)

Clauses can only be filled in once real numbers exist. The audit method:

1. Pick three to five core paths: launch, sign-in, the core task, payment, settings.
2. Run on real devices, on a slow network, in dark mode, with large text; record and
   play back frame by frame.
3. Check each frame for:
   - jank, jumps, white screens, flicker
   - time from tap to feedback (PRF-02, FLW-04)
   - whether empty, error, loading, success and disabled states exist (STA-02, STA-04)
   - whether type, spacing, radius and icons are consistent (TOK-04, TOK-05)
   - whether small screens, large text, dark mode and slow networks break the layout
     (A11Y-01..03, REL-04)
   - whether every error state has a recovery path (STA-03, FLW-02)
4. Produce an issue list graded P0/P1/P2 and map each item to a clause id.
5. After fixing, re-run `verify_contract.py`; the clause statuses are the acceptance record.

## Producing evidence

| Clause | Typical tooling | Artefact |
|---|---|---|
| PRF-02 cold start | Instruments, Perfetto, Firebase Performance | trace file or report JSON |
| PRF-03 crash and ANR | Sentry, Firebase Crashlytics, platform console | exported report |
| SCN-04 P0 scenario execution | device matrix plus screenshot diff | execution report and screenshot directory |
| STA-04 state records | Storybook, Compose Preview, SwiftUI Preview | state matrix screenshots or links |
| A11Y-04 accessibility scan | Accessibility Scanner, axe, platform audit | scan report |
| PLT-05 axis visual baseline | screenshot diff (Percy or in-house) | one baseline directory per axis |
| PLT-06 axis device matrix | device cloud or in-house device lab | one execution report per axis |

The minimum for an evidence record is `status: pass`, `verified_by`, `verified_at` and
`artifact`. Missing any of them means UNVERIFIED.

## Per-axis evidence

Clauses with a `file_pattern` (PLT-05, PLT-06) expand **per declared axis**:

```yaml
verify:
  method: evidence
  file_pattern: evidence/PLT-05-{platform}.yml
  max_age_days: 30
```

If `platforms.yml` declares five axes, the verifier requires five files and names the one
that is missing:

```
PLT-05: UNVERIFIED - evidence/PLT-05-miniprogram.yml missing
```

Reusing one screenshot set across axes is not evidence: host container, system font, safe
areas and rendering engine all differ, so baselines must be established per axis.

## Freshness

`max_age_days` is an obligation, not a suggestion:

| Clause | Freshness | Rationale |
|---|---|---|
| PRF-02 / PRF-03 | 7 days | Performance and crash rate move with the code; old data does not describe the current build |
| PLT-06 device matrix | 14 days | Devices, OS versions and builds all change, and it runs per axis |
| SCN-04 | 14 days | Scenario execution must be close to the release candidate |
| STA-04 / A11Y-04 / PLT-05 | 30 days | Lower change frequency, but still re-checked within the release cycle |

Expired evidence becomes UNVERIFIED and blocks release. This is not bureaucracy: it stops
"we tested it last time" from standing in for "we tested it this time".

## CI wiring

```yaml
# Pseudoconfig; any CI system works
quality-contract:
  run_on: [pull_request, release_branch, release_tag]
  steps:
    - run: python3 scripts/verify_contract.py quality --report quality/report.md
    - publish: quality/report.md
  fail_when: exit_code != 0
  required_checks: [P0, P1]      # matches GAT-02
```

Four ways to use it:

1. **PR gate** - static clauses only, to catch structural regressions fast (dead ends, raw
   colour values, missing states, thresholds loosened below the profile).
2. **Release gate** - the full set including evidence and freshness, with the report kept
   as the release record.
3. **Regression baseline** - retain historical `--report` files and track the clause pass
   rate over time rather than a single verdict.
4. **Per-axis tracking** - run in full even for a single-axis release: expired evidence on
   an untouched axis still blocks, because "we did not change it" is not "it is fine".

## Common misuse

| Misuse | Consequence | Correct approach |
|---|---|---|
| Writing `status: pass` with no artefact | False acceptance | The artefact must point at a re-checkable measurement |
| Loosening a `contract.yml` threshold to make the build green | The contract is void | Fix the product; if relaxation is truly needed, bump the version and record the reason |
| Running only static clauses before release | Every evidence clause is UNVERIFIED | The release gate must run the full set |
| Replacing an evidence file with "confirmed manually" | Not auditable | People and tools are the same here: both must produce a record |
| Adding a waiver for a cyclic relation graph | Hides a structural problem | Break the cycle and point the edge one layer up |
| Setting a project threshold below the profile to go green | Platform adaptation exists in name only | Fix the product; if relaxation is needed, change the profile first and bump the version |
| Marking an axis capability `not_applicable` with no reason | Shedding an obligation | `reason` is required and is reviewed as a design decision |
| Reusing one screenshot set for several axes | Per-axis evidence is invalid | PLT-05 is per axis; a missing axis is UNVERIFIED |
