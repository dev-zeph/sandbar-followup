#!/usr/bin/env python3
"""Sandbar show follow-up.

Turns one show's files (badge scans, booth notes, after-show activity) into:
  - one row per real conversation (people.csv)
  - a draft for everyone it is OK to write to (drafts-owen.md, drafts-nadia.md)
  - the people who need a human check first (check-first.md)
  - Nadia's four piles at day 30 (piles.md)

Rules only, no AI, standard Python 3, no installs.
Run:  python3 sandbar.py            (asks for the folder)
      python3 sandbar.py data       (no questions, just runs)
"""
import csv
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import sandbar_ai as ai

HERE = Path(__file__).resolve().parent
DNE_FILE = HERE / "do-not-email.csv"

# ---------------------------------------------------------------- text helpers

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9$?]+", " ", s).strip()


def tokens(s):
    return norm(s).replace("?", " ").split()


def phone10(p):
    d = re.sub(r"\D", "", p or "")
    if len(d) >= 11 and d.startswith("1"):
        d = d[1:]
    return d[:10] if len(d) >= 10 else ""


def domain(email):
    return email.split("@")[-1].lower().strip() if email and "@" in email else ""


GENERIC_DOMAINS = {"example.com", "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "icloud.com"}

NICKNAMES = [
    {"jennifer", "jen", "jenny"}, {"stephen", "steven", "steve"}, {"gordon", "gord"},
    {"rajesh", "raj"}, {"margaret", "peggy", "maggie", "meg"}, {"daniel", "dan", "danny"},
    {"david", "dave"}, {"patrick", "pat"}, {"benjamin", "ben"}, {"robert", "rob", "bob"},
    {"michael", "mike"}, {"katherine", "kathleen", "kate", "kathy"}, {"elizabeth", "liz", "beth"},
    {"william", "will", "bill"}, {"thomas", "tom"}, {"christopher", "chris"}, {"matthew", "matt"},
    {"andrew", "andy"}, {"anthony", "tony"}, {"joseph", "joe"}, {"samuel", "sam"},
    {"alexander", "alex"}, {"alexandra", "alex"}, {"nicholas", "nick"}, {"jonathan", "jon"},
    {"richard", "rick", "dick"}, {"edward", "ed", "eddie"}, {"susan", "sue"}, {"deborah", "deb"},
    {"victoria", "vicky"}, {"rebecca", "becky"}, {"jessica", "jess"}, {"melanie", "mel"},
    {"douglas", "doug"}, {"gregory", "greg"}, {"timothy", "tim"}, {"kenneth", "ken"},
    {"ronald", "ron"}, {"donald", "don"}, {"lawrence", "larry"}, {"frederick", "fred"},
]


def first_variants(first):
    f = norm(first)
    out = {f}
    for group in NICKNAMES:
        if f in group:
            out |= group
    return out


GENERIC_CLINIC_WORDS = set("""physio physiotherapy massage rehab therapy therapeutic clinic clinics health
collective wellness sports centre center and the of group massotherapie physiotherapie inc""".split())

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "single": 1, "solo": 1}

STOPWORDS = set("""a an the and or of to in on at for with from is was were be been he she her his him they
them their it its i im we our you your that this there here who what not no but so up out just really
about all do did dont didnt said says like one two get got very me my some""".split())

# ---------------------------------------------------------------- load files

def find_files(folder):
    found = {}
    for p in sorted(Path(folder).iterdir()):
        if p.suffix.lower() == ".csv":
            with open(p, newline="", encoding="utf-8-sig") as f:
                header = next(csv.reader(f), [])
            if "scan_id" in header:
                found["scans"] = p
            elif "event_id" in header:
                found["activity"] = p
            elif "back_of_card" in header:
                found.setdefault("late_cards", []).append(p)
        elif p.suffix.lower() == ".json":
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(data, dict) and "cards" in data:
                if "notes" not in found and ("voice_notes" in data or "owen_list" in data):
                    found["notes"] = p
                else:
                    found.setdefault("late_cards", []).append(p)
    return found


def fix_case(name):
    name = (name or "").strip()
    return name.title() if name.isupper() or name.islower() else name


def owner_of(text):
    t = norm(text)
    return "Nadia" if "nadia" in t else "Owen"


def split_card_name(name):
    name = re.sub(r"^\s*dr\.?\s+", "", name.strip(), flags=re.I)
    name = name.split(",")[0].strip()
    parts = name.split()
    if not parts:
        return "", ""
    return " ".join(parts[:-1]), parts[-1]


