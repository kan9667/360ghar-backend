---
name: qa
description: >
  Run QA tests for 360Ghar. Analyzes git diff to determine affected areas,
  runs configured test flows with multiple personas (guest, user, agent, admin),
  and generates diff-targeted tests. Uses curl for backend API testing.
  Use when testing PRs, releases, or smoke testing environments.
---

# QA Orchestrator

**SCOPE: This skill performs manual/functional QA only -- verifying that the application actually works by interacting with it as a real user would (API calls via curl/httpx). Do NOT run or report on CI checks, linting, ruff, mypy, pytest, unit tests, or any static analysis. Those are handled by separate workflows.**

## Step 1: Load Configuration

Read `.factory/skills/qa/config.yaml` for environment URLs, credentials, personas, and app definitions.

## Step 2: Determine Target Environment

Use the `default_target` from config unless the user specifies a different environment.
Respect any environment restrictions (e.g., no user creation in prod).

**CRITICAL: Preview deployments are DEV environments.** If a preview URL is provided, treat it as the dev environment -- use dev API keys, dev flows, dev data. Do NOT attempt prod-specific flows against preview URLs.

## Step 3: Analyze Git Diff

Run `git diff` to determine what changed. Map changed files to apps using the `path_patterns` in config.yaml.

Files that don't match ANY app's `path_patterns` (e.g., `.factory/skills/**`, `docs/**`, `.github/**`, config files) are NOT associated with any app. Do NOT run app test flows for them.

For each affected app:
- Run ONLY that app's flows from its module file
- Generate ADDITIONAL targeted tests based on the specific changes in the diff

For apps NOT affected by the diff:
- Do NOT load or run their module. Do NOT run their flows. Do NOT run their pre-flight checks. They are completely out of scope.

If NO app is affected by the diff (e.g., docs-only, CI-only, or config-only changes), report as INCONCLUSIVE: "No app code changed -- QA not applicable for this diff." Do NOT run any app flows.

## Step 4: Pre-flight Checks (app-specific only)

Run pre-flight checks ONLY for the apps that are affected by the diff.

**Backend API testing:**
1. Check that the API server is reachable at the target environment URL (poll `/health` endpoint with `curl -sf`)
2. Verify Supabase auth is working by validating a test token (if available)
3. If the API server is not reachable, report as BLOCKED with remediation steps

Do NOT run pre-flight checks for apps that are NOT affected. If a pre-flight check fails for an affected app, report it as BLOCKED with the specific error and remediation steps -- but still proceed with other affected apps.

## Step 5: Execute Diff-Relevant Flows Only

For each app that IS affected by the diff, read its sub-skill from `.factory/skills/qa-backend/SKILL.md`.

The sub-skill contains a MENU of available test flows. You must:

1. Read the diff carefully and identify which flows are relevant to the change
2. Run those flows PLUS any adjacent flows that verify the change integrates correctly (e.g., if a new endpoint is added, test that it appears in OpenAPI docs, that auth boundaries are enforced, that error handling works)
3. Do NOT run completely unrelated flows (e.g., if the diff only adds a flatmates endpoint, do NOT test bookings or tours)
4. If no existing flow covers the change, write a NEW ad-hoc test that directly verifies the changed behavior
5. Do NOT run unit tests, lint, typecheck, or any automated test suite. This is manual/functional QA -- interact with the API as a real user would.

## Step 6: Evidence Capture

After each significant test step, capture evidence. Use **text-based API response captures** as primary evidence:

For backend API testing:
- Use `curl -s` or `httpx` to make API calls and capture full response bodies
- Include HTTP status code, response headers (notably `content-type`), and response body
- Embed the response directly in the report as a fenced code block with a descriptive label
- Each evidence capture MUST show something DIFFERENT. Verify the response changed before capturing again.
- Truncate large responses to the relevant portion (e.g., first 5 items in a list, key fields only)

Evidence quality rules:
- Focus on the RELEVANT content. Trim responses to the meaningful part.
- Label each capture clearly: what it shows and why it matters for the test.
- NEVER include full auth tokens in evidence. Mask them with `[REDACTED]`.

## Step 7: Test Quality Gate

TEST QUALITY REQUIREMENTS:

