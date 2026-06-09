# Spec-Driven / Test-Driven Development Guide

## From Requirements to Shipped Product

> Context: redesigning how acsys-python delivers control-system data to users, potentially spanning multiple connected systems.

------

## 1. Discovery & Problem Framing

1.1. **Identify stakeholders** — physicists, operators, automated systems, downstream AI pipelines. Each has different tolerance for complexity, latency, and data gaps.

1.2. **Write a problem statement** — one paragraph that names the pain, the user, and the cost of doing nothing. Pin this to your repo. Every future scope debate references it.

1.3. **Enumerate use cases** — not features. "A physicist streams beam-loss readings live during a run." "An ML pipeline replays a week of data to retrain a model." Use cases expose the actual contract before any API is chosen.

1.4. **Identify system boundaries** — what is in scope (the Python API, the chunk format, protocol adapters) vs. out of scope (the control system itself, ACNET/DPM internals). Draw a boundary diagram. Anything outside the boundary is a dependency, not a deliverable.

1.5. **Surface open questions explicitly** — list every assumption that, if wrong, would change the design. Don't answer them yet. Just list them.

------

## 2. Specification Writing

2.1. **Choose a spec format** — for a data API, a good spec has three parts:

- **Behavioral spec**: what the API *does* (inputs, outputs, error modes, timing guarantees)
- **Data contract spec**: what a chunk *looks like* (schema, fields, gap/missing representation)
- **Integration spec**: how subsystems connect

2.2. **Write specs in plain language first** — avoid code. "A chunk contains exactly one rep-rate period of data for each requested parameter. Missing cycles are represented explicitly, never silently filled." That sentence *is* a spec.

2.3. **Make specs falsifiable** — every spec statement should be testable. If you can't write a test that would fail if the statement were violated, the statement is too vague.

2.4. **Version and store specs alongside code** — specs live in the repo (`docs/specs/`), reviewed in PRs like code. They drift if they live in a wiki.

2.5. **Get stakeholder sign-off on the data contract first** — the chunk format is the highest-leverage spec. Everything else depends on it. Don't finalize anything else until the chunk format is agreed on.

2.6. **Enumerate error and edge cases explicitly**:

- Missing/dropped cycle
- Parameter unavailable (device offline)
- Cross-machine rep-rate mismatch
- Sub- and super-rep-rate data
- Timeout

------

## 3. Architecture Design

3.1. **Draw the data flow** — source → protocol adapter → chunk assembler → user API. Name each layer. Define what each layer is responsible for and, critically, what it is *not* responsible for.

3.2. **Define layer contracts** — each interface between layers is a mini-spec. "The protocol adapter delivers raw samples tagged with machine cycle number and wall-clock time. It does not interpret, align, or fill data."

3.3. **Identify integration points** — where do subsystems connect? What are the failure modes at each seam?

3.4. **Decide on the chunk as the universal data structure** — confirm the invariant: the chunk format used in historical replay is identical to the chunk format delivered live. Document this as an architectural constraint.

3.5. **Defer protocol-specific decisions** — the architecture should be stable whether the underlying protocol is DPM, ACNET, or something new.

3.6. **Produce an Architecture Decision Record (ADR) for each major choice** — one page: context, options, decision, consequences.

------

## 4. Test Specification (Before Code)

4.1. **Write acceptance tests from use cases** — each use case becomes at least one black-box acceptance test.

4.2. **Write contract tests for each layer boundary** — "Given a raw sample with a gap flag, the chunk assembler produces a chunk with an explicit missing-cycle entry, not a filled value."

4.3. **Write property-based tests for the data contract** — use `hypothesis` or similar.

4.4. **Define a test oracle for alignment** — for cross-machine or multi-parameter chunks, specify exactly what "aligned" means and write a test that catches misalignment.

4.5. **Classify tests by speed and dependency**:

