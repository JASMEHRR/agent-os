# The launch series: 6 posts, in order

**Post these first.** Everything in `2026-09-05-candidates.md` assumes a reader
who already knows you build things. Nobody does. Those were week-47 posts
written for someone who has never posted week 1.

This is week 1. It is written for a stranger scrolling past, and each post
stands alone, but read in order they tell one story: a marketer got tired of
waiting for somebody else to build things and learned to build them.

Newsletter is off. All six are LinkedIn only.

## The order, and why

| | Post | What it does |
|---|---|---|
| **Week 1, Mon** | 1. The decision | Establishes who you are and what changed |
| **Week 1, Wed** | 2. What I did not know | The relatable one. Most likely to travel |
| **Week 1, Fri** | 3. How I actually build | Answers the "how, though" that post 2 provokes |
| **Week 2, Mon** | 4. What ventureadda is | Now they know you, show them the thing |
| **Week 2, Wed** | 5. The week it got real | Proves it is not a demo |
| **Week 2, Fri** | 6. Everything I have built | The full list, and the invitation |

Post 1 before post 4 on purpose. A product post from an unknown account is an
advert. The same post from someone whose story you read on Monday is a payoff.

---

## 1. The decision

**Hook**
I used to write briefs for developers. Then I got tired of waiting and described the app to a machine instead.

**Body**
For a long time the pattern was the same. I would see a problem, imagine the product that fixes it, write it up properly, and then wait for somebody with the skills to care about it as much as I did.

Nobody ever did. Not because they were lazy. Because it was my problem, not theirs.

So this year I stopped briefing and started building. Not by learning to code. By learning to describe a system precisely enough that AI could build it, then reading everything that came back until I understood why it worked.

The first thing I shipped is a marketplace for my campus. It is live, and students sell out of hostel rooms on it.

The second is the platform that writes these posts from my commit history. 28 modules, 1,947 tests, first commit 14 days ago.

I still could not write Python from memory. I can tell you what every file in those projects does and why it is there.

**Close**
I am not a developer, and I shipped two products. Both of those are true at the same time.

**Hashtags**
#buildinpublic #promptengineering #campusmarketplace #aitools

---

## 2. What I did not know

**Hook**
4 things I had never heard of at the start of this year: GitHub. Firebase. Deployment. What a database rule is.

**Body**
I am tech savvy. I was not a coder. Those are further apart than they sound, and I found out how far by trying to build something real.

The things I had to be introduced to, roughly in order:

GitHub. I did not know what a repository was. I have several now.

Firebase and Supabase. I did not know what a database rule meant, which is a little embarrassing given I later found a hole in one of my own.

Netlify, Vercel, deployment. I did not know that getting something onto the internet was a separate skill from making it.

Claude Code, Codex, Antigravity. I did not know AI could hold an entire project in its head rather than answer one question at a time.

Error names. I did not know that most errors are a sentence telling you exactly what is wrong, and that learning to read them calmly is most of the job.

None of this came from a course. It was one blocked afternoon at a time, and each one taught me the word for the thing in my way.

**Close**
You do not need the vocabulary before you start. You pick it up on the way, one stuck problem at a time.

**Hashtags**
#learninginpublic #github #firebase #buildinpublic

> **This is the one I would bet on.** Everybody who has ever felt locked out of
> building recognises this list. It is specific, it is checkable, and it costs
> you nothing to admit because you shipped anyway.

---

## 3. How I actually build

**Hook**
I do not write the code. I write the instructions, then read everything that comes back until I understand it.

**Body**
People assume building with AI means typing a wish and watching a product appear. That has not happened to me once.

What it actually looks like:

I describe the problem rather than the solution. A seller cannot photograph 40 items because they are running a shop between classes. That is the input.

Something comes back that half works. I read all of it. Not to judge the syntax, which I could not do anyway, but to check whether it understood the problem.

Usually it did not, and the fix is a better description rather than better code.

I keep the parts that are decisions and throw out the parts that are guesses. Which library to use, it can choose. Whether to take product photos from a company that owns them, I decide.

Then it breaks in front of a real user, and I read the error, and I learn one more word.

Run that loop enough times and it stops being copying and starts being a skill. It is closer to editing than to engineering.

**Close**
Prompting well is not a way around understanding the system. It is the thing that forces you to understand it.

**Hashtags**
#promptengineering #vibecoding #buildinpublic #aitools

> **Why this one matters most for hiring.** Post 2 makes people like you. This
> one makes them take you seriously, because it shows judgement: you can name
> which decisions you keep and which you delegate. That distinction is the
> actual skill, and most people posting about AI cannot articulate it.

---

## 4. What ventureadda is

**Hook**
My campus is full of students running shops out of their hostel rooms. None of them had a storefront.

**Body**
They sell snacks, prints, thrifted clothes, cakes, design work. The whole economy runs on WhatsApp status updates that disappear in 24 hours.

So I built ventureadda, a marketplace for exactly that.

What it had to handle, which an ordinary marketplace does not:

