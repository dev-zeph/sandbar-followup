"""Claude layer for sandbar.py.

Claude does the fuzzy parts:
  1. ties each voice note and Owen's list line to a person (or says it is unsure)
  2. reads what each person asked for and said at the booth
  3. writes the draft in Owen's or Nadia's voice

Code still does the exact parts (email/phone joins, who is real, consent,
do-not-email, already-handled, day-30 piles) and checks everything Claude returns.

What goes to Anthropic: names, clinic, title, city, and booth notes AFTER personal
remarks (family, health, kids...) are removed on this computer. Results are cached
in .cache/ so a rerun costs nothing. Turn it off: run with --rules.
"""
import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MODEL = "claude-opus-5-5"
CACHE = Path(os.environ.get("SANDBAR_CACHE") or Path(__file__).resolve().parent / ".cache")  # SANDBAR_CACHE: test runs only

# ---------------------------------------------------------------- privacy filter (runs locally, before anything is sent)

SENSITIVE = re.compile(
    r"\b(dad|dads|mom|moms|mum|mother|father|parents?|kids?|kid's|children|son|daughter|wife|husband|"
    r"boyfriend|girlfriend|baby|pregnan\w*|hospital\w*|sick|illness|cancer|surgery|diagnos\w*|funeral|"
    r"passed away|died|divorce\w*|hockey|church|religio\w*)\b", re.I)

# words that must never appear in a draft (sensitive topics + descriptors Owen uses to remember people)
DRAFT_BANNED = re.compile(SENSITIVE.pattern[:-3] + r"|dog|dogs|photos|bow tie|tall guy|lovely guy|small world)\b", re.I)


def redact(text):
    """Drop any clause that touches a sensitive topic. Returns (clean_text, removed_clauses)."""
    if not text:
        return "", []
    parts = re.split(r"(?<=[.;!?])\s+|,\s+(?=(?:oh|and|so|but)\b)", text)
    keep, removed = [], []
    for part in parts:
        if not SENSITIVE.search(part):
            keep.append(part)
            continue
        # keep the harmless pieces of the sentence (names, clinic), drop only the personal piece
        pieces = re.split(r",\s*|\s+-\s+", part)
        good = [x for x in pieces if x.strip() and not SENSITIVE.search(x)]
        removed += [x.strip() for x in pieces if SENSITIVE.search(x)]
        if good:
            keep.append(", ".join(good).rstrip(".") + ".")
    return " ".join(keep).strip(), removed


# ---------------------------------------------------------------- client and cache

def load_env_file():
    """Read KEY=VALUE lines from .env next to this file (never printed)."""
    env = Path(__file__).resolve().parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def available():
    load_env_file()
    if os.environ.get("SANDBAR_RULES_ONLY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


_client = None


def client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(max_retries=4)
    return _client


def _cached_call(kind, system, user, schema, effort="medium", max_tokens=16000):
    key = hashlib.sha256(json.dumps([MODEL, kind, system, user, schema, effort], sort_keys=True).encode()).hexdigest()
    path = CACHE / kind / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    import anthropic
    kwargs = dict(
        model=MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        betas=["server-side-fallback-2026-07-01"],
    )
    try:
        resp = client().beta.messages.create(fallbacks="default", **kwargs)
    except TypeError:
        resp = client().beta.messages.create(extra_body={"fallbacks": "default"}, **kwargs)
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Claude API error {e.status_code}: {e.message}") from e
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Claude's answer was cut off (max_tokens)")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


# ---------------------------------------------------------------- 1. tie notes to people

MATCH_SYSTEM = """You help a small Canadian booking-software company (Sandbar Scheduling) sort its trade-show notes.
You get a list of people met at the booth (from badge scans and business cards, already merged by email/phone)
and a list of short notes: Owen's voice notes (phone transcripts, names often misspelled by sound) and the
list Owen typed on the plane (nicknames, shorthand). For each note, say which person or people it is about.

Rules:
- Match on meaning: first name or nickname (Jen = Jennifer, Gord = Gordon, Dan = Daniel), surname heard by
  sound, clinic name, city, job, number of clinics, booking system, and what was asked.
- A list line may describe someone without a name; use the voice notes as context to work out who.
- One note can be about two people (for example a clinic owner and her business partner). Then return both, and
  for each put only the part of the note that is about that person in text_about_them.
- A note may be about a conversation another staff member had; still match the person.
- Different people can share a surname or a clinic word. Do not merge people because of a surname alone.
- If you are not sure, set confidence to "unsure". If a note is about nobody in the list (a general remark),
  return no matches. Never invent a person_id."""

MATCH_SCHEMA = {
    "type": "object",
    "properties": {"assignments": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "note_id": {"type": "string"},
            "matches": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "person_id": {"type": "string"},
                    "text_about_them": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["sure", "unsure"]},
                },
                "required": ["person_id", "text_about_them", "confidence"],
                "additionalProperties": False,
            }},
        },
        "required": ["note_id", "matches"],
        "additionalProperties": False,
    }}},
    "required": ["assignments"],
    "additionalProperties": False,
}


