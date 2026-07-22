"""Lumeon pre-build EDA over the Gaia DR3 epoch photometry files.

Validates the organizer formula and sizes the problem:
  per band: percentage_change = ((max - min) / min) * 100   (valid fluxes only)
  result  : max(BP%, RP%);  keep if > 100
"""

import csv
import glob
import math
import os
import sys

csv.field_size_limit(10**7)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
THRESHOLD = 100.0


def parse_array(s):
    """Parse '[1.0,NaN,2.0]' -> list of valid floats (drop NaN/null/empty)."""
    s = s.strip()
    if len(s) < 2 or s == "[]":
        return []
    out = []
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
        out.append(v)
    return out


def iter_rows(path):
    with open(path) as fh:
        reader = csv.reader(l for l in fh if not l.startswith("#"))
        header = next(reader)
        idx = {c: i for i, c in enumerate(header)}
        for row in reader:
            yield row, idx


def section(t):
    print(f"\n{'='*72}\n{t}\n{'='*72}")


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "EpochPhotometry_*.csv")))
    if not files:
        sys.exit("No EpochPhotometry CSVs found")

    section(f"A. STRUCTURE ({len(files)} files)")
    total_sources = 0
    total_size = 0
    headers_ok = True
    ref_header = None
    for f in files:
        total_size += os.path.getsize(f)
        n = 0
        for row, idx in iter_rows(f):
            if ref_header is None:
                ref_header = tuple(sorted(idx))
            n += 1
        total_sources += n
        print(f"  {os.path.basename(f):42s} {os.path.getsize(f)/1e6:7.1f} MB  {n:>7d} sources")
    print(f"\n  Total: {total_size/1e6:.1f} MB, {total_sources:,} sources")

    section("B. ARRAY / QUALITY + C. COMPUTATION")
    n_src = 0
    no_bp = no_rp = no_both = 0
    minflux_zero = minflux_neg = 0
    valid_bp_counts = []
    valid_rp_counts = []
    pct_changes = []
    bp_drives = rp_drives = 0
    survivors = 0
    top = []

    for f in files:
        for row, idx in iter_rows(f):
            n_src += 1
            bp = parse_array(row[idx["bp_flux"]])
            rp = parse_array(row[idx["rp_flux"]])
            valid_bp_counts.append(len(bp))
            valid_rp_counts.append(len(rp))
            if not bp:
                no_bp += 1
            if not rp:
                no_rp += 1
            if not bp and not rp:
                no_both += 1

            def band_pct(vals):
                nonlocal minflux_zero, minflux_neg
                if len(vals) < 2:
                    return None, None, None
                mn, mx = min(vals), max(vals)
                if mn == 0:
                    minflux_zero += 1
                    return mn, mx, None
                if mn < 0:
                    minflux_neg += 1
                    return mn, mx, None
                return mn, mx, (mx - mn) / mn * 100.0

            bp_min, bp_max, bp_pct = band_pct(bp)
            rp_min, rp_max, rp_pct = band_pct(rp)
            cands = [p for p in (bp_pct, rp_pct) if p is not None]
            if not cands:
                continue
            pct = max(cands)
            pct_changes.append(pct)
            if bp_pct is not None and (rp_pct is None or bp_pct >= rp_pct):
                bp_drives += 1
            else:
                rp_drives += 1
            if pct > THRESHOLD:
                survivors += 1
                sid = row[idx["source_id"]]
                top.append((pct, sid, bp_min, bp_max, rp_min, rp_max))

    def dist(name, xs):
        xs = sorted(xs)
        k = len(xs)
        if not k:
            print(f"  {name}: empty"); return
        p = lambda q: xs[min(k - 1, int(q * k))]
        print(f"  {name}: min={xs[0]} med={p(.5)} p90={p(.9)} max={xs[-1]}")

    print(f"  sources processed: {n_src:,}")
    print(f"  no valid BP: {no_bp:,} ({100*no_bp/n_src:.1f}%)   "
          f"no valid RP: {no_rp:,} ({100*no_rp/n_src:.1f}%)   "
          f"no valid either: {no_both:,}")
    print(f"  min_flux == 0: {minflux_zero}   min_flux < 0: {minflux_neg}")
    dist("valid BP epochs/src", valid_bp_counts)
    dist("valid RP epochs/src", valid_rp_counts)

    section("C. PERCENTAGE_CHANGE DISTRIBUTION")
    dist("percentage_change", pct_changes)
    print(f"  band driving the max:  BP={bp_drives:,}  RP={rp_drives:,}")
    print(f"\n  survivors (> {THRESHOLD:.0f}%): {survivors:,} of {n_src:,} "
          f"({100*survivors/n_src:.2f}%)")
    for thr in [100, 200, 500, 1000, 5000]:
        c = sum(1 for p in pct_changes if p > thr)
        print(f"    > {thr:>5}%: {c:,}")

    section("D. SAMPLE OUTPUT (source_id,bp_min,bp_max,rp_min,rp_max,percentage_change)")
    top.sort(reverse=True)
    for pct, sid, bpmn, bpmx, rpmn, rpmx in top[:8]:
        fmt = lambda v: "%.6f" % v if v is not None else ""
        print(f"  {sid},{fmt(bpmn)},{fmt(bpmx)},{fmt(rpmn)},{fmt(rpmx)},{pct:.4f}")


if __name__ == "__main__":
    main()