def load(folder):
    files = find_files(folder)
    missing = [k for k in ("scans", "notes") if k not in files]
    if missing:
        sys.exit(f"Could not find the {', '.join(missing)} file(s) in {folder}.")

    records = []
    with open(files["scans"], newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            records.append({
                "id": r["scan_id"], "kind": "scan", "by": owner_of(r.get("scanned_by", "")),
                "first": fix_case(r["first_name"]), "last": fix_case(r["last_name"]),
                "title": r.get("title", ""), "clinic": r.get("company", ""),
                "email": r.get("email", "").strip().lower(), "phone": phone10(r.get("phone")),
                "city": r.get("city", ""), "share": r.get("share_with_exhibitors", "").strip().upper(),
                "rating": r.get("rating", "").strip(), "text": r.get("notes", "") or "",
                "time": r.get("scanned_at", ""), "dr": False,
            })

    notes = json.loads(files["notes"].read_text(encoding="utf-8"))
    for c in notes.get("cards", []):
        first, last = split_card_name(c.get("name", ""))
        records.append({
            "id": c["card_id"], "kind": "card", "by": owner_of(c.get("collected_by", "")),
            "first": first, "last": last, "title": c.get("title", ""), "clinic": c.get("clinic", ""),
            "email": c.get("email", "").strip().lower(), "phone": phone10(c.get("phone")),
            "city": "", "share": "", "rating": "", "text": c.get("back_of_card", "") or "",
            "time": c.get("typed_on", ""), "dr": bool(re.match(r"\s*dr\b", c.get("name", ""), re.I)),
        })

    # late cards: typed in after the first run (CSV with the same columns as a card, or a JSON with "cards")
    n_late = 0
    for lf in files.get("late_cards", []):
        if lf.suffix.lower() == ".csv":
            with open(lf, newline="", encoding="utf-8-sig") as f:
                late = list(csv.DictReader(f))
        else:
            late = json.loads(lf.read_text(encoding="utf-8")).get("cards", [])
        for c in late:
            n_late += 1
            first, last = split_card_name(c.get("name", ""))
            records.append({
                "id": c.get("card_id") or f"LC{n_late:02d}", "kind": "card", "by": owner_of(c.get("collected_by", "")),
                "first": first, "last": last, "title": c.get("title", ""), "clinic": c.get("clinic", ""),
                "email": c.get("email", "").strip().lower(), "phone": phone10(c.get("phone")),
                "city": "", "share": "", "rating": "", "text": c.get("back_of_card", "") or "",
                "time": c.get("typed_on", ""), "dr": bool(re.match(r"\s*dr\b", c.get("name", ""), re.I)),
                "late": lf.name,
            })

    voice = [{"id": v["note_id"], "kind": "voice", "text": v.get("transcript", ""), "time": v.get("recorded_at", "")}
             for v in notes.get("voice_notes", [])]
    lst = notes.get("owen_list") or {}
    lines = [{"id": l["line_id"], "kind": "list", "text": l.get("text", "")} for l in lst.get("lines", [])]

    activity = []
    if "activity" in files:
        with open(files["activity"], newline="", encoding="utf-8-sig") as f:
            activity = list(csv.DictReader(f))

    about = notes.get("about", "")
    m = re.search(r"from the (.+?) booth \(([^,]+)", about)
    show = f"{m.group(1)} in {m.group(2)}" if m else "the show"
    return records, voice, lines, activity, show, files

# ---------------------------------------------------------------- group into people

class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def clinic_key(clinic):
    toks = [t for t in tokens(clinic) if t not in GENERIC_CLINIC_WORDS]
    return toks[0] if toks else ""


def firsts_compatible(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if len(a) == 1 or len(b) == 1:          # an initial on a card
        return a[0] == b[0]
    return bool(first_variants(a) & first_variants(b)) or a.split()[0] == b.split()[0]


def group_people(records):
    uf = UF(len(records))
    by_key = {}
    joins = []  # (record a, record b, why), for the decision log
    for i, r in enumerate(records):
        for key in (("e", r["email"]), ("p", r["phone"])):
            if key[1]:
                if key in by_key:
                    if uf.find(i) != uf.find(by_key[key]):
                        joins.append((by_key[key], i, "same email" if key[0] == "e" else "same phone number"))
                    uf.union(i, by_key[key])
                else:
                    by_key[key] = i
    # same surname + compatible first name + same clinic or same email domain
    for i, a in enumerate(records):
        for j in range(i + 1, len(records)):
            b = records[j]
            if norm(a["last"]) != norm(b["last"]) or not norm(a["last"]):
                continue
            if not firsts_compatible(a["first"], b["first"]):
                continue
            same_dom = domain(a["email"]) and domain(a["email"]) == domain(b["email"]) \
                and domain(a["email"]) not in GENERIC_DOMAINS
            same_clinic = clinic_key(a["clinic"]) and clinic_key(a["clinic"]) == clinic_key(b["clinic"])
            if same_dom or same_clinic:
                if uf.find(i) != uf.find(j):
                    joins.append((i, j, "same surname, matching first name, and same "
                                  + ("clinic" if same_clinic else "email domain")))
                uf.union(i, j)
    groups = defaultdict(list)
    for i, r in enumerate(records):
        groups[uf.find(i)].append(r)
    people = []
    for recs in groups.values():
        recs.sort(key=lambda r: (r["kind"] != "scan", r["id"]))
        people.append({"records": recs, "voice": [], "lines": [], "log": []})
    for a, b, why in joins:
        ra, rb = records[a], records[b]
        person = next(p for p in people if ra in p["records"])
        person["log"].append(f"Joined {ra['id']} ({ra['first']} {ra['last']}, {ra['email'] or 'no email'}) with "
                             f"{rb['id']} ({rb['first']} {rb['last']}, {rb['email'] or 'no email'}): {why}.")
    return people

# ---------------------------------------------------------------- match voice notes and Owen's list

def person_profile(p):
    recs = p["records"]
    firsts, lasts, clinic_toks, cities = set(), set(), set(), set()
    for r in recs:
        if len(norm(r["first"])) > 1:
            firsts |= first_variants(r["first"])
        if r["last"]:
            lasts.add(norm(r["last"]))
        clinic_toks |= {t for t in tokens(r["clinic"]) if t not in GENERIC_CLINIC_WORDS and len(t) > 2}
        if r["city"]:
            cities.add(norm(r["city"]))
    return firsts, lasts, clinic_toks, cities, any(r["dr"] for r in recs)


def match_score(text, prof):
    firsts, lasts, clinic_toks, cities, dr = prof
    t = " " + norm(text).replace("?", " ") + " "
    toks = set(t.split())
    score, pos = 0, None
    for f in firsts:
        hit = (" " + f + " ") in t if " " in f else (f in toks or (len(f) >= 5 and any(
            tk.startswith(f[:5]) and len(tk) >= 4 and f.startswith(tk[:5]) for tk in toks)))
        if not hit and len(f) >= 5:
            hit = any(len(tk) >= 4 and f.startswith(tk) for tk in toks)   # helen -> helene
        if hit:
            score += 2
            idx = [m.start() for m in re.finditer(r"\b" + re.escape(f[:4]), t)]
            pos = min(idx) if idx else pos
            break
    if lasts & toks:
        score += 2
    if clinic_toks & toks:
        score += 2
    if any((" " + c + " ") in t for c in cities):
        score += 1
    if dr and "dr" in toks:
        score += 1
    return score, pos


def attach_notes(people, voice, lines):
    profiles = [person_profile(p) for p in people]
    unmatched = []

    def best_matches(text, multi):
        scored = []
        for i, prof in enumerate(profiles):
            s, pos = match_score(text, prof)
            if s:
                scored.append((s, i, pos))
        scored.sort(reverse=True)
        if not scored or scored[0][0] < 3:
            return []
        if multi:
            named = [x for x in scored if x[0] >= 4 and x[2] is not None]
            if len(named) > 1:
                return named                            # one note about several named people
        if len(scored) > 1 and scored[1][0] == scored[0][0]:
            return []                                   # tie: too unsure
        return [scored[0]]

    voice_owner = {}
    for v in voice:
        hits = best_matches(v["text"], multi=True)
        if not hits:
            unmatched.append(v)
            continue
        if len(hits) == 1:
            people[hits[0][1]]["voice"].append(v)
            voice_owner[v["id"]] = [hits[0][1]]
            continue
        # one note about several people: split the text where each name starts
        hits.sort(key=lambda h: h[2] if h[2] is not None else 0)
        t = norm(v["text"])
        voice_owner[v["id"]] = []
        for k, (_, i, pos) in enumerate(hits):
            start = 0 if k == 0 else pos
            end = hits[k + 1][2] if k + 1 < len(hits) else len(t)
            people[i]["voice"].append({**v, "text": t[start:end]})
            voice_owner[v["id"]].append(i)

    # Owen's list: match a person directly, or match the voice note it echoes
    df = Counter()
    vt = {v["id"]: set(tokens(v["text"])) - STOPWORDS for v in voice}
    for s in vt.values():
        df.update(s)
    for line in lines:
        hits = best_matches(line["text"], multi=False)
        if hits:
            people[hits[0][1]]["lines"].append(line)
            continue
        lt = set(tokens(line["text"])) - STOPWORDS
        best, best_v = 0.0, None
        for vid, s in vt.items():
            sim = sum(1.0 / df[w] for w in lt & s)
            if sim > best:
                best, best_v = sim, vid
        if best >= 0.9 and best_v in voice_owner and len(voice_owner[best_v]) == 1:
            people[voice_owner[best_v][0]]["lines"].append(line)
        else:
            unmatched.append(line)
    return unmatched

# ---------------------------------------------------------------- read what each person said

DRIVE_BY_TITLE = re.compile(r"student|sales rep|account (manager|executive)|territory manager|exhibitor|"
                            r"event staff|marketing", re.I)
DRIVE_BY_NOTE = re.compile(r"\bdraw\b|swag|\bcomp\b|competitor|exhibitor|student|didnt talk|didn't talk", re.I)
DRIVE_BY_ORG = re.compile(r"college|university|insurance|equipment|supply|supplies|products|expo\b", re.I)
COMPETITORS = {"bookstead", "clinivo", "pracshift"}


def all_text(p):
    parts = [r["text"] for r in p["records"]] + [v["text"] for v in p["voice"]] + [l["text"] for l in p["lines"]]
    return " | ".join(x for x in parts if x)


def is_real(p):
    recs = p["records"]
    if p["voice"] or p["lines"] or any(r["kind"] == "card" for r in recs):
        real_signal = True
    else:
        real_signal = any(r["text"].strip() or r["rating"] for r in recs)
    if not real_signal:
        return False, "blank scan, nothing else"
    for r in recs:
        if DRIVE_BY_TITLE.search(r["title"]) or DRIVE_BY_ORG.search(r["clinic"]):
            return False, f"not a clinic contact ({r['title']}, {r['clinic']})"
        if norm(clinic_key(r["clinic"])) in COMPETITORS or norm(r["clinic"]) in COMPETITORS:
            return False, "competitor"
        if DRIVE_BY_NOTE.search(r["text"]) and not (p["voice"] or p["lines"]):
            return False, f"drive-by note: {r['text']}"
    return True, ""


ASKS = [
    ("call back", re.compile(r"\bcall (me|her|him|them|back|when|once|after)\b|\bappeler\b")),
    ("trial", re.compile(r"\btrial\b(?!\s*\?)")),
    ("demo", re.compile(r"\bdemo\b(?!\s*\?)")),
    ("pricing", re.compile(r"\bpricing\b(?!\s*\?)|\$|\bprice per\b|\bquote\b")),
]
INFO = re.compile(r"send (info|brochure|stuff|one ?pager|him|her|something)|info for owner|one ?pager|"
                  r"for (the )?owner|show the owner|take to the owner")


def clean_for_asks(text):
    t = text.lower()
    t = re.sub(r"not (a |an )?(demo|trial)", " ", t)
    return t


def find_ask(text):
    t = clean_for_asks(text)
    for name, rx in ASKS:
        if rx.search(t):
            return name
    return ""


def locations(text):
    t = norm(text)
    best = 1
    for m in re.finditer(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:\w+\s+)?"
                         r"(clinics?|locs?|locations?|sites?)\b", t):
        n = m.group(1)
        best = max(best, int(n) if n.isdigit() else NUMBER_WORDS[n])
    if re.search(r"\b(2nd|second) (loc|location|clinic|site)", t):
        best = max(best, 2)
    return best


SYSTEMS = [
    ("Clinivo", re.compile(r"clinivo|clean ?evo")),
    ("Pracshift", re.compile(r"prac ?shift|pract ?shift")),
    ("Bookstead", re.compile(r"book ?stead|\bbs user\b")),
    ("Google Calendar", re.compile(r"gcal|google ?cal")),
    ("spreadsheet", re.compile(r"excel|sheets|spreadsheet")),
    ("paper book", re.compile(r"paper")),
]
PAID = {"Clinivo", "Pracshift", "Bookstead"}


def booking_system(text):
    t = norm(text)
    t = re.sub(r"(ditched|left|dropped|moved off) (book ?stead|clinivo|prac ?shift)", " ", t)
    for name, rx in SYSTEMS:
        if rx.search(t):
            return name
    return "unknown"


# What they said at the booth, as safe phrases. Only these phrases can reach a draft,
# so nothing personal from a voice note (family, health, hobbies) can leak into an email.
# (pattern, English clause after "You mentioned", French clause after "Vous m'avez parlé de")
DETAILS = [
    (r"double ?book", "{sys} has been double-booking your RMTs", "des doubles réservations dans {sys}"),
    (r"overwrit", "your RMTs keep overwriting each other on the shared calendar",
     "de vos massothérapeutes qui s'écrasent les rendez-vous dans le calendrier partagé"),
    (r"reporting", "you can't get a number out of {sys}'s reporting", "des rapports de {sys}"),
    (r"renew|renouvel", "your {sys} contract renews at the end of the year",
     "de votre contrat {sys} qui se renouvelle en fin d'année"),
    (r"mandarin", "you'd like reminders to go out in Mandarin", "des rappels en mandarin"),
    (r"security", "your IT team wants the security one-pager first",
     "de la fiche sécurité pour votre équipe informatique"),
    (r"in writing", "your partner wants pricing in writing", "des prix par écrit pour votre associé"),
    (r"per practitioner", "you want the price per practitioner", "du prix par praticien"),
    (r"(two|2) rmts first|try it with", "you want to try it with your two RMTs first",
     "de l'essai avec vos deux massothérapeutes"),
    (r"owner (is |= ?)?dr (\w+)", "Dr. {m2} needs to be on the demo", "de la présence du Dr {m2} à la démo"),
    (r"ditched|left book ?stead", "you left Bookstead and are running the clinic off a spreadsheet",
     "de votre départ de Bookstead"),
    (r"second location|2nd loc|new place", "your second location is about to open",
     "de l'ouverture de votre deuxième clinique"),
    (r"(sick of|answering) (the )?phone", "you're sick of answering the phone all day",
     "du téléphone qui sonne toute la journée"),
    (r"drowning in phone|phone bookings", "your front desk is buried in phone bookings",
     "de votre réception débordée par les appels"),
    (r"phones? rings? all lunch", "the phones ring through the whole lunch hour",
     "du téléphone qui sonne tout le midi"),
    (r"(txt|text) reminder", "{sys} charges extra for text reminders", "des frais de {sys} pour les rappels texto"),
    (r"logg\w* .{0,20}out", "{sys} keeps logging your RMTs out", "de {sys} qui déconnecte vos massothérapeutes"),
    (r"(\d+) no ?shows", "you're losing about {m1} no-shows a week", "des quelque {m1} absences par semaine"),
    (r"no ?shows", "the no-shows you're losing every week", "des absences chaque semaine"),
    (r"price went up|raised", "{sys} raised its price this year", "de la hausse de prix de {sys}"),
    (r"import", "you'd want to bring your data across from {sys}", "de l'import de vos données depuis {sys}"),
    (r"front desk shared", "one front desk is shared between your two clinics",
     "de votre réception partagée entre deux cliniques"),
    (r"rota|schedule and bookings", "your staff schedule and bookings live in two different places",
     "de vos horaires et réservations séparés"),
    (r"master spreadsheet|own google cal", "each clinic runs its own calendar and head office copies it into a spreadsheet",
     "des calendriers de chaque clinique recopiés dans un tableur"),
    (r"evening slot", "your clients keep asking for evening slots", "des créneaux en soirée"),
    (r"rebook", "Monday mornings go to rebooking the weekend", "des lundis matin passés à replanifier"),
    (r"deposit", "you'd like to take a deposit when clients book", "des dépôts à la réservation"),
    (r"intake form", "you'd like intake forms filled in before the first visit",
     "des formulaires d'accueil avant la première visite"),
    (r"direct billing", "you'd like direct billing to insurers in the same place as bookings",
     "de la facturation directe aux assureurs"),
    (r"cancellation", "you'd like clients to grab cancellation slots online",
     "des annulations reprises en ligne par vos clients"),
    (r"show the owner|for (the )?owner|take to the owner", "you wanted something to take to the owner",
     "d'un document à montrer au propriétaire"),
    # plain facts, used only when nothing more specific was said
    (r"paper", "you're running bookings off a paper book", "de votre agenda papier"),
    (r"excel|sheets|spreadsheet", "you're running bookings off a spreadsheet", "de votre tableur"),
    (r"gcal|google ?cal", "you're booking through Google Calendar", "de Google Agenda"),
]
FACT_DETAILS = 3  # the last three entries above are plain facts


def booth_detail(text, sysname):
    t = norm(text)
    for k, (pat, en, fr) in enumerate(DETAILS):
        m = re.search(pat, t)
        if m:
            grp = [x for x in m.groups() if x]
            g = {"sys": sysname if sysname in PAID else "your current system",
                 "m1": grp[0] if grp else "", "m2": grp[-1].title() if grp else ""}
            return en.format(**g), fr.format(**g), k >= len(DETAILS) - FACT_DETAILS
    return "", "", True


FRENCH = re.compile(r"propriétaire|massothérap|physiothérap|\bpht\b|renouvellement|appeler|\bmerci\b", re.I)


def is_french(p):
    return any(FRENCH.search(r["title"] + " " + r["text"] + " " + r["clinic"]) for r in p["records"])


def sender(p, french):
    if french:
        return "Nadia"
    votes = Counter(r["by"] for r in p["records"])
    votes["Owen"] += len(p["voice"]) + len(p["lines"])
    for v in p["voice"]:
        if re.search(r"nadia (told|had|met|talked)|she had in french", norm(v["text"])):
            votes["Nadia"] += 2
    if votes["Owen"] == votes["Nadia"]:
        return p["records"][0]["by"]
    return votes.most_common(1)[0][0]


def when_to_call(text):
    t = norm(text)
    m = re.search(r"call (?:me|her|him|them|back)?\s*((?:once|when|after) [a-z ]+?)(?: not |\bnadia|$| she | he )", t + " ")
    return m.group(1).strip() if m else ""

# ---------------------------------------------------------------- consent and day 30

def load_dne():
    out = {}
    if DNE_FILE.exists():
        with open(DNE_FILE, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out[r["email"].lower()] = r
    return out


REMOVE = re.compile(r"remove me|take me off|unsubscribe|stop emailing|no more emails", re.I)
NO_LIST = re.compile(r"mailing list|newsletter", re.I)


GIVEN_FILE = "drafts-given.csv"   # kept in the show's folder: who already got a draft, so late cards never cause a second one


def load_given(folder):
    path = Path(folder) / GIVEN_FILE
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["email"]: r for r in csv.DictReader(f)}


def release(res, folder):
    """Erin has checked: record every draft handed to Owen and Nadia, so no later run writes to them again."""
    path = Path(folder) / GIVEN_FILE
    exists = path.exists()
    today = datetime.now().strftime("%Y-%m-%d")
    rows = [{"email": e, "name": p["name"], "sender": p["sender"], "date": today}
            for p in res["real"] if p["gets_draft"] for e in sorted(p["emails"])]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["email", "name", "sender", "date"])
        if not exists:
            w.writeheader()
        w.writerows(rows)
    return len({r["name"] for r in rows})


