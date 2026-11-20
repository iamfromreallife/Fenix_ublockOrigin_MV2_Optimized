# Fenix MV2 — Optimisation Changelog

Input baseline: `Fenix_uBO_MV2_1.76.5b6_Merged.zip`  
Output: `Fenix_uBO_MV2_Full_Performance_Optimized.zip`

## Changes

1. **`js/resources/scriptlets.js` — YouTube `/get_watch` response streaming**: Replaced unconditional eight-byte suffix retention and whole incoming-chunk concatenation with an exact partial-prefix detector. Unrelated chunks are passed through without copying. Only up to eight bytes are retained if the end of a chunk could begin `"adSlots"`. First-match-only `"adSlots"` → `"no_ads"` transformation and original response handling remain in place. The initial, slower prototype was rejected; only the verified prefix-aware implementation was retained.
2. **`js/scriptlets/youtube-player.js` — Promise callback scanning**: Added a `WeakMap` source-match cache behind the existing two-entry MRU. This avoids rescanning reusable callbacks that recur after more than two other handlers. Existing MAIN-world scope/route checks, native-call forwarding, and positive-match handling remain intact.
3. **`js/scriptlets/epicker.js` — selector candidate optimisation**: Construct CSS selector suffixes incrementally instead of repeatedly slicing and joining the candidate path array. Candidate ordering, query operations and outgoing messages remain the same.

## Explicitly preserved

- All other **668** package files (including `manifest.json`, `js/storage.js`, network/cosmetic filter engines, popup resources, translations, WASM modules, SABR stream rewriter and licensing) are byte-identical to the supplied baseline.
- Manifest V2, original version **1.76.5.6**, Chrome permissions, extension UI, configuration/schema, and external resource set remain unchanged.
- No additional telemetry, dependencies, external assets, filters or permissions.

The exact source diff is available in `Fenix_Optimization_Changes.patch`.
