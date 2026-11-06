# Sandbar show follow-up

Volta Anchor Sprint 3. Turns one trade show's files (badge scans, business cards, Owen's voice notes and plane list,
and the 30-day activity export) into one row per real conversation, with a priority, a next step and a
ready-to-send draft in Owen's or Nadia's voice, plus Nadia's four day-30 piles.

## Run it

    python3 -m venv .venv && .venv/bin/pip install anthropic
    echo "ANTHROPIC_API_KEY=..." > .env          # optional: without it the tool uses the rules only
    .venv/bin/python sandbar.py path/to/show-folder      # or double-click "Run Sandbar.command" on a Mac

Results go to out/<show folder>/: people.csv, drafts-owen.md, drafts-nadia.md, check-first.md, decisions.md,
piles.md, reply-forwarding.md.

## Check accuracy

    .venv/bin/python score.py out/<show>/people.csv <answer-key.csv>    # e.g. data/erin-recount-toronto.csv
    .venv/bin/python stress_test.py          # Toronto changed six ways (free, rules only)
    .venv/bin/python stress_rewrite.py       # new names + reworded notes, with Claude

Toronto: 80/80 right, day-30 piles 80/80, 0 drive-bys drafted. Same on every stress test.

## Files

- sandbar.py: the tool. sandbar_ai.py: the Claude part (reads notes, writes drafts, checks every draft against the notes).
- data/: the Toronto show files and Erin's recount (the answer key). All data is made up.
- discovery/, transcripts/, followups.md: the brief, interviews and what each person said.
- plan.md, edge-cases.md, erin-written-version.md: the plan, the 42 edge cases, and Erin's one-page guide.
