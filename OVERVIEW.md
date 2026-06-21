# What This Project Is - In Plain English

*A simple guide to the "Buildable Land Analysis" app. No technical background needed.
If you can read a map, you can understand this.*

---

## 1. The real-world problem it solves

Imagine you own a piece of land and you want to build something on it - a house, a
warehouse, a solar farm. You can't just build on the **whole** plot. Parts of it are
off-limits:

- **Wetlands** - marshy, protected ground you legally can't build on (and you usually
  have to stay a certain distance *back* from them).
- **Floodplains** - areas that flood in a bad storm. Building there is restricted.
- **Power-line easements** - the strip of land under and around high-voltage
  transmission lines, which has to be kept clear.

So the real question every landowner, developer, or surveyor asks is:

> **"Of this whole plot, how much can I *actually* build on?"**

Answering that by hand means staring at several different maps, overlaying them, and
doing a lot of careful measuring. This app does it **automatically, in under a second,
and shows you the answer on a map.**

---

## 2. What you see and do (the experience)

You open the app and see a **satellite map** of a coastal county in Texas (Aransas
County), covered in thousands of property outlines.

**Step 1 - Click a plot of land.**
The app instantly colours it in:
- 🟢 **Green = buildable** (you can build here)
- 🔴 **Red = excluded** (you can't - it's wetland, flood zone, or under a power line)

**Step 2 - Read the summary panel.**
On the side it tells you, in acres:
- the total size of the plot,
- how much is buildable,
- and a **breakdown of *why*** the rest was removed - e.g. "Wetlands took 12 acres,
  flood zone took 4 acres."

**Step 3 - Adjust the rules with sliders.**
Different towns have different rules about *how far back* from a wetland you must stay.
There are **sliders** for this. Drag the "wetland buffer" slider from 50 feet to 100
feet, and the map **redraws live** - the green area shrinks, the numbers update. You
never have to edit any settings files or code to do this.

**Step 4 - Draw your own changes.**
- **"Carve out"** - draw a shape on the map to mark *extra* land as off-limits (maybe
  you know about a problem the data doesn't).
- **"Add back"** - draw a shape to restore land the app excluded (maybe you have a
  permit for it).

Every time you do this, the totals update instantly and **always add up correctly**.

---

## 3. The one rule that makes it trustworthy

The whole app is built around a promise that must *never* break:

> **Buildable land + Excluded land = the whole plot. Always. Exactly.**

It sounds obvious, but it's surprisingly easy to get wrong - because the off-limits
zones **overlap each other** (a wetland can sit inside a flood zone, with a power line
crossing both). A naïve program would count that overlapping ground *twice* and report
nonsense numbers.

This app handles overlaps carefully so that:
- nothing is ever double-counted,
- the breakdown ("wetlands removed X, flood removed Y…") **always sums to the exact
  total removed**, and
- the green + red **always equals the full plot**.

There's an automated test suite whose only job is to keep checking this promise holds.

---

## 4. How it works under the hood (gently)

You don't need this section to *use* the app, but here's the idea in everyday terms.

Think of it like working with **transparent sheets of tracing paper**:

1. **Bottom sheet:** the plot of land you picked.
2. **Overlay sheets:** one for wetlands, one for flood zones, one for power lines.
   Each off-limits area is drawn a little *bigger* than reality, to include the
   required "stay-back" distance (the setback).
3. **Stack them up and look through:** wherever an overlay covers the plot, that part
   is **red (excluded)**. Whatever's still clear is **green (buildable)**.
4. **Measure the green** - that's your buildable acreage.

Two important details that make the measuring honest:

- **Measuring on a flat, true-scale map.** The Earth is round, so the usual GPS
  coordinates (latitude/longitude) distort areas - a mile looks different near the
  equator than near the poles. Before measuring anything, the app converts everything
  into a special "equal-area" map designed for Texas, where an acre is an acre
  everywhere. *All* the measuring happens there, then results are converted back for
  display. This is the single most important technical choice in the project.

- **Only looking nearby.** The county has ~26,000 plots. The app doesn't scan all of
  them every time. It keeps a smart index (like a book's index) so that when you click
  one plot, it instantly grabs only the handful of wetlands/flood zones *touching that
  plot* and ignores everything else. That's why it stays fast no matter how big the
  county is.

---

## 5. Where the data comes from

Everything uses **free, public, official data** - no paid sources:

| Layer | Who publishes it |
|-------|------------------|
| Property boundaries | Aransas County Appraisal District (the local tax authority) |
| Wetlands | U.S. Fish & Wildlife Service (National Wetlands Inventory) |
| Flood zones | FEMA (the federal flood-mapping agency) |
| Power lines | U.S. national infrastructure dataset (HIFLD) |

The app downloads this data **once** into a local file, then runs entirely from that  - 
so after the first download it doesn't depend on the internet.

---

## 6. The two pieces that make up the app

Like most modern software, it has two halves that talk to each other:

- **The "brain" (backend):** does all the geometry and measuring. Written in Python.
  It's the part that takes a plot + the rules and returns "here's what's buildable."
- **The "face" (frontend):** the interactive map you see and click. Written in the
  same kind of technology websites use (React + a free mapping library called
  MapLibre - no paid map keys needed).

The face asks the brain a question every time you click or move a slider, and redraws
the map with the answer.

---

## 7. Honest limits (what it doesn't do yet)

A good engineer is upfront about the edges. This is a focused demo, not a finished
product, and on purpose:

- It covers **one county**. Loading a huge city county would need a proper database
  behind it (a planned next step).
- The official property data occasionally has **overlapping outlines**, so a click can
  rarely grab the wrong one of two stacked plots.
- The "stay-back" distances are **single sensible defaults** you can adjust, not the
  exact local ordinance for every town (the real rules vary by power-line voltage,
  wetland type, and jurisdiction).

None of these are bugs to hide - they're documented trade-offs that show *where* the
project would grow next.

---

## In one sentence

> **It's an interactive map that instantly tells you how much of any plot of land you
> can actually build on - and why the rest is off-limits - with rules you can tweak and
> draw on, where the numbers always add up.**
