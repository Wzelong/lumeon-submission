# Lumeon — Project Brief

*Light over time.* A Gaia DR3 epoch-photometry variability detector for the 1st
InterSystems Programming Challenge.

---

## 1. The task

Using the Gaia DR3 epoch-photometry archive, identify every source whose **BP or RP
flux changed by more than 100%** across the mission, and emit the result set as CSV.

Standard benchmark dataset: the first **20 files** of the archive
(`EpochPhotometry_000000-003111` … `EpochPhotometry_020985-021233`), shipped with the
solution so every submission is judged on identical input.

**Computation** (per `source_id`, over the valid values of the per-epoch `bp_flux` and
`rp_flux` arrays — ignoring null / NaN / non-finite):

```
per band:  percentage_change = ((max_flux − min_flux) / min_flux) × 100
result:    percentage_change = max(BP%, RP%)
keep if:   percentage_change > 100
```

**Output columns:** `source_id, bp_min_flux, bp_max_flux, rp_min_flux, rp_max_flux,
percentage_change`.

**Contract:** individual submission, open-sourced, built on InterSystems IRIS, run
unattended via `do ^RunScript` in the official Docker template.

---

## 2. The solution

All computation runs inside IRIS in **embedded Python** — `Lumeon.Challenge.Run()`
(`src/Lumeon/Challenge.cls`), driven by `src/RunScript.mac`.

**Approach:**
- The 20 files ship as gzip-compressed ECSV in `data/in/`. Each file is read directly
  from disk — no network, no intermediate database table.
- Per file, we stream line by line, skip the `#` ECSV header, and parse **only** the
  two flux-array columns (`bp_flux` at index 11, `rp_flux` at 16 of 48). Invalid tokens
  are dropped; `min_flux ≤ 0` and bands with no valid epochs are guarded.
- The files are independent, so they are processed **in parallel across CPU cores**.

**Why it's fast (and why the obvious approach hangs):** min/max is already optimal
`O(n)` — there is no better algorithm. The win is parallelism. But the default
`multiprocessing` **`fork`** start method *deadlocks* when launched from inside the
live IRIS process (children inherit IRIS runtime state). The fix is the **`spawn`**
start method — children start as fresh interpreters and import a standalone pure-Python
worker (`src/Lumeon/worker.py`). This takes the run from **~15 s serial to ~2.4 s**.

**Verified correct:** an independent standalone Python reference over the same 20 files
produces the identical result set — **57,099 records, byte-for-byte, zero diff**.

---

## 3. Nomination strategy

| Nomination | Stance |
|---|---|
| Code Golf | Concede — not the goal (leaders at ~400 chars). |
| Benchmarking | Compete respectably — ~2.4 s in clean Python. The sub-0.25 s leaders use hand-tuned ObjectScript/C; the Python floor is ~0.5–0.8 s. |
| **Experts** 🎯 | Correct + IRIS-native + embedded Python (+3) + AI Hub (+3). |
| **Community** 🎯 | The visualization frontend (`web/`) + article (+10) + video (+10) — no other entry ships a frontend. |

---

## 4. The frontend (Community track)

`web/` is a Next.js visualization of the result set — a full-screen WebGL starfield
where variability drives glow, with search, filtering, and an LLM "professor" that
answers natural-language questions about the stars. Everything (including the LLM call,
on the OpenAI Responses API) runs inside the one Next.js app; the API key stays
server-side in a route handler. It is **optional** and separate from the benchmarked
computation.

---

## 5. Layout

```
src/Lumeon/Challenge.cls   embedded-Python compute (the solution)
src/Lumeon/worker.py       per-file min/max, importable by spawned workers
src/RunScript.mac          entry point: do ^RunScript
data/in/*.csv.gz           the 20 benchmark files (tracked)
data/out/results.csv       generated output
Dockerfile, docker-compose.yml, iris.script, merge.cpf   IRIS + Docker scaffolding
web/                       optional Next.js visualization (Community track)
lab/                       exploratory data-analysis scripts
```

---

## 6. Dates

- Begins: June 22, 2026
- **Submission deadline: July 26, 2026, 11:59 pm EDT**
