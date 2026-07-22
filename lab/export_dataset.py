"""Build the static dataset for the web app from the local DR3 CSVs.

Phase 1 — results.json: the summary list that powers the canvas + filters +
search. One compact record per survivor (percentage_change > 100):

  id   source_id
  ra   right ascension  (deg, decoded from source_id via HEALPix-12)
  dec  declination      (deg)
  pct  percentage_change  = max(BP%, RP%)
  bmin bmax  BP min/max flux
  rmin rmax  RP min/max flux
  nbp  nrp   valid epoch counts (for the 'min epochs' filter)
  band 0 = BP drove the max, 1 = RP   (for the band filter)

Light curves (the large per-star arrays) are exported separately, on demand.
"""

import csv
import glob
import json
import math
import os

from astropy_healpix import HEALPix
from astropy.coordinates import ICRS

csv.field_size_limit(10**7)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(os.path.dirname(__file__), "..", "web", "public", "data", "results.json")
THRESHOLD = 100.0
SHARDS = 60

_hp = HEALPix(nside=2**12, order="nested", frame=ICRS())


def radec(source_id):
    c = _hp.healpix_to_skycoord(source_id >> 35)
    return round(float(c.ra.deg), 4), round(float(c.dec.deg), 4)


def minmax(s):
    if not s or len(s) < 2:
        return None, None
    lo = hi = None
    for tok in s[1:-1].split(","):
        tok = tok.strip()
        if not tok or tok in ("NaN", "nan", "null", "None"):
            continue
        try:
            v = float(tok)
        except ValueError:
            continue
        if math.isnan(v) or math.isinf(v):
            continue
        if lo is None or v < lo:
            lo = v
        if hi is None or v > hi:
            hi = v
        # count handled by caller
    return lo, hi


def count_valid(s):
    if not s or len(s) < 2:
        return 0
    n = 0
    for tok in s[1:-1].split(","):
        tok = tok.strip()
        if tok and tok not in ("NaN", "nan", "null", "None"):
            n += 1
    return n


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "EpochPhotometry_*.csv")))
    records = []
    seen = 0
    for f in files:
        with open(f) as fh:
            reader = csv.reader(l for l in fh if not l.startswith("#"))
            header = next(reader)
            ix = {c: i for i, c in enumerate(header)}
            for row in reader:
                seen += 1
                sid = int(row[ix["source_id"]])
                bp = row[ix["bp_flux"]]
                rp = row[ix["rp_flux"]]
                bmin, bmax = minmax(bp)
                rmin, rmax = minmax(rp)
                bpct = (bmax - bmin) / bmin * 100.0 if (bmin and bmin > 0) else None
                rpct = (rmax - rmin) / rmin * 100.0 if (rmin and rmin > 0) else None
                cands = [p for p in (bpct, rpct) if p is not None]
                if not cands:
                    continue
                pct = max(cands)
                if pct <= THRESHOLD:
                    continue
                ra, dec = radec(sid)
                band = 0 if (bpct is not None and (rpct is None or bpct >= rpct)) else 1
                records.append({
                    "id": sid, "ra": ra, "dec": dec,
                    "pct": round(pct, 3),
                    "bmin": round(bmin, 3), "bmax": round(bmax, 3),
                    "rmin": round(rmin, 3), "rmax": round(rmax, 3),
                    "nbp": count_valid(bp), "nrp": count_valid(rp),
                    "band": band,
                })

    records.sort(key=lambda r: r["pct"], reverse=True)
    # Shard assignment by sorted position (round-robin) — exactly even ~952/shard,
    # independent of the non-uniform source_id bits. This is the single source of
    # truth; the light-curve exporter reads the "sh" field back from here.
    for i, r in enumerate(records):
        r["sh"] = i % SHARDS
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fo:
        json.dump({"count": len(records), "total": seen, "shards": SHARDS,
                   "rows": records}, fo, separators=(",", ":"))
    size = os.path.getsize(OUT)
    print(f"sources scanned: {seen:,}")
    print(f"survivors (>100%): {len(records):,}")
    print(f"wrote {OUT}  ({size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