1. CHANGE-SPECIFIC FIRST. Prioritize tests that directly verify the behavioral change in the diff. At least half your tests should be testing the new/changed feature itself.
2. INTEGRATION TESTS ARE VALID. Tests that verify the change integrates correctly with existing features are good (e.g., new endpoint works with auth, new model field appears in responses). These are NOT smoke tests -- they verify the change didn't break integration points.
3. NO UNRELATED FLOWS. Do NOT test features completely unrelated to the diff (e.g., don't test bookings when only flatmates changed, don't test tours when only properties changed).
4. NO AUTOMATED TEST SUITES. Do NOT run pytest, ruff, mypy, or any CI-style checks. This is manual/functional QA only.
5. NEGATIVE TESTS. Include at least 1 test verifying error handling or boundary conditions related to the change.
6. INTERACTIVE TESTING. Test by actually making API calls as a real user would.
7. INCONCLUSIVE IF UNSURE. If you cannot articulate what the PR changes, mark as INCONCLUSIVE rather than PASS.

## Step 8: Handle Failures

**Never silently skip a flow.** If a flow cannot complete, report it as BLOCKED with what was tried and how the user can fix it. Then continue to the next flow -- never abort the entire run for a single failure.

## Step 9: Generate Report

Generate the report at `./qa-results/report.md` using `.factory/skills/qa/REPORT-TEMPLATE.md`.

The report MUST follow the template. Key rules:
- Start with `## QA Report` heading followed by the test results table
- Result column MUST use emojis: :white_check_mark: PASS, :x: FAIL, :no_entry: BLOCKED, :warning: FLAKY, :grey_question: INCONCLUSIVE
- Keep it CONCISE. The table + a short "Action Required" section (if any) + collapsed evidence = the entire report.
- Do NOT include: "Behavioral Change Summary", "Blocked Flows" prose, "Info" metadata table, or verbose explanations of what the diff does. The reviewer already knows that.
- Do NOT report setup/prerequisite steps (health checks, auth token retrieval) as test rows. Those are means to an end, not test cases. Only report rows that verify actual user-facing behavior or the specific behavioral change from the diff.
- Put ALL evidence in a single collapsed `<details>` block
- For API evidence: embed response bodies as labeled fenced code blocks (e.g., `### GET /api/v1/properties response` followed by a code block with the JSON response).

## Step 10: Suggest Skill Updates (Failure Learning)

After generating the report, check if any BLOCKED or FAIL results revealed a **testing environment insight** that would help future QA runs succeed. This is about learning how the testing environment works, NOT about fixing bad selectors or skill typos.

**Good suggestions** (environment/workflow knowledge):
- "Supabase token expires after 30 minutes -- refresh before long test runs"
- "The /api/v1/properties endpoint requires `page` param or returns empty results"
- "Geospatial queries require PostGIS extension -- ensure database has it"

**Bad suggestions** (skill bugs, not environment insights -- do NOT suggest these):
- "Wrong endpoint path" -- that's a skill bug, fix it directly
- "Response format changed" -- that's expected from the PR diff

Format as a table with severity, collapsible fix prompts, and a count in the heading:

## Suggested Skill Updates (N issues found)

| # | Severity | File | Issue | Fix Prompt |
| --- | --- | --- | --- | --- |
| 1 | <emoji> <level> | `<file>` | <short description> | <details><summary>Copy</summary><br>`<full droid prompt to fix the issue>`</details> |

**Severity levels:**
- `🔴 Breaking` -- Causes test failures every run
- `🟡 Degraded` -- Causes intermittent failures
- `🔵 Info` -- New knowledge that improves future runs

Read the `failure_learning` field from config.yaml. Currently set to `suggest_in_report` -- include the table in the report only. Do NOT write `skill-updates.json`.

Do NOT suggest updates for failures already covered in Known Failure Modes, bad paths, or expected behavior changes from the PR. If no genuinely new environment insights were discovered, omit this section entirely.

## Auth Token Management

For authenticated API calls, obtain tokens as follows:

1. **Existing test accounts**: Read the token from the environment variable specified in the persona's `secret_name` (e.g., `QA_USER_TOKEN`, `QA_AGENT_TOKEN`, `QA_ADMIN_TOKEN`)
2. **New user signup**: Use Supabase Auth API to create a new user and obtain a token
3. **Token in requests**: Pass as `Authorization: Bearer <token>` header

**IMPORTANT**: Never expose full auth tokens in evidence or reports. Mask them with `[REDACTED]`.