def show_end(records):
    dates = [r["time"][:10] for r in records if r["kind"] == "scan" and r["time"]]
    return datetime.strptime(max(dates), "%Y-%m-%d") if dates else None


def day30(people, activity, end):
    """Attach activity events to people and work out the pile for each one."""
    real = [p for p in people if p["real"]]
    by_email, by_domain = {}, defaultdict(list)
    for p in real:
        for e in p["emails"]:
            by_email[e] = p
        for d in {domain(e) for e in p["emails"]} - GENERIC_DOMAINS:
            by_domain[d].append(p)

    def name_match(name):
        f, _, l = norm(name).replace("dr ", "").rpartition(" ")
        if not l:
            return None
        hits = [p for p in real if l in p["lasts"] and (not f or first_variants(f.split()[0]) & p["firsts"])]
        return hits[0] if len(hits) == 1 else None

    removals = []
    not_linked = []
    cutoff = end + timedelta(days=31) if end else None
    for p in real:
        p["events"] = []
    for ev in activity:
        when = datetime.strptime(ev["date_time"][:10], "%Y-%m-%d")
        if cutoff and when >= cutoff:
            continue
        email = ev.get("email", "").lower()
        if ev["event"] == "reply received" and REMOVE.search(ev.get("detail", "")):
            removals.append((email, ev.get("name", ""), ev["date_time"][:10], ev.get("detail", "")))
        if ev["event"] == "email bounced":
            target = by_email.get(email)
            if target:
                target["bounced"].add(email)
            continue
        p, how = by_email.get(email), "same email"
        if not p:
            p, how = name_match(ev.get("name", "")), f"same name ({ev.get('name', '')}), different email {email}"
        if not p and ev["event"] in ("demo booked", "trial started"):
            cands = by_domain.get(domain(email), [])
            how = f"booked from the same clinic's email ({email})"
            if len(cands) > 1:
                cands = [c for c in cands if any(f in norm(ev.get("detail", "")).split() for f in c["firsts"])]
                how += ", and the booking note names them"
            if len(cands) == 1:
                p = cands[0]
        if not p:
            if ev["event"] in ("demo booked", "trial started", "reply received"):
                not_linked.append(ev)
            continue
        p["events"].append(ev)
        if ev["event"] in ("demo booked", "trial started", "reply received") and how != "same email":
            p["log"].append(f"Linked '{ev['event']}' on {ev['date_time'][:10]} to this person: {how}.")

    for p in real:
        kinds = [e["event"] for e in p["events"]]
        sent_to = {e["email"].lower() for e in p["events"] if e["event"] == "email sent"}
        delivered = sent_to - p["bounced"]
        if "demo booked" in kinds:
            p["day30"] = "demo"
        elif "trial started" in kinds:
            p["day30"] = "trial"
        elif delivered:
            p["day30"] = "no reply"
        else:
            p["day30"] = "never followed up"
        p["followed_up"] = "; ".join(sorted({f"{e['date_time'][:10]} {e['channel']}" for e in p["events"]
                                             if e["event"] == "email sent" and e["email"].lower() in delivered})) or "no"
    return removals, not_linked

