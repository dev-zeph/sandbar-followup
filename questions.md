# Sprint 3 interview questions

The clock starts at the first message. Say who each question is for. Ask for files early so they can arrive while we talk.

## Group call (30 min): Nadia, Owen, Erin

### Open (2 min)
1. Nadia: Walk me through the last show, from packing up the booth to now. What happened to the people you met?

### The $9,000 and the 30-day answer (Nadia, 5 min)
2. Nadia: What does the $9,000 cover? Is that the full cost, or booth only (travel, staff time, swag)?
3. Nadia: 30 days after a show, what exactly do you want to be able to say? A number? A list? Who it goes to (board, investors, yourself)?
4. Nadia: What would make a show "worth it" vs "cut it"? Have you ever dropped or kept a show based on gut feel?
5. Nadia: What counts as "brought in": a booked demo, a trial, a signed customer, revenue? How long is your typical sales cycle?

### What happens after the booth (Owen, 8 min)
6. Owen: At the last show, how did you capture each conversation? Badge scanner, cards, phone notes, memory?
7. Owen: When you got back, what did you do with them, and when? How many got a follow-up, and how many days later?
8. Owen: Tell me about one great conversation that went cold. What happened? Why didn't it get followed up?
9. Owen: How do you decide who's hot vs not worth chasing? What words or signals tell you?
10. Owen: Who should NEVER get an email? (competitors, vendors, students, existing customers, people who said no, other exhibitors?)
11. Owen: What does a good follow-up email look like? What do you put in it?

