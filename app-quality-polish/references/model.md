# The five-dimension model (informative)

> This file is **informative**. It explains the model so the config graph makes sense.
> The normative constraints live in `contract.yml` as clause ids. This file defines no
> thresholds and is not an acceptance basis.

The five dimensions: **Entity, Attribute/State, Relation, Scenario, Flow**.

> An entity is a node, an attribute/state is a field, a relation is an edge,
> a scenario is a query, and a flow is a state transition sequence.
> These are not five documents; they are five views of one queryable config graph.

## Dimension definitions

| Dimension | Definition | Carried by | Clauses |
|---|---|---|---|
| Entity | An independently designable, buildable and testable object with an id, a type and a lifecycle | entities.yml | ENT-01..03 |
| Attribute / State | An entity's observable characteristics and its state machine | states.yml, page-state.yml, component-state.yml | STA-01..05 |
| Relation | Structural, behavioural and dependency relationships between entities | relations.yml | REL-01..04 |
| Scenario | A user goal plus an environment plus a combination of entity states | scenarios.yml | SCN-01..04 |
| Flow | The state transition sequence inside a scenario, including normal, error and recovery paths | flows.yml | FLW-01..05 |
| Platform | Implementation constraints for the same entities, states and flows on each axis | platforms.yml, platforms/<id>.yml | PLT-01..07 |

The platform axis is a sixth, orthogonal dimension, split into `kind: platform` and
`kind: runtime`. It adds no new entities; it adds **declarative constraints** (units,
capabilities, thresholds) to the entities, states and flows that already exist. That is
why the `PLT-*` clauses read `platforms.yml` plus profiles instead of restating the model.

One model, different values per axis: the same button entity requires 44pt on iOS,
48dp on Android, 48vp on HarmonyOS and 28px on desktop. **Share the model, split the
values.** That is what makes quality a contract instead of five separate style guides.

## 1. Entity

| Entity type | Example id | Notes | Lifecycle | Config source | Gate |
|---|---|---|---|---|---|
| App | `app` | Bundle, launch, version | install -> run -> update | build config | cold start target met |
| Page | `page.home` | Route-level container | enter -> loading -> present -> exit | page-state.yml | no white screen |
| Component | `comp.button.primary` | Reusable interactive unit | create -> interact -> dispose | component-state.yml | states complete |
| Element | `elem.icon`, `elem.text` | Icon, text, divider | render -> update | Token | aligned, contrast ok |
| Token | `token.color.brand` | Colour, type, spacing, radius | define -> reference | design-token.json | no hardcoding |
| Motion | `motion.pageEnter` | Transition, feedback, loop | trigger -> play -> end | motion.json | duration and curve unified |
| Copy | `copy.empty.search` | Empty, error, success, permission | scene -> render | copy.yml | no jargon |
| Data | `data.user`, `data.list` | Local or remote data | request -> cache -> expire | data layer | usable on slow network |
| User | `user.guest`, `user.auth` | Identity and permission | guest -> signed in -> signed out | account system | permission guidance |
| Session | `session` | Auth state, token | create -> refresh -> expire | security config | expiry recoverable |
| Network | `net.online/offline/slow` | Network environment | change listener | network layer | slow network notice |
| Permission | `perm.camera`, `perm.notify` | System permission | undetermined -> request -> granted/denied | permission layer | denial guidance |
| Notification | `notify.push` | Push, in-app message | receive -> present -> tap | notification centre | can be disabled |
| Theme | `theme.light/dark` | Appearance | switch -> apply | theme config | no broken layout |
| Accessibility | `a11y` | Contrast, text scale, screen reader | global | a11y.yml | baseline met |

**Entity gate** (ENT-01..03): no unregistered entities, no orphan components, and every
entity declares type, owner, lifecycle, source and gate.

## 2. Attribute / State

