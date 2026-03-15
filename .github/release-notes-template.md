# Release Notes Template
#
# Use this structure when editing GitHub release notes after `gh release create`.
# The workflow generates notes automatically; edit the body to match this format.
#
# ── Template ──────────────────────────────────────────
#
# ## What's Changed
#
# ### Fixed
# - Description of bug fix (#PR)
#
# ### Added
# - Description of new feature (#PR)
#
# ### Changed
# - Description of behavior change (#PR)
#
# ### Removed
# - Description of removal (#PR)
#
# ## Upgrade Notes
# - Any migration steps, option changes, or entity ID impacts.
# - If tariff/economics changed: recommend running `rebuild_economics`.
#
# ── Section rules ─────────────────────────────────────
# - Omit empty sections (don't include "### Removed" if nothing was removed)
# - Order: Fixed → Added → Changed → Removed
# - Each bullet: imperative mood, concise, link PR number
# - "Upgrade Notes" only when user action is needed
# - Keep "What's Changed" as the top heading for consistency with GitHub auto-notes
#
# ── Category mapping from commit types ────────────────
#  feat     → Added
#  fix      → Fixed
#  refactor → Changed
#  perf     → Changed
#  docs     → Changed (or omit if trivial)
#  chore    → omit unless user-visible
#  test     → omit unless user-visible
#  style    → omit
