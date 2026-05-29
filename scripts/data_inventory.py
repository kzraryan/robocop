#!/usr/bin/env python
"""Walk the NICU data tree and report what's actually on disk.

    python scripts/data_inventory.py            # all sites
    python scripts/data_inventory.py MU Iowa    # specific sites

For each site prints the file list (dir / name / size) under its NICU tree, so
you can reconcile the data guide against reality before writing loaders.
"""

from __future__ import annotations

import sys

from robocop import SITES
from robocop import data
from robocop.config import DATA_ROOT, site_root


def main(argv: list[str]) -> int:
    sites = argv or list(SITES)
    print(f"DATA_ROOT = {DATA_ROOT}  (exists={DATA_ROOT.exists()})\n")
    for site in sites:
        root = site_root(site)
        print(f"=== {site} :: {root}  (exists={root.exists()}) ===")
        df = data.inventory(site)
        if not len(df):
            print("  (no CSV/XLSX found)\n")
            continue
        total = df["size_mb"].sum()
        for _, r in df.iterrows():
            print(f"  {r['size_mb']:8.2f} MB  {r['dir']}/{r['name']}")
        print(f"  -- {len(df)} files, {total:.1f} MB total\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