def match_notes(candidates, notes):
    """candidates: list of dicts {id, names, title, clinic, city, domain, met_by, notes}
    notes: list of dicts {id, kind, text} (already redacted).
    Returns {note_id: [(person_id, text_about_them)]} with only sure, valid matches."""
    people_txt = "\n".join(
        f"{c['id']} | {' / '.join(c['names'])} | {c['title']} | {c['clinic']} | {c['city']} | "
        f"@{c['domain']} | met by {c['met_by']} | notes: {c['notes'] or '-'}" for c in candidates)
    notes_txt = "\n".join(f"{n['id']} ({n['kind']}): {n['text']}" for n in notes)
    user = f"PEOPLE\n{people_txt}\n\nNOTES\n{notes_txt}\n\nReturn one assignment per note id."
    data = _cached_call("match", MATCH_SYSTEM, user, MATCH_SCHEMA, effort="high")
    valid = {c["id"] for c in candidates}
    out = {}
    for a in data.get("assignments", []):
        hits = [(m["person_id"], m["text_about_them"]) for m in a.get("matches", [])
                if m["confidence"] == "sure" and m["person_id"] in valid]
        out[a["note_id"]] = hits
    return out


# ---------------------------------------------------------------- 2 + 3. read the person, write the draft

PERSON_SYSTEM = """You help Sandbar Scheduling (online booking for physio and massage clinics) follow up after a trade show.
You get everything recorded about ONE person met at the booth. Do two things.

A) Read the notes:
- ask: what they explicitly asked Sandbar for: "demo", "trial", "pricing", "call back", or "none".
  A word with a question mark ("demo?", "trial?") is the note-taker's guess, not an ask. "not a demo" is not
  an ask for a demo. If the notes disagree, trust the voice note and Owen's list over the badge shorthand.
  "$" or "price per practitioner" means pricing. Wanting a call later ("call me once...", "call after...") is "call back".
- asked_for_info: true if they asked for info, a brochure, a one-pager, a security document, or something to show
  the owner (and ask is "none").
- locations: number of clinics/sites/locations (default 1).
- booking_system: what they use now. Mentioning a system they LEFT does not count.
- booth_detail: one specific business thing THEY said or care about (a pain, a wish, a question), in plain words.
  Never personal or family matters, health, hobbies, or how they look.
- no_mailing_list: true if they said not to add them to a mailing list or newsletter.
- open_question: a question THEY asked that nobody answered at the booth (for example "can reminders go out in
  Mandarin?"), in a few plain words. Empty string if none.

B) Write the follow-up email draft from the sender named below, as if written two days after the show:
- Sound like a real person who met them: short (50 to 110 words), plain, warm, no hype, no buzzwords,
  no exclamation marks except at most one, no em dashes, no "I hope this email finds you well".
- Open with exactly "Hi <greet>, great to meet you in <show city>." (French: "Bonjour <greet>, ravie de vous avoir
  rencontré(e) à <show city>.") and go straight to the next step in the next sentence. Never write "thanks for
  stopping by", never name the booth or the show: they know where they met.
- Then mention the booth_detail naturally, in their words where possible.
- Do exactly the next step given below and nothing more. Use placeholders: [booking link], [trial link],
  [pricing attached], [one-pager attached], [security one-pager attached]. For a call back, say when you'll call
  if the notes say when.
- If no_mailing_list, say plainly you have kept them off the mailing list.
- Write in the language given. Sign with the sender's first name only.
- Never mention anything personal, family, health, appearance, or how Owen remembers them.

C) Stick to what is in the notes. This matters most:
- Every fact about them (their clinics, staff, software, problems, questions, plans, timing) must come from
  the notes about THIS person. Do not add details, guess numbers, or borrow from typical clinics.
- Do not describe what Sandbar does, how it works, or what a feature would do for them, unless a note says
  Owen or Nadia already told them that at the booth. If they asked a question nobody answered, say you'll
  answer it (or go through it on the demo); do not answer it yourself.
- Do not describe what the pricing, one-pager or trial contains ("per practitioner", "tiers", "includes...").
  Just say it is attached or linked.
- No promises beyond the next step (no discounts, set-up help, migrations, deadlines) unless a note says so.
- facts_used: copy, word for word, each short piece of the notes that the draft relies on (3 to 15 words
  each, exactly as written in the notes, including misspellings). If a sentence in the draft states a fact
  about them, its source must be in facts_used."""

