# Seven candidates, 2026-09-05

All seven pass `voice.py` `check()` with zero violations, and both newsletters
pass `check_newsletter()`. That is the floor, not the point. Each one carries a
note on who it reaches and what it costs you.

Ranked by whether a hiring manager in Dubai or Tokyo would think better of you
after reading it. A three-a-week schedule is at the bottom.

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

> **Why it works.** Broad reach: product people and engineers both follow it,
> and the close is the kind of line that gets reshared without your name on it,
> which is a compliment worth having.

---

## E. The check that never ran

**Hook**
A check I wrote had never once run. It looked correct in my editor, in grep, and in the diff.

**Body**
It was meant to catch prices written as Rs. In every tool I had, it read exactly like the pattern I intended.

The bytes on disk were not that. Where the backslashes should have been sat literal backspace characters, put there by a shell heredoc that ate the escape when the file was written.

Every tool that displays a file showed me what I meant, because every one of them renders a backspace as nothing at all.

So the pattern was really demanding a backspace character on either side of the letters. Nothing could ever match it. The check was dead from the day I added it, and dead in a way no amount of rereading could show me.

Printing the compiled function at runtime is what found it. That was 1 of 2 bugs that came out of testing the same feature.

I now do that for any pattern I have not watched fail at least once.

**Close**
A check that has never failed is not a check yet. It is a line you are trusting.

**Hashtags**
#regex #debugging #javascript #shellscripting

> **Why it works.** The most impressive engineering story of the week, and the
> one nobody can fake: a bug that was invisible to the editor, grep and the
> diff simultaneously, found only by printing the compiled function. Senior
> engineers will recognise the specific horror. The close generalises it so
> non-engineers still take something away.

---

## F. From you to them

**Hook**
Placing an order on my site opens WhatsApp and sends the message from the buyer's own number, under their name.

**Body**
Until this week, the first they knew of that was WhatsApp appearing.

Somebody who assumed the site delivered the order for them, and who did not expect to turn up in a stranger's chat under their real name, has a right to know before pressing the button. Not while it is happening.

There is a second thing people miss. The chat opens with the text already in it and nothing is sent until they press send. That is easy to walk away from on a screen that says Order placed and looks finished.

So the form and the confirmation both say it plainly now: WhatsApp opens, the message goes from you to them, and you press send.

Only the buyer making contact gets told. The one who asked to be contacted is hearing what they already agreed to.

It is 3 extra lines of copy.

**Close**
Most of what I shipped this week was code. This is the change I would defend hardest.

**Hashtags**
#productdesign #uxwriting #trustandsafety #campusmarketplace

> **Why it works.** The rarest signal on LinkedIn: someone who shipped a change
> that makes their own funnel slightly scarier because the user deserved to
> know. Nothing here is technical, so it reaches everybody, and the close is
> the strongest single line in the set.

---

## G. A door, not a brochure

**Hook**
People were reading my landing page, understanding the product, and leaving satisfied. Never seeing the shop.

**Body**
That is the failure that does not look like one. No error, no complaint, no number that would alarm you. They arrived, read the pitch, learned what the site is, and left. Never suspecting there was a shop behind it.

Two causes.

The page described instead of asking. Every word above the fold was about the site, and the way in was 2 quiet buttons the same size as each other, so neither read as the thing to do.

And the link everybody pastes is the root, so visit 20 opened the same introduction as visit 1.

The first screen is now a question addressed to the reader, and two doors: the shop, carrying the live count so it reads as a running thing rather than an idea, and selling, deliberately smaller. Anyone signed in goes straight to browsing. The introduction still lives at /welcome for anyone who wants it again.

Everything that was on that page is still on it. Underneath, where an explanation belongs.

**Close**
I spent weeks writing a page that explained the product well. Explaining it well was the problem.

**Hashtags**
#landingpage #conversionrate #productmarketing #campusmarketplace

> **Why it works.** This is the one that is about your actual discipline. You
> are a marketer who can name a conversion failure precisely and fix it in the
> product, not just in the copy. The close is the most quotable thing here.

---

# Newsletter versions

