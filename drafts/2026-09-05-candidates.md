# Four candidates, 2026-09-05

All four pass `voice.py` `check()` with zero violations. That is the floor, not
the point. Ranked below by whether a hiring manager in Dubai or Tokyo would
think better of you after reading it.

## What was wrong with the 2026-09-02 draft

It wrote *about* the commits. The commit messages are better writing than the
post was, and the post paraphrased them into something flatter. Compare:

> **The commit:** "AND THE PASSWORD SCREEN WAS LYING. 'That password does not
> match this address' is a guess. It told people who had nothing to type that
> they had typed it wrong."
>
> **The post:** "The fix wasn't just swapping providers."

The second one is a summary of a summary. Everything below lifts your own
sentences instead, and picks stories the last draft skipped entirely.

---

## A. The Amazon photos refusal  (my pick)

**Hook**
Somebody asked me to pull our product photos off Amazon. I said no and built the slower thing.

**Body**
Most sellers on my site photograph nothing. They run a shop out of a hostel room between classes, so 40 items means 40 blank tiles.

The easy fix is obvious. Go take the picture off Amazon.

Here is the problem with that. Reselling something you bought is lawful. The photograph of it is a separate work, owned by whoever shot it, and that does not stop being true because a search engine sat in the middle.

So: Wikimedia Commons for generic items, Open Food Facts for packaged ones. Searching kurkure now returns 8 actual packets. Every photo keeps its creator and licence, printed at the foot of the venture page, because the credit is the condition the picture is here under.

It finds generic things well and branded ones badly. There is no openly licensed photo of one particular energy drink, because that photo belongs to the company selling it. The dialog says so, instead of letting somebody search four times and decide it is broken.

**Close**
The licensed version took a week longer. It is the only one I can leave running when nobody is watching it.

**Hashtags**
#wikimediacommons #openfoodfacts #campusmarketplace #buildinpublic

> **Why this one.** It is the only post here where you are visibly *choosing*
> rather than *fixing*. Someone asked for the cheap thing, you understood the
> law well enough to refuse, you paid a week for it, and you can state the
> limitation without defensiveness. That is the whole hiring signal in one
> post. The cost line at the end is what stops "I said no" reading as a boast.

---

## B. The rocket emoji

**Hook**
A rocket emoji turned 8 sections of a seller's menu into 9, and every check I had said the parse was fine.

**Body**
My regex matched the rocket as a surrogate pair. Under JavaScript's u flag that is two lone surrogates, which match nothing at all.

So the rocket was never recognised as a bullet. An item with no price in it got read as a section heading instead, and every row after it was filed under one of the venture's own products.

Here is what makes it the bad kind. Nothing failed. The parse succeeded. The row count was correct the whole time. The only way to see it was to read the sections it produced on a real 150 item list and notice one that should not exist.

I match by code point now.

A test asserting the row count would have passed on every run.

**Close**
The bugs that scare me are not the ones that crash. They are the ones that hand back a plausible answer.

**Hashtags**
#javascript #unicode #regex #parsing

> **Why it works.** Engineers will recognise this instantly and it is
> unfakeable: nobody invents surrogate pairs. Narrower audience than A, and a
> non-technical recruiter will skim the middle, but the close lands for anyone.

---

## C. The console-line security hole

**Hook**
Anyone could have given themselves posting rights on my site by typing one line into a browser console.

**Body**
My security rules granted posting rights to any @thapar.edu address in the account's linked identities. That was safe while an emailed sign-in link was the only way into that slot.

It was not the only way. With email and password sign-in enabled, one call to linkWithCredential puts any address you like in there, from the console, proving nothing. Firebase gives the rules no per-address verified flag, so they cannot tell an inbox somebody opened from a string somebody typed.

I found it while fixing something else. The free tier ran out of email sends, which broke the link, which is the only reason I went back and read that rule at all.

The fix asks Google's own record which provider each address came from. A password credential for the same address is a different provider, and it is ignored. Nothing the browser claims is trusted.

6 commits in one day, all of them because a quota ran out.

**Close**
The hole was mine from the start. The outage just made me look at it.

**Hashtags**
#firebase #appsecurity #oauth #campusmarketplace

> **Your call, not mine.** This is the same week as the 09-02 draft but told
> with the fact that draft left out: the hole, not the outage. It reads as
> maturity because the fix shipped first. The thing to decide is whether you
> want a public post saying your live site had a self-service permissions hole.
> Most engineers would respect it. Some recruiters skim and remember only
> "security hole". I would post it. You may not.

---

## D. Who should never get the nudge

**Hook**
The shop that stops trading is exactly the shop that never comes back to mark anything sold out.

**Body**
So its menu keeps offering things that are not there. And nothing on my site could tell that listing apart from one edited yesterday, because nothing recorded when anything was last touched.

Every venture now carries an updatedAt, stamped on save. After 6 weeks the seller gets one question with a one tap answer: is this still right.

Six weeks is the whole design. A seller who is still trading edits something well inside that window. A nudge that fires on the steady ones teaches everybody to ignore it.

Two details I would defend in a review. Still right writes a single field, rather than making somebody open a form of thirty items, change nothing and press Save. And a listing written before the field existed says nothing at all, rather than being accused of being old.

The wording lives in one file with a test, because "1 weeks ago" is the kind of bug nobody notices until it is a screenshot in the group chat.

**Close**
The reminder was the easy half. The hard half was deciding who should never receive one.

**Hashtags**
#productdesign #uxwriting #campusmarketplace #buildinpublic

> **Why it works.** The broadest of the four: product people and engineers both
> follow it, and the close is the most quotable line in the set. Closest to a
> post that gets reshared.

---

## From the commits

- Find a photo for an item nobody photographed  (A)
- Find the actual packet, on white  (A)
- Match emoji bullets by code point, not by surrogate pair  (B)
- Parse the lists people actually paste, not the ones a parser would like  (B)
- Prove a Thapar address on the server, and fix the password screen's lies  (C)
- Prove a Thapar address through Google, with no mail at all  (C)
- Let Google carry sign-in, and open listing to any account  (C)
- Ask a seller whether a stale listing is still right  (D)
- Hand sellers a prompt for their own AI, and fix what it exposed
- Show the moderator what the site has actually done

## The one thing that would make the next batch better

Pick the one that is closest, and paste 2 or 3 posts by other people that you
actually think are good. Not templates, real posts you stopped scrolling for.

Right now there are zero rated samples in the voice library, so every draft is
written against rules rather than examples, and `START_HERE.md` says it
plainly: "Five good examples changes the output more than any amount of rules."
That file is right, and the library is empty.
