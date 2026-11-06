#!/usr/bin/env python3
"""Score the tool's people.csv against an answer key (like Erin's recount).

A person is right when: they appear once, priority matches, next step matches,
and they get a draft exactly when the key says it is OK to email them.
Run: python3 score.py <out/<show>/people.csv> <answer-key.csv>

The key needs a name or source_rows column; priority, promised_next_step (or next_step),
email_ok and day30_result are checked when the key has them. People are matched by scan/card
IDs when the key has source_rows, otherwise by name.
"""
import csv
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
mine_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out" / "data" / "people.csv"
key_path = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "data" / "erin-recount-toronto.csv"


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    # tolerate "Priority", " next step ", etc.
    return [{re.sub(r"\s+", "_", (k or "").strip().lower()): (v or "").strip() for k, v in r.items()} for r in rows]


mine, key = read(mine_path), read(key_path)
cols = set(key[0]) if key else set()
STEP = "promised_next_step" if "promised_next_step" in cols else ("next_step" if "next_step" in cols else None)


def plain(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"^\s*dr\.?\s+", "", s).replace("'", "")
    return re.sub(r"[^a-z ]", " ", s.split(",")[0]).split()


try:  # nicknames (Peggy = Margaret), from the tool itself
    sys.path.insert(0, str(HERE))
    from sandbar import first_variants
except Exception:  # noqa: BLE001
    def first_variants(f):
        return {f}


def srcs(row):
    return {s.strip() for s in row.get("source_rows", "").split(";") if s.strip()}


def same_person(k, m):
    if "source_rows" in cols and srcs(k):
        solid = {s for s in srcs(k) if s[0] in "SC"} or srcs(k)  # voice notes can be shared by two people
        return bool(srcs(m) & solid)
    a, b = plain(k.get("name")), plain(m.get("name"))
    if not a or not b:
        return False
    if a == b:
        return True
    if a[-1] != b[-1]:
        return False
    fa, fb = a[:-1], b[:-1]  # every first-name word, including "(Peggy)"
    if not fa or not fb:
        return True
    if any(len(x) == 1 or len(y) == 1 for x in fa for y in fb):  # "C. Inglis" vs "Colin Inglis"
        return any(x[0] == y[0] for x in fa for y in fb)
    return any(first_variants(x) & first_variants(y) for x in fa for y in fb)


def should_draft(row):
    ok = row.get("email_ok", "").lower()
    return ok == "yes" or ok.startswith("personal")


right, problems, day30_right, held = 0, [], 0, 0
used = set()
for n, k in enumerate(key, 1):
    hits = [m for m in mine if same_person(k, m)]
    used |= {m["person_id"] for m in hits}
    issues = []
    if len(hits) != 1:
        issues.append(f"appears {len(hits)} times")
    else:
        m = hits[0]
        if "priority" in cols and m["priority"].lower() != k["priority"].lower():
            issues.append(f"priority {m['priority']} (key {k['priority']})")
        if STEP and m["promised_next_step"].lower() != k[STEP].lower():
            issues.append(f"next step {m['promised_next_step']} (key {k[STEP]})")
        if "email_ok" in cols and (m["draft"] in ("yes", "held")) != should_draft(k):  # held = draft written, held back
            if m["draft"] == "no" and m.get("already_handled"):
                issues.append(f"held back, already handled: {m['already_handled']}")
            else:
                issues.append(f"draft={m['draft']} (key email_ok {k['email_ok']})")
        if "source_rows" in cols and srcs(k) and srcs(m) != srcs(k):
            issues.append(f"sources differ: extra {sorted(srcs(m) - srcs(k))} missing {sorted(srcs(k) - srcs(m))}")
        if "day30_result" in cols:
            if m["day30_result"] == k["day30_result"]:
                day30_right += 1
            else:
                issues.append(f"day30 {m['day30_result']} (key {k['day30_result']})")
    core = [i for i in issues if not i.startswith(("sources", "day30", "held back"))]
    if any(i.startswith("held back") for i in issues):
        held += 1
    if not core:
        right += 1
    if issues:
        problems.append((k.get("person_id") or f"#{n}", k.get("name", ""), issues))

extra = [m for m in mine if m["person_id"] not in used]
print(f"Right (once + priority + next step + draft decision): {right}/{len(key)}")
print(f"  (counts held-back drafts for already-handled people as right; held back: {held})")
print(f"Day-30 pile right: {day30_right}/{len(key)}" if "day30_result" in cols else "Day-30 pile right: n/a (key has no day30_result)")
print(f"Extra people the key does not have (drive-bys let in): {len(extra)}")
bad_drafts = [m for m in extra if m["draft"] in ("yes", "held")]
print(f"  of those, drafted: {len(bad_drafts)}")
checked = [c for c in ("priority", STEP, "email_ok", "day30_result", "source_rows") if c and c in cols]
print(f"  (key columns checked: {', '.join(checked)})")
for pid, name, issues in problems:
    print(f"  {pid} {name}: " + "; ".join(issues))
for m in extra:
    print(f"  EXTRA {m['name']} ({m['clinic']}) sources {m['source_rows']} draft={m['draft']}")
