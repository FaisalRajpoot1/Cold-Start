# Design — Cold Start

> How it looks, and why. The page, the stamp, the video, the thumbnail.
>
> **Design principle:** Cold Start produces a **receipt**. Not a dashboard, not a report, not
> an analytics view. A receipt is itemised, it has a total, it is denominated in money, and it
> is *evidence*. Nobody argues with a receipt.
>
> Last updated: 2026-09-26

---

# 1. The One Thing The Screen Must Say

A judge watches for **eight seconds**. In that time, one fact must land:

> ## $1.35 wasted
> **per new hire, on three steps that cannot work**

Everything else on the page is the itemisation that proves it. If the layout ever competes
with that number, the layout is wrong.

**Why money and not the step count.** Every winner at FortyGuard and at AMD put a price on
screen. Both of our losing entries put a measurement on screen. `3 of 14 steps are broken` is
a measurement. `$1.35 wasted per new hire` is a decision — because the reader immediately
multiplies it by their own headcount, and we never have to.

---

# 2. Visual Direction — Black Ink On Paper

**A receipt, printed.** Warm paper, near-black ink, and exactly one other colour: the red of a
correction mark.

## The deliberate deviation

`ui-ux-pro-max` recommends **Dark Mode (OLED)** for this product type and explicitly marks
light mode *"not-recommended"*. **We are overriding it, on purpose.**

The tool optimises for the category. It does not know that at Bob hackathon #1, **6 of 318
repos shipped any visual artifact at all**, and that the ones that did were dark developer
dashboards indistinguishable from one another. Light paper in a field of dark dashboards is
differentiation we can see from across a room, and it photographs far better as a video
thumbnail and a submission-grid cover image.

**Recorded as a deviation, not an oversight.** If it reads badly in rehearsal, the fallback is
the Assay instrument palette, which is already proven.

## The colour rule that makes it look designed

**Passing steps get no colour at all.**

On a real receipt, a correct line item is unmarked. Only the problems get a pen through them.
So: no green ticks, no green tiles, no status pills. A step that worked is simply a line of
black ink.

This is the single decision that stops the page looking like every other AI dashboard, and it
is also more honest — we are not celebrating the nine steps that work, we are pointing at the
three that do not.

## Palette

| Token | Value | Used for |
|---|---|---|
| `--paper` | `#FBFAF7` | Page ground. Warm white, not blue-white, not cream |
| `--paper-edge` | `#F2F0EA` | The perforated strip, the fold shadow |
| `--ink` | `#14110F` | All primary text. Warm near-black, never pure `#000` |
| `--ink-muted` | `#8A8078` | Labels, units, step numbers. Warm grey, not slate |
| `--rule` | `#E0DCD5` | Hairlines, dotted leaders, the tear line |
| **`--stamp`** | **`#C1272D`** | **The correction red. Failures, the wasted total, the stamp. NOTHING ELSE** |
| `--stamp-wash` | `rgba(193,39,45,0.07)` | The tint behind a struck line |

**Seven tokens. One accent.** If a new colour is needed, a decision has been dodged.

`--stamp` is a **stamped-ink red**, not an alert red. `#EF4444` says *system error*. `#C1272D`
says *someone marked this by hand* — which is exactly what the deterministic check does.

**Contrast:** `--ink` on `--paper` is ~16:1. `--stamp` on `--paper` is ~5.9:1. `--ink-muted`
on `--paper` is ~4.6:1. All clear AA for body text.

---

# 3. Typography — IBM Plex

**Both faces are IBM Plex. This is not decoration.**

| Role | Face | Why |
|---|---|---|
| Numbers, costs, durations, step text | **IBM Plex Mono** 400/500/600 | True tabular figures. Columns align without hacks |
| Headings and prose | **IBM Plex Sans** 400/500/600 | Same family, same voice, cohesive |

**IBM Plex is IBM's own open-source typeface.** Setting an IBM hackathon submission in it is a
quiet, correct nod that an IBM judge will register in the first second without being told. It
costs nothing and no other entry will think of it.

```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
```

⚠️ **The font is fetched from Google. The page must still be correct with no network** —
`RULES.md` requires it to render from `file://` offline. So: `font-display: swap`, and a full
local fallback stack (`ui-monospace, "Cascadia Mono", Consolas, monospace`). Fonts degrade.
Layout does not.

## Rules

- `font-variant-numeric: tabular-nums` on **every** element containing a figure. Non-negotiable
  — a money column that shifts as digits change looks amateur instantly.
