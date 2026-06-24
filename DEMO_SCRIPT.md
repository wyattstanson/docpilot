# DocPilot — Demo Script

A ~4-minute walkthrough for a live interview or a screen recording. Hits every
part of the product: the dashboard, live staleness detection, the Audit/upload
mode (summaries + similarities/differences + syntax errors), and real CI proof.

**Links to have open in tabs**

- Dashboard — https://docpilot-dashboard.onrender.com
- Real fix PR — https://github.com/wyattstanson/docpilot-demo/pull/1
- Marketplace — https://github.com/marketplace/actions/docpilot-self-healing-docs
- Repo — https://github.com/wyattstanson/docpilot

---

## Prep (2 minutes before)

1. **Warm the server** — open the dashboard a minute early so the free-tier cold
   start (~50s) is over before you record.
2. Open **File Explorer** at `C:\Users\HP\docpilot-samples\` so uploads are one click away.
3. Run scenes ③ and ④ once as a dry run so the first (cold) call's latency doesn't show.
4. Close clutter — the custom cursor and splash look best on a clean screen.

---

## Script

### ① Hook — the problem (~20s)
> "Every team has docs that drift out of sync with the code. DocPilot is a GitHub
> Action that detects when a code change makes documentation stale and either opens
> a fix PR or flags it — and this dashboard is its monitoring panel."

Load the dashboard so the **"Welcome to DocPilot"** splash plays on camera.

### ② Overview (~20s)
Point at the hero stats counting up, the activity feed, the health orb.
> "These aren't mocked — they're seeded from the real engine running four staleness
> scenarios."

*Optional flourish:* grab the nav grip, float it, then dock it — shows the polish.

### ③ Live Console → Demo (~45s)
Click **Demo**, run **`renamed_param`**.
> "Watch it think — it parses the diff, queries the link graph, checks with the
> model, and proposes a fix."

Point at the side-by-side diff (`user_id` → `account_id`) and **"Validation gate: passed."**

### ④ Live Console → Audit — the centerpiece (~70s)
Click **Audit**. Upload `partial\notifications.py` + `partial\notifications_docs.pdf`.
> "No diff needed — drop in your code and your docs, even a PDF."

Walk the result top to bottom: the **Summary** (code + docs), **Similarities**,
**Differences**, then the **2 inconsistencies** (SMS param, rate limit) while
**Email and Retries pass**.
> "It summarizes both files, shows where they agree, and pinpoints exactly where
> they diverge."

### ⑤ Syntax detection (~15s)
Swap the code for `syntax-error\broken.py`, re-run.
> "And if the code won't even parse, it tells you exactly where" — point at the
> line-4 banner.

### ⑥ The real proof — CI (~45s)
Switch to the demo PR tab.
> "This is it running for real in GitHub Actions. I opened a PR renaming a
> parameter; DocPilot commented the report and opened this fix PR automatically."

Scroll the DocPilot comment, then click into the fix PR diff.

### ⑦ Close (~20s)
Flash the Marketplace listing.
> "It's published on the GitHub Marketplace, has a labeled accuracy benchmark —
> 91% recall, 0% false positives — and 49 tests. Built like a product."

---

## Sample files (in `docpilot-samples/`)

| Folder | Upload | Shows |
|--------|--------|-------|
| `match/` | `cart.py` + `cart_docs.(md\|pdf)` | 🟢 Consistent |
| `mismatch/` | `payments.py` + `payments_docs.(md\|pdf)` | 🔴 3 inconsistent |
| `partial/` | `notifications.py` + `notifications_docs.(md\|pdf)` | 🟠 2 inconsistent, 2 pass |
| `syntax-error/` | `broken.py` + `order_docs.md` | ⚠️ Syntax error banner |

`partial/` is the best single audit example — it shows match, mismatch, summary
and similarities/differences all on one screen.

---

## Pitfalls to avoid

- The deployed site runs in **mock mode** (free, deterministic) — safe to click
  rapidly. Only a real-LLM build (Groq/OpenAI) has rate limits.
- Run scenes ③ and ④ once before recording so cold-start latency doesn't show.
- If the splash feels long on a re-record, hard-refresh once; it is ~2s.

## Variants

- **60-second teaser:** scenes ① → ④ → ⑥ only.
- **Full 4-minute:** all seven scenes in order.