# ---------------------------------------------------------------- drafts

BOOKING = "[booking link]"
TRIAL = "[trial link]"


def draft(p, show):
    first = p["greet"]
    if p["french"]:
        detail = f"Vous m'avez parlé {p['detail_fr']}." \
            if p["detail_fr"] else ""
        step = {
            "demo": f"Comme convenu, voici mon lien pour réserver une démo : {BOOKING}.",
            "trial": f"Comme promis, voici votre accès d'essai : {TRIAL}.",
            "pricing": "Comme promis, voici nos prix en pièce jointe.",
            "call back": "Comme promis, je vous appelle bientôt pour en parler. Quel moment vous convient le mieux ?",
            "send info": "Comme promis, voici notre fiche de présentation en pièce jointe.",
            "thank-you note": "Merci d'être passé(e) au kiosque. Si jamais vous voulez voir comment Sandbar s'y prend, "
                              "répondez simplement à ce courriel.",
        }[p["next_step"]]
        body = f"Bonjour {first},\n\nRavie de vous avoir rencontré(e) à {show.split(' in ')[-1]}. {detail}\n\n{step}\n\nAu plaisir,\n{p['sender']}"
        subject = "Suite à notre rencontre au salon"
    else:
        detail = f"You mentioned {p['detail']}." if p["detail"] else ""
        extra = ""
        if p["next_step"] == "demo":
            step = f"You asked for a demo, so here's my booking page: {BOOKING}. Grab whatever time works for you."
            subject = "Your Sandbar demo"
        elif p["next_step"] == "trial":
            step = f"As promised, here's your trial, ready to go: {TRIAL}."
            subject = "Your Sandbar trial"
        elif p["next_step"] == "pricing":
            step = "As promised, our pricing is attached."
            subject = "Sandbar pricing, as promised"
        elif p["next_step"] == "call back":
            when = f" {p['call_when']}" if p["call_when"] else ""
            step = f"As promised, I'll give you a call{when}. Just reply if there's a better time."
            subject = "Following up from the expo"
        elif p["next_step"] == "send info":
            step = "As promised, here's our one-pager. It's attached."
            if "owner" in p["detail"]:
                step = "Here's a one-pager you can pass to your owner. It's attached."
            if "security" in p["detail"]:
                step = "Here's the security one-pager for your IT team. It's attached."
            subject = "The Sandbar one-pager"
        else:
            how = "handles that" if detail else "works"
            step = f"Thanks for stopping by the booth. If it would ever help to see how Sandbar {how}, just reply and I'll set something up."
            subject = "Good to meet you at the expo"
        if p["email_ok"].startswith("personal"):
            extra = "\n\nI've kept you off our mailing list, as you asked."
        body = f"Hi {first}, great to meet you in {show.split(' in ')[-1]}. {detail}\n\n{step}{extra}\n\n{p['sender']}"
    return subject, re.sub(r"  +", " ", body).replace(" \n", "\n")

