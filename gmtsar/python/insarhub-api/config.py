"""GMTSAR_S1_Config — config dataclass for the InSARHub GMTSAR_S1 processor.

Mirrors the shape of InSARHub's own ISCE_S1_Config (see
insarhub.config.ISCE_S1_Config upstream) so this adapter is a drop-in
sibling, not a special case. Field names deliberately match ISCE_S1_Config
where the concept overlaps (workdir, slc_dir, orbit_dir, dem_path, bbox,
polarization) so a user switching backends doesn't have to relearn a new
vocabulary.

STATUS: v0, staged for testing (2026-07-20). Not yet run against a real
InSARHub install -- see ../README.md for what's verified vs. assumed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GMTSAR_S1_Config:
    # --- paths -----------------------------------------------------------
    workdir: str = "."
    # Directory of raw Sentinel-1 SLC products (.SAFE dirs or .zip), same
    # convention as ISCE_S1_Config.slc_dir. GMTSAR itself wants these
    # staged into a per-case raw/ directory -- see gmtsar_s1.py's
    # _stage_case() for the raw/slc_dir bridge.
    slc_dir: Optional[str] = None
    orbit_dir: Optional[str] = None
    # GMTSAR DEM convention: a single DEM grd in topo/dem.grd per case,
    # unlike ISCE2's per-scene binary+xml. If None, auto-derived the same
    # way ISCE_S1 does (bbox from SLC footprints) and fetched via GMTSAR's
    # own dem tooling -- NOT YET IMPLEMENTED, see README "Known gaps".
    dem_path: Optional[str] = None
    bbox: Optional[list[float]] = None  # [S, N, W, E], matches ISCE_S1_Config

    # --- GMTSAR-specific ---------------------------------------------------
    # p2p_processing's SAT argument. GMTSAR_S1 hardcodes the sensible
    # default; exposed for forward-compat with multi-sensor InSARHub
    # support (GMTSAR already supports 14 sensor families -- see this
    # class's sibling docstring in gmtsar_s1.py).
    sat: str = "S1_TOPS"
    polarization: str = "vv"

    # Path to a GMTSAR config.py template. If None, one is auto-generated
    # per case via `pop_config <sat>` (GMTSAR's own default-config tool),
    # matching p2p_processing's own "no config.py given" behavior.
    config_template: Optional[str] = None

    # --- execution ---------------------------------------------------------
    max_workers: int = 4          # pairs processed concurrently
    skip_existing: bool = True    # like ISCE_S1_Config: don't redo a
                                   # pair whose intf/<ref>_<sec>/ already
                                   # has a completed status marker
    dry_run: bool = False

    def __post_init__(self):
        self.workdir = str(Path(self.workdir).expanduser().resolve())