- **Unit** — pure logic, no I/O, milliseconds
- **Integration** — layer seams with fakes/stubs, seconds
- **System/Acceptance** — real or simulated control system, minutes

4.6. **Write tests against an interface, not an implementation** — tests that reach into private state break on refactors that don't change behavior.

------

## 5. Iterative Implementation (TDD Loop)

5.1. **Red** — write the smallest test that fails because the feature doesn't exist. Confirm it fails for the right reason.

5.2. **Green** — write the minimum code to make that test pass. No more.

5.3. **Refactor** — clean up while keeping tests green. Not optional.

5.4. **Integrate in vertical slices** — implement one complete use case end-to-end before building a second. Avoid building horizontal layers in isolation.

5.5. **Keep the chunk format frozen once tests exist** — any schema change requires updating the spec, the tests, and a migration note.

5.6. **Use fakes, not mocks, for protocol adapters** — a fake is a lightweight correct-behavior substitute (e.g., a replay adapter reading from a file). Fakes double as documentation of the protocol contract.

------

## 6. Multi-System Integration

6.1. **Define the integration contract before building either system** — the contract is a shared artifact owned by both sides.

6.2. **Build consumer-driven contract tests** — the consumer (e.g., the ML pipeline) writes the test asserting "I expect a chunk that looks like X." The producer must pass it.

6.3. **Run integration tests in CI against a control-system simulator** — a real control system is not a test fixture.

6.4. **Use feature flags for cross-system work in progress** — incomplete integration is hidden behind a flag so main stays shippable.

6.5. **Test the failure modes, not just the happy path** — timeout, partial data, malformed data, out-of-order delivery.

------

## 7. Review & Validation

7.1. **Spec review before code review** — a PR that changes behavior must update the spec first.

7.2. **Acceptance test sign-off by a non-author** — a physicist or operator validates that the behavior matches their mental model.

7.3. **Review the data contract with the ML pipeline owner** — confirm gaps are surfaced, not hidden, before any data is used for AI training.

7.4. **Adversarial review** — assign someone to try to break the API. Document every break as a bug or a spec clarification.

------

## 8. Documentation

8.1. **API reference is generated from code** — docstrings are the source of truth.

8.2. **Conceptual docs are written by hand** — "What is a chunk?", "How does missing data work?" These don't auto-generate.

8.3. **Keep a changelog** — every behavioral change gets an entry. Semantic versioning: breaking changes bump major.

8.4. **Document deliberately deferred open questions** — a "known limitations" section is honest and protects users from building on unstable behavior.

------

## 9. Shipping

9.1. **Define "done" per use case** — done when: acceptance test passes, spec is updated, non-author has validated.

9.2. **Ship in layers** — v1: single-machine, single-protocol, live data. v2: historical replay with identical chunk format. v3: cross-machine alignment. Each layer is useful independently.

9.3. **Pin the public API surface before the first release** — anything public is a promise. Keep the surface small.

9.4. **Run the full test suite in CI on every merge to main**.

9.5. **Have a rollback plan** — for control-room systems, define rollback before you ship.

9.6. **Collect feedback against use cases, not feature requests** — "does this solve the physicist's problem?" prevents scope creep.

------

## Appendix: Key Artifacts Checklist

| Artifact                      | Lives In                     | Updated When                 |
| ----------------------------- | ---------------------------- | ---------------------------- |
| Problem statement             | `docs/PROBLEM.md`            | Never (or a new doc)         |
| Use cases                     | `docs/use-cases/`            | New use case discovered      |
| Data contract spec            | `docs/specs/chunk-format.md` | Schema changes               |
| Architecture Decision Records | `docs/adr/`                  | Major design choices         |
| Acceptance tests              | `tests/acceptance/`          | Use case implemented         |
| Contract tests                | `tests/contract/`            | Layer boundary changes       |
| Changelog                     | `CHANGELOG.md`               | Every behavioral change      |
| Open questions log            | `docs/OPEN-QUESTIONS.md`     | Questions opened or resolved |