# ---------------------------------------------------------------- main pipeline

PRIORITY_ORDER = {"hot": 0, "warm": 1, "cold": 2}


DECLINED = re.compile(r"not for now|no thanks|not interested|signed (another|with)|went with|not at this time|"
                      r"pass for now|not the right time", re.I)
PERSONAL_CHANNELS = re.compile(r"(owen|nadia)'?s? mailbox", re.I)


def ai_candidates(people):
    cands = []
    for i, p in enumerate(people):
        recs = p["records"]
        if any(DRIVE_BY_TITLE.search(r["title"]) or DRIVE_BY_ORG.search(r["clinic"]) for r in recs):
            continue
        cands.append({
            "id": f"X{i:03d}", "names": sorted({f"{r['first']} {r['last']}".strip() for r in recs}),
            "title": recs[0]["title"], "clinic": recs[0]["clinic"],
            "city": next((r["city"] for r in recs if r["city"]), ""), "domain": domain(recs[0]["email"]),
            "met_by": "/".join(sorted({r["by"] for r in recs})),
            "notes": " | ".join(t for t in (ai.redact(r["text"])[0] for r in recs) if t)})
    return cands


def ai_notes(voice, lines):
    return [{"id": n["id"], "kind": "voice note" if n["kind"] == "voice" else "Owen's plane list",
             "text": ai.redact(n["text"])[0]} for n in voice + lines]


def ai_attach(people, voice, lines):
    """Tie voice notes and list lines to people with Claude. Unsure = left unmatched for a person to check."""
    result = ai.match_notes(ai_candidates(people), ai_notes(voice, lines))
    unmatched = []
    for n in voice + lines:
        hits = result.get(n["id"], [])
        if not hits:
            unmatched.append(n)
            continue
        for pid, about in hits:
            p = people[int(pid[1:])]
            entry = {**n, "text": about} if len(hits) > 1 else n
            (p["voice"] if n["kind"] == "voice" else p["lines"]).append(entry)
            what = "voice note" if n["kind"] == "voice" else "plane list line"
            shared = f" (one note about {len(hits)} people; this part: \"{about[:90]}\")" if len(hits) > 1 else ""
            p["log"].append(f"Tied {what} {n['id']} to this person: Claude was sure{shared}.")
    return unmatched


def person_payload(p, show, end):
    notes = []
    for r in p["records"]:
        bits = [ai.redact(r["text"])[0]] if r["text"] else []
        if r["rating"]:
            bits.append(f"booth rating {r['rating']}")
        if bits:
            what = "badge scan note" if r["kind"] == "scan" else "back of business card"
            notes.append(f"{what} ({r['by']}): " + "; ".join(b for b in bits if b))
    notes += [f"Owen's voice note: {ai.redact(v['text'])[0]}" for v in p["voice"]]
    notes += [f"Owen's plane list: {ai.redact(l['text'])[0]}" for l in p["lines"]]
    main = p["records"][0]
    return {"show": show, "show_end": end.strftime("%Y-%m-%d") if end else "", "name": p["name"],
            "greet": p["greet"], "clinic": p["clinic"], "title": main["title"], "city": p["city"],
            "sender": p["sender"], "language": "French" if p["french"] else "English",
            "notes": notes or ["(nothing written down beyond the badge)"]}


