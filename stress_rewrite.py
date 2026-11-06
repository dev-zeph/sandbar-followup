#!/usr/bin/env python3
"""Hardest stress test: new names and new wording, same people and same facts.

Every first name, surname and clinic name is swapped for a new one (in scans, cards, notes, activity and emails),
and Claude rewords every note (scan notes, card backs, voice notes, Owen's plane list, activity details) while
keeping the facts. Voice notes get sound-alike misspellings of the NEW names; the plane list keeps nicknames.
Erin's recount is still the answer key, because the scorer matches people by scan and card IDs.

Run:  .venv/bin/python stress_rewrite.py            make stress/rewrite, run with Claude, score
      .venv/bin/python stress_rewrite.py --fresh    also run a second time with an empty cache (is Claude stable?)
Cost: about $3-5 for the rewrite + run, plus $2-3 for --fresh.
"""
import csv
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sandbar  # noqa: E402
import sandbar_ai as ai  # noqa: E402

DATA, OUT = HERE / "data", HERE / "stress" / "rewrite"
KEY = DATA / "erin-recount-toronto.csv"
rnd = random.Random(11)

FIRST_POOL = """Abigail Adele Adrian Aidan Aisha Alana Alicia Amara Anders Anika Annika Arjun Astrid Audrey Avery Beatrice
Bianca Blake Bronwyn Caleb Calla Camille Carmen Cecily Celeste Cormac Dalia Damon Darius Delphine Desmond Dina Dominic
Elodie Emil Enzo Esme Ezra Fatima Felix Fiona Flora Gemma Gideon Greta Hamish Harriet Hazel Imogen Ines Isla Ivan Jasper
Joelle Jonah Josie Jude Juniper Kaia Kamal Keira Kofi Lachlan Laila Leander Leona Lila Linnea Lorcan Lucian Mabel Maeve
Malik Marguerite Marisa Maya Milo Mira Nadine Naomi Nell Niamh Nico Noor Odette Olive Omar Orla Oscar Petra Philippa
Pia Quentin Rafael Reid Rhea Rory Rosalie Ruben Sabine Saoirse Selma Silas Simone Soren Stellan Sunita Tamsin Tariq
Theo Thea Uma Valentina Vera Wesley Wren Xavier Yara Yusuf Zara Zoltan Ansel Brigid Cassius Dagny Eamon Freya Ginevra
Hugo Ilse Joaquin Kasimir Lisette Matteo Nerys Osric Perpetua Quinn Rosamund Sigrid Torin Ulla Vivienne Wilhelmina""".split()

LAST_POOL = """Abernethy Achterberg Ahn Albrecht Alcott Amundsen Arbour Ashby Bancroft Barlow Beaudry Belanger Bergstrom
Blackwood Boateng Bramwell Brennick Calloway Carrington Castellano Chaudhry Cheng Coady Corcoran Cormier Crowley Dalgleish
Dempster Desjardins Dinsmore Donnelly Drummond Dufresne Eastman Ellery Esposito Fairweather Falconer Faraday Fennimore
Fitzroy Fontaine Forsythe Galloway Garnier Gillespie Goss Greaves Haldane Halvorsen Hargreaves Hawley Hendry Holloway
Iqbal Isaksen Jarvis Jeffries Kavanagh Kearney Kemp Kincaid Kowalski Lachance Langdon Larkin Lavoie Lindqvist Lockhart
Lombardi Lundgren MacAulay MacKinnon Mahoney Marchetti Maxwell McCrae Meunier Molloy Montgomery Morrow Nakamura Neville
Nyberg Oakes Okonkwo Oyelaran Palmquist Pemberton Penhaligon Pettigrew Quigley Radcliffe Rasmussen Redfern Rinaldi
Rourke Rutherford Saunders Sauvé Selkirk Sinclair Somerville Strand Sutherland Tavernier Thibault Thornbury Tremblay
Underhill Vandermeer Varga Vasquez Waddell Wakefield Weatherby Whitlock Winslow Wojcik Yarrow Youngblood Zielinski
Ackerley Brightwater Coldstream Dunleavy Etherington Fairbairn Gallagher Hollis Ingram Jessop Keswick Lamontagne""".split()