| Entity | Core attributes | State machine | Default | Boundary rule | Config |
|---|---|---|---|---|---|
| Page | route, title, cache, ttl | idle -> loading -> success \| empty \| error \| offline \| noAuth | idle | every page must cover six states | page-state.yml |
| Button | variant, size, tone | default -> pressed -> loading -> success \| error \| disabled | default | feedback within 100ms of tap | component-state.yml |
| Input | value, error, focus | default -> focus -> filled -> error \| disabled | default | errors anchor to the field | component-state.yml |
| List | page, hasMore, cache | skeleton -> content -> loadingMore -> end \| error | skeleton | end-of-list notice, retry on error | page-state.yml |
| Image | src, ratio, cache | placeholder -> loading -> success \| error -> retry | placeholder | failure has a placeholder | image config |
| Motion | duration, easing, property | idle -> playing -> done \| cancelled | idle | supports reduced motion | motion.json |
| Network | online, rtt, retry | online -> slow -> offline -> timeout -> retry | online | slow network shows cache | network layer |
| Permission | status | notDetermined -> requesting -> granted \| denied \| restricted | notDetermined | denial guides to settings | permission config |
| Theme | mode | light <-> dark <-> highContrast | system | semantic colours, never inverted | design-token.json |
| Accessibility | contrast, fontScale | normal -> large -> accessibility | normal | contrast at least 4.5:1 | a11y.yml |

**State gate** (STA-01..05):

- Every entity has a state machine. Shipping only the default state is not a design.
- Every state declares entry condition, exit condition, visual, copy and feedback.
- Every error state has a recovery path, i.e. at least one outgoing edge.

## 3. Relation

| Relation | Source -> target | Cardinality | Constraint | Config | Gate |
|---|---|---|---|---|---|
| contains | page -> comp | 1:N | pages must be assembled from components | relations.yml | no orphan components |
| composes | comp -> elem | 1:N | elements inherit tokens | relations.yml | no hardcoded values |
| uses | comp -> token/motion | N:M | only semantic tokens may be referenced | design-token.json | no raw values |
| triggers | event -> motion/flow | 1:N | every event has feedback | motion.json | tap produces a response |
| depends | flow -> data/net/perm | N:M | dependency failure has a degraded path | flows.yml | usable on slow network |
| inherits | theme.dark -> token | 1:N | dark mode uses semantic colours | design-token.json | no broken layout |
| overrides | page -> copy | 1:N | pages may override shared copy | copy.yml | tone stays consistent |
| maps | error -> copy | 1:1 | every error has copy | copy.yml | no unknown error |
| excludes | loading <-> error | - | must never render together | state machine | no state conflict |
| sequences | flow -> flow.step | 1:N | steps are ordered and cancellable | flows.yml | no dead ends |

**Relation gate** (REL-01..04): no cycles; no cross-layer references such as a page
referencing a raw colour value; pages must cover their states; scenarios must cover slow
network, dark mode and large text.

## 4. Scenario

| Scenario id | Scenario | Goal | Entities | State combination | Expectation | Exception / recovery | Gate |
|---|---|---|---|---|---|---|---|
| S01 | First launch | Reach the app quickly | app + page.home | cold start -> skeleton -> success | interactive under 2s | failure -> retry | P0 |
| S02 | Sign in | Establish identity | page.login + form + perm | default -> input -> validate -> submit -> success | errors anchored to fields | failure -> inline copy | P0 |
| S03 | Search | Find content | page.search + list + copy | recent -> typing -> results / empty | empty state offers a next step | slow network -> local history | P1 |
| S04 | Browse a list | Consume smoothly | page.list + list + image | skeleton -> content -> load more -> end | 60fps | error -> retry | P0 |
| S05 | View detail | Read information | page.detail + comp + data | skeleton -> success / removed | cache is usable | no permission -> sign in | P1 |
| S06 | Submit a form | Persist data | form + button + copy | edit -> error -> correct -> submit -> success | success haptic | failure -> draft | P0 |
| S07 | Pay | Complete a transaction | page.pay + perm + net | confirm -> loading -> success / failure | double submit prevented | timeout -> query order | P0 |
| S08 | Slow network | Remain usable | net.slow + list + cache | stale data + timestamp + retry | no white screen | timeout -> cache | P0 |
| S09 | Offline | Work from local data | net.offline + data | offline notice + cache | state is explicit | recovery -> refresh | P1 |
| S10 | Permission denied | Recover gracefully | perm.denied + copy | denied -> explain -> open settings | no repeated prompts | settings -> recovered | P0 |
| S11 | Dark mode | Stay consistent | theme.dark + token | switch -> applied globally | contrast holds | broken -> block release | P0 |
| S12 | Large text | Avoid broken layout | a11y.fontScale + page | scale up -> adaptive layout | scrolls | clipping -> fix | P0 |
| S13 | Accessibility | Readable and operable | a11y + comp | reader -> focus -> operate | touch targets at least 44pt | focus order -> fix | P0 |
| S14 | Error recovery | Never dead-end | error + copy + flow | error -> explain -> retry / back | recoverable | no recovery -> block release | P0 |
| S15 | Release acceptance | Quality gate | release + gate | P0 pass -> gray -> full | metrics do not regress | regression -> rollback | P0 |

