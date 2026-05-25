---
name: style
description: Manage custom style and formatting profiles for legal memos. Sub-actions new / list / use / show / delete. Use only when explicitly invoked via /legal-memo-writer:style.
argument-hint: "[new <name> [--examples <paths>] [--rules <text-or-path>] [--mode brief|full] | list | use <name> | show <name> | delete <name>]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Task, AskUserQuestion
---

# legal-memo-writer / style skill

You manage the user's custom style profiles. A profile is a directory under `~/.claude/plugin-data/legal-memo-writer/profiles/<name>/` containing `prose-style.md` (always), `template.md` (sometimes), `meta.json`, and supporting files. The `memo` skill reads these at Phase 1.5 when the user picks a profile for a new memo.

**Authority hierarchy** (highest wins, same shape as `memo` skill):

1. Cowork / Anthropic platform policy.
2. This skill and its arguments.
3. `scripts/resolve_style_profile.py` — the canonical write path for profiles. Never bypass it.
4. User input from `AskUserQuestion` or text replies.

**Key invariant.** All user-facing strings (menu items, checkpoint questions, warnings, summaries) are **English**. The contents of generated `prose-style.md` and `template.md` are in the input language (English, Russian, etc.) — that is the extractor's concern, not yours.

## Parse `$ARGUMENTS`

Split `$ARGUMENTS` by whitespace. The first token is the **action**:

- `new <name> [flags…]` — create a new profile. See §`new` below.
- `list` — list existing profiles. See §`list`.
- `use <name>` or `use --clear` — set or clear the default profile. See §`use`.
- `show <name>` — print profile contents. See §`show`.
- `delete <name>` — delete a profile. See §`delete`.
- (no action / empty `$ARGUMENTS` / `menu` / `help`) — go to §`menu` (interactive).

For any other first token, print: `Unknown action. Use new | list | use | show | delete, or run /legal-memo-writer:style with no arguments for the interactive menu.` End turn.

## `menu` — interactive entry point

When `$ARGUMENTS` is empty, ask the user what they want to do. Use `AskUserQuestion` with these options (English; copy verbatim):

- **Question:** "What would you like to do?"
- **Header:** "Style" (≤12 chars).
- **multiSelect:** false.
- **Options:**
  - label: "Create a new profile", description: "From example memos, written rules, or both"
  - label: "List existing profiles", description: "See your saved profiles, current default, mode bindings"
  - label: "Set default profile", description: "Choose which profile /memo uses by default"
  - label: "Show profile contents", description: "Print prose-style.md and template.md of a profile"
  - label: "Delete a profile", description: "Remove a profile permanently"

If the host has no `AskUserQuestion`, fall back to a plain-text prompt listing the same options and end the turn. The user then re-runs `/legal-memo-writer:style <action> ...` with the chosen action.

Branch on the answer and continue inline to the matching section below (§`new`, §`list`, etc.).

## `new` — create a new profile

### Step 1 — Collect profile name

If `<name>` is missing from `$ARGUMENTS`, ask via `AskUserQuestion`:

- **Question:** "Profile name (lowercase, dashes, no spaces — for example, `my-firm-brief`)"
- **Header:** "Name"
- **multiSelect:** false.
- Single option with description `"Type the profile name as 'Other'"`. (AskUserQuestion always offers an Other / free-text input.)

If `AskUserQuestion` is unavailable, print the prompt as text and end the turn.

Validate the name via Bash:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_style_profile.py" validate-name "<name>"
```

If exit code is non-zero, print the stderr message and re-ask the name (or end turn if no `AskUserQuestion`).

Also check that the name does NOT already exist. Read the list:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_style_profile.py" list
```

If the JSON output contains a record with this name, ask:

- "Profile `<name>` already exists. Overwrite or cancel?"
  - "Overwrite" → delete the existing profile via `delete <name>` and proceed.
  - "Cancel" → end turn.

