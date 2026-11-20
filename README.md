# Fenix uBlock Origin MV2 — Optimized

Custom Manifest V2 Chromium build based on upstream [gorhill/uBlock](https://github.com/gorhill/uBlock), retaining the Fenix interface, YouTube streaming and player fixes, element picker behaviour and performance improvements.

## Repository layout

- `extension/` — unpacked MV2 extension, maintained by the synchronisation workflow.
- `dist/` — packaged, complete installable MV2 ZIP.
- `.github/workflows/` — initial snapshot installer and upstream release monitor.
- `scripts/` — deterministic release downloader, three-way updater and validation.
- `.fenix/state.json` — upstream version on which the committed extension was last synchronised.

The initial optimized ZIP is preserved byte-for-byte during bootstrap, then unpacked into `extension/`. The automation checks the upstream **stable and prerelease** GitHub releases, selects official Chromium ZIP assets, and rebases changes onto the current Fenix build using three-way merges. If an upstream edit overlaps a Fenix change, the workflow **fails closed** instead of dropping modifications.

The workflow relies on scheduled polling because a GitHub release event in `gorhill/uBlock` cannot directly trigger `release` in a different repository. GitHub schedules can be delayed; there is no absolute real-time guarantee.

## Installation

Download a ZIP from `dist/`, unpack it, and load it as an unpacked extension in an MV2-capable browser. Modern Chromium versions may refuse to load MV2 extensions; check browser support before installing.

## Attribution

uBlock Origin is developed by Raymond Hill and contributors. This project retains the original upstream licensing notices and is a separately maintained derivative. No official association is implied.
