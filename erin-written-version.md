# Sandbar show follow-up: how it works (for Erin)

Draft for Erin to read on Thursday. Nothing here sends an email. Every email is sent by a person, from their own inbox.

## 1. What we agreed

- Drafts come from whoever had the conversation (Owen, or Nadia in French where needed).
- The order every time: the tool runs, Erin checks the flags and the matches, and only after Erin says OK do the drafts go to Owen and Nadia.
- Replies: Owen's Gmail forwards replies from that show's people (and only them) to hello@, so Erin can see what came back and count the four piles. The tool writes the filter for each show. Gap: a reply from a different address at the clinic (like a front desk) is not caught, and Owen forwards those himself.
- No draft, ever, for:
  - drive-bys (blank scans, students, other exhibitors, competitors)
  - anyone who asked to be removed (kept on a do-not-email list that every future show checks)
  - anyone whose badge said "don't share" who didn't hand over a card or ask for anything. They go on Erin's list with the reason, and stay there until someone who knows the law says otherwise.
  - anyone Owen or Nadia already wrote to personally
  - anyone who already booked a demo (listed for Owen instead, so he knows)
- Someone who started a trial, and hasn't been written to, gets two lines: "Glad you're trying it, I'm around if you get stuck."
- Questions Owen promised to check (for example "can reminders go out in Mandarin?") are listed at the top of his drafts for him to chase.

## 2. After each show (Erin)

1. Download the scan export from the badge portal. Do this first: the link stops working 30 days after the show.
2. Make a new folder for the show, for example "Halifax 2027". Put in it: the scan export and the booth notes file. After 30 days, add the activity export to the same folder.
3. Double-click "Run Sandbar" in the Sandbar folder. A window opens and asks which show. Drag the show folder into the window and press Enter.
4. Wait about two minutes. When it says done, the results folder opens.
5. Check before anything goes to Owen:
   - check-first.md: who got no draft and why, and any note the tool could not tie to a person.
   - decisions.md: every place the tool joined two records, picked one email over another, tied a voice note to someone, or linked a booking to someone from the show, with the reason. At the bottom: bookings it did not link to anyone (Google, podcast, referrals).
   - The "From" line on each draft says which scan, card or voice note it came from.
6. When you're happy, press r (release) and type yes. The tool writes down everyone who got a draft (drafts-given.csv in the show folder), so no later run ever writes to them again. Then send Owen and Nadia their drafts (see section 4), and give Owen the reply filter (reply-forwarding.md) to paste into Gmail.

Late cards (for example Nadia's, weeks later): type them into a file called late-cards.csv in the same show folder (columns: name, title, clinic, email, phone, back_of_card, collected_by) and run it again. Only people who haven't had a draft get one. Everyone already released is listed as "already got a draft" and is not repeated.
7. At day 30, add the activity export to the folder and run it again. piles.md gives Nadia's four piles.

(Mac or Windows decides how "Run Sandbar" is built. Erin is checking with Sam.)

## 3. What comes out

| File | What it is |
|---|---|
| drafts-owen.md | Owen's drafts. A list at the top, people who asked for something first, then trials, then thank-you notes. Above the drafts: questions he promised to check, and who already booked a demo. |
| drafts-nadia.md | Nadia's drafts, in French where needed. |
| check-first.md | Who got no draft, with the reason next to each name. |
| piles.md | Day 30: booked a demo, started a trial, written to with nothing back, never written to. |
| people.csv | One row per real conversation. |
| reply-forwarding.md | The Gmail filter for Owen and for Nadia (show people only, to hello@). |
| decisions.md | What the tool decided between files, and why: joins, emails, voice notes, bookings. |
| drafts-given.csv (in the show folder) | Everyone released a draft for this show. Don't delete it: it is what stops second emails. |
| do-not-email.csv | Everyone who asked to be removed. Carries over to every show. Don't delete it. |

## 4. Getting drafts to Owen's phone

- First version: the results go into a shared Google Drive folder that only Owen, Nadia and Erin can open. Never "anyone with the link".
- Later, if Owen wants it and approves it himself: the drafts go straight into his Gmail drafts folder, only after Erin's check. The access can create drafts only, never send. Not built this week.
- Switching that access off (when it exists): Owen goes to myaccount.google.com, then Security, then "Your connections to third-party apps & services", picks the Sandbar connection, and removes access. Drafts already in his folder stay there until he deletes them.

## 5. Not decided yet (for Nadia)

- Who runs this when Erin is away. Nobody has been named.
- Mac or Windows for "Run Sandbar" (Erin is checking with Sam).
- Whether Owen's drafts go straight into his Gmail later (Owen approves; Erin checks first).

## 6. The AI part (for Nadia and Sam to decide)

The tool uses Claude, made by Anthropic, to tie voice notes to people, read what each person asked for, and write the drafts. Plain code does the rest: who is real, consent, the do-not-email list, the piles.

The one sentence: Names, clinic, job, city and booth notes go to Anthropic after anything about family, health or kids is removed on this computer. Anthropic doesn't use it to train its models by default, and deletes it within 30 days (longer only if it breaks Anthropic's rules or the law requires it). Turning it off is one setting, and then nothing leaves the computer.

Where this comes from (Anthropic's own privacy pages, checked Nov 3, 2026):
- Training: "By default, we will not use your inputs or outputs from our commercial products", and the Anthropic API is one of them. Source: https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training (updated Aug 18, 2026)
- Retention: "we automatically delete inputs and outputs on our backend within 30 days of receipt or generation", except where agreed otherwise, to enforce their Usage Policy, or where the law requires it. Content flagged for breaking the policy can be kept up to 2 years. Source: https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-personal-data (updated Jul 1, 2026)

The tool also keeps a copy of Claude's answers on this computer (the .cache folder), so running a show again costs nothing. Deleting that folder removes them.

Cost: about $2 to $3 per show, paid for what it uses. No monthly subscription.
