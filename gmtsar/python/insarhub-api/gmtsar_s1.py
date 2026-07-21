"""GMTSAR_S1 — Sentinel-1 InSAR processor for InSARHub, backed by GMTSAR's
own Python p2p_processing pipeline.

STATUS: v0, staged for testing (2026-07-20) -- NOT yet run against a real
InSARHub install (the `insarhub` package isn't available in this dev
environment). Written directly against InSARHub's real interface, pulled
from github.com/jldz9/InSARHub (src/insarhub/core/base.py, LocalProcessor
ABC) and cross-checked against the existing ISCE_S1 implementation for
conventions (status constants, job JSON shape, per-step/per-pair
parallel execution). See README.md in this directory for what's verified
vs. still assumed, and the concrete list of things to test before this
is real.

Interface (matches insarhub.core.LocalProcessor):
    submit()  -- stage each pair's GMTSAR case dir, launch p2p_processing
                 per pair (subprocess), up to config.max_workers concurrent.
    refresh() -- read per-pair status, print a table.
    retry()   -- re-run failed pairs (and only failed pairs).
    watch()   -- poll until every pair is SUCCEEDED or FAILED.
    save()    -- persist gmtsar_jobs.json (job state), matching ISCE_S1's
                 isce_jobs.json convention.

Why no custom output-normalization step: GMTSAR's native per-pair output
directory (intf/<ref>_<sec>/ -- corr_ll.grd, phasefilt_ll.grd,
unwrap_ll.grd, two numeric-named *.PRM files) is EXACTLY what MintPy's
own prep_gmtsar.py already expects (confirmed by reading
mintpy/prep_gmtsar.py upstream: it globs `{fbase}_ll*.grd` and
`*.PRM` files named as plain digits). So InSARHub's existing
Mintpy_SBAS_Base_Analyzer should be able to consume a GMTSAR_S1 case
directory as-is, once InSARHub's own compatible_processor wiring for
that analyzer is extended to include "GMTSAR_S1" -- that's a
one-line change on InSARHub's side, not new code here.
"""
from __future__ import annotations

import json
import logging
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PENDING = "PENDING"
_RUNNING = "RUNNING"
_SUCCEEDED = "SUCCEEDED"
_FAILED = "FAILED"

JOBS_FILE = "gmtsar_jobs.json"

# GMTSAR's own multi-sensor coverage (see gmtsar/python/tests/cases.py) --
# GMTSAR_S1 only exercises S1_TOPS today, but every one of these is
# already a real, tested SAT argument to p2p_processing. Listed here so
# a future GMTSAR_<sensor> processor doesn't have to re-derive this.
SUPPORTED_SATS = (
    "ERS", "ENVI", "ENVI_SLC", "ALOS", "ALOS_SLC", "ALOS2", "ALOS2_SCAN",
    "S1_STRIP", "S1_TOPS", "CSK_RAW", "CSK_SLC", "TSX", "RS2", "GF3",
)

try:
    from insarhub.core import LocalProcessor
except ImportError:  # pragma: no cover - dev environment has no insarhub install
    class LocalProcessor:  # type: ignore[no-redef]
        """Stand-in so this module imports and can be unit-tested without
        the real `insarhub` package on PATH. Delete this shim once
        developing directly inside an InSARHub checkout / env."""
        name: str
        default_config = None

        def __init__(self, config=None):
            self.config = config

        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)


from .config import GMTSAR_S1_Config


def _read_status(case_dir: Path, ref: str, sec: str) -> str:
    marker_dir = case_dir / "intf" / f"{ref}_{sec}"
    if (marker_dir / ".succeeded").exists():
        return _SUCCEEDED
    if (marker_dir / ".failed").exists():
        return _FAILED
    if marker_dir.exists():
        return _RUNNING
    return _PENDING


def _write_status(case_dir: Path, ref: str, sec: str, status: str) -> None:
    marker_dir = case_dir / "intf" / f"{ref}_{sec}"
    marker_dir.mkdir(parents=True, exist_ok=True)
    for name in (".succeeded", ".failed"):
        f = marker_dir / name
        if f.exists():
            f.unlink()
    if status == _SUCCEEDED:
        (marker_dir / ".succeeded").touch()
    elif status == _FAILED:
        (marker_dir / ".failed").touch()


