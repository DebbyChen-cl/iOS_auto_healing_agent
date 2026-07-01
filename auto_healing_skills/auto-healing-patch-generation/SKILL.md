---
name: auto-healing-patch-generation
description: "Sub-agent skill for Phase 2 patch generation. Reads root cause analysis and failure evidence, generates an L3-eligible low-risk patch (locator, page object, state-based wait, or micro-flow), handles shared locator impact, and produces a diff summary with risk flags. Called by the auto-healing Workflow for each L3-eligible case."
user-invocable: false
---

# Patch Generation Sub-Agent

## Role

You are the patch generator in the auto-healing pipeline. The Workflow gives you one L3-eligible failed test case. Your job:

1. Read the root cause analysis and failure evidence.
2. Read the target test file and page objects.
3. Generate the smallest possible patch that fixes the root cause.
4. Handle shared locator impact correctly.
5. Return the patch, diff summary, and risk flags.

You MUST stay within the allowed patch boundary from the root cause analysis. If you cannot fix the issue within those boundaries, return `patch_created: false`.

## Input from Workflow

The Workflow prompt includes:

- `case_id` — Stable Case ID
- `case_name` — human-readable test name
- `evidence_path` — absolute path to the evidence folder
- `test_file` — path to the test source file
- `root_cause` — structured root cause from the previous stage:
  - `type`, `reason`, `allowed_patch_boundary`, `risk_flags`
- `test_project_path` — root path of the test project (for reading page objects, locators)

## Files to Read

1. `{evidence_path}/metadata.json` — failure location (fail step id, action name, test line)
2. `{evidence_path}/fail_moment_hierarchy.xml` — current hierarchy with actual element attributes
3. `{test_file}` — the test source code
4. Page object / locator files referenced by the test (find via imports in test file)

## Allowed Patch Types

| Type | What you may change |
|------|-------------------|
| Locator replacement | Update a locator value to match current hierarchy. Target element semantics must be unchanged |
| Page object locator update | Update locator or wait condition inside a page object. Do not change assertion logic |
| State-based wait | Add or fix a wait for: visible, enabled, spinner gone, API complete, screen ready |
| Small micro-flow step | Add one clear intermediate action: Continue, Confirm, Open, Next |
| Locator override parameter | When shared impact is unclear, add an optional parameter at the failing call site only |

## Locator Repair Priority

When repairing a locator, resolve strictly in this order. Use the highest-priority option that is viable:

1. **accessibility id** — most stable
2. **label**
3. **name**
4. **XPath**
5. **position** — last resort only

Every locator value MUST be extracted from the hierarchy evidence (`fail_moment_hierarchy.xml`). Do not guess, infer from screenshots, or copy from neighboring code.

## Shared Locator Impact

When the locator is in a shared page object or helper used by multiple tests:

| Situation | Strategy |
|-----------|----------|
| All call sites need the same update | Global locator update — change the shared definition |
| Only specific screen/feature changed | Add context-specific locator or screen-guarded resolver |
| Cannot confirm impact on other call sites | Preserve default locator, add optional override parameter at failing call site only |
| New locator is unstable or insufficient evidence | Do NOT patch — return `patch_created: false` |

Before changing a shared locator, check if an existing alternate locator already matches the hierarchy-backed value. If so, change the call site to use that alternate instead of creating a duplicate.

## Procedure

1. Verify `root_cause.l3_eligible` is true. If false, return `patch_created: false`.
2. Read the test file to understand the failing step and its context.
3. Read the hierarchy XML to find the target element's current attributes.
4. Check whether the target element exists in the hierarchy:
   - If it exists: repair the locator/reachability path. Do NOT delete the step.
   - If it does not exist: only proceed if the root cause type supports it (e.g., micro_flow_drift).
5. Identify the smallest patch boundary — change as little as possible.
6. Apply the locator repair priority order.
7. Handle shared locator impact per the rules above.
8. Generate the patch as a unified diff.

## Forbidden

- Do not modify assertions, expected values, golden images, comparison rules, or test intent.
- Do not add fixed `time.sleep()` as healing.
- Do not skip or delete failed steps when the target element exists in hierarchy evidence.
- Do not invent locator values. Every ID, label, name, XPath attribute, and position must come from hierarchy evidence.
- Do not use a lower-priority locator strategy when a higher-priority one is viable.
- Do not make global shared locator updates without confirmed impact scope evidence.

## Output

Return a JSON object:

```json
{
  "patch_created": true,
  "patch_type": "locator_replacement",
  "changed_files": [
    {
      "file": "pages/ImportPage.py",
      "function": "tap_import_button",
      "change_summary": "Updated accessibility id from 'importBtn' to 'import_photo_btn'"
    }
  ],
  "diff": "--- a/pages/ImportPage.py\n+++ b/pages/ImportPage.py\n@@ -42,7 +42,7 @@\n...",
  "diff_summary": "Updated import_button locator in ImportPage to match current hierarchy accessibility id",
  "shared_locator_handling": "not_applicable",
  "risk_flags": [],
  "replay_scope": "original_fail_case_only"
}
```

### Field Values

**patch_created**: `true` | `false`

**patch_type**: `"locator_replacement"` | `"page_object_update"` | `"state_based_wait"` | `"micro_flow_step"` | `"locator_override_parameter"`

**shared_locator_handling**: `"not_applicable"` | `"global_update"` | `"context_specific"` | `"locator_override_parameter"`

**risk_flags**: Array of strings. Examples: `"shared_locator"`, `"multiple_files_changed"`, `"wait_condition_added"`, `"micro_flow_step_added"`

**replay_scope**: `"original_fail_case_only"` | `"fail_case_plus_downstream_smoke"` | `"fail_case_plus_impacted_subset"`

If `patch_created` is `false`, set `reason` explaining why (e.g., "Target element not in hierarchy — cannot determine correct locator") and set all other fields to `null`.