CLINIC_POOL = """Alderwood Amberline Anchorage Applecross Ashgrove Baywind Beacon Birchbank Bluewater Bramble Brightside
Brookhaven Canopy Cedarline Clearbrook Cliffside Copperleaf Coralbay Cornerstone Cove Crescent Driftstone Eastwind
Elmcrest Evergreen Fernbrook Fieldstone Firthside Foxhollow Glenmore Goldfinch Granitebay Greenhaven Harborview Hartwell
Hawthorn Heathrow Highgate Hollowbrook Inglewood Juniper Keystone Kingsmere Lakemont Larchwood Laurelton Lighthouse
Lilac Linden Mapleton Marshfield Meadowbrook Millbrook Mistral Moonstone Mossbank Northbay Oakridge Orchard Osprey
Parkside Pebblebrook Pinecrest Quarry Ravenwood Redwater Riverbend Rockport Rosewood Saltwind Sandpiper Shoreline
Silverbrook Skyline Southgate Springhill Stillbrook Stonebridge Summerside Sunridge Tamarack Thistle Timberline
Trailhead Truenorth Twinrivers Valleyview Westhaven Whistler Willowbank Windward Woodbridge Yarrowdale Zephyr""".split()

# words that are not names: generic clinic words, kinds of practice, and product / competitor names
GENERIC = sandbar.GENERIC_CLINIC_WORDS | sandbar.COMPETITORS | {
    "&", "-", "and", "inc.", "ltd", "dr", "dr.", "acupuncture", "chiropractic", "chiro", "osteopathy", "kinesiology",
    "pilates", "sport", "spa", "studio", "allied", "practice", "expo", "sandbar", "scheduling", "jane", "google",
    "college", "university", "school", "program", "student", "insurance", "tape", "co", "equipment", "products",
    "supply", "orthotics", "massothérapie", "physiothérapie", "clinique", "est", "côte", "de", "du", "la", "le"}


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- the name map

def build_map(scans, notes, acts):
    firsts, lasts, clinic_words = set(), set(), set()
    for r in scans:  # word by word, so "Mei Lin" maps the same everywhere
        firsts |= {w.lower() for w in r["first_name"].split()}
        lasts.add(r["last_name"].strip().lower())
    for c in notes["cards"]:
        first, last = sandbar.split_card_name(c["name"])
        firsts |= {w.lower() for w in first.split()}
        if last:
            lasts.add(last.lower())
    clinics = [r["company"] for r in scans] + [c["clinic"] for c in notes["cards"]] + [a["clinic"] for a in acts]
    for c in clinics:
        for w in re.findall(r"[A-Za-zÀ-ÿ']+", c):
            if w.lower() not in GENERIC and w.lower() not in lasts and len(w) > 2:
                clinic_words.add(w.lower())
    firsts.discard("")
    lasts.discard("")
    taken = firsts | lasts | clinic_words

    fmap = {}
    groups_used = [g for g in sandbar.NICKNAMES if g & firsts]
    spare = [g for g in sandbar.NICKNAMES if not (g & (firsts | taken))]
    for g in groups_used:  # a nickname family maps to another family of the same size (Raj/Rajesh -> Rob/Robert)
        tgt = next((t for t in spare if len(t) == len(g)), None)
        if tgt is None:
            continue
        spare.remove(tgt)
        for a, b in zip(sorted(g, key=len, reverse=True), sorted(tgt, key=len, reverse=True)):
            fmap[a] = b
    pool = [n.lower() for n in FIRST_POOL if n.lower() not in taken]
    rnd.shuffle(pool)
    for f in sorted(firsts):
        if f not in fmap:
            fmap[f] = pool.pop()
    lpool = [n.lower() for n in LAST_POOL if n.lower() not in taken]
    rnd.shuffle(lpool)
    lmap = {l: lpool.pop() for l in sorted(lasts)}
    heads = ("alder amber ash bay birch blue bright brook cedar clear copper coral fern fox glen gold green harbor "
             "hazel high holly iron lake larch linden maple marsh meadow mill moss north oak pine raven red river rock "
             "rose salt sand silver sky south spring stone sun thistle timber west willow wind wood").split()
    tails = "bank brook crest dale field gate haven holm hurst leigh mere mont moor ridge shore side vale view wick worth".split()
    cpool = [h + t for h in heads for t in tails if h + t not in taken]
    rnd.shuffle(cpool)
    cmap = {w: cpool.pop() for w in sorted(clinic_words)}
    return fmap, lmap, cmap


def case_like(src, new):
    if src.isupper() and len(src) > 1:
        return new.upper()
    if src[:1].isupper():
        if new.startswith("mac") and len(new) > 3:
            return "Mac" + new[3].upper() + new[4:]
        if new.startswith("mc") and len(new) > 2:
            return "Mc" + new[2].upper() + new[3:]
        return new[:1].upper() + new[1:]
    return new