Sellers who photograph nothing, because they are between classes. There is a photo finder that pulls openly licensed pictures, and a ladder of brand logos and initial tiles under that for when it finds none.

Menus that arrive as a pasted WhatsApp message in whatever shape the seller typed it. The parser reads the lists people actually paste, not the tidy ones a parser would prefer.

Orders that go over WhatsApp, because that is where these students already are. The site opens the chat with the message written, and says plainly that it sends from the buyer's own number.

Only students of my college can sell, and that is proved through Google rather than an emailed link nobody opens.

50 commits went into it in one week.

**Close**
It is not a startup. It is a fix for something that annoyed me daily, and now other people use it.

**Hashtags**
#campusmarketplace #buildinpublic #studentfounder #firebase

> **Name the college here if you want to.** You said you have never posted that
> you got in. Swapping "my college" for "Thapar" in the line about who can sell
> does that quietly, inside a post about something you built, which is a much
> better way to say it than an announcement post. Your call, both versions work.

---

## 5. The week it got real

**Hook**
My side project stopped being a side project the week a free tier ran out and took sign-in down with it.

**Body**
Firebase caps how much email it will send on the free plan. My sign-in was an emailed link. So when the cap was reached, nobody could get in, and it did not look like a quota. It looked like the site being broken.

That is the moment a project becomes real. Not launching it. The first time it fails somebody who was counting on it.

Fixing it meant going back to security rules I had written earlier, and finding something worse than the outage. Any address from my college's domain on an account granted selling rights, and it turned out anybody could put any address there from a browser console, proving nothing at all.

I had written that. It had been live.

The fix moved the decision to a server that asks Google which provider each address genuinely came from. 6 commits in one day, all of them because a quota ran out and made me look.

I would like to claim I designed my way to that. An outage did.

**Close**
Nobody warns you that the frightening part of shipping is the part where people start depending on it.

**Hashtags**
#buildinpublic #appsecurity #firebase #studentfounder

> **Same caveat as before.** This says publicly that your live site had a hole.
> After posts 1 to 3 have established that you are honest about what you do not
> know, it reads as maturity rather than incompetence, which is exactly why it
> sits at number 5 and not number 1.

---

## 6. Everything I have built

**Hook**
Everything I have built this year, having not known what a repository was when I started.

**Body**
ventureadda. A marketplace for my campus. Students selling out of hostel rooms get a real storefront, a menu they can paste straight from WhatsApp, and photographs for items they never photographed. Live, with real sellers on it.

Agent OS. The platform underneath my writing. It reads my commit history, drafts posts from it in my own voice, and rejects any draft containing a number it cannot trace back to something I did. 28 modules, 1,947 tests, and deliberately no publish button, because approving is my job and not the machine's.

ClipForge. A video tool, still in progress.

None of these existed at the start of this year. I had a marketing background, a habit of writing briefs for other people to build, and no idea what a repository was.

What changed was not talent. I got specific about problems, and I got good at describing them to something that could build.

That is a learnable skill, and it takes months rather than years. I am the evidence for the low end of it.

**Close**
If you have been waiting for somebody to build the thing you keep describing, that wait is optional now.

**Hashtags**
#buildinpublic #promptengineering #studentfounder #aitools

---

# Check these before you post

All six pass `check()`. What they cannot check is whether the claims are true,
so read this list.

**Numbers I verified myself.** 28 modules and 1,947 tests in Agent OS, and its
first commit 14 days ago, are real as of today. 50 commits in one week on
ventureadda is real for 28 August to 2 September.

**The one number I could not verify.** How long you have been at this. The copy
of ventureadda I can see is a shallow clone, so its history starts partway
through and I cannot tell when you began. Every post says "this year", which is
safe if you started in 2026. If it was late 2025, change those lines.

**Things I took from your own words, not from the repositories.** ClipForge
being a video tool in progress. Your marketing background. That you wrote
briefs for developers before this. If any of that is off, it is off in several
posts at once.

**What I deliberately did not write.** You said you are not good at coding
languages and that you did not want to emphasise it. So no post leads with it,
and no post pretends otherwise either. Post 1 says you could not write Python
from memory and follows it immediately with what you can do, which is the
version of that sentence that helps you. Post 3 makes the method the point
rather than the gap.

**On the word vibe coding.** Post 3 carries `#vibecoding`. It is the accurate
tag and it finds the right audience, but it is also a term some engineers use
dismissively. Drop it if you would rather not hand anyone that framing.

# What happens to the other eight posts

`2026-09-05-candidates.md` stays exactly where it is. Those posts are good and
they are the natural week 3 onwards, once this series has told people who you
are. The four newsletter versions in that file are parked, not deleted.

One thing I cannot switch off from here: the stored prompt for your weekly
scheduled routine still asks for a newsletter issue alongside the LinkedIn
post. That prompt lives in your scheduled task settings rather than in this
repository, so you have to edit it. Post Studio itself already defaults to
LinkedIn only, so nothing to do there.