def build(folder, use_ai=False, payload_file=None):
    records, voice, lines, activity, show, files = load(folder)
    people = group_people(records)
    mode = "rules"
    if use_ai:
        try:
            unmatched = ai_attach(people, voice, lines)
            mode = "claude"
        except Exception as e:  # noqa: BLE001
            print(f"  Claude could not match the notes ({e}). Using the rules instead.")
            use_ai = False
    if not use_ai:
        unmatched = attach_notes(people, voice, lines)
        for p in people:
            for n in p["voice"] + p["lines"]:
                what = "voice note" if n["kind"] == "voice" else "plane list line"
                p["log"].append(f"Tied {what} {n['id']} to this person: rules (name, clinic or city in the note).")
    dne = load_dne()
    end = show_end(records)

    for p in people:
        recs = p["records"]
        scan = next((r for r in recs if r["kind"] == "scan"), None)
        card = next((r for r in recs if r["kind"] == "card"), None)
        main = scan or card
        p["name"] = f"{main['first']} {main['last']}".strip()
        p["clinic"] = main["clinic"]
        p["city"] = scan["city"] if scan else ""
        p["emails"] = {r["email"] for r in recs if r["email"]}
        p["email"] = (scan or card)["email"]
        p["firsts"] = set().union(*[first_variants(r["first"]) for r in recs if len(norm(r["first"])) > 1]) if recs else set()
        p["lasts"] = {norm(r["last"]) for r in recs if r["last"]}
        p["bounced"] = set()
        p["real"], p["why_not"] = is_real(p)
        p["sources"] = [r["id"] for r in recs] + [v["id"] for v in p["voice"]] + [l["id"] for l in p["lines"]]
        p["has_card"] = card is not None
        p["french"] = is_french(p)
        p["sender"] = sender(p, p["french"])
        spoken = [f for f in p["firsts"] if re.search(r"\b" + re.escape(f) + r"\b", norm(" ".join(
            v["text"] for v in p["voice"]) + " " + " ".join(l["text"] for l in p["lines"])))]
        nick = [f for f in spoken if norm(main["first"]) != f]
        p["greet"] = nick[0].title() if nick and len(nick[0]) > 2 else main["first"]

        # rules reading (always computed; used when Claude is off or fails for this person)
        text = all_text(p)
        p["ask"] = find_ask(text)
        p["asked_info"] = bool(INFO.search(norm(text)))
        p["locations"] = locations(text)
        p["system"] = booking_system(text)
        p["detail"], p["detail_fr"], fact_only = booth_detail(text, p["system"])
        p["rules_detail"] = p["detail"] if not fact_only else ""
        p["detail_specific"] = not fact_only
        p["no_list"] = bool(NO_LIST.search(text) and re.search(r"(not|dont|don't|do not|hates)", text, re.I))
        p["call_when"] = when_to_call(text)
        p["ai"], p["ai_error"] = None, ""
        emails = [(r["id"], r["email"]) for r in recs if r["email"]]
        if len({e for _, e in emails}) > 1:
            src = "badge scan" if scan and p["email"] == scan["email"] else "card"
            others = ", ".join(f"{e} ({i})" for i, e in emails if e != p["email"])
            p["log"].append(f"Emails disagree. Drafting to {p['email']} from the {src} (badge first, then card); "
                            f"also on file: {others}.")
        votes = Counter(r["by"] for r in recs)
        if len(votes) > 1 or p["french"]:
            p["log"].append(f"Sender {p['sender']}: " + ("French, so Nadia." if p["french"] else
                            f"both met them; more of the notes are {p['sender']}'s."))

    real_people = [p for p in people if p["real"]]
    payloads = [person_payload(p, show, end) for p in real_people]
    if payload_file:
        payload_file.parent.mkdir(parents=True, exist_ok=True)
        payload_file.write_text(json.dumps({"match_people": ai_candidates(people), "match_notes": ai_notes(voice, lines),
                                            "per_person": payloads}, indent=1, ensure_ascii=False), encoding="utf-8")
    if use_ai:
        print(f"  asking Claude about {len(payloads)} people...")
        for p, pl, (r, err) in zip(real_people, payloads, ai.read_people(payloads)):
            p["notes_sent"] = pl["notes"] + [pl["name"], pl["greet"], pl["title"], pl["clinic"], pl["city"]]
            if not r:
                p["ai_error"] = err or "no answer"
                continue
            p["ai"] = r
            rules_ask = p["ask"]
            p["ask"] = "" if r["ask"] == "none" else r["ask"]
            if rules_ask != p["ask"]:
                p["log"].append(f"Notes disagree on the ask. Rules read '{rules_ask or 'none'}', Claude read "
                                f"'{p['ask'] or 'none'}'. Used Claude's reading (a '?' is a guess, the voice note wins).")
            p["asked_info"] = r["asked_for_info"]
            p["locations"] = max(1, r["locations"])
            p["system"] = r["booking_system"]
            p["detail"] = r["booth_detail"].strip().rstrip(".")
            p["detail_specific"] = bool(p["detail"])
            p["no_list"] = r["no_mailing_list"]

    for p in people:
        if p["ask"]:
            p["priority"], p["next_step"] = "hot", p["ask"]
        else:
            p["priority"] = "warm" if (p["locations"] >= 2 or p["system"] in PAID) else "cold"
            p["next_step"] = "send info" if p["asked_info"] else "thank-you note"
        if p["next_step"] != "call back":
            p["call_when"] = ""
        shares = {r["share"] for r in p["records"] if r["kind"] == "scan"}
        if p["priority"] == "hot":
            p["consent"] = "asked at booth"
        elif p["has_card"]:
            p["consent"] = "card handed over"
        else:
            p["consent"] = "badge scan, opted in" if "Y" in shares else "badge scan, not opted in"
        if any(e in dne for e in p["emails"]):
            hit = next(dne[e] for e in p["emails"] if e in dne)
            p["email_ok"] = f"no: asked to be removed {hit.get('date', '')}".strip()
        elif p["priority"] == "hot" and p["no_list"]:
            p["email_ok"] = "personal reply only, no newsletter"
        elif not p["has_card"] and p["priority"] != "hot" and "Y" not in shares:
            p["email_ok"] = "check first"
        else:
            p["email_ok"] = "yes"

    removals, not_linked = day30(people, activity, end)
    new_dne = []
    for email, name, date, detail in removals:
        if email and email not in dne and email not in {d["email"] for d in new_dne}:
            new_dne.append({"email": email, "name": name, "date": date, "reason": detail, "show": show})
    for p in people:
        if p["real"] and any(e in {d["email"] for d in new_dne} for e in p["emails"]):
            p["email_ok"] = f"no: asked to be removed {next(d['date'] for d in new_dne if d['email'] in p['emails'])}"

    given_before = load_given(folder)
    # already handled: someone already did the next step, or the person already answered
    for p in real_people:
        evs = p.get("events", [])
        why = []
        if any(e["event"] == "demo booked" for e in evs):
            why.append("already booked a demo")
        if any(e["event"] == "trial started" for e in evs):
            why.append("already started a trial")
        if any(e["event"] == "reply received" and DECLINED.search(e.get("detail", "")) for e in evs):
            why.append("already said no")
        personal = [e for e in evs if e["event"] == "email sent" and PERSONAL_CHANNELS.search(e.get("channel", ""))
                    and e["email"].lower() not in p["bounced"]]
        if personal:
            who = personal[0]["channel"].split("'")[0].strip()
            why.append(f"{who} already wrote personally on {personal[0]['date_time'][:10]}")
        given = next((given_before[e] for e in p["emails"] if e in given_before), None)
        if given:
            why = [f"already got a draft from {given['sender']}, released on {given['date']} (earlier run)"]
            personal = []
        p["handled"] = "; ".join(why)
        # Owen: wrote personally or said no = nothing; booked a demo = no email, but tell him;
        # started a trial (and nobody wrote) = two lines, "glad you're trying it"
        p["trial_note"] = bool(why) and not personal and why == ["already started a trial"]
        if p["trial_note"]:
            p["handled"] = "already started a trial, nobody has written yet (Owen would send two lines: " \
                           "\"Glad you're trying Sandbar. I'm around if you get stuck, just reply here.\")"

    real = sorted(real_people, key=lambda p: (PRIORITY_ORDER[p["priority"]], p["name"]))
    for i, p in enumerate(real, 1):
        p["pid"] = f"P{i:02d}"
        ok_to_email = (p["email_ok"] == "yes" or p["email_ok"].startswith("personal")) and bool(p["email"])
        p["gets_draft"] = ok_to_email and not p["handled"]
        # already handled: still write the draft, but hold it at the end of the file ("don't send unless you
        # want to"). Never for someone who said no, or who already got a draft in an earlier run.
        p["held"] = ok_to_email and bool(p["handled"]) and "already said no" not in p["handled"] \
            and "earlier run" not in p["handled"]
        p["draft_by"] = ""
        if not (p["gets_draft"] or p["held"]):
            continue
        if p["ai"]:
            problem = ai.check_draft(p["ai"]["draft_body"], p["ai"].get("facts_used"), p.get("notes_sent"),
                                     plain_thanks=p["next_step"] == "thank-you note")
            if not problem:
                p["subject"], p["body"], p["draft_by"] = p["ai"]["draft_subject"], p["ai"]["draft_body"].strip(), "Claude"
                continue
            p["ai_error"] = f"draft rejected: {problem}"
        if p["ai"]:
            p["detail"] = p["rules_detail"]  # Claude's reading was not trusted for this draft
        p["subject"], p["body"] = draft(p, show)
        p["draft_by"] = "template"
    return {"people": people, "real": real, "unmatched": unmatched, "show": show, "files": files,
            "new_dne": new_dne, "has_activity": bool(activity), "mode": mode, "not_linked": not_linked,
            "given_before": given_before}


