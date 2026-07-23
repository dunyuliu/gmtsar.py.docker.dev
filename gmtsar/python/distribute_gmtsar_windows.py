#!/usr/bin/env python3
"""distribute_gmtsar_windows.py -- package a working native-Windows GMTSAR
build into a single self-contained, relocatable bundle: no conda, no
Git-for-Windows, nothing else required on the target machine.

Precondition: `python gmtsar/python/install.py --system conda-windows-full` has
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
            "    python gmtsar/python/install.py --system conda-windows-full\n"
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

# Windows system DLLs are resolved by checking real presence in System32
# (the 64-bit view -- NOT SysWOW64, whose 32-bit DLLs an x64 exe cannot
# load; a name present ONLY there must be bundled, not skipped). Not a
# maintained name-pattern allowlist, which is exactly the kind of list
# that silently rots. Two deliberate exceptions:
#  - api-ms-win-*/ext-ms-* "API set" names are VIRTUAL on Win10+: the
#    loader resolves them via the OS ApiSetSchema, never the filesystem.
#    Treated as system unconditionally, and never bundled (shipping the
#    conda env's stub files alongside the exes is at best dead weight).
#  - MSVC runtime DLLs (vcruntime*/msvcp*/concrt*) are NEVER treated as
#    system even when present in System32: presence there just means THIS
#    machine has some VC redist installed -- a clean target may not, and
#    conda-built DLLs (gmt.dll etc.) hard-require them. Bundle app-locally
#    from the conda env (which ships them, and their license permits it).
_SYSTEM32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"


def _is_system_dll(name: str) -> bool:
    low = name.lower()
    if low.startswith(("api-ms-", "ext-ms-")):
        return True
    if low.startswith(("vcruntime", "msvcp", "concrt")):
        return False
    return (_SYSTEM32 / name).is_file()


def _dll_imports(objdump: Path, path: Path) -> list[str]:
    out = subprocess.run([str(objdump), "-p", str(path)], capture_output=True, text=True).stdout
    return [ln.split("DLL Name:")[1].strip() for ln in out.splitlines() if "DLL Name:" in ln]


def _pe_forwarder_targets(path: Path) -> set[str]:
    """DLL names referenced by this PE's export FORWARDERS -- exports whose
    address entry points at an ASCII "TargetModule.TargetFunction" string
    instead of code. The loader resolves these at import time exactly like
    static imports, but NO import-table walk can see them. Real bug found
    2026-07-23 by the isolated-PATH verify: conda-forge's libblas.dll/
    liblapack.dll are pure forwarder shims to mkl_rt.N.dll, so gmt.dll
    (which imports the shims) died STATUS_DLL_NOT_FOUND with every
    import-table dependency present and loadable.

    Minimal PE export-directory parse (stdlib only, no pefile dep). Any
    malformed/unparseable file returns empty -- the import walk still
    covers it, and _verify is the final backstop."""
    try:
        data = path.read_bytes()
        pe_off = int.from_bytes(data[0x3C:0x40], "little")
        if data[pe_off:pe_off + 4] != b"PE\0\0":
            return set()
        n_sections = int.from_bytes(data[pe_off + 6:pe_off + 8], "little")
        opt_size = int.from_bytes(data[pe_off + 20:pe_off + 22], "little")
        opt_off = pe_off + 24
        magic = int.from_bytes(data[opt_off:opt_off + 2], "little")
        dd_off = opt_off + (112 if magic == 0x20B else 96)  # PE32+ vs PE32
        exp_rva = int.from_bytes(data[dd_off:dd_off + 4], "little")
        exp_size = int.from_bytes(data[dd_off + 4:dd_off + 8], "little")
        if not exp_rva:
            return set()
        sections = []
        sec_off = opt_off + opt_size
        for i in range(n_sections):
            s = sec_off + 40 * i
            va = int.from_bytes(data[s + 12:s + 16], "little")
            raw_size = int.from_bytes(data[s + 16:s + 20], "little")
            raw_ptr = int.from_bytes(data[s + 20:s + 24], "little")
            virt_size = int.from_bytes(data[s + 8:s + 12], "little")
            sections.append((va, max(raw_size, virt_size), raw_ptr))

        def off(rva: int) -> int | None:
            for va, size, raw in sections:
                if va <= rva < va + size:
                    return raw + (rva - va)
            return None

        e = off(exp_rva)
        if e is None:
            return set()
        n_funcs = int.from_bytes(data[e + 20:e + 24], "little")
        aof_rva = int.from_bytes(data[e + 28:e + 32], "little")
        aof = off(aof_rva)
        if aof is None:
            return set()
        targets: set[str] = set()
        for i in range(n_funcs):
            func_rva = int.from_bytes(data[aof + 4 * i:aof + 4 * i + 4], "little")
            # A forwarder iff the entry points INSIDE the export directory.
            if not (exp_rva <= func_rva < exp_rva + exp_size):
                continue
            so = off(func_rva)
            if so is None:
                continue
            end = data.index(b"\0", so)
            fwd = data[so:end].decode("ascii", "replace")
            module = fwd.rsplit(".", 1)[0]  # "mkl_rt.2.dll.dgemm_" -> "mkl_rt.2.dll"
            if not module.lower().endswith(".dll"):
                module += ".dll"           # "NTDLL.RtlX" -> "NTDLL.dll"
            targets.add(module)
        return targets
    except Exception:
        return set()


def do_collect_dlls(gmtsar_bin: Path, conda_env_path: Path, objdump: Path, dist_bin: Path) -> None:
    """BFS every bin/*.exe and *.dll over BOTH dependency channels -- the
    import table AND export forwarders (see _pe_forwarder_targets) --
    resolving each non-system DLL against the conda env's library dirs and
    copying into dist_bin/. Raises if anything can't be resolved -- a
    silently-missing DLL is a bundle that works on the dev machine and
    crashes for every real user (project_rules.md Rule 1)."""
    search_dirs = [
        conda_env_path / "Library" / "bin",
        conda_env_path / "Library" / "mingw-w64" / "bin",
        conda_env_path,
        gmtsar_bin,
    ]
    start = list(gmtsar_bin.glob("*.exe")) + list(gmtsar_bin.glob("*.dll"))
    _log(f"==> walking DLL dependencies (imports + export forwarders) "
         f"from {len(start)} files in {gmtsar_bin}")
    resolved: dict[str, Path] = {}
    queue = list(start)
    unresolved: set[str] = set()
    while queue:
        f = queue.pop()
        deps = set(_dll_imports(objdump, f)) | _pe_forwarder_targets(f)
        for dll in deps:
            if dll.lower() in resolved or _is_system_dll(dll):
                continue
            hit = next((d / dll for d in search_dirs if (d / dll).is_file()), None)
            if hit is None:
                unresolved.add(dll)
                continue
            resolved[dll.lower()] = hit
            queue.append(hit)

    mkl = sorted(n for n in resolved if n.startswith("mkl_"))
    if mkl:
        sys.exit(
            f"ERROR: the dependency walk pulled in MKL ({mkl}) -- this env's "
            "libblas/liblapack shims are the MKL variant. MKL cannot be "
            "bundled statically (mkl_rt dispatches to mkl_core/mkl_avx*/... "
            "via runtime LoadLibrary that no static walk can see). Switch "
            "the env to the openblas variant first:\n"
            "    conda install -n <env> -c conda-forge libblas=*=*openblas "
            "liblapack=*=*openblas libcblas=*=*openblas\n"
            "(install.py's WINDOWS_CONDA_BOOTSTRAP_PACKAGES pins this for "
            "fresh envs since v2.10.3.)")

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