**Scenario gate** (SCN-01..04): all P0 scenarios pass; slow network, dark mode, large text
and accessibility are mandatory; every scenario declares entities, states, expectation and
exception branch.

## 5. Flow

| Flow id | Flow | Steps | State transitions | Event / feedback | Exception / recovery | Metric | Gate |
|---|---|---|---|---|---|---|---|
| F01 | Cold start | launch -> splash -> home | launch -> splash -> loading -> success/empty/error | brand transition, skeleton | failure -> retry | cold start P90 under 2s | blocking |
| F02 | Sign in | input -> validate -> submit | default -> editing -> validating -> submitting -> success/error | field-level errors, loading | failure -> inline copy | response under 100ms | blocking |
| F03 | List loading | skeleton -> content -> more | skeleton -> content -> loadingMore -> end/error | pull to refresh, end notice | error -> retry | FPS at least 58 | blocking |
| F04 | Form submit | edit -> submit -> success | idle -> editing -> error -> submitting -> success | haptic, toast | failure -> draft | double submit prevented | blocking |
| F05 | Slow network recovery | online -> slow -> offline -> retry | online -> slow -> offline -> timeout -> retry -> online | cached notice | automatic retry | availability | blocking |
| F06 | Permission request | undetermined -> request -> denied -> settings | notDetermined -> requesting -> denied -> explain -> granted | rationale copy | no repeated prompts | grant rate | blocking |
| F07 | Release gate | dev -> CI -> device -> gray | dev -> ci -> device -> gray -> full | reports, dashboards | regression -> rollback | crash rate under 0.1% | blocking |

**Flow gate** (FLW-01..05): normal, error and recovery paths all present; non-terminal
nodes always have an outgoing edge; error-class states are never terminal; every node is
reachable from the first step; feedback within 100ms.

## Integrated example

One component, all five dimensions plus the platform axis:

```yaml
entities:
  comp.button.primary:
    type: component
    owner: design-system
    lifecycle: reusable
    attrs:
      size: { type: enum, values: [sm, md, lg], default: md }
      tone: { type: enum, values: [brand, danger], default: brand }
    states:
      default: { bg: token.color.brand.primary, text: token.color.text.onBrand }
      pressed: { scale: 0.98, haptic: light }
      disabled: { opacity: 0.4 }
      loading: { spinner: true, disabled: true }
      success: { icon: check, haptic: light }
      error: { tone: danger }
    relations:
      contains: [elem.icon, elem.label]
      uses: [token.color, token.radius, motion.fast]
      triggered_by: [event.tap]
    scenes: [S02, S06, S07]
    flows:
      - id: F04
        transitions:
          - { from: default, event: tap, to: pressed }
          - { from: pressed, event: release, to: loading }
          - { from: loading, event: success, to: success }
          - { from: loading, event: error, to: error }
          - { from: error, event: retry, to: loading }   # required by STA-03 and FLW-02
        gate:
          - no_double_submit
          - feedback_100ms
          - error_copy_mapped
```

## Dimensions to pipeline

| Dimension | Pipeline focus | Config artefact |
|---|---|---|
| Entity + Scenario | baseline audit | issue list |
| Entity + Attribute/State | token normalisation | design-token.json |
| Attribute/State + Relation | component states | component-state.yml |
| Entity + Relation + Scenario | page assembly | page-state.yml |
| Attribute/State + Flow | motion | motion.json |
| Attribute/State + Scenario | copy | copy.yml |
| Flow + Attribute/State | performance and accessibility | perf-budget.yml, a11y.yml |
| Platform (all axes) | per-axis adaptation | platforms.yml, platforms/*.yml |
| Scenario + Flow | release gate | release-gate.yml |
| Flow + Scenario | monitoring | dashboard, regression items |