def write_outputs(res, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    real = res["real"]
    with open(outdir / "people.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["person_id", "name", "clinic", "city", "locations", "booking_system", "source_rows", "priority",
                    "promised_next_step", "booth_detail", "consent", "email_ok", "already_handled", "sender", "language", "draft",
                    "draft_by", "followed_up", "day30_result", "note"])
        for p in real:
            w.writerow([p["pid"], p["name"], p["clinic"], p["city"], p["locations"], p["system"],
                        "; ".join(p["sources"]), p["priority"], p["next_step"],
                        p["detail"] if p["detail_specific"] else "", p["consent"], p["email_ok"], p["handled"], p["sender"],
                        "French" if p["french"] else "English", "yes" if p["gets_draft"] else ("held" if p.get("held") else "no"),
                        p["draft_by"], p.get("followed_up", ""), p.get("day30", ""), p["ai_error"]])

    def source_line(p):
        bits = []
        for r in p["records"]:
            bits.append(f"{'badge scan' if r['kind'] == 'scan' else 'card'} {r['id']} ({r['by']})")
        bits += [f"voice note {v['id']} ({v.get('time', '')[:16]})" for v in p["voice"]]
        bits += [f"plane list {l['id']}" for l in p["lines"]]
        return ", ".join(bits)

    TAG = {"demo": "DEMO", "trial": "TRIAL", "pricing": "PRICING", "call back": "CALL BACK",
           "send info": "INFO", "thank-you note": "THANKS"}
    for who in ("Owen", "Nadia"):
        mine = [p for p in real if p["gets_draft"] and p["sender"] == who]
        asked = [p for p in mine if p["priority"] == "hot"]
        rest = [p for p in mine if p not in asked]
        held = [p for p in real if p.get("held") and p["sender"] == who]
        promises = [p for p in real if p["sender"] == who and p["ai"] and p["ai"].get("open_question", "").strip()]
        booked = [p for p in real if p["sender"] == who and "already booked a demo" in p["handled"]]
        before = sum(1 for p in real if p["sender"] == who and "earlier run" in p["handled"])
        out = [f"# {who}'s drafts: {res['show']}", ""]
        if before:
            out += [f"Only NEW drafts. {before} people already got a draft in an earlier run and are not repeated.", ""]
        out += [
               f"{len(mine)} drafts: {len(asked)} asked for something, {len(rest)} thank-you notes. Fix a word and "
               f"send from your own email. Cc hello@ so Erin sees replies.", "",
               "## At a glance", ""]
        out += [f"- [{TAG[p['next_step']]}] {p['name']}, {p['clinic']}" for p in asked]
        out += [f"- [{TAG[p['next_step']]}] {p['name']}, {p['clinic']}" for p in rest]
        if promises:
            out += ["", "## Promises to keep (questions you said you'd check)", ""]
            out += [f"- {p['name']}, {p['clinic']}: {p['ai']['open_question'].strip().rstrip('?')}?" for p in promises]
        if booked:
            out += ["", "## Already booked a demo (no email from you, just so you know)", ""]
            out += [f"- {p['name']}, {p['clinic']}: {p['handled']}" for p in booked]
        if held:
            out += ["", f"## Already handled ({len(held)}): drafts at the end of this file, don't send unless you want to", ""]
            out += [f"- {p['name']}, {p['clinic']}" for p in held]
        for title, group in (("Asked for something", asked), ("Thank-you notes", rest),
                             ("Already handled. Don't send unless you want to", held)):
            if not group:
                continue
            out += ["", f"# {title}", ""]
            for p in group:
                out += [f"## [{TAG[p['next_step']]}] {p['name']}, {p['clinic']}", ""]
                if p.get("held"):
                    out += [f"ALREADY HANDLED: {p['handled']}. Don't send unless you want to.", ""]
                out += [f"From: {source_line(p)}", "",
                        f"To: {p['email']}", "Cc: hello@", f"Subject: {p['subject']}", "", p["body"], "", "---", ""]
        (outdir / f"drafts-{who.lower()}.md").write_text("\n".join(out), encoding="utf-8")

    # Gmail filter so replies from show people (only) are forwarded to hello@ for Erin
    out = [f"# Reply forwarding: {res['show']}", "",
           "Owen and Nadia each set this up once per show in Gmail: Settings, Filters, Create a new filter.",
           "Paste the 'From' line, click Create filter, tick 'Forward it to' hello@. Only replies from these",
           "people are forwarded, nothing else in the inbox. (Gmail asks to confirm hello@ the first time.)", ""]
    for who in ("Owen", "Nadia"):
        emails = sorted({e for p in real if p["gets_draft"] and p["sender"] == who for e in p["emails"]})
        chunks, cur = [], []
        for e in emails:  # Gmail filters get unreliable past ~1,000 characters, so split
            if len(" OR ".join(cur + [e])) > 900:
                chunks.append(cur)
                cur = []
            cur.append(e)
        if cur:
            chunks.append(cur)
        for i, c in enumerate(chunks, 1):
            label = f" (filter {i} of {len(chunks)})" if len(chunks) > 1 else ""
            out += [f"## {who}{label}", "", "From:", "", " OR ".join(c), ""]
    (outdir / "reply-forwarding.md").write_text("\n".join(out), encoding="utf-8")

    check = [p for p in real if not p["gets_draft"]]
    out = [f"# No draft written: {res['show']}", "",
           "These are real conversations, but the tool did not write to them. A person decides.", ""]
    late_rows = []
    for p in res["people"]:
        for r in p["records"]:
            if not r.get("late"):
                continue
            name = f"{r['first']} {r['last']}".strip()
            if not p["real"]:
                what = f"no draft: not a real conversation ({p['why_not']})"
            elif p.get("gets_draft"):
                what = f"NEW draft for {p['sender']}"
            elif p["handled"]:
                what = f"no draft: {p['handled']}"
            else:
                what = f"no draft: {p['email_ok'] if p['email_ok'] != 'yes' else 'no email address'}"
            joined = f" (joined to {p['name']}, already in the files)" if len(p["records"]) > 1 else ""
            late_rows.append(f"- {r['id']} {name}, {r['clinic']}{joined}: {what}")
    if late_rows:
        out += [f"## Late cards in this run ({len(late_rows)})", "", "What happened to each card added after the first run.", ""]
        out += late_rows + [""]
    handled = [p for p in check if p["handled"]]
    rest = [p for p in check if not p["handled"]]
    if rest:
        out += ["## Should not be emailed, or a person must check first", ""]
    for p in rest:
        if p["email_ok"] == "check first":
            reason = "badge said don't share, no card handed over, didn't ask for anything. Leave until someone who knows the law says otherwise"
        elif p["email_ok"].startswith("no: asked to be removed"):
            reason = "asked to be removed" + p["email_ok"][len("no: asked to be removed"):] + " (on do-not-email.csv for every show)"
        else:
            reason = p["email_ok"] if p["email_ok"] != "yes" else "no email address"
        out.append(f"- {p['name']}, {p['clinic']} ({p['priority']}, {p['next_step']}): {reason}")
    if handled:
        out += ["", "## Already handled (draft held at the end of Owen's or Nadia's file, not to send)", ""]
        out += [f"- {p['name']}, {p['clinic']} ({p['priority']}, {p['next_step']}): {p['handled']}" for p in handled]
    flagged = [p for p in real if p["ai_error"]]
    if flagged:
        out += ["", "## Claude could not help with these (used the rules instead)", ""]
        out += [f"- {p['name']}: {p['ai_error']}" for p in flagged]
    if res["unmatched"]:
        out += ["", "## Notes the tool could not tie to a person", ""]
        out += [f"- {u['id']}: {u['text']}" for u in res["unmatched"]]
    (outdir / "check-first.md").write_text("\n".join(out) + "\n", encoding="utf-8")

    # decision log: every place the tool chose between files, or linked something to a person
    out = [f"# Decisions: {res['show']}", "",
           "Every place the tool joined records, chose one file over another, or linked a note or a booking to "
           "someone. Check the ones that look wrong; nothing goes to Owen or Nadia until you release.", ""]
    late = [r for p in res["people"] for r in p["records"] if r.get("late")]
    if late:
        out += [f"Late cards in this run: {len(late)} (" + ", ".join(sorted({r['late'] for r in late})) + ")", ""]
    for p in real:
        if p["log"]:
            out += [f"## {p['name']}, {p['clinic']}", ""] + [f"- {x}" for x in p["log"]] + [""]
    if res["not_linked"]:
        out += ["## Bookings and replies not linked to anyone from the show", "",
                "Not counted in the piles. Most come from Google, a podcast or a referral.", ""]
        out += [f"- {e['date_time'][:10]} {e['event']}: {e.get('name', '')} <{e.get('email', '')}> {e.get('detail', '')}"
                for e in res["not_linked"]]
    (outdir / "decisions.md").write_text("\n".join(out) + "\n", encoding="utf-8")

    piles = Counter(p.get("day30", "") for p in real)
    labels = [("demo", "Booked a demo"), ("trial", "Started a trial"),
              ("no reply", "We wrote, nothing came of it"), ("never followed up", "We never wrote to them")]
    out = [f"# Day 30: {res['show']}", "", f"{len(real)} real conversations.", ""]
    for key, label in labels:
        out.append(f"- {label}: {piles[key]}")
    for key, label in labels:
        out += ["", f"## {label}", ""]
        out += [f"- {p['name']}, {p['clinic']} ({p['priority']})" for p in real if p.get("day30") == key]
    (outdir / "piles.md").write_text("\n".join(out) + "\n", encoding="utf-8")

    if res["new_dne"]:
        exists = DNE_FILE.exists()
        with open(DNE_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["email", "name", "date", "reason", "show"])
            if not exists:
                w.writeheader()
            w.writerows(res["new_dne"])