- Type scale, and nothing between: **12 · 14 · 16 · 20 · 28 · 64**.
- The wasted-money hero is **64px, weight 600, `--stamp`**. It is the largest thing on the page
  by a wide margin.
- Line height 1.45 for prose, **1.3** for the itemised rows — receipts are dense.
- Never bold a whole row. Emphasis comes from colour and the strike, not from weight.

---

# 4. The Page

One column. No navigation, no tabs, no sidebar. It answers one question.

```
        ╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲        ← perforated edge
   ┌──────────────────────────────────────────────┐
   │                                              │
   │   COLD START                                 │
   │   ITEMISED COST OF FOLLOWING CONTRIBUTING.md │
   │                                              │
   │   sqlfluff/sqlfluff @ a3f9c21                │
   │   14 steps · IBM Bob 2.0.5 · 26 Sep 2026     │
   │                                              │
   ├──────────────────────────────────────────────┤
   │                                              │
   │   01  Fork and clone the repo    0:42  $0.31 │
   │   02  Create a virtualenv        0:38  $0.24 │
   │   03  pip install -e .           1:12  $0.48 │
   │ ╔═╗                                          │
   │ ║ ║ 04  Run the grammar tests    0:51  $0.39 │   ← struck, stamp red
   │ ╚═╝     └ test/core/parser/grammar_test.py   │
   │           no such file in this repository    │
   │                                              │
   │   05  Install pre-commit hooks   0:33  $0.21 │
   │ ╔═╗                                          │
   │ ║ ║ 06  Run the dbt tests        1:04  $0.52 │   ← struck
   │ ╚═╝     └ tox env 'dbt019-py310' not in      │
   │           tox.ini                            │
   │   ...                                        │
   │                                              │
   ├╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┤
   │                                              │
   │   TOTAL                        31:04   $4.90 │
   │                                              │
   │   WASTED                        9:42         │
   │                                              │
   │        $1.35                                 │   ← 64px, stamp red
   │        on 3 steps that cannot work           │
   │                                              │
   │   ┌────────────────────────────────────┐     │
   │   │   THE CHECK OVERRULED BOB ON       │     │   ← the stamp block
   │   │   2 OF 9 CLAIMED SUCCESSES         │     │
   │   └────────────────────────────────────┘     │
   │                                              │
   ├──────────────────────────────────────────────┤
   │   Every figure read from Bob's own headless  │
   │   result event. Recordings committed.        │
   │   1 Bobcoin = $0.50 (IBM published rate)     │
   └──────────────────────────────────────────────┘
        ╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲
```

## Rules for the page

| Rule | Why |
|---|---|
| **The wasted figure is above the fold, always** | It is the finding |
| **Dotted leaders** join the step text to its figures | It is what makes it read as a receipt rather than a table |
| **Red appears only on failure** and on the wasted total | One accent, used with discipline |
| **A failed row is struck through + tinted + bracketed** | Never colour alone — `color-not-only`, and it survives greyscale printing |
| Every figure carries its unit or basis | `$0.39` and `0:51`, never a bare `0.39` |
| The reason sits **under** the failed row, in `--ink-muted` | The evidence is right there, not in a tooltip |
| Max width **720px**, centred | Receipt proportions. Wider stops reading as paper |
| **No logos, no charts, no icons, no gradients, no shadows** | See the anti-list below |

## The perforated edge

A CSS-only zigzag (`repeating-linear-gradient`) top and bottom. It sells the metaphor in one
glance and costs nothing. **Two lines of CSS, no image.** Do not add a paper texture, a curl,
a drop shadow or a skew — that tips from designed into kitsch.

---

# 5. The Stamp — The Memorable Image

The single frame the judge remembers, and the cover image.

```
        ╔═══════════════════════════════╗
       ╱  THE CHECK OVERRULED BOB ON   ╱
      ╱       2 OF 9 CLAIMED           ╱
     ╱          SUCCESSES             ╱
    ╚═══════════════════════════════╝
```

- Rotated **−4°**, `--stamp` red, 3px double border, letter-spaced caps
- Slightly transparent so the ink beneath shows through, like a real rubber stamp
- **Appears only if the overrule count is greater than zero.** It is data, not decoration —
  if the check never overrules Bob, there is no stamp and we say so

**This is the AgeBand move.** AgeBand took second at AMD with our exact architecture by
leading with *"a 27B model was fooled, but the deterministic guard held."* Spillguard led with
100% accuracy, showed no save, and placed nowhere. **The stamp is our save, made visible.**