### Step 2 — Determine input type

Parse the remaining `$ARGUMENTS` flags:

- `--examples <path-or-paths>` — one or more whitespace-separated paths. Can also be a directory; expand to its contents.
- `--rules <text-or-path>` — either inline text (typically quoted) or a path to a `.md`/`.txt` file. Distinguish: if the value is a path that exists on disk, treat as path; else treat as inline text.
- `--mode brief|full` — explicit mode pick (skip the mode checkpoint at Step 4).

`input_type` is computed from what was provided:

- Both flags set → `both`
- Only `--examples` → `examples`
- Only `--rules` → `rules`
- Neither flag set → ask via `AskUserQuestion`:

  - **Question:** "How would you like to define this profile?"
  - **Header:** "Input"
  - **multiSelect:** false.
  - Options:
    - label: "Examples only", description: "Provide paths to one or more example memos"
    - label: "Rules only", description: "Type or paste style rules as plain text"
    - label: "Both examples and rules", description: "Examples set the baseline; rules override on conflict"

  After the answer, ask for the missing input(s):
  - For examples: "Paths to example memos (space-separated, or a directory):" via AskUserQuestion (free-text via Other).
  - For rules: "Provide rules as text (paste below) or path to a .md/.txt file:" via AskUserQuestion (free-text via Other).

  Without `AskUserQuestion`: print the prompts as text, end the turn, and have the user re-invoke `/legal-memo-writer:style new <name> --examples ... --rules ...` with the values.

### Step 3 — Validate paths (if examples were provided)

For each example path: check it exists via Bash (`test -e`). If a path does not exist, print:

```
error: example path not found: <path>
```

and end the turn (no profile is created).

If `--examples` was a directory, expand to all `.md`, `.txt`, `.pdf`, `.docx` files under it (use Glob).

If `--rules` was a path, validate similarly.

### Step 4 — Mode pick (Brief vs Full)

If `--mode` was set on the command line, use it. Otherwise ask:

- **Question:** "Which mode is this profile for — Brief (1-3 pages) or Full (5-15 pages)?"
- **Header:** "Mode"
- **multiSelect:** false.
- Options:
  - label: "Brief (1-3 pages)", description: "For executive-brief memos — compressed, single-issue or 2-3 risks"
  - label: "Full (5-15 pages)", description: "For classical-memo deep analysis with full IRAC and Executive Summary"

Without `AskUserQuestion`: print the prompt as text and end the turn.

Map the answer: "Brief…" → `brief`, "Full…" → `full`. Store as `mode_binding`.

### Step 5 — Dispatch `style-extractor`

Print a one-line heads-up to chat: `Extracting style profile '<name>' — this takes ~1 minute…`

Dispatch the extractor via `Agent`:

```
Agent(
  subagent_type="style-extractor",
  prompt="""
  Extract a style profile.
  - profile_name: <name>
  - examples: <space-separated list of absolute paths, or empty>
  - rules: <inline text OR path to file, or empty>
  - input_type: <examples|rules|both>
  - mode_binding: <brief|full>
  - work_dir: <a writable temp directory; create $TMPDIR/style-extract-<name> if needed>

  Follow your agent spec in agents/style-extractor.md exactly.
  Init the profile via scripts/resolve_style_profile.py first; write prose-style.md (always);
  write template.md only if structural input is present; write rules.md if rules were provided;
  copy examples into sources/; atomically write the final meta.json at the end.
  Return a ≤200-word English summary with any warnings.
  """
)
```

Wait for the extractor to return. Print its summary to chat verbatim (it is already English and concise).

### Step 6 — Validate the written profile