def summary(res, outdir):
    real = res["real"]
    pr = Counter(p["priority"] for p in real)
    drafts = Counter(p["sender"] for p in real if p["gets_draft"])
    none = [p for p in real if not p["gets_draft"]]
    print(f"\nDone: {res['show']}" + ("" if res["mode"] == "claude" else "  (Claude off: rules only)"))
    print(f"  {len(real)} real conversations, out of {len(res['people'])} people scanned or carded")
    print(f"  {pr['hot']} asked for something, {pr['warm']} warm, {pr['cold']} cold")
    print(f"  Drafts ready: Owen {drafts['Owen']}, Nadia {drafts['Nadia']}")
    held = sum(1 for p in real if p.get("held"))
    if held:
        print(f"  Already handled: {held} (draft held at the end of the file, don't send unless you want to)")
    print(f"  No draft: {len(none)}, with the reason next to each name (option 3)")
    late = sum(1 for p in res["people"] for r in p["records"] if r.get("late"))
    before = sum(1 for p in real if "earlier run" in p["handled"])
    if late or before:
        print(f"  Late cards: {late}. Already had a draft from an earlier run: {before} (not repeated)")
    if res["unmatched"]:
        print(f"  Notes the tool couldn't tie to anyone: {len(res['unmatched'])} (option 3)")
    if res["has_activity"]:
        piles = Counter(p.get("day30") for p in real)
        print(f"  Day 30: demo {piles['demo']}, trial {piles['trial']}, wrote but nothing back {piles['no reply']}, "
              f"never written to {piles['never followed up']}")
    if res["new_dne"]:
        print(f"  Added {len(res['new_dne'])} to the do-not-email list")
    print(f"  Results folder: {outdir}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    interactive = not args
    if args:
        folder = args[0]
    else:
        raw = input("Drag the show's folder into this window, then press Enter: ").strip()
        # a dragged folder arrives as /path/with\ spaces or in quotes
        folder = raw.strip("'\"").replace("\\ ", " ").rstrip() or "data"
    folder = Path(folder).expanduser()
    if not folder.is_dir() and not (HERE / folder).is_dir():
        sys.exit(f"I can't find that folder: {folder}")
    if not folder.is_absolute():
        folder = (Path.cwd() / folder) if (Path.cwd() / folder).exists() else HERE / folder
    use_ai = "--rules" not in flags and ai.available()
    if "--rules" not in flags and not use_ai:
        print("  Claude is off (no ANTHROPIC_API_KEY, or the anthropic package is missing). Using the rules.")
    outdir = HERE / "out" / folder.name
    res = build(folder, use_ai=use_ai, payload_file=outdir / "sent-to-claude.json" if "--show-sent" in flags else None)
    write_outputs(res, outdir)
    summary(res, outdir)
    if "--release" in flags:
        print(f"  released {release(res, folder)} drafts: no later run will write to these people again\n")
    if not interactive:
        return
    if sys.platform == "darwin" and sys.stdin.isatty():
        subprocess.run(["open", str(outdir)])  # show Erin the results folder
    menu = {"1": ("drafts-owen.md", "Open Owen's drafts"), "2": ("drafts-nadia.md", "Open Nadia's drafts"),
            "3": ("check-first.md", "Check the no-draft list (who got no draft, and why)"),
            "4": ("decisions.md", "Check the decisions (what the tool chose, and why)"),
            "5": ("piles.md", "Nadia's day-30 piles")}
    n = sum(1 for p in res["real"] if p["gets_draft"])
    released = False
    opened = set()
    if not res["has_activity"]:
        menu["5"] = ("piles.md", "Nadia's day-30 piles (not yet: add the activity export after 30 days)")
    while True:
        print("\nWhat next?")
        for k, (_, label) in menu.items():
            print(f"  {k}  {label}")
        print(f"  r  Released" if released else f"  r  Release the {n} drafts to Owen and Nadia (after you've checked 3 and 4)")
        print("  q  Quit" + ("" if released else " without releasing"))
        pick = input("Type a number or letter, then press Enter: ").strip().lower()
        if pick in ("q", "quit"):
            if not released:
                print("\n  Not released. Nothing has gone to Owen or Nadia. Run it again when you're ready.")
            break
        if pick == "r":
            if released:
                print("\n  Already released.")
                continue
            missing = [k for k in ("3", "4") if k not in opened]
            if missing:
                print("\n  Check first: open " + " and ".join(f"{k} ({menu[k][1].split(' (')[0].lower()})" for k in missing)
                      + ". Release once you've looked through them.")
                continue
            ok = input(f"\n  Release {n} drafts? These people will never get a second draft from this show.\n"
                       "  Type yes and press Enter (anything else cancels): ").strip().lower()
            if ok == "yes":
                release(res, folder)
                released = True
                print(f"\n  Released. Recorded in {GIVEN_FILE} in the show folder. Now share the drafts with Owen and Nadia.")
            else:
                print("\n  Cancelled. Nothing released.")
            continue
        if pick in menu:
            opened.add(pick)
            path = outdir / menu[pick][0]
            if sys.platform == "darwin" and sys.stdin.isatty():
                subprocess.run(["open", "-a", "TextEdit", str(path)])  # easier to read than this window
                print(f"\n  Opened {path.name} in TextEdit.")
            else:
                print("\n" + path.read_text(encoding="utf-8"))
        elif pick:
            print("\n  Please type 1, 2, 3, 4, 5, r or q.")


if __name__ == "__main__":
    main()