---

# 6. The Before / After

Two receipts, side by side. Same renderer, different committed recordings.

| | Left — before the patch | Right — after |
|---|---|---|
| Struck rows | 3, in red | 0 |
| Stamp | present | absent |
| Wasted | **$1.35** | **$0.00** |

**No animation between them. A hard cut.** Two still frames of the same object, one marked up
and one clean, is a stronger image than any transition — and it is trivially reproducible from
committed data, which a transition is not.

---

# 7. Motion — Almost None

| What | How |
|---|---|
| Struck rows | Appear already struck. **No reveal animation** |
| The stamp | `opacity 0 → 1` plus `scale 1.06 → 1`, **180ms**, once, on load |
| Everything else | Static |

`prefers-reduced-motion: reduce` disables the stamp animation entirely; it renders in place.

**Why so little.** The winning trait at this event was *"the same repository always produces
the same city."* A still, deterministic artifact reads as a **measurement**. Animation reads
as a **presentation**, and invites the question of what is being hidden.

---

# 8. The Anti-List — What This Page Must Never Contain

Every item here is something a generic AI dashboard would add.

- ❌ Gradients. Anywhere.
- ❌ Drop shadows, glassmorphism, blur, glow
- ❌ Rounded cards floating on a grey background
- ❌ A sidebar, a top nav, a breadcrumb, a hamburger
- ❌ Donut charts, sparklines, progress rings, gauges
- ❌ Emoji. Icon fonts. Any icon at all, in fact
- ❌ Green success pills, "✓ Passed" badges, status chips
- ❌ A "Powered by" strip, a logo wall, a hero gradient
- ❌ More than one accent colour
- ❌ Dark mode

**If a reviewer cannot name the page's style in three words, it has drifted.** The three words
are: **paper, ink, stamp.**

---

# 9. Thumbnail And Cover Image

1200×630, and it must be legible at **200px wide** in a submission grid.

**Composition:** the wasted figure, huge, in stamp red, on paper. The overrule stamp beneath
it, rotated. The project name small at the top. Nothing else.

```
   ┌────────────────────────────────┐
   │  COLD START                    │
   │                                │
   │      $1.35                     │
   │      wasted per new hire       │
   │                                │
   │   ╔══════════════════════╗     │
   │  ╱  OVERRULED 2 OF 9    ╱      │
   │  ╚══════════════════════╝      │
   └────────────────────────────────┘
```

**Two elements, one colour.** A thumbnail with four things in it reads as nothing.

---

# 10. Video — 180 Seconds

Beat sheet lives in `PHASES.md`. This is how it should *look*.

| Choice | Decision |
|---|---|
| Format | **Screen capture only.** No talking head — it costs seconds and adds nothing |
| Voice | Calm, plain, unhurried. Explaining a receipt, not selling a product |
| Resolution | 1080p / 30fps. 4K buys nothing on a judging laptop |
| Cuts | **Hard cuts only.** No transitions, no music under narration |
| On-screen text | Two labels only: `$4.90 total` and `$1.35 wasted` |
| Terminal | Real. Show `bob run --format stream-json` actually streaming |

**Open on the document, not on our tool.** Beat one is sqlfluff's CONTRIBUTING.md scrolling
past — an ordinary, reasonable, well-written guide. Establish that it looks fine before
showing that three of its steps cannot work.

**The single most important frame** is the stamp landing. **Hold it for four full seconds in
silence.** Let it land.

⚠️ **≥90 seconds must show the solution working** — a hard hackathon requirement. The parallel
runs streaming and the receipt assembling are that 90 seconds. Budget it before the narration.

---

# 11. Voice

Everywhere: the page, the README, the video, the deck, the PR.

| Do | Don't |
|---|---|
| "Three steps in this guide have drifted from the code" | "Their docs are broken" |
| "The fixture moved to `profiles_yml/`. The doc still points at the old path" | "They forgot to update their docs" |
| "Following this guide costs $4.90. $1.35 of that buys nothing" | "This project is wasting your money" |
| "The check overruled Bob on 2 of 9" | "Bob lied" |
| Short sentences. Figures with units. Dates on claims | Adjectives. Hype. Round numbers with no basis |

**The test, from `RULES.md` §6:** would we be happy for a sqlfluff maintainer to read this
sentence aloud?

sqlfluff's CONTRIBUTING.md has a section headed **"AI-Assisted Contributions."** They invited
this. The receipt is addressed to them, and we are sending the patch.