class GMTSAR_S1(LocalProcessor):
    """Sentinel-1 InSAR processor backed by GMTSAR's p2p_processing.

    Usage (mirrors ISCE_S1's own docstring example)::

        from insarhub.processor import GMTSAR_S1
        from insarhub.config import GMTSAR_S1_Config

        proc = GMTSAR_S1(
            pairs  = [("20200101", "20200113"), ("20200101", "20200125")],
            config = GMTSAR_S1_Config(
                workdir = '/data/stack',
                slc_dir = '/data/slcs',
                orbit_dir = '/data/orbits',
                bbox = [33.0, 38.0, -120.0, -115.0],
            ),
        )
        proc.submit()
        proc.watch()
    """

    name = "GMTSAR_S1"
    description = (
        "Sentinel-1 InSAR via GMTSAR's Python p2p_processing pipeline. "
        "Requires GMTSAR installed (gmtsar/python/install.py) and GMTSAR "
        "env vars set. Output is directly consumable by MintPy's "
        "prep_gmtsar.py -- no format conversion needed."
    )
    compatible_downloader = "S1_SLC"
    default_config = GMTSAR_S1_Config

    def __init__(self, pairs: list[tuple[str, str]], config: GMTSAR_S1_Config | None = None):
        super().__init__(config)
        self.config: GMTSAR_S1_Config = self.config or GMTSAR_S1_Config()
        if not pairs and not getattr(self, "jobs", None):
            raise ValueError("pairs must be a non-empty list of (reference, secondary) tuples.")
        self.pairs = pairs
        self.jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    #  Paths                                                              #
    # ------------------------------------------------------------------ #

    @property
    def workdir(self) -> Path:
        return Path(self.config.workdir)

    @property
    def case_dir(self) -> Path:
        """GMTSAR case directory -- one shared case for the whole stack,
        matching how p2p_processing expects raw/, topo/, config.py to
        live in a single directory that every pair's invocation shares.
        """
        return self.workdir / "gmtsar_case"

    def _pair_key(self, ref: str, sec: str) -> str:
        return f"{ref}_{sec}"

    # ------------------------------------------------------------------ #
    #  Case staging (the InSARHub <-> GMTSAR directory-convention bridge) #
    # ------------------------------------------------------------------ #

    def _stage_case(self) -> None:
        """Populate case_dir/{raw,topo}/ and config.py from the InSARHub
        config, matching what GMTSAR's own case.setup / p2p_config would
        produce for a manually-run case.

        KNOWN GAP (see README): this currently assumes slc_dir already
        contains files p2p_processing can consume directly (i.e. already
        run through the sensor's own pre_proc/make_slc step, or GMTSAR's
        p2p_processing is invoked in a mode where it does that itself --
        needs a real run to confirm which). DEM auto-download from a
        bbox (dem_path=None) is NOT implemented -- config.dem_path must
        point at an existing GMTSAR-format DEM (topo/dem.grd) for now.
        """
        cfg = self.config
        self.case_dir.mkdir(parents=True, exist_ok=True)
        raw_dir = self.case_dir / "raw"
        topo_dir = self.case_dir / "topo"
        raw_dir.mkdir(exist_ok=True)
        topo_dir.mkdir(exist_ok=True)

        if cfg.slc_dir:
            src = Path(cfg.slc_dir)
            for f in src.glob("*"):
                dest = raw_dir / f.name
                if not dest.exists():
                    dest.symlink_to(f.resolve())

        if cfg.orbit_dir:
            for f in Path(cfg.orbit_dir).glob("*"):
                dest = raw_dir / f.name
                if not dest.exists():
                    dest.symlink_to(f.resolve())

        if cfg.dem_path:
            dest = topo_dir / "dem.grd"
            if not dest.exists():
                dest.symlink_to(Path(cfg.dem_path).resolve())
        else:
            raise NotImplementedError(
                "GMTSAR_S1_Config.dem_path is required in this v0 -- "
                "bbox-driven DEM auto-fetch (matching ISCE_S1's GLO-30 "
                "download) is not implemented yet."
            )

        config_py = self.case_dir / "config.py"
        if not config_py.exists():
            if cfg.config_template:
                import shutil
                shutil.copy(cfg.config_template, config_py)
            else:
                subprocess.run(
                    ["pop_config", cfg.sat],
                    cwd=str(self.case_dir),
                    check=True,
                )

    # ------------------------------------------------------------------ #
    #  LocalProcessor interface                                          #
    # ------------------------------------------------------------------ #

    def submit(self) -> dict:
        self._stage_case()

        pending = []
        for ref, sec in self.pairs:
            key = self._pair_key(ref, sec)
            status = _read_status(self.case_dir, ref, sec)
            if status == _SUCCEEDED and self.config.skip_existing:
                logger.info("%s already succeeded, skipping.", key)
                self.jobs[key] = self._job_meta(ref, sec, _SUCCEEDED)
                continue
            _write_status(self.case_dir, ref, sec, _PENDING)
            self.jobs[key] = self._job_meta(ref, sec, _PENDING)
            pending.append((ref, sec))

        if self.config.dry_run:
            logger.info("dry_run: would submit %d pair(s): %s", len(pending), pending)
            return self.jobs

        thread = threading.Thread(target=self._run_pairs, args=(pending,), daemon=True)
        thread.start()
        self._thread = thread
        self.save()
        return self.jobs

    def _run_pairs(self, pairs: list[tuple[str, str]]) -> None:
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as pool:
            futures = {
                pool.submit(self._run_one_pair, ref, sec): (ref, sec)
                for ref, sec in pairs
            }
            for fut in as_completed(futures):
                ref, sec = futures[fut]
                key = self._pair_key(ref, sec)
                try:
                    ok = fut.result()
                except Exception:
                    logger.exception("pair %s raised", key)
                    ok = False
                status = _SUCCEEDED if ok else _FAILED
                _write_status(self.case_dir, ref, sec, status)
                with self._lock:
                    self.jobs[key]["status"] = status
                self.save()

    def _run_one_pair(self, ref: str, sec: str) -> bool:
        key = self._pair_key(ref, sec)
        with self._lock:
            self.jobs[key]["status"] = _RUNNING
        log_path = self.case_dir / "intf" / key / "p2p.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["p2p_processing", self.config.sat, ref, sec, "config.py"]
        with open(log_path, "w") as log_f:
            proc = subprocess.run(
                cmd, cwd=str(self.case_dir), stdout=log_f, stderr=subprocess.STDOUT,
            )
        return proc.returncode == 0

    def refresh(self) -> dict:
        for ref, sec in self.pairs:
            key = self._pair_key(ref, sec)
            status = _read_status(self.case_dir, ref, sec)
            if key in self.jobs:
                self.jobs[key]["status"] = status
        self._print_table()
        return self.jobs

    def retry(self) -> dict:
        failed = [
            (ref, sec) for ref, sec in self.pairs
            if _read_status(self.case_dir, ref, sec) == _FAILED
        ]
        if not failed:
            logger.info("No failed pairs to retry.")
            return self.jobs
        for ref, sec in failed:
            _write_status(self.case_dir, ref, sec, _PENDING)
        thread = threading.Thread(target=self._run_pairs, args=(failed,), daemon=True)
        thread.start()
        self._thread = thread
        return self.jobs

    def watch(self, poll_interval: float = 10.0) -> dict:
        import time
        while True:
            self.refresh()
            statuses = {j["status"] for j in self.jobs.values()}
            if statuses <= {_SUCCEEDED, _FAILED}:
                break
            time.sleep(poll_interval)
        return self.jobs

    def save(self) -> None:
        jobs_path = self.case_dir / JOBS_FILE
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        jobs_path.write_text(json.dumps(self.jobs, indent=2))

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _job_meta(self, ref: str, sec: str, status: str) -> dict:
        return {
            "pair": [ref, sec],
            "status": status,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

    def _print_table(self) -> None:
        for key, meta in self.jobs.items():
            print(f"  {key:24s} {meta['status']}")
