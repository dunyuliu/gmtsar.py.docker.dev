#!/usr/bin/env python3
"""distribute_gmtsar_windows.py -- package a working native-Windows GMTSAR
build into a single self-contained, relocatable bundle: no conda, no
Git-for-Windows, nothing else required on the target machine.

Precondition: `python gmtsar/python/install.py --system windows_conda` has
already been run successfully against THIS checkout (bin/, lib/, share/
exist and work). This script does not build gmtsar -- it only packages an
existing build. It never modifies install.py or the conda env it built
from; it only reads from them.

Pipeline (see the do_* functions below, run in this order by main()):
  1. do_pack_python()   -- conda-pack the env's Python runtime (numpy,
     scipy, numba, netCDF4, matplotlib, h5py, ...) into dist/pyenv/,
     excluding build-only content (compiler toolchain, C headers, debug
     symbols, and unrelated junk -- see PYENV_EXCLUDE_FILTERS) that a
     *user* of the pre-built binaries never needs. A full env is ~3.5GB;
     the runtime-only subset is a fraction of that.
  2. do_collect_dlls()  -- recursively resolve every non-system DLL the
     built .exe/.dll files in bin/ depend on (objdump -p, BFS over the
     import table) and copy them into dist/bin/. This is what lets the
     .exe files run standalone: same DLL-search-order issue as the
     conv.c fopen("r") bug elsewhere in this port, solved here by
     co-locating the DLLs instead of relying on PATH.
  3. do_copy_gmtsar()   -- copy bin/, lib/, share/ from the repo.
  4. do_bundle_bash()   -- copy a minimal Git Bash (bash.exe +
     msys-2.0.dll + the specific POSIX coreutils gmtsar_lib.py's
     shell_run() commands actually invoke) into dist/git-bash/.
     gmtsar_lib.py shells out via bash for POSIX syntax (ln -sf, rm -rf,
     mkdir -p, &&, |) that cmd.exe can't run.
  5. do_write_launcher() -- write a relocatable gmtsar_shell.bat, using
     %~dp0 so the bundle works from wherever it's extracted, that runs
     conda-unpack on first launch (conda-pack's relocation step) and
     then sets GMTSAR/PATH and drops into a shell.
  6. do_zip()           -- zip dist/ into the final archive.

Usage:
    python gmtsar/python/distribute_gmtsar_windows.py
    python gmtsar/python/distribute_gmtsar_windows.py --conda-env gmtsar --output D:/dist
    python gmtsar/python/distribute_gmtsar_windows.py --skip-pyenv   # iterate on steps 2-6 fast

Does NOT (yet): run a full pipeline smoke test against the packaged
bundle on a machine with no conda/git on PATH -- that is the real bar
for "self-contained" (see project_rules.md on not trusting unverified
claims) and is intentionally a separate, slower pass. --verify here only
confirms each staged .exe loads its bundled DLLs and runs, and that the
bundled python can import the required packages -- necessary, not
sufficient.
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = (SCRIPT_DIR / ".." / "..").resolve()

_LOG_PATH: Path | None = None

# conda-forge packages installed for the build toolchain (m2w64-toolchain,
# cmake, ninja -- see install.py's WINDOWS_CONDA_BOOTSTRAP_PACKAGES) that a
# *user* running pre-built .exe files never needs. Excluding these is what
# takes the packed env from ~3.5GB down to a fraction of that. Also strips
# debug symbols, C/C++ headers (build-only), and doc/man content.
# node_modules/ is NOT gmtsar's -- it's stray content (an npm install that
# landed inside this particular env directory by accident, unrelated to
# any conda-forge package) observed in the dev env this was built against;
# excluded defensively since it's large (500MB+) and never touched by
# anything gmtsar does.
PYENV_EXCLUDE_FILTERS = [
    ("exclude", "Library/mingw-w64/**"),
    ("exclude", "Library/include/**"),
    ("exclude", "Library/symbols/**"),
    ("exclude", "Library/man/**"),
    ("exclude", "Library/cmake/**"),
    ("exclude", "node_modules/**"),
    ("exclude", "conda-meta/**"),
    ("exclude", "pkgs/**"),
]

# Git Bash coreutils gmtsar_lib.py's shell_run()-based commands actually
# invoke, across p2p_stages.py/filter/intf/geocode/pre_proc/cleanup/etc
# (grepped for POSIX-syntax `run("...")`/`shell_run("...")` call sites --
# ln, rm, mkdir, cp, mv, cat, alias are used directly; the rest are
# bash builtins or come along with coreutils' usual companions and are
# cheap enough to include rather than risk a missing-tool failure deep
# in a pipeline run).
BASH_COREUTILS = [
    "ln.exe", "rm.exe", "mkdir.exe", "cp.exe", "mv.exe", "cat.exe",
    "ls.exe", "rmdir.exe", "touch.exe", "basename.exe", "dirname.exe",
    "grep.exe", "sed.exe", "tr.exe", "cut.exe", "head.exe", "tail.exe",
    "sort.exe", "uniq.exe", "wc.exe", "env.exe", "sleep.exe", "true.exe",
    "false.exe", "printf.exe", "echo.exe", "test.exe", "[.exe",
]


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _log(line: str) -> None:
    print(line)
    if _LOG_PATH is not None:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def _run(cmd: list[str], **kwargs) -> None:
    cmd_str = " ".join(str(c) for c in cmd)
    _log(f"[{_utc_now()}] ==> {cmd_str}")
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1, **kwargs)
    for line in proc.stdout:
        _log(line.rstrip("\n"))
    rc = proc.wait()
    dt = time.time() - t0
    if rc != 0:
        _log(f"[{_utc_now()}] FAILED after {dt:.3f}s (rc={rc}): {cmd_str}")
        raise subprocess.CalledProcessError(rc, cmd)
    _log(f"[{_utc_now()}] done in {dt:.3f}s (rc=0): {cmd_str}")


# ------------------------------------------------------------ preconditions --

def check_preconditions(gmtsar_bin: Path) -> None:
    missing = [p for p in (gmtsar_bin, REPO_ROOT / "share" / "gmtsar" / "filters",
                            REPO_ROOT / "lib")
               if not p.exists()]
    if missing:
        sys.exit(
            "ERROR: this checkout doesn't have a working native-Windows build "
            f"yet (missing: {', '.join(str(m) for m in missing)}). Run:\n"
            "    python gmtsar/python/install.py --system windows_conda\n"
            "first -- this script only packages an existing build, it doesn't "
            "create one.")
    conv_exe = gmtsar_bin / "conv.exe"
    if not conv_exe.is_file():
        sys.exit(f"ERROR: {conv_exe} not found -- build looks incomplete.")


def locate_conda_env(conda_env: str) -> Path:
    import json
    conda_base = None
    for base in (r"D:\anaconda", os.path.expanduser("~\\.conda"),
                 os.path.expanduser("~\\anaconda3"), os.path.expanduser("~\\miniconda3"),
                 r"C:\ProgramData\Anaconda3"):
        conda_bat = Path(base) / "condabin" / "conda.bat"
        envs_root = Path(base) / "envs"
        if (envs_root / conda_env).is_dir():
            return envs_root / conda_env
        if conda_bat.is_file():
            conda_base = Path(base)
    if conda_base is not None:
        out = subprocess.run(["cmd", "/c", str(conda_base / "condabin" / "conda.bat"),
                               "env", "list", "--json"],
                              capture_output=True, text=True)
        if out.returncode == 0:
            for p in json.loads(out.stdout).get("envs", []):
                if Path(p).name == conda_env:
                    return Path(p)
    sys.exit(f"ERROR: could not locate conda env '{conda_env}' -- pass --conda-env-path explicitly.")


# ---------------------------------------------------------------- step 1 ----

def do_pack_python(conda_env_path: Path, dist: Path, force: bool) -> Path:
    """conda-pack the env's Python runtime into dist/pyenv/ (a directory,
    not an archive -- do_zip() folds it into the final single zip)."""
    pyenv_dir = dist / "pyenv"
    if pyenv_dir.exists():
        if not force:
            _log(f"==> {pyenv_dir} already exists, skipping pack (--force to redo)")
            return pyenv_dir
        shutil.rmtree(pyenv_dir)

    import conda_pack  # noqa: local import -- optional dep, see requirements note in main()
    _log(f"==> conda-pack {conda_env_path} -> {pyenv_dir} "
         "(excluding build-only toolchain/headers/symbols; this takes a while)")
    conda_pack.pack(
        prefix=str(conda_env_path),
        output=str(pyenv_dir),
        format="no-archive",
        filters=PYENV_EXCLUDE_FILTERS,
        force=force,
        n_threads=-1,
        verbose=True,
    )
    return pyenv_dir


# ---------------------------------------------------------------- step 2 ----

# Windows system DLLs are resolved by checking real presence in System32/
# SysWOW64 -- NOT a maintained name-pattern allowlist, which is exactly the
# kind of list that silently rots (new api-ms-win-* sets ship with every
# Windows feature update). A DLL is "system" iff Windows itself already
# provides it.
_SYSTEM_DIRS = [Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32",
                Path(os.environ.get("SystemRoot", r"C:\Windows")) / "SysWOW64"]


def _is_system_dll(name: str) -> bool:
    return any((d / name).is_file() for d in _SYSTEM_DIRS)


def _dll_imports(objdump: Path, path: Path) -> list[str]:
    out = subprocess.run([str(objdump), "-p", str(path)], capture_output=True, text=True).stdout
    return [ln.split("DLL Name:")[1].strip() for ln in out.splitlines() if "DLL Name:" in ln]


def do_collect_dlls(gmtsar_bin: Path, conda_env_path: Path, objdump: Path, dist_bin: Path) -> None:
    """BFS the PE import table of every bin/*.exe and *.dll, resolve each
    non-system DLL against the conda env's library dirs, copy into
    dist_bin/. Raises if anything can't be resolved -- a silently-missing
    DLL is a bundle that works on the dev machine and crashes for every
    real user (project_rules.md Rule 1: fail loud, not quiet)."""
    search_dirs = [
        conda_env_path / "Library" / "bin",
        conda_env_path / "Library" / "mingw-w64" / "bin",
        conda_env_path,
        gmtsar_bin,
    ]
    start = list(gmtsar_bin.glob("*.exe")) + list(gmtsar_bin.glob("*.dll"))
    _log(f"==> walking DLL dependencies from {len(start)} files in {gmtsar_bin}")
    resolved: dict[str, Path] = {}
    queue = list(start)
    unresolved: set[str] = set()
    while queue:
        f = queue.pop()
        for dll in _dll_imports(objdump, f):
            if dll.lower() in resolved or _is_system_dll(dll):
                continue
            hit = next((d / dll for d in search_dirs if (d / dll).is_file()), None)
            if hit is None:
                unresolved.add(dll)
                continue
            resolved[dll.lower()] = hit
            queue.append(hit)

    if unresolved:
        sys.exit(
            "ERROR: could not resolve these DLL dependencies (bundle would be "
            f"broken on a clean machine): {sorted(unresolved)}\n"
            "Either they're genuinely missing from the conda env, or "
            "_is_system_dll()/search_dirs needs updating.")

    dist_bin.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, src in sorted(resolved.items()):
        dst = dist_bin / src.name
        shutil.copy2(src, dst)
        total += dst.stat().st_size
    _log(f"==> copied {len(resolved)} DLLs ({total/1e6:.1f} MB) into {dist_bin}")


# ---------------------------------------------------------------- step 3 ----

def do_copy_gmtsar(dist: Path, force: bool) -> None:
    for name in ("bin", "lib", "share"):
        src = REPO_ROOT / name
        dst = dist / name
        if dst.exists() and not force:
            _log(f"==> {dst} already exists, skipping (--force to redo)")
            continue
        if dst.exists():
            shutil.rmtree(dst)
        _log(f"==> copying {src} -> {dst}")
        shutil.copytree(src, dst)


# ---------------------------------------------------------------- step 4 ----

def do_bundle_bash(dist: Path, force: bool) -> None:
    """Copy bash.exe + msys-2.0.dll + the specific coreutils gmtsar_lib.py
    needs into dist/git-bash/. Located via gmtsar_lib._win_bash()'s own
    candidate list, so this always bundles whatever bash the dev build
    actually validated against."""
    git_bash_dir = dist / "git-bash"
    if git_bash_dir.exists() and not force:
        _log(f"==> {git_bash_dir} already exists, skipping (--force to redo)")
        return
    if git_bash_dir.exists():
        shutil.rmtree(git_bash_dir)

    sys.path.insert(0, str(REPO_ROOT / "gmtsar" / "python" / "utils"))
    import gmtsar_lib
    bash_exe = Path(gmtsar_lib._win_bash())
    if not bash_exe.is_file():
        sys.exit("ERROR: no working Git Bash found on this machine -- can't bundle it. "
                  "Install Git for Windows first.")
    git_root = bash_exe.parent.parent  # .../Git/bin/bash.exe -> .../Git

    (git_bash_dir / "bin").mkdir(parents=True, exist_ok=True)
    shutil.copy2(bash_exe, git_bash_dir / "bin" / "bash.exe")
    msys_dll = next(
        (c for c in (bash_exe.parent / "msys-2.0.dll",
                      git_root / "usr" / "bin" / "msys-2.0.dll")
         if c.is_file()),
        None)
    if msys_dll is None:
        sys.exit(f"ERROR: msys-2.0.dll not found under {git_root} (checked bin/ and usr/bin/)")
    shutil.copy2(msys_dll, git_bash_dir / "bin" / "msys-2.0.dll")

    missing = []
    for tool in BASH_COREUTILS:
        src = bash_exe.parent / tool
        if not src.is_file():
            src = git_root / "usr" / "bin" / tool
        if not src.is_file():
            missing.append(tool)
            continue
        shutil.copy2(src, git_bash_dir / "bin" / tool)
    if missing:
        _log(f"WARN: coreutils not found, not bundled (may be builtins, or missing "
             f"a real dependency -- check if the pipeline actually needs them): {missing}")
    _log(f"==> bundled Git Bash ({bash_exe}) + {len(BASH_COREUTILS) - len(missing)} "
         f"coreutils into {git_bash_dir}")


# ---------------------------------------------------------------- step 5 ----

LAUNCHER_TEMPLATE = r"""@echo off
setlocal
set "HERE=%~dp0"
if not exist "%HERE%pyenv\.gmtsar_unpacked" (
    echo First run: relocating the bundled Python environment...
    call "%HERE%pyenv\Scripts\conda-unpack.exe"
    if errorlevel 1 (
        echo conda-unpack failed -- see above.
        exit /b 1
    )
    echo done > "%HERE%pyenv\.gmtsar_unpacked"
)
set "GMTSAR=%HERE%."
set "PATH=%HERE%bin;%HERE%git-bash\bin;%HERE%pyenv;%HERE%pyenv\Scripts;%PATH%"
set "GMTSAR_WIN_BASH=%HERE%git-bash\bin\bash.exe"
if "%~1"=="" (
    echo GMTSAR environment ready (native Windows, self-contained bundle^).
    echo Try: p2p_processing RS2 ^<master^> ^<aligned^> config.py
    cmd /k
) else (
    %*
)
"""


def do_write_launcher(dist: Path) -> None:
    launcher = dist / "gmtsar_shell.bat"
    launcher.write_text(LAUNCHER_TEMPLATE, encoding="utf-8")
    _log(f"==> wrote {launcher}")


# ---------------------------------------------------------------- step 6 ----

def do_zip(dist: Path, output: Path) -> None:
    _log(f"==> zipping {dist} -> {output} (this takes a while for a multi-GB bundle)")
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _dirs, files in os.walk(dist):
            for fn in files:
                fp = Path(root) / fn
                zf.write(fp, fp.relative_to(dist.parent))
    _log(f"==> wrote {output} ({output.stat().st_size/1e9:.2f} GB)")


# --------------------------------------------------------------- verify -----

def do_verify(dist: Path) -> None:
    """Necessary-not-sufficient sanity pass: each staged .exe runs (proves
    its bundled DLLs resolve) and the bundled python can import the
    packages the framework needs. Does NOT run a real pipeline case --
    see module docstring.

    Deliberately uses an ISOLATED PATH -- Windows system dirs only, no
    conda env, no Git for Windows, nothing from this dev machine's own
    setup. Testing with the dev machine's PATH still attached would let a
    genuinely-missing bundled DLL silently resolve from the conda env
    instead, passing "verification" for a bundle that's actually broken
    on a clean target machine -- the exact failure mode this script
    exists to catch (project_rules.md: don't trust unverified claims)."""
    _log("==> verify: running each bin/*.exe with an ISOLATED PATH "
         "(no conda/git -- proves the bundle is really standalone)")
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    isolated_path = os.pathsep.join([
        str(dist / "bin"), os.path.join(system_root, "System32"), system_root,
    ])
    env = {"PATH": isolated_path, "SystemRoot": system_root}
    failures = []
    for exe in sorted((dist / "bin").glob("*.exe")):
        r = subprocess.run([str(exe)], capture_output=True, env=env, timeout=15,
                            cwd=str(dist / "bin"))
        # DLL-load failure is STATUS_DLL_NOT_FOUND (0xC0000135) or similar;
        # a normal "Usage: ..." exit (whatever code) means it started fine.
        if r.returncode in (-1073741515, 3221225781):
            failures.append(exe.name)
    if failures:
        sys.exit(f"ERROR: these .exe failed to start under an isolated PATH "
                  f"(DLL resolution problem -- bundle is NOT self-contained): {failures}")
    _log(f"==> all {len(list((dist/'bin').glob('*.exe')))} .exe files start cleanly "
         "with no conda/git on PATH")

    py = dist / "pyenv" / "python.exe"
    check = subprocess.run(
        [str(py), "-c", "import numpy, scipy, numba, netCDF4, matplotlib; print('ok')"],
        capture_output=True, text=True, env={"PATH": isolated_path, "SystemRoot": system_root})
    if check.returncode != 0 or "ok" not in check.stdout:
        sys.exit(f"ERROR: bundled python failed required imports under isolated PATH:\n"
                  f"{check.stdout}\n{check.stderr}")
    _log("==> bundled python imports numpy/scipy/numba/netCDF4/matplotlib OK "
         "with no conda/git on PATH")

    bash = dist / "git-bash" / "bin" / "bash.exe"
    bash_check = subprocess.run(
        [str(bash), "-c", "echo hello && ln --version >/dev/null && mkdir -p /tmp/x && rm -rf /tmp/x && echo OK"],
        capture_output=True, text=True, env={"PATH": isolated_path, "SystemRoot": system_root})
    if bash_check.returncode != 0 or "OK" not in bash_check.stdout:
        sys.exit(f"ERROR: bundled Git Bash failed a basic POSIX-command smoke test "
                  f"under isolated PATH:\nstdout={bash_check.stdout}\nstderr={bash_check.stderr}")
    _log("==> bundled Git Bash runs echo/ln/mkdir/rm OK with no system Git on PATH")


# ------------------------------------------------------------------- main ---

def main() -> None:
    global _LOG_PATH
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--conda-env", default="gmtsar")
    p.add_argument("--output", default=str(REPO_ROOT / "dist" / "gmtsar-windows"))
    p.add_argument("--force", action="store_true", help="redo steps even if their output already exists")
    p.add_argument("--skip-pyenv", action="store_true", help="skip conda-pack (slow); reuse existing dist/pyenv")
    p.add_argument("--skip-zip", action="store_true", help="build dist/ but don't zip it (faster iteration)")
    p.add_argument("--verify", action="store_true", help="run do_verify() after packaging")
    args = p.parse_args()

    if sys.platform != "win32":
        sys.exit("ERROR: this packages a native-Windows build; run it on Windows.")

    dist = Path(args.output).resolve()
    dist.mkdir(parents=True, exist_ok=True)
    _LOG_PATH = dist.parent / f"distribute_{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}.log"
    _log(f"[{_utc_now()}] distribute_gmtsar_windows.py start; dist={dist}")

    gmtsar_bin = REPO_ROOT / "bin"
    check_preconditions(gmtsar_bin)
    conda_env_path = locate_conda_env(args.conda_env)
    objdump = conda_env_path / "Library" / "mingw-w64" / "bin" / "objdump.exe"
    if not objdump.is_file():
        sys.exit(f"ERROR: {objdump} not found -- is m2w64-toolchain installed in '{args.conda_env}'?")

    if not args.skip_pyenv:
        do_pack_python(conda_env_path, dist, args.force)
    else:
        _log("==> --skip-pyenv: reusing existing dist/pyenv")

    # Order matters: do_copy_gmtsar wipes+recreates dist/bin from the repo's
    # bin/ (via rmtree+copytree), so it must run BEFORE do_collect_dlls adds
    # the DLL dependencies alongside those .exe files -- the reverse order
    # would have do_copy_gmtsar delete the DLLs do_collect_dlls just copied.
    do_copy_gmtsar(dist, args.force)
    do_collect_dlls(gmtsar_bin, conda_env_path, objdump, dist / "bin")
    do_bundle_bash(dist, args.force)
    do_write_launcher(dist)

    if args.verify:
        do_verify(dist)

    if not args.skip_zip:
        do_zip(dist, dist.parent / f"{dist.name}.zip")

    _log(f"[{_utc_now()}] distribute_gmtsar_windows.py done. Output: {dist}")


if __name__ == "__main__":
    main()
