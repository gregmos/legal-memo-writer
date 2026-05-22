# Smoke tests

Unit tests for the Python scripts that the pipeline shells into. Run from the plugin root:

```bash
python3 -m unittest discover scripts/tests -v
```

Or run an individual module:

```bash
python3 -m unittest scripts.tests.test_validate_state -v
python3 -m unittest scripts.tests.test_validate_review_json -v
python3 -m unittest scripts.tests.test_md_to_docx_banner -v
```

## What's covered

| File | Behaviour exercised |
|------|---------------------|
| `test_validate_state.py` | Phase-aware required fields, rejection of top-level `max_iterations`, `counterargument` (singular) rejection in reviewer_list, `research_summary_only` heartbeat_choice acceptance, export phase requires `final_status`. |
| `test_validate_review_json.py` | Brief mode (3 reviewers) validates with 3 JSONs, Full mode requires 5, `--reviewers` flag overrides state, unknown reviewer kind rejected. |
| `test_md_to_docx_banner.py` | `fallback_banners[]` from state.json is rendered as bullets in the warning banner of the docx. |

## What's NOT covered (intentionally)

- End-to-end memo runs (require Anthropic API, MCP, real Cowork session).
- Agent dispatch flow (the orchestrator is a markdown skill, not a Python module).
- docx visual rendering (we check that the banner is present in the document XML, not the visual layout).

For the runtime contracts that *are* code, this directory is the single place to verify Brief mode / research_summary_only / fallback banners / state schema. Add a test here whenever you change a `scripts/*.py` invariant.
