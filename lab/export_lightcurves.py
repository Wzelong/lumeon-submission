"""Export light curves for all survivors as sharded columnar-JSON files.

Shard assignment comes from results.json (field "sh") so the two exports always
agree and shards are exactly even (~952 stars each). The frontend reads "sh" off
the in-memory summary row and fetches lightcurves/shard_NN.json on click.

Shard shape (columnar, rounded — the rounding is what keeps gzip small):
  { "<source_id>": [bt[], bf[], rt[], rf[], gt[], gf[]], ... }
  time rounded 4dp, flux rounded 3dp.

Run export_dataset.py first (it writes results.json with the "sh" field).
"""

import csv
import glob
import json
import os

csv.field_size_limit(10**7)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DATA_OUT = os.path.join(os.path.dirname(__file__), "..", "web", "public", "data")
RESULTS = os.path.join(DATA_OUT, "results.json")
OUT_DIR = os.path.join(DATA_OUT, "lightcurves")


def parse(s):
    if not s or len(s) < 2:
        return []
    out = []
    for tok in s[1:-1].split(","):
        tok = tok.strip()
        if not tok or tok in ("NaN", "nan", "null", "None"):
            out.append(None)
        else:
            try:
                out.append(float(tok))
            except ValueError:
                out.append(None)
    return out


def pair(t_raw, f_vals, td=4, fd=3):
    t = parse(t_raw)
    out_t, out_f = [], []
    for ti, fi in zip(t, f_vals):
        if ti is not None and fi is not None:
            out_t.append(round(ti, td))
            out_f.append(round(fi, fd))
    return out_t, out_f


def main():
    with open(RESULTS) as f:
        meta = json.load(f)
    shard_of = {r["id"]: r["sh"] for r in meta["rows"]}
    nshards = meta["shards"]
    print(f"survivors in results.json: {len(shard_of):,}  shards: {nshards}")

    shards = [dict() for _ in range(nshards)]
    files = sorted(glob.glob(os.path.join(DATA_DIR, "EpochPhotometry_*.csv")))
    for f in files:
        with open(f) as fh:
            r = csv.reader(l for l in fh if not l.startswith("#"))
            h = next(r)
            ix = {c: i for i, c in enumerate(h)}
            for row in r:
                sid = int(row[ix["source_id"]])
                sh = shard_of.get(sid)
                if sh is None:
                    continue  # not a survivor
                bt, bf = pair(row[ix["bp_obs_time"]], parse(row[ix["bp_flux"]]))
                rt, rf = pair(row[ix["rp_obs_time"]], parse(row[ix["rp_flux"]]))
                gt, gf = pair(row[ix["g_transit_time"]], parse(row[ix["g_transit_flux"]]))
                shards[sh][str(sid)] = [bt, bf, rt, rf, gt, gf]

    os.makedirs(OUT_DIR, exist_ok=True)
    total = 0
    sizes = []
    for i, shard in enumerate(shards):
        path = os.path.join(OUT_DIR, f"shard_{i:02d}.json")
        with open(path, "w") as fo:
            json.dump(shard, fo, separators=(",", ":"))
        sz = os.path.getsize(path)
        total += sz
        sizes.append((len(shard), sz))

    counts = [c for c, _ in sizes]
    print(f"exported: {sum(counts):,} across {nshards} shards")
    print(f"stars/shard: min {min(counts)} max {max(counts)}")
    print(f"size/shard:  min {min(s for _, s in sizes)/1e6:.2f} MB "
          f"max {max(s for _, s in sizes)/1e6:.2f} MB")
    print(f"total raw: {total/1e6:.1f} MB")


if __name__ == "__main__":
    main()