PERSON_SCHEMA = {
    "type": "object",
    "properties": {
        "ask": {"type": "string", "enum": ["demo", "trial", "pricing", "call back", "none"]},
        "asked_for_info": {"type": "boolean"},
        "locations": {"type": "integer"},
        "booking_system": {"type": "string", "enum": ["Clinivo", "Pracshift", "Bookstead", "Google Calendar",
                                                       "spreadsheet", "paper book", "other", "unknown"]},
        "booth_detail": {"type": "string"},
        "no_mailing_list": {"type": "boolean"},
        "draft_subject": {"type": "string"},
        "draft_body": {"type": "string"},
        "facts_used": {"type": "array", "items": {"type": "string"}},
        "open_question": {"type": "string"},
    },
    "required": ["ask", "asked_for_info", "locations", "booking_system", "booth_detail", "no_mailing_list",
                 "draft_subject", "draft_body", "facts_used", "open_question"],
    "additionalProperties": False,
}

NEXT_STEP_TEXT = {
    "demo": "offer to book the demo they asked for",
    "trial": "give them the trial they asked for",
    "pricing": "send the pricing they asked for",
    "call back": "confirm you will call them as promised",
    "send info": "send the info / one-pager they asked for",
    "thank-you note": "a short thank-you with a soft, no-pressure offer to show them more",
}


def read_person(payload):
    """payload: dict with name, greet, clinic, title, city, sender, language, show, notes (list of 'source: text').
    The next step is not known yet, so Claude is asked to pick it from its own reading:
    we pass the rule so the draft matches what code will compute."""
    user = (
        f"Show: {payload['show']} (ended {payload['show_end']}). Show city: {payload['show'].split(' in ')[-1]}\n"
        f"Person: {payload['name']} (greet as {payload['greet']}), {payload['title']}, {payload['clinic']}, {payload['city']}\n"
        f"Sender: {payload['sender']}    Language: {payload['language']}\n\n"
        "Notes about them:\n" + "\n".join(f"- {n}" for n in payload["notes"]) + "\n\n"
        "Next step for the draft: if ask is not none, do that ask. Otherwise, if asked_for_info, send the info. "
        "Otherwise a thank-you note."
    )
    return _cached_call("person", PERSON_SYSTEM, user, PERSON_SCHEMA, effort="medium")


def read_people(payloads, workers=6):
    def one(p):
        try:
            return read_person(p), None
        except Exception as e:  # noqa: BLE001 - any failure falls back to rules for this person
            return None, str(e)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, payloads))


def _plain(text):
    return " ".join(re.sub(r"[^\w$]+", " ", text.lower()).split())


def check_draft(body, facts_used=None, notes=None, plain_thanks=False):
    """Return a reason if the draft is not safe to show, else ''.
    Removed personal clauses were never sent to Claude, so this is a second net.
    With notes given, every fact Claude says it used must really be in the notes.
    A plain thank-you note may use no facts (some cards say nothing)."""
    if notes is not None:
        source = _plain(" ".join(notes))
        if not facts_used and not plain_thanks:
            return "no facts from the notes"
        made_up = [f for f in facts_used if _plain(f) and _plain(f) not in source]
        if made_up:
            return f"uses something not in the notes: '{made_up[0][:60]}'"
    m = DRAFT_BANNED.search(body)
    if m:
        return f"mentions '{m.group(0)}'"
    if "—" in body:
        return "has an em dash"
    return ""
