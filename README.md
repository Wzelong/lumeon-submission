# Lumeon

*Light over time.* A Gaia DR3 epoch-photometry variability detector for the 1st
InterSystems Programming Challenge, built on InterSystems IRIS in embedded Python.

Given the standard 20-file Gaia DR3 epoch-photometry benchmark, Lumeon finds every
source whose **BP or RP flux changed by more than 100%** across the observation period
and writes the qualifying sources to a CSV. The entire computation runs inside IRIS,
driven by `do ^RunScript`.

## The computation

For each `source_id`, over the valid (non-null, non-NaN, finite) values of the per-epoch
`bp_flux` and `rp_flux` arrays:

```
per band:  percentage_change = ((max_flux - min_flux) / min_flux) * 100
result:    percentage_change = max(BP%, RP%)
keep if:   percentage_change > 100
```

Output — one record per qualifying source, with a header row:

```
source_id, bp_min_flux, bp_max_flux, rp_min_flux, rp_max_flux, percentage_change
```

## How it works

- The 20 benchmark files ship in `data/in/` as gzip-compressed ECSV
  (`EpochPhotometry_000000-003111.csv.gz` … `EpochPhotometry_020985-021233.csv.gz`),
  so every run is judged on identical input with no network access.
- `Lumeon.Challenge.Run()` (`src/Lumeon/Challenge.cls`, embedded Python) reads each file
  directly from disk, skips the `#` ECSV header, and parses **only** the two flux-array
  columns — `bp_flux` at index 11 and `rp_flux` at index 16 of the 48-column schema.
  Invalid tokens are dropped; `min_flux ≤ 0` and bands with no valid epochs are guarded.
- min/max is already an optimal `O(n)` scan, so the speedup comes from **parallelism**:
  the 20 files are independent and are processed across CPU cores with a
  `multiprocessing` pool.
- The pool uses the **`spawn`** start method. Launched from inside the live IRIS process,
  the default **`fork`** inherits IRIS runtime state and deadlocks; spawned children start
  as fresh interpreters and import the standalone pure-Python worker
  (`src/Lumeon/worker.py`) cleanly. This takes the run from **~15 s serial to ~2.4 s**.
- Qualifying sources are written to `data/out/results.csv`.

**Verified correct:** an independent standalone Python reference over the same 20 files
produces the identical result set — **57,099 records, byte-for-byte, zero diff**.

## Run it

Built on the official `intersystems-challenge1-docker-template`. Requires Docker.

```bash
docker-compose up --build -d
docker-compose exec iris iris session iris
```

Then in the IRIS terminal:

```
USER> do ^RunScript
```

`^RunScript` runs the computation, writes `data/out/results.csv`, and prints the record
count and the elapsed wall-clock time:

```
57099 records written to data/out/results.csv
Elapsed time: 2.4 seconds
```

The class and routine compile automatically at image build time (`iris.script`) — no
manual loading. Tear down with `docker-compose down`.

## Benchmarking

The timed section is `Lumeon.Challenge.Run()`, bracketed by `$ZHOROLOG` in
`src/RunScript.mac`, so the elapsed time `^RunScript` prints is the pure compute cost —
it excludes container start and IRIS boot. To reproduce a measurement, build once, then
run `do ^RunScript` three times and take the lowest reported elapsed value:

```bash
docker-compose up --build -d
docker-compose exec iris iris session iris   # then: do ^RunScript  (repeat 3x)
```

Reference: ~2.4 s of embedded-Python compute on a 14-core host. Results are written fresh
each run, so repeated runs are directly comparable.

## Layout

```
src/Lumeon/Challenge.cls   embedded-Python compute (the solution)
src/Lumeon/worker.py       per-file min/max, imported by spawned workers
src/RunScript.mac          entry point moderators run: do ^RunScript
data/in/*.csv.gz           the 20 benchmark files (tracked)
data/out/results.csv       generated output
Dockerfile, docker-compose.yml, iris.script, merge.cpf   IRIS + Docker scaffolding
lab/                       exploratory data-analysis scripts (not part of the run)
```

## Explore the results

The 57,099-row CSV is just numbers. **[lumeon.vercel.app](https://lumeon.vercel.app)** turns
it into a sky you can fly through — every qualifying source becomes a star you can find,
watch, and ask about.

**Fly through the sky.** All 57,099 variable stars are painted into one living Milky Way band:
the more violently a source varies, the brighter and larger it burns, pulling the wildest
stars into a glowing core while calmer ones settle toward the edges. Zoom in up to ~600×, pan
across the field, and click any star to smoothly fly to it. A single toggle re-tints the whole
sky by *which color of light drove the change* — blue when Gaia's BP band swung hardest, red
when RP did.

**Ask the sky in plain English.** The search bar takes real language, not filters — by type
(*"eclipsing binaries," "RR Lyrae pulsators"*), by feeling (*"something restless," "something
violent," "surprise me"*), or by light-curve shape (*"a star that vanishes, then returns"*). A
grounded AI agent answers by searching the real catalog — the stars and numbers it returns are
always real, never invented — and narrates the matches in the warm voice of an old astronomer
at the eyepiece.

**Open any star.** Every star opens a detail card with an animated two-color light curve you
can scrub across to read the exact year and brightness of each real Gaia measurement, plus its
swing (how many times brighter dimmest-to-brightest), epoch count, magnitude, and band. Below
it, a one-of-a-kind description is written *from that star's own measured record* — its rarity
among peers, how it was watched, and the real shape of its curve — so it tells you what *this*
star actually did, not a generic blurb about its class.

**Wander or narrow down.** A rotating Spotlight tours real phenomena hiding in the data — black
holes flickering across billions of years, supernovae, clockwork eclipsing binaries, egg-shaped
stars turning their long side toward us. Or narrow the whole map at once by variability class
(18 of them), brightness, "drama," and band — filters that govern the sky, the search, and the
random-star button together. Live counters track how many stars the community has explored and
how many stargazers have visited.

*The frontend is a separate, optional companion — it plays no part in the benchmarked
computation above.*