### Data and systems (Erin, 8 min)
12. Erin: Where does the show data end up? Spreadsheet, CRM, inbox? Who owns it?
13. Erin: Do the same people show up in more than one place (scanner list and Owen's notes and cards)? How do you tell they're the same person?
14. Erin: When a lead books a demo or signs up, can you trace it back to the show? Where would that link live?
15. Erin: Is there consent or privacy stuff we need to respect (opt-ins on the scanner, CASL)?

### Files to request (ask by name, any of the three)
- Badge scan / lead export from the last show
- Owen's booth notes (raw, as written)
- Business card list or photos
- CRM / contact export and the demo booking log since that show
- A couple of follow-up emails Owen actually sent (good examples)
- Any list of people who must not be emailed (existing customers, competitors, unsubscribes)
- Costs for each show

### Close (2 min)
16. All: If this works perfectly, what's different the Monday after the next show?
17. All: Anything we haven't asked that you think is the real reason?

## Root-cause probes (use anywhere, don't take the first answer)
- "Why didn't that one get followed up?" then "And why was that?"
- "When did that last happen? What happened next?"
- "How many out of how many?"
- Listen for disagreements between the three. Note who says what.

## Follow-ups (save at least one)
Decide after the group call and after reading the files. Likely candidates:
- Owen: to pin down priority levels and next steps against real rows (what "right" means).
- Nadia: if the 30-day answer is still fuzzy, or to check what she must approve before drafts go out.
- Erin: if duplicates or data formats are the hard part.
Good trigger: the first time the files contradict what someone said.

## Running notes

### Group call (2026-11-02, interview-1.md)
- Toronto: ~$9k, first follow-up 9 days after (24th), only 31 people written to. Nadia wants drafts by Thursday EOD after a Tuesday flight home (17th not 24th), for ALL real conversations.
- 30-day answer = four piles per real conversation: booked a demo, started a trial, written to but nothing came of it, never written to. Purpose: tell Sam/investors if a show was worth it; thinking of dropping one of four shows.
- Notes live in 4 places: badge scans (everyone scanned for espresso draw), business cards (incl. Nadia's blazer pocket), Owen's voice notes, Owen's plane list (~15 lines).
- Root cause story: cards marked demo/pricing/trial were left for Owen by Erin without telling him; Owen worked only off his list, assumed "demo" on a card = handled. So the people who asked for something fell through.
- Drafts come from whoever had the conversation (Owen or Nadia), in French where needed. Erin must be able to see replies (needed for the piles).
- Hard no's: nothing sent automatically; no drafts to drive-bys; nothing personal from voice notes; no new app for Owen; no monthly subscription ($50/show OK); Erin looks after it without Sam and without code.
- Owen: reads on phone at night in hotel, fixes a word, sends from his own email. Robot-sounding = rewritten.
- Consent: share_with_exhibitors Y/N on scan. Erin: scan alone isn't permission, esp. N; card or a direct ask is different; record which one per person. Her template hit 3 people who only had an N scan.
- No do-not-email list (only newsletter unsubscribes + Erin's memory). Removals must stick across shows. Partial consent exists (Amira: pricing yes, mailing list no).
- Hosting: no public link with names. Laptop-must-stay-open is a no. Nadia: "not convinced it's only public link vs my laptop."
- AI: fine if one sentence on what goes in, whether kept, how to turn off. Names + booth talk OK, Owen's personal remarks not.
- Nadia promised to check which browsers they use.
- Must show who said yes to what and how (6 people, no complaints).

### Files (Toronto, Allied Practice Expo, Sep 14-15)
- badge-scans.csv: 150 scans. booth-notes.json: 35 cards, 22 voice notes, 15-line Owen list. after-show-activity.csv: 72 events. erin-recount-toronto.csv: 80 real people, marked by Nadia + Owen (= answer key format).
- Recount: 16 hot / 30 warm / 34 cold. Day 30: 46 never followed up, 24 no reply, 7 demo, 3 trial. 7 of 16 hot people were never followed up.

### Rules the recount implies (checked against all 80 rows)
- Real = scan with notes or a rating (minus drive-by words: student, draw, swag, comp, exhibitor) OR appears on a card / voice note / Owen's list. Blank scans with no other source = drive-by (70 of 150 scans).
- Drive-bys also: students, vendors/exhibitors, insurance reps, event staff, competitor reps (Bookstead, Clinivo).
- Priority: hot = asked for a demo, trial, pricing or a call back. Otherwise warm = 2+ locations OR on paid software (Clinivo, Pracshift, Bookstead). Otherwise cold. 0 mismatches.
- Next step: hot = the ask (demo / trial / pricing / call back). Non-hot = "send info" if they asked for info/brochure/one-pager/something for the owner, else "thank-you note".
- booth_detail: always present for hot/warm, always empty for cold.
- email_ok: "check first" = share N + no card + no ask (3). "no" = asked removal (Monique). Amira = personal pricing reply only.
- Day 30 precedence: demo/trial > wrote and delivered (no reply) > never followed up. A bounce counts as never followed up (Vincent Roy). Replies without demo/trial still = "no reply" pile.
- Matching traps: different emails per source (card vs badge), nicknames (Jen/Jennifer, Steve/Stephen, Raj/Rajesh, Peggy/Margaret, Gord/Gordon), typo'd card emails (orcahrd, birhcwood), same surname different people (MacIsaac x3, Arsenault x2), same clinic different people (Jen + Ravi), bookings by someone else at the clinic (Dr. Feng for Marisol, Bayview front desk, Pottie front desk, Whitecap office@), decoy domain (bayviewphysio-referral = not Bayview), personal emails (Pat Doucet, rajmenon.pt), and non-show leads (Google, podcast, "conference").

### Usability: where it runs (2026-11-02, after plan)
Two separate questions: (A) how Erin runs it once after a show, (B) where Owen and Nadia read the drafts.
- It runs once per show (Wednesday, files in, drafts out), so nothing has to stay open. The phone part is about where the output lands.
- A options: terminal script; folder Erin asks Claude to run (Claude plan = subscription?); Google Apps Script button inside a Sheet (in their Workspace).
- B options: private Google Sheet/Doc in their Workspace (phone apps already there); drafts in Owen's own Gmail drafts (best fit for him, but real inbox is out of scope this week); a file Erin emails/shares; private page behind a login (new login = no).

### Open questions for the follow-ups
- "check first" people: draft or no draft? (Target says no one who shouldn't be emailed gets a draft.)
- Who signs each draft: scanned_by / collected_by? Sophie (Owen scanned, French, Owen said Nadia should write)? Lucie (French title, Nadia's card)?
- Cold people have no booth detail in the recount, but every draft must mention something specific. What should a cold thank-you note mention?
- Where replies go so Erin sees them (Bcc/cc hello@? shared label?).
- Hosting that is not public link and not a laptop left open (they already have Google Workspace).