def swap_words(text, *maps):
    def one(m):
        w = m.group(0)
        for mp in maps:
            if w.lower() in mp:
                return case_like(w, mp[w.lower()])
        return w
    return re.sub(r"[A-Za-zÀ-ÿ']+", one, text or "")


def swap_initials(text, scans, fmap):
    """'H. Bouchard' -> new first name's initial + new surname (initial looked up from that surname's person)."""
    def one(m):
        ini, last = m.group(1), m.group(2)
        olds = {f.lower() for f, l in scans if l.lower() == last.lower() and f[:1].upper() == ini
                and len(f.strip(". ")) > 1}
        news = {fmap.get(o, ini)[:1].upper() for o in olds}  # Jen and Jennifer both -> R
        if len(news) == 1:
            return news.pop() + ". " + last
        return m.group(0)
    return re.sub(r"\b([A-Z])\. ?([A-Z][A-Za-z']+)", one, text or "")


def swap_email(email, fmap, lmap, cmap):
    if "@" not in (email or ""):
        return email
    local, domain = email.split("@", 1)
    lead = len(local) - len(local.lstrip())
    local = local.strip()
    parts = re.split(r"([._-])", local)
    out = []
    for p in parts:
        lo = p.lower()
        if lo in fmap:
            out.append(case_like(p, fmap[lo]))
        elif lo in lmap:
            out.append(case_like(p, lmap[lo]))
        else:
            q = p
            for old, new in sorted(lmap.items(), key=lambda kv: -len(kv[0])):
                if len(old) >= 4 and old in q.lower():
                    i = q.lower().index(old)
                    q = q[:i] + new + q[i + len(old):]
                    break
            out.append(q)
    label, _, rest = domain.partition(".")
    both = {k: v for k, v in {**cmap, **lmap}.items() if len(k) >= 4}
    if both:  # one pass, so a new word is never replaced again
        pat = re.compile("|".join(re.escape(k) for k in sorted(both, key=len, reverse=True)), re.I)
        label = pat.sub(lambda m: both[m.group(0).lower()], label)
    return " " * lead + "".join(out) + "@" + label + ("." + rest if rest else "")


# ---------------------------------------------------------------- Claude rewords the notes

REWRITE_SYSTEM = """You help build a test set. You get short notes from a trade-show booth and a table of name changes.
For each note, write a new version that:
- says exactly the same facts: same asks (demo, pricing, trial, call back, info), same promises and dates, same numbers
  (locations, staff), same booking software names (Clinivo, Bookstead, Pracshift, Jane, etc.), same doubts ("?"),
  same refusals or unsubscribe requests, same personal remarks. Never add or drop a fact.
- uses different wording and word order, in the same style: voice notes stay as messy lowercase phone transcripts,
  plane-list lines stay terse shorthand, card backs stay short scribbles, activity details stay like system logs or
  short emails. Keep roughly the same length. Keep French in French.
- swaps every person and clinic name using the table. If the original spells a name by sound or wrong
  ("derek oh say" for Osei), write a similar sound-alike or misspelling of the NEW name. If it uses a nickname or
  initial ("Steve L", "Dr. M"), use the matching nickname or initial of the new name. Names not in the table stay.
Return every note id exactly once."""

REWRITE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["items"],
                  "properties": {"items": {"type": "array", "items": {
                      "type": "object", "additionalProperties": False, "required": ["id", "text"],
                      "properties": {"id": {"type": "string"}, "text": {"type": "string"}}}}}}


def reword(kind, items, table):
    if not items:
        return {}
    got = {}
    for start in range(0, len(items), 20):  # small batches keep each answer well under the token limit
        chunk = items[start:start + 20]
        user = (f"Name changes (old -> new):\n{table}\n\nNotes ({kind}):\n" +
                json.dumps([{"id": i, "text": t} for i, t in chunk], ensure_ascii=False, indent=0))
        data = ai._cached_call(f"rewrite-{kind}", REWRITE_SYSTEM, user, REWRITE_SCHEMA, effort="medium")
        got.update({d["id"]: d["text"] for d in data["items"]})
    missing = [i for i, _ in items if i not in got]
    if missing:
        print(f"  {kind}: Claude skipped {len(missing)}, kept the originals with names swapped: {missing[:5]}")
    return got


# ---------------------------------------------------------------- make the show

