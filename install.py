# ===============================================================================
# pyADR — NTNU modified fork (v3.7) one-click installer
# Original Copyright 2021 An-Jun Liu
# Modified 2026 for v3.7 (NTNU fork)
# ===============================================================================
#
# Self-contained: package list is embedded below, no separate requirements.txt
# needed (though one is kept in the repo for users who prefer manual install).

import platform
import sys
import subprocess
import os
import shutil

# ---------------------------------------------------------------------------
# Required Python packages (embedded — install.py is self-contained)
# ---------------------------------------------------------------------------
REQUIRED_PACKAGES = [
    "PyQt5>=5.15",
    "numpy>=1.21",
    "scipy>=1.7",
    "matplotlib>=3.5",
    "pandas>=1.3",
    "openpyxl>=3.0",
    "scikit-learn>=1.0",
    "seaborn>=0.11",
    "requests>=2.25",
    "winotify>=1.0",      # Windows-only; pip will skip on macOS/Linux
]


print(r'''
                  __     ______  ______
                 /  \   |  ___ \|  ___ \

                / /\ \  | |   \ | |___)|
  _______    __/ /__\ \ | |   | |  __  /
 |  __ \ \  / /  ____  \| |___/ | |  \ \
 | |__) \ \/ /__/     \_|______/|_|   \_\
 |  ___/ \  /
 | |     / /
 |_|    /_/

pyADR -- NTNU modified fork (v3.7)  one-click installer
''')
input("Press Enter to start installation, or Ctrl+C to abort...")

IS_WINDOWS = platform.system() == 'Windows'
dir_path = os.path.dirname(os.path.realpath(__file__))


def step(n, t):
    print(f"\n[{n}] {t}")
    print('-' * 60)


# 1. Python version
step(1, "Python version check")
print(f"  Python {sys.version.split()[0]}  ({sys.executable})")
if sys.version_info < (3, 10):
    print(f"  WARNING: pyADR v3.7 tested on Python 3.10+. "
          f"You're on {sys.version_info.major}.{sys.version_info.minor}.")
    if input("  Continue anyway? [y/N] ").strip().lower() != 'y':
        sys.exit(1)
print("  OK")

# 2. Drive / path check
if IS_WINDOWS:
    step(2, "Install location check")
    drive = os.path.splitdrive(dir_path)[0].upper()
    print(f"  Path: {dir_path}")
    if drive != 'C:':
        print(f"  Recommendation: install on C: drive (currently {drive}).")
        if input("  Continue anyway? [y/N] ").strip().lower() != 'y':
            sys.exit(1)
    if any('一' <= c <= '鿿' for c in dir_path):
        print("  Warning: path contains Chinese characters; may break Excel export.")
    print("  OK")

# 3. Install Python packages (embedded list — no requirements.txt needed)
step(3, f"Installing {len(REQUIRED_PACKAGES)} Python packages")
for p in REQUIRED_PACKAGES:
    print(f"    - {p}")
print()
try:
    subprocess.check_call(
        [sys.executable, '-m', 'pip', 'install', '--upgrade'] + REQUIRED_PACKAGES
    )
    print("  OK — all packages installed")
except subprocess.CalledProcessError as e:
    print(f"  pip install FAILED (exit {e.returncode}).")
    print("  Check internet connection and try again, or install manually:")
    print(f"    pip install {' '.join(REQUIRED_PACKAGES)}")
    if input("  Continue with rest of install? [y/N] ").strip().lower() != 'y':
        sys.exit(1)

# 4. Folder structure
step(4, "Creating folder structure (Data/, Figures/)")
folders = [
    'Data', 'Data/T0', 'Data/J value',
    'Data/MassRatio', 'Data/MassRatio/AirRatio',
    'Data/MassRatio/Standerd/FSC',
    'Data/MassRatio/Standerd/LP6',
    'Data/MassRatio/Standerd/MMHB',
    'Data/MassRatio/Salt/CaF',
    'Data/MassRatio/Salt/Ksalt',
    'Data/SaltRatio/CaF', 'Data/SaltRatio/Ksalt',
    'Data/Statistics/T0', 'Data/Statistics/J', 'Data/Statistics/AS',
    'Data/Statistics/Salt/[36Ar37Ar]Ca',
    'Data/Statistics/Salt/[39Ar37Ar]Ca',
    'Data/Statistics/Salt/[40Ar39Ar]K',
    'Data/Statistics/Salt/[38Ar39Ar]K',
    'Data/Agecalc', 'Data/Publish',
    'Figures', 'Figures/T0', 'Figures/MassRatio',
    'Figures/Agecalc', 'Figures/Publish',
]
created = 0
for f in folders:
    p = os.path.join(dir_path, f)
    if not os.path.exists(p):
        os.makedirs(p, exist_ok=True)
        created += 1
print(f"  {created} new folders created ({len(folders) - created} already existed)")

# 5. Verify .work/
step(5, "Verifying .work/ seed files")
seed_files = ['.app_info.txt', 'logo.png', 'setting.csv', 'rawpath.txt']
missing = [f for f in seed_files if not os.path.exists(os.path.join(dir_path, '.work', f))]
if missing:
    print(f"  MISSING from .work/: {missing}")
    print("  pyADR may fail at startup. Re-clone the repo.")
else:
    print("  All seed files present")

# 6. Launcher
step(6, "Generating launcher (pyADR.bat / pyADR.sh)")
fname = 'pyADR.bat' if IS_WINDOWS else 'pyADR.sh'
with open(fname, 'w') as f:
    if IS_WINDOWS:
        f.write('@echo off\n')
        anaconda = sys.executable[:-10]
        f.write(f'call {anaconda}Scripts/activate.bat {anaconda}\n')
    f.write(f'cd {dir_path}\n')
    f.write(f'{sys.executable} {os.path.abspath("NTNU_DataReduction.py")}')
if IS_WINDOWS:
    subprocess.call(['CACLS', os.path.abspath(fname), '/e', '/p', 'Everyone:f'])
else:
    subprocess.call(['chmod', '777', os.path.abspath(fname)])
print(f"  {fname} created")

# 7. Desktop shortcut
step(7, "Copying launcher to Desktop")
HOME = os.path.expanduser('~')
candidates = [
    os.path.join(HOME, 'Desktop'),
    os.path.join(HOME, 'OneDrive', 'Desktop'),
    os.path.join(HOME, 'OneDrive', '桌面'),
    os.path.join(HOME, '桌面'),
]
desktop = next((d for d in candidates if os.path.isdir(d)), None)
if desktop:
    try:
        shutil.copyfile(os.path.abspath(fname), os.path.join(desktop, fname))
        print(f"  Copied to {desktop}")
    except Exception as e:
        print(f"  Could not copy to Desktop: {e}")
else:
    print(f"  Desktop folder not found")

print("\n" + "=" * 60)
print("  Installation complete! Double-click pyADR.bat to launch.")
print("=" * 60)