## Newsletter A: the Amazon photos refusal

**Subject**
Why I said no to Amazon product photos

**Body**
Most sellers on ventureadda photograph nothing. They are running a shop out of a hostel room between classes, and 40 items with 40 blank tiles is the normal outcome, not the sad exception. A products page full of grey squares is a products page nobody browses.

The obvious fix was suggested to me, more than once: just pull the photos off Amazon. Everyone does it. The listings are for the same packet of Kurkure.

Here is why I did not. Reselling something you bought is lawful and has nothing to do with the photograph of it. That photograph is a separate work, owned by whoever shot it, and it does not stop being owned because a search engine sat in the middle of the copying. Amazon's own terms forbid the reuse besides. A shortcut that depends on nobody minding is not a foundation, and I am going to be running this thing while I am asleep.

So it searches openly licensed libraries instead. Wikimedia Commons for generic items, and Open Food Facts, a co-operative product database where packaged goods are photographed front-on against a plain ground, for the packets. Searching kurkure now returns 8 actual packets before anything else. Every photograph keeps its creator and its licence, and those print at the foot of the venture page, because the credit is the condition the picture is here under rather than a footnote.

Two things I only learned by trying them. Openverse, my first choice, never answers from Vercel's edge network: the same query returns in a second from my laptop and hangs until the function is killed at 25 seconds. And Cloudinary cannot fetch from Wikimedia, which refuses fetchers it does not recognise, so the browser downloads the bytes and uploads them as an ordinary file instead.

The honest limitation is that it finds generic things well and branded ones badly. There is no openly licensed photograph of one particular energy drink, because that photograph belongs to the company selling it. The dialog says so, rather than letting somebody search four times and conclude it is broken.

**Close**
If you have shipped the slower, licensed version of something, I would like to hear what it cost you.

---

## Newsletter E: the bug the editor could not show

**Subject**
The bug my editor could not show me

**Body**
I had a guard in the price parser meant to catch amounts written as Rs. It had never matched anything, ever, since the day I wrote it.

It looked perfect. In my editor it read as the pattern I intended. In grep, the same. In the diff when I wrote it, the same. Every tool I own agreed with me.

The bytes on disk disagreed. Where the backslashes should have been there were literal backspace characters, written that way by a shell heredoc that ate the escape when the file was created. And a backspace is not a character any of those tools draw: they render it as nothing at all, so what I saw was the pattern minus the invisible parts, which is exactly the pattern I meant to write.

What the compiled pattern actually demanded was a backspace character on either side of the letters. Nothing in any seller's list was ever going to contain that. The check was not weak or subtly wrong. It was dead, and it had been dead from the first commit that added it.

Printing the compiled function at runtime is what found it. Not reading the file. The file was lying, and it was lying identically to every program I could point at it.

That was 1 of 2 bugs that came out of testing the same feature properly. The other was in the format itself: an item with no price sitting directly above a priced one is indistinguishable from a heading, so it was being promoted into one, and every row after it filed underneath.

The rule I took from it: a check I have never watched fail is not a check. It is a line I am trusting because it is shaped like one.

**Close**
What is the bug that took you longest to see because your tools kept agreeing with you?

---

# Three a week

Two weeks of material, spaced so the same flavour never lands twice running.
The mix follows the planner in the bundle: authority, then something personal,
then craft.

| | Post | Angle |
|---|---|---|
| **Week 1, Mon** | A. The Amazon photos refusal | judgment |
| **Week 1, Wed** | F. From you to them | trust |
| **Week 1, Fri** | E. The check that never ran | craft |
| **Week 2, Mon** | G. A door, not a brochure | your discipline |
| **Week 2, Wed** | D. Who should never get the nudge | product |
| **Week 2, Fri** | B. The rocket emoji | craft |

C, the security one, sits outside the schedule on purpose. Post it when you
have decided you want it public, not because a slot came up.

On timing: post in the morning India time and watch what happens for a
fortnight. Any hour I gave you beyond that would be a number I made up, and
your own first ten posts will beat anybody's general advice about when
students and recruiters are awake.

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
