#!/usr/bin/env python3
"""Stress test: change the Toronto files in ways a new show could look different, and check the tool
still gets the same 80 people right (Erin's recount is still the answer key, because the people are the same).

Variants:
  shuffle      every file's rows and columns in a different order
  new_show     a different show, city and dates (moved ~6 months later)
  messy        emails in capitals with spaces, phones written other ways, names in capitals, new file names
  noise        20 extra drive-bys (blank scans, students, vendors, a competitor, draw entries) + duplicate scans
  no_activity  right after the show: no activity file yet (no day-30 piles, nobody "already handled")
  all          all of the above at once (except no_activity)

Run:  .venv/bin/python stress_test.py            rules only (free)
      .venv/bin/python stress_test.py --claude   also runs "all" with Claude (about $2-3)
"""
import csv
import json
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "stress"
KEY = DATA / "erin-recount-toronto.csv"
SHIFT = timedelta(days=175)
rnd = random.Random(7)


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def write_csv(path, fields, rows, bom=False):
    with open(path, "w", newline="", encoding="utf-8-sig" if bom else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def load():
    sf, scans = read_csv(DATA / "badge-scans.csv")
    af, acts = read_csv(DATA / "after-show-activity.csv")
    notes = json.loads((DATA / "booth-notes.json").read_text(encoding="utf-8"))
    return {"sf": sf, "scans": scans, "af": af, "acts": acts, "notes": notes,
            "names": {"scans": "badge-scans.csv", "acts": "after-show-activity.csv", "notes": "booth-notes.json"}}


# ---------------------------------------------------------------- changes

def shuffle(d):
    rnd.shuffle(d["scans"])
    rnd.shuffle(d["acts"])
    for k in ("cards", "voice_notes"):
        rnd.shuffle(d["notes"][k])
    rnd.shuffle(d["notes"]["owen_list"]["lines"])
    rnd.shuffle(d["sf"])
    rnd.shuffle(d["af"])


def shift_date_text(text):
    def move(m):
        fmt = "%Y-%m-%d %H:%M" if m.group(2) else "%Y-%m-%d"
        return (datetime.strptime(m.group(0), fmt) + SHIFT).strftime(fmt)
    return re.sub(r"\b(20\d\d-\d\d-\d\d)( \d\d:\d\d)?\b", move, text or "")


def new_show(d):
    for r in d["scans"]:
        r["scanned_at"] = shift_date_text(r["scanned_at"])
    for r in d["acts"]:
        r["date_time"] = shift_date_text(r["date_time"])
        r["detail"] = shift_date_text(r["detail"]).replace("Allied Practice Expo", "Coastal Clinic Summit")
    n = d["notes"]
    n["about"] = ("Everything from the Coastal Clinic Summit booth (Halifax, 2027-03-08 and 2027-03-09) other than "
                  "the badge scans. Cards were typed up by Erin from the originals; voice notes are the phone's "
                  "automatic transcripts of Owen's recordings; Owen's list is copied as he typed it.")
    for c in n["cards"]:
        c["typed_on"] = shift_date_text(c["typed_on"])
    for v in n["voice_notes"]:
        v["recorded_at"] = shift_date_text(v["recorded_at"])


def messy_phone(p):
    digits = re.sub(r"\D", "", p or "")
    if len(digits) < 10:
        return p
    a, b, c = digits[-10:-7], digits[-7:-4], digits[-4:]
    return rnd.choice([f"+1 {a} {b} {c}", f"{a}.{b}.{c}", f"({a}){b}-{c}", f"1-{a}-{b}-{c}", f"{a}{b}{c}"])


def messy(d):
    for r in d["scans"]:
        if r["email"] and rnd.random() < 0.5:
            r["email"] = f"  {r['email'].upper()} "
        r["phone"] = messy_phone(r["phone"])
        if rnd.random() < 0.2:
            r["first_name"], r["last_name"] = r["first_name"].upper(), r["last_name"].upper()
    for c in d["notes"]["cards"]:
        if c["email"] and rnd.random() < 0.5:
            c["email"] = c["email"].upper()
        c["phone"] = messy_phone(c["phone"])
    for r in d["acts"]:
        if r["email"] and rnd.random() < 0.5:
            r["email"] = r["email"].upper()
    d["names"] = {"scans": "lead-export-final(2).csv", "acts": "crm_activity.csv", "notes": "notes from erin.json"}


def noise(d):
    base = d["scans"][0]
    when = base["scanned_at"][:10]
    extra = [
        ("Brenda", "Kowal", "Student", "Northgate College", "", ""),
        ("Ahmed", "Rahimi", "Physiotherapy student", "Western Shore University", "student - asked about jobs", "B"),
        ("Lena", "Fischer", "Territory Manager", "Kinetix Tape Co.", "wants to partner, sells tape", "A"),
        ("Marco", "Bellini", "Account Executive", "Pracshift", "competitor rep, asked lots of questions", ""),
        ("Joan", "Pyke", "Owner", "Harbourlight Physio", "draw entry", ""),
        ("Tom", "Reilly", "RMT", "Reilly Massage", "espresso draw - didnt talk", ""),
        ("Sara", "Lindh", "Event staff", "Allied Practice Expo", "", ""),
        ("Nora", "Quinlan", "Marketing Coordinator", "BrightPath Insurance", "swag", ""),
    ]
    for i in range(12):
        extra.append((f"Guest{i}", f"Visitor{i}", rnd.choice(["Physiotherapist", "RMT", "Owner"]),
                      rnd.choice(["Saltmarsh Physio", "Driftwood Massage", "Pebble Rehab"]), "", ""))
    for i, (first, last, title, org, note, rating) in enumerate(extra, 1):
        d["scans"].append({**{k: "" for k in base}, "scan_id": f"S9{i:02d}", "scanned_at": f"{when} 1{i % 8}:0{i % 6}",
                           "scanned_by": "Owen (iPad)", "first_name": first, "last_name": last, "title": title,
                           "company": org, "email": f"{first.lower()}@{re.sub(r'[^a-z]', '', org.lower())}.example.ca",
                           "phone": f"902-555-9{i:03d}", "city": "Halifax", "province": "NS",
                           "share_with_exhibitors": "Y", "rating": rating, "notes": note})
    # duplicate scans of two real people (same badge scanned again, email typed differently)
    for sid, new in (("S106", "S990"), ("S042", "S991")):
        orig = next(r for r in d["scans"] if r["scan_id"] == sid)
        d["scans"].append({**orig, "scan_id": new, "email": orig["email"].upper(), "notes": "came back"})


VARIANTS = {
    "shuffle": [shuffle],
    "new_show": [new_show],
    "messy": [messy],
    "noise": [noise],
    "no_activity": [],
    "all": [new_show, messy, noise, shuffle],
}


def make(name):
    d = load()
    for change in VARIANTS[name]:
        change(d)
    folder = OUT / name
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    write_csv(folder / d["names"]["scans"], d["sf"], d["scans"], bom=(name in ("messy", "all")))
    if name != "no_activity":
        write_csv(folder / d["names"]["acts"], d["af"], d["acts"])
    (folder / d["names"]["notes"]).write_text(json.dumps(d["notes"], indent=1, ensure_ascii=False), encoding="utf-8")
    return folder


def run(folder, claude=False):
    cmd = [sys.executable, str(HERE / "sandbar.py"), str(folder)] + ([] if claude else ["--rules"])
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    res = subprocess.run([sys.executable, str(HERE / "score.py"), str(HERE / "out" / folder.name / "people.csv"),
                          str(KEY)], check=True, capture_output=True, text=True).stdout
    return res


def headline(score):
    right = re.search(r"Right .*?: (\d+/\d+)", score).group(1)
    held = re.search(r"held back: (\d+)", score).group(1)
    day30 = re.search(r"Day-30 pile right: (\d+/\d+)", score).group(1)
    extra = re.search(r"drive-bys let in\): (\d+)", score).group(1)
    drafted = re.search(r"of those, drafted: (\d+)", score).group(1)
    return right, held, day30, extra, drafted


def main():
    dne = HERE / "do-not-email.csv"
    backup = dne.read_bytes() if dne.exists() else None
    rows = []
    try:
        for name in VARIANTS:
            score = run(make(name))
            rows.append((name, "rules", *headline(score), score))
        if "--claude" in sys.argv:
            score = run(OUT / "all", claude=True)
            rows.append(("all", "Claude", *headline(score), score))
    finally:
        if backup is not None:
            dne.write_bytes(backup)  # stress runs must not change the real do-not-email list
    print(f"{'variant':12} {'reading':7} {'right':7} {'held':5} {'day-30':7} {'extras':6} {'extras drafted'}")
    for name, mode, right, held, day30, extra, drafted, _ in rows:
        print(f"{name:12} {mode:7} {right:7} {held:5} {day30:7} {extra:6} {drafted}")
    for name, mode, *_, score in rows:
        problems = [l for l in score.splitlines() if l.startswith("  P") or l.startswith("  EXTRA")]
        problems = [l for l in problems if "held back, already handled" not in l or ";" in l.split(":", 1)[1]]
        if problems:
            print(f"\n{name} ({mode}):")
            print("\n".join(problems[:15]))


if __name__ == "__main__":
    main()
