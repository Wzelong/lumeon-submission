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

An interactive companion frontend visualizes the full result set as a starfield where
variability drives the glow, with search, filtering, and a natural-language guide to the
stars: **[lumeon.vercel.app](https://lumeon.vercel.app)**. It is a separate, optional
project and plays no part in the benchmarked computation above.
