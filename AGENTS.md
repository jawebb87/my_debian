# Agent Directives & Workflow Guidelines

## Self-Healing Bounded Review-and-Fix Pipeline

Whenever the planner tool (`openrouter-planner` / `generate_project_plan`) is called, all tasks MUST follow this self-healing, bounded review-and-fix lifecycle:

### 1. Execution Flow Specification
1. **Plan Generation:**
   - Query `generate_project_plan` using OpenRouter's free router (`openrouter/free`).
2. **Implementation:**
   - Apply all planned architecture and code modifications systematically.
3. **Deterministic Gate (Local Verification):**
   - Automatically execute the project's build, compile/typecheck, linter, and test suites.
   - If tests/build fail, route errors directly back to the fixer model *before* initiating any LLM review pass.
4. **Targeted AI Review Pass:**
   - Supply the reviewer model with the `git diff` against the base state (plus relevant interface/type definitions), rather than dumping raw file dumps.
   - Use the structured review schema and severity gates defined below.
5. **Patch & Re-verify:**
   - Apply fixes for all flagged `P0 (Blocker)` and `P1 (Warning)` defects. Ignore `P2 (Nit/Style)`.
   - Re-run the local build/test suite to verify the fixes didn't introduce compile or logic regressions.
6. **Termination / Loop Conditions:**
   - Conclude successfully when the review pass returns `0` findings classified as `P0` or `P1`.
   - **Circuit Breaker:** Enforce a hard cap of `MAX_REVIEW_ITERATIONS = 3`. If unresolved `P0`/`P1` items remain after 3 passes, halt the loop, preserve current state, and dump the remaining diff + outstanding issues for human intervention.

---

### 2. Reviewer Prompt Template
When initiating the code review query, inject the following system/task constraints:

```text
You are an adversarial code review engine. Your sole task is detecting real runtime failures, logic errors, regressions, edge cases, and security vulnerabilities introduced in the provided diff.

Rules of Engagement:
1. Focus ONLY on actionable, high-confidence defects introduced by the diff.
2. DO NOT flag subjective style choices, formatting, variable naming preferences, or non-critical refactors.
3. Every reported defect must include:
   - File & line reference
   - Exact failure scenario / attack vector / edge case
   - Suggested concrete fix
4. Categorize all issues strictly by severity:
   - P0 (Blocker): Data loss, memory corruption, crash/panic, fatal concurrency/race condition, active security vulnerability, broken invariant.
   - P1 (Warning): Logic error under realistic edge cases, resource leak, unhandled error condition, breaking API contract.
   - P2 (Nit): Stylistic, micro-optimization, or informational notes (ignored by automated fixers).

Output Schema (JSON):
{
  "clean": boolean, // true ONLY if count of P0 and P1 is 0
  "findings": [
    {
      "severity": "P0" | "P1" | "P2",
      "file": "path/to/file",
      "line_range": "start-end",
      "summary": "Concise failure description",
      "failure_scenario": "How this fails in practice",
      "suggested_fix": "Concrete implementation fix"
    }
  ]
}
```
