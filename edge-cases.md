# Edge cases (Sandbar, from the Toronto files)

Each one: what it looks like, a Toronto example, and what goes wrong if we miss it.

## A. One person, many records (must come out ONCE)

1. Scanned twice, same badge. Kevin LeBlanc (S001, S091 "came back"), Lorne, Chantal, Rebecca, Zoe, Glen, Dan Pothier. Miss it: two drafts to one person.
2. Badge and card with different emails. Jen (jennifer.macisaac@ vs jen@), Steve (steve.lau@ vs slau@), Peggy (peggy@ vs mobrien@), Raj (clinic vs personal). Erin's template already wrote to Jen twice and to Victor at both addresses. Miss it: two drafts.
3. Card uses a shared inbox. frontdesk@ (Freya, Victor), info@ (Andrea, Emeka). Miss it: duplicate, or a draft to the wrong inbox.
4. Nicknames. Jen/Jennifer, Steve/Stephen, Gord/Gordon, Raj/Rajesh, Peggy/Margaret, Dan/Daniel, Pat/Patrick (Doucet booked as "Pat").
5. Initials and titles on cards. "V. Ward", "V. Roy", "N. Chen", "S. Rossi", "A. MacDonald", "Dr. J. MacIsaac, DPT", "Dr. Stephen Lau, DC", "Mei Lin Zhou, R.Ac, RMT", "Hélène Arsenault, pht".
6. Typo in the card email. vincent.roy@orcahrdphysio (bounced), gsingh@birhcwoodphysio. Phone still matches. Miss it: duplicate, and a draft to a dead address.
7. Phone written differently. "(902) 555-0135", "902.555.0135", "519-555-0164 x2".
8. Same card given to Owen AND Nadia. Steve (C03, C28), Ines (C21, C32).
9. Owen's list names one person twice as if two. L01 "Dr. MacIsaac" and L06 "Jen from Bayview".
10. Voice note corrects an earlier one. V15 updates V03 (Jen's demo: Monday the 28th, copy ops manager).
11. Voice note spelled by sound. "derek oh say" (Osei), "gord potty" (Pottie), "sophie trembly", "clean evo" (Clinivo), "book stead", "ellen or helen".
12. Names in capitals. "DOT OXNER", "ADA JESSOME".
13. Second-hand note. V07 is Owen recording Nadia's conversation with Hélène. It's Nadia's person, not Owen's.
14. Only a voice note or list line, no email. Owen's list says "guy who knew Sam", "ottawa massage lady w the dog pics", "fredericton RMT guy". They have to be tied to someone through the voice notes.
15. Scanner down, so card only. Farah, Tyler (12:30 to 13:45 on day 2). There's no badge and no share flag.

## B. Different people who look like one (must NOT merge)

16. Same surname. MacIsaac x3 (Jen, Colin, Kayla the student), Arsenault x2 (Hélène, Nicole), Hachey (Melanie, Brett), Gaudreau x3, Hanlon x4.
17. Same clinic, two people. Jen and Ravi at Bayview, both hot with different asks (demo vs pricing per practitioner). One voice note (V03) covers both.
18. Same city and job. Two Fredericton RMTs: Liam (real) and Brett (drive-by). Owen's list only says "fredericton RMT guy".
19. Look-alike clinic names. Seaglass Physiotherapy vs Seaglass Physio, Heron x2, Dune x2, Fogbank x2, Wharf x2, Breakwater x2, Dockside x2. All different clinics. Bayview Physio vs Bayview Physiotherapy & Wellness is the SAME clinic.
20. Decoy email domain. bayviewphysio-referral is not bayviewphysio.
21. Possible on Friday: two people at one clinic sharing the main phone line. Not in Toronto, but a phone match would wrongly merge them.

## C. Already handled (like last sprint's "already has the appointment")

22. Booked or started a trial before anyone wrote. Patrick (demo), Farah (trial), Heather's clinic (demo). A "here's my booking link" draft would be wrong. They need a "see you at the demo" note.
23. Someone else at the clinic booked for them. Dr. Feng for Marisol, the Bayview front desk for Jen, the Pottie front desk for Gord, office@ at Whitecap for Heather. The email doesn't match the person, but it IS them.
24. Already said no. Hugo: "We just signed another two years with Clinivo." A sales draft would be tone-deaf.
25. Asked to be removed. Monique, Darcy. This must hold for every future show.
26. Already written to by Owen personally. Steve, Derek, Jen, Gord, Marisol, Dan, Ben, Raj. A second draft = written to twice.
27. Bounced. Vincent's card address bounced, but the badge address works. Bounced does not count as followed up.
28. Out-of-office reply. Elliot. Not a real reply and not a result.
29. Promise has a date. "Call after Thanksgiving" (Hélène), "back on the 5th" (Patrick), "week of the 28th" (Jen), "once the new place opens" (Shauna). The draft must not offer a time the person ruled out.
30. Might already be a customer. Erin's CRM has ~1,900 contacts. We don't have it, so we can't check.

## D. Who is real, and consent

31. Opted in, but "draw - didnt talk" (Lyle), "espresso draw" (Kendra), "swag". Not real.
32. Real-sounding job at a vendor or competitor. Bookstead rep, Clinivo rep, CoreFlex, Northern Orthotics, BrightPath Insurance, event staff. Not real.
33. Badge says don't share, but card given. Natalie: OK to email. Badge says don't share, no card, no ask: check first (Dara, Hannah, Melanie).
34. Badge says don't share, but asked for something. Amira: pricing only, no mailing list.
35. Blank scan rescued by a voice note. Amira's scan is blank. Only V05 makes her real.

## E. Writing the draft

36. Personal details in notes. Grace's father in hospital, Lucie's kids' hockey, "lady with the dog photos", "bow tie guy", "lovely guy", "retiring in 2 yrs?". These must never reach a draft.
37. Who signs. Both met them (Kevin, Lorne, Lucie). French speakers (Hélène, Sophie, Lucie) go to Nadia.
38. Uncertain ask. "demo?" (Gord's scan, but he wants a trial), "pricing + trial?" (Raj, pricing wins), "not a demo".
39. Decision maker isn't the contact. Marisol (owner Dr. Feng), Peggy, Ben, Nathan: the draft is "something for your owner".

## F. Counting the day-30 piles

40. Booking not from the show. Google, podcast, Instagram, "a colleague", "conference" (Paula). Don't count.
41. Referral from a show contact. Corinne Abbott, "referral from Bayview". She's not a booth conversation. Question for Nadia: does it count for Toronto?
42. Events after day 30 shouldn't count.
