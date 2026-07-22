"""Per-file variability computation for one Gaia DR3 epoch-photometry file.

Lives as a standalone module (no IRIS imports) so it can be imported by
`spawn`-started worker processes — the only multiprocessing start method that
survives being launched from inside the live IRIS process. `fork` deadlocks.
"""
import gzip
import csv

# Column positions in the 48-column DR3 epoch-photometry ECSV.
SRC, BP, RP = 1, 11, 16


def _minmax(s):
    # "[v,NaN,...]" -> (min, max) over valid finite values, or (None, None).
    if not s or len(s) < 2:
        return None, None
    lo = hi = None
    for tok in s[1:-1].split(","):
        tok = tok.strip()
        if not tok or tok in ("NaN", "nan", "null", "None", "inf", "-inf"):
            continue
        try:
            v = float(tok)
        except ValueError:
            continue
        if v != v or v in (float("inf"), float("-inf")):
            continue
        if lo is None or v < lo:
            lo = v
        if hi is None or v > hi:
            hi = v
    return lo, hi


def _pct(lo, hi):
    # ((max - min) / min) * 100, only when min is strictly positive.
    if lo is None or lo <= 0:
        return None
    return (hi - lo) / lo * 100.0


def process_file(path):
    """Return [(source_id, bp_min, bp_max, rp_min, rp_max, pct), ...] for the
    sources in `path` whose percentage_change exceeds 100."""
    out = []
    with gzip.open(path, "rt") as fh:
        rows = (ln for ln in fh if not ln.startswith("#"))
        rdr = csv.reader(rows)
        next(rdr, None)  # header
        for row in rdr:
            if len(row) <= RP:
                continue
            bmn, bmx = _minmax(row[BP])
            rmn, rmx = _minmax(row[RP])
            bp, rp = _pct(bmn, bmx), _pct(rmn, rmx)
            cands = [p for p in (bp, rp) if p is not None]
            if not cands:
                continue
            pc = max(cands)
            if pc <= 100.0:
                continue
            out.append((row[SRC], bmn, bmx, rmn, rmx, pc))
    return out
