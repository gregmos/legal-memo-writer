#!/usr/bin/env bash
# Resolve the working directory for a fresh memo task.
#
# Resolution order (first writable wins):
#   1. $CLAUDE_PLUGIN_OPTION_OUTPUT_FOLDER (plugin option)
#   2. $MEMOFORGE_OUTPUT_FOLDER (environment variable)
#   3. $HOME/Documents/memoforge (default for desktop installs)
#   4. outputs/memoforge-work (sandbox fallback, relative to CWD)
#
# Computes:
#   - TASK_ID = memo-<UTC-timestamp>-<slug>
#   - WORK_DIR = <resolved output folder>/<TASK_ID>
#   - REL_WORK_DIR = WORK_DIR relative to CWD (falls back through realpath -> python3 -> python -> WORK_DIR)
#
# Creates the work dir tree (intake, checkpoints, research, drafts, etc.).
#
# Output is key=value lines on stdout — the caller parses them:
#   task_id=<id>
#   work_dir=<absolute path>
#   rel_work_dir=<CWD-relative path>
#   output_folder=<parent>
#
# Usage:
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_work_dir.sh" <slug>
#
# <slug> is a 2-4 word kebab-case descriptor derived from the user query
# (e.g. "biometric-data-minors"). The orchestrator supplies it.

set -e

SLUG="${1:-task}"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
TASK_ID="memo-${TIMESTAMP}-${SLUG}"

OUTPUT_FOLDER=""
for CANDIDATE in \
  "$CLAUDE_PLUGIN_OPTION_OUTPUT_FOLDER" \
  "$MEMOFORGE_OUTPUT_FOLDER" \
  "$HOME/Documents/memoforge" \
  "outputs/memoforge-work"; do
  [ -z "$CANDIDATE" ] && continue
  if mkdir -p "$CANDIDATE" 2>/dev/null && [ -w "$CANDIDATE" ]; then
    OUTPUT_FOLDER="$CANDIDATE"
    break
  fi
done

if [ -z "$OUTPUT_FOLDER" ]; then
  echo "error: no writable output folder candidate" >&2
  exit 1
fi

WORK_DIR="$OUTPUT_FOLDER/$TASK_ID"
mkdir -p "$WORK_DIR"/{intake,checkpoints,research,research/raw,drafts,reviews,widgets,cache}

# Compute REL_WORK_DIR — path relative to current CWD.
# Use this for the plain-text path the user sees (per D2 file-reference rule —
# Cowork only renders relative paths as clickable; absolute platform paths and
# ${CLAUDE_PLUGIN_DATA}/... placeholders do NOT render as clickable).
# Fallback chain: GNU realpath -> python3 -> python -> echo WORK_DIR unchanged.
REL_WORK_DIR=$(realpath --relative-to="$(pwd)" "$WORK_DIR" 2>/dev/null \
  || python3 -c "import os.path,sys; print(os.path.relpath(sys.argv[1]))" "$WORK_DIR" 2>/dev/null \
  || python  -c "import os.path,sys; print(os.path.relpath(sys.argv[1]))" "$WORK_DIR" 2>/dev/null \
  || echo "$WORK_DIR")

echo "task_id=$TASK_ID"
echo "work_dir=$WORK_DIR"
echo "rel_work_dir=$REL_WORK_DIR"
echo "output_folder=$OUTPUT_FOLDER"
