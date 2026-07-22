/// Lumeon — Gaia DR3 epoch-photometry variability detector.
///
/// Reads the 20 local epoch-photometry files shipped in data/in, computes each
/// source's per-band flux change, and writes the sources exceeding 100% to
/// data/out/results.csv in the required column order:
///   source_id,bp_min_flux,bp_max_flux,rp_min_flux,rp_max_flux,percentage_change
///
/// per band: percentage_change = ((max_flux - min_flux) / min_flux) * 100
/// result:   max(BP%, RP%);  keep if > 100
///
/// Each file is independent, so the 20 files are processed across CPU cores with
/// a multiprocessing pool. The pool uses the "spawn" start method: launched from
/// inside the live IRIS process, the default "fork" inherits IRIS runtime state
/// and deadlocks, whereas spawned children start as fresh interpreters and import
/// the pure-Python worker cleanly. This takes the run from ~15s serial to ~2s.
Class Lumeon.Challenge Extends %RegisteredObject
{

Parameter SRCDIR = "/home/irisowner/dev/src";

Parameter INDIR = "/home/irisowner/dev/data/in";

Parameter OUTFILE = "/home/irisowner/dev/data/out/results.csv";

/// Run the full challenge: scan data/in in parallel, write data/out/results.csv.
/// Returns the number of records kept (percentage_change > 100).
ClassMethod Run() As %Integer [ Language = python, SqlProc ]
{
    import sys, os, glob, csv, multiprocessing as mp

    workerdir = "/home/irisowner/dev/src/Lumeon"
    indir = "/home/irisowner/dev/data/in"
    outfile = "/home/irisowner/dev/data/out/results.csv"

    # spawned children start as fresh interpreters and do NOT inherit this
    # process's sys.path — but they DO inherit the environment, so seed
    # PYTHONPATH so `import worker` resolves in every child.
    if workerdir not in sys.path:
        sys.path.insert(0, workerdir)
    os.environ["PYTHONPATH"] = workerdir + os.pathsep + os.environ.get("PYTHONPATH", "")
    import worker

    files = sorted(glob.glob(os.path.join(indir, "*.csv.gz")))
    ctx = mp.get_context("spawn")
    with ctx.Pool(min(len(files), os.cpu_count() or 1)) as pool:
        results = pool.map(worker.process_file, files)

    def fmt(v):
        return "" if v is None else "%.6f" % v

    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    kept = 0
    with open(outfile, "w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["source_id", "bp_min_flux", "bp_max_flux",
                    "rp_min_flux", "rp_max_flux", "percentage_change"])
        for rows in results:
            for sid, bmn, bmx, rmn, rmx, pc in rows:
                w.writerow([sid, fmt(bmn), fmt(bmx), fmt(rmn), fmt(rmx),
                            "%.6f" % pc])
                kept += 1
    return kept
}

}