def make():
    sf, scans = read_csv(DATA / "badge-scans.csv")
    af, acts = read_csv(DATA / "after-show-activity.csv")
    notes = json.loads((DATA / "booth-notes.json").read_text(encoding="utf-8"))
    fmap, lmap, cmap = build_map(scans, notes, acts)
    scans_orig = [(r["first_name"], r["last_name"]) for r in scans] + \
        [sandbar.split_card_name(c["name"]) for c in notes["cards"]]
    table = "\n".join([f"first name {a} -> {b}" for a, b in sorted(fmap.items())] +
                      [f"surname {a} -> {b}" for a, b in sorted(lmap.items())] +
                      [f"clinic word {a} -> {b}" for a, b in sorted(cmap.items())])

    texts = {
        "scan-notes": [(r["scan_id"], r["notes"]) for r in scans if r["notes"].strip()],
        "card-backs": [(c["card_id"], c["back_of_card"]) for c in notes["cards"] if c["back_of_card"].strip()],
        "voice-notes": [(v["note_id"], v["transcript"]) for v in notes["voice_notes"]],
        "plane-list": [(l["line_id"], l["text"]) for l in notes["owen_list"]["lines"]],
        "activity": [(a["event_id"], a["detail"]) for a in acts if a["detail"].strip()],
    }
    print("  Claude is rewording the notes...")
    with sandbar_pool() as pool:
        results = dict(zip(texts, pool.map(lambda k: reword(k, texts[k], table), texts)))

    def new_text(kind, i, old):
        return results[kind].get(i) or swap_words(old, fmap, lmap, cmap)

    for r in scans:
        r["first_name"] = swap_words(r["first_name"], fmap)
        r["last_name"] = swap_words(r["last_name"], lmap)
        r["company"] = swap_words(r["company"], lmap, cmap)
        r["email"] = swap_email(r["email"], fmap, lmap, cmap)
        if r["notes"].strip():
            r["notes"] = new_text("scan-notes", r["scan_id"], r["notes"])
    for c in notes["cards"]:
        c["name"] = swap_words(swap_initials(c["name"], scans_orig, fmap), lmap, fmap)
        c["clinic"] = swap_words(c["clinic"], lmap, cmap)
        c["email"] = swap_email(c["email"], fmap, lmap, cmap)
        if c["back_of_card"].strip():
            c["back_of_card"] = new_text("card-backs", c["card_id"], c["back_of_card"])
    for v in notes["voice_notes"]:
        v["transcript"] = new_text("voice-notes", v["note_id"], v["transcript"])
    for l in notes["owen_list"]["lines"]:
        l["text"] = new_text("plane-list", l["line_id"], l["text"])
    for a in acts:
        a["name"] = swap_words(swap_initials(a["name"], scans_orig, fmap), lmap, fmap)
        a["clinic"] = swap_words(a["clinic"], lmap, cmap)
        a["email"] = swap_email(a["email"], fmap, lmap, cmap)
        if a["detail"].strip():
            a["detail"] = new_text("activity", a["event_id"], a["detail"])

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    write_csv(OUT / "badge-scans.csv", sf, scans)
    write_csv(OUT / "after-show-activity.csv", af, acts)
    (OUT / "booth-notes.json").write_text(json.dumps(notes, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "stress" / "rewrite-names.txt").write_text(table, encoding="utf-8")
    return OUT


class sandbar_pool:
    def __enter__(self):
        from concurrent.futures import ThreadPoolExecutor
        self.p = ThreadPoolExecutor(5)
        return self.p

    def __exit__(self, *a):
        self.p.shutdown()


def run_and_score(env=None):
    subprocess.run([sys.executable, str(HERE / "sandbar.py"), str(OUT)], check=True, env=env)
    return subprocess.run([sys.executable, str(HERE / "score.py"), str(HERE / "out" / OUT.name / "people.csv"),
                           str(KEY)], check=True, capture_output=True, text=True).stdout


def main():
    if not ai.available():
        sys.exit("Claude is off (no key). This test needs Claude.")
    dne = HERE / "do-not-email.csv"
    backup = dne.read_bytes() if dne.exists() else None
    try:
        make()
        print("\n=== run 1 ===")
        print(run_and_score())
        if "--fresh" in sys.argv:
            with tempfile.TemporaryDirectory() as tmp:
                env = {**os.environ, "SANDBAR_CACHE": tmp}
                print("\n=== run 2 (empty cache: Claude answers everything again) ===")
                print(run_and_score(env))
    finally:
        if backup is not None:
            dne.write_bytes(backup)  # test runs must not change the real do-not-email list


if __name__ == "__main__":
    main()