After the extractor returns, validate the result:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_style_profile.py" validate-profile "<name>"
```

If exit code is non-zero, print: `Profile validation failed — the profile directory is malformed and was not registered. Please retry or report this issue.` Then run `delete <name>` to clean up. End turn.

### Step 7 — Offer to set as default

Ask:

- **Question:** "Make `<name>` the default profile for new memos?"
- **Header:** "Default"
- **multiSelect:** false.
- Options:
  - label: "Yes — make it default", description: "Next /legal-memo-writer:memo will preselect this profile"
  - label: "No — keep current default", description: "You can change later with /legal-memo-writer:style use <name>"

If "Yes": run `set-default <name>` via Bash. Print confirmation.

If "No": print a one-line note: `Profile saved. Use /legal-memo-writer:style use <name> to select it later.`

End turn.

## `list` — print profiles table

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_style_profile.py" list
```

Parse the JSON and render a plain-text table in chat:

```
Profile          | Created    | Input    | Mode   | Template | Default | Lang
-----------------|------------|----------|--------|----------|---------|-----
my-firm-brief    | 2026-05-25 | examples | brief  | yes      | ✓       | en
acme-rules-full  | 2026-05-20 | rules    | full   | no       |         | en
```

If the list is empty, print: `No profiles yet. Create one with /legal-memo-writer:style new <name>.`

If any profile has `valid=false`, print a warning line below the table: `⚠️ <name>: <first error message>`. Suggest re-running `/legal-memo-writer:style delete <name>` and creating fresh.

End turn.

## `use` — set or clear default

If `$ARGUMENTS` is `use --clear`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_style_profile.py" clear-default
```

Print: `Default profile cleared. /legal-memo-writer:memo will offer all profiles next time.` End turn.

Otherwise, `<name>` is the second token. Validate and set:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_style_profile.py" set-default "<name>"
```

If exit code is non-zero, print the stderr message (`profile not found: <name>` is the common case — suggest `/legal-memo-writer:style list`).

On success, print: `Default profile set to '<name>'. /legal-memo-writer:memo will preselect it for new memos.` End turn.

## `show` — print profile contents

`<name>` is the second token. Validate it exists:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_style_profile.py" validate-profile "<name>"
```

If exit code is non-zero, print the stderr message and end turn.

Print `meta.json` content:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_style_profile.py" read-meta "<name>"
```

Then print the first 30 lines of `prose-style.md` and (if present) the first 30 lines of `template.md`, each with a header:

```
=== prose-style.md (first 30 lines) ===
<content>

=== template.md (first 30 lines) ===
<content>

(Open the full files at <profile_dir>.)
```

Use `Read` with `offset=0, limit=30` for the lines; `Bash` for resolving the profile dir path:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_style_profile.py" resolve-paths "<name>"
```

End turn.

## `delete` — remove a profile

`<name>` is the second token. Check if it is currently the default:

```bash
DEFAULT=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_style_profile.py" get-default)
```

If `DEFAULT == <name>`, ask first:

- **Question:** "`<name>` is the current default. Delete and clear default?"
- **Header:** "Confirm"
- Options:
  - label: "Yes — delete it", description: "Profile is removed; default is cleared; /memo will offer all remaining profiles next time"
  - label: "No — keep it", description: "Cancel deletion"

If "No": end turn.

Otherwise (or if not the default), run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_style_profile.py" delete "<name>"
```

The script atomically removes the directory AND clears the default file if `<name>` was the default.

Print confirmation: `Profile '<name>' deleted.` End turn.

## Hard constraints

- Never write to `~/.claude/plugin-data/legal-memo-writer/` directly — always go through `scripts/resolve_style_profile.py`. The script is the canonical write path: it validates names, writes atomically, and keeps the default-file consistent on delete.
- Never modify `state.json` of an in-flight memo task. This skill manages user-level style profiles only — it has no relationship to any specific memo task in progress.
- Never call `Agent` for anything other than `style-extractor` from this skill. Subagents for the memo pipeline are dispatched by `skills/memo/SKILL.md`, not from here.
- All user-facing strings (chat output, AskUserQuestion text) are English. Profile body content language is decided by the extractor based on the inputs.