def do_bundle_bash(dist: Path, objdump: Path, force: bool) -> None:
    """Bundle a minimal REAL Git Bash into dist/git-bash/usr/bin/.

    Crucial subtlety (found by the isolated-PATH verify, 2026-07-23):
    Git for Windows' `Git\\bin\\bash.exe` -- the path gmtsar_lib's
    _win_bash() resolves and everyone knows -- is NOT bash. It's a tiny
    launcher stub that re-executes `..\\usr\\bin\\bash.exe`; copied
    alone it dies with "('...\\usr\\bin\\bash.exe' not found) Need a
    valid command-line". The real interpreter, its msys-*.dll runtime,
    and the coreutils all live under `usr\\bin\\`, so the bundle
    replicates exactly that layout and everything (launcher, verify,
    GMTSAR_WIN_BASH) points at usr/bin/bash.exe directly -- no stub.

    Each bundled tool's msys-*.dll dependencies are resolved via its
    actual import table (same objdump walk as the main DLL step) rather
    than a hardcoded 'msys-2.0.dll' guess -- sed/grep etc. pull extra
    msys runtime DLLs (iconv, intl, pcre) a guess would miss."""
    git_bash_dir = dist / "git-bash"
    if git_bash_dir.exists() and not force:
        _log(f"==> {git_bash_dir} already exists, skipping (--force to redo)")
        return
    if git_bash_dir.exists():
        shutil.rmtree(git_bash_dir)

    sys.path.insert(0, str(REPO_ROOT / "gmtsar" / "python" / "utils"))
    import gmtsar_lib
    stub_or_real = Path(gmtsar_lib._win_bash())
    if not stub_or_real.is_file():
        sys.exit("ERROR: no working Git Bash found on this machine -- can't bundle it. "
                  "Install Git for Windows first.")
    git_root = stub_or_real.parent.parent  # .../Git/bin/bash.exe -> .../Git
    usr_bin = git_root / "usr" / "bin"
    real_bash = usr_bin / "bash.exe"
    if not real_bash.is_file():
        sys.exit(f"ERROR: {real_bash} not found -- unexpected Git for Windows layout.")

    dst = git_bash_dir / "usr" / "bin"
    dst.mkdir(parents=True, exist_ok=True)

    to_copy = [real_bash]
    missing = []
    for tool in BASH_COREUTILS:
        src = usr_bin / tool
        if src.is_file():
            to_copy.append(src)
        else:
            missing.append(tool)

    copied: set[str] = set()
    queue = list(to_copy)
    while queue:
        f = queue.pop()
        if f.name.lower() in copied:
            continue
        shutil.copy2(f, dst / f.name)
        copied.add(f.name.lower())
        for dep in _dll_imports(objdump, f):
            if dep.lower().startswith("msys-") and dep.lower() not in copied:
                dep_src = usr_bin / dep
                if dep_src.is_file():
                    queue.append(dep_src)
    # MSYS maps /tmp to <msys-root>/tmp (= git-bash/tmp here); without it
    # every bash start warns "could not find /tmp, please create!" and
    # anything using mktemp breaks. Ship it empty.
    (git_bash_dir / "tmp").mkdir(exist_ok=True)
    if missing:
        _log(f"WARN: coreutils not found in {usr_bin}, not bundled: {missing}")
    n_dlls = sum(1 for c in copied if c.endswith(".dll"))
    _log(f"==> bundled real Git Bash ({real_bash}) + "
         f"{len(copied) - n_dlls - 1} coreutils + {n_dlls} msys DLLs into {dst}")


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
set "PATH=%HERE%bin;%HERE%git-bash\usr\bin;%HERE%pyenv;%HERE%pyenv\Scripts;%PATH%"
set "GMTSAR_WIN_BASH=%HERE%git-bash\usr\bin\bash.exe"
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
    # git-bash/usr/bin is on this PATH deliberately: it mirrors what the
    # launcher (gmtsar_shell.bat) sets up. MSYS bash does NOT implicitly
    # put its own /usr/bin on PATH for non-login `bash -c` invocations --
    # without this entry, every coreutil (ln, mkdir, ...) is
    # command-not-found even though it sits right next to bash.exe
    # (found by this verify, 2026-07-23).
    isolated_path = os.pathsep.join([
        str(dist / "bin"), str(dist / "git-bash" / "usr" / "bin"),
        os.path.join(system_root, "System32"), system_root,
    ])
    env = {"PATH": isolated_path, "SystemRoot": system_root}
    failures = []
    for exe in sorted((dist / "bin").glob("*.exe")):
        # stdin=DEVNULL: several gmtsar tools (esarp, conv's grd path, ...)
        # read stdin when invoked bare -- with an inherited console handle
        # they block forever, which a verify harness must not do. A closed
        # stdin makes them hit EOF and exit immediately.
        try:
            r = subprocess.run([str(exe)], capture_output=True, env=env,
                                timeout=15, cwd=str(dist / "bin"),
                                stdin=subprocess.DEVNULL)
            rc = r.returncode
        except subprocess.TimeoutExpired:
            # It RAN for 15s -- DLL resolution succeeded (a load failure is
            # instant); it just doesn't exit without real input. That's a
            # pass for what THIS check verifies (startability), not a hang
            # of the harness. subprocess already killed the child.
            _log(f"    note: {exe.name} ran past the 15s cap (waits for "
                 "input) -- counted as started-OK, killed")
            continue
        # DLL-load failure is STATUS_DLL_NOT_FOUND (0xC0000135) or
        # STATUS_INVALID_IMAGE_FORMAT (0xC000007B, 32/64 mismatch); a
        # normal "Usage: ..." exit (whatever code) means it started fine.
        if rc in (-1073741515, 3221225781, -1073741701, 3221225595):
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

    bash = dist / "git-bash" / "usr" / "bin" / "bash.exe"
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
    do_bundle_bash(dist, objdump, args.force)
    do_write_launcher(dist)

    if args.verify:
        do_verify(dist)

    if not args.skip_zip:
        do_zip(dist, dist.parent / f"{dist.name}.zip")

    _log(f"[{_utc_now()}] distribute_gmtsar_windows.py done. Output: {dist}")


if __name__ == "__main__":
    main()
