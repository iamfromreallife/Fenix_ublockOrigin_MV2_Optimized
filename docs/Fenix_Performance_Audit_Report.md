# Fenix uBlock Origin MV2 — Performance and Code Audit

**Source:** `Fenix_uBO_MV2_1.76.5b6_Merged.zip`  
**Final build:** `Fenix_uBO_MV2_Full_Performance_Optimized.zip`  
**Extension manifest:** MV2; **version retained:** 1.76.5.6

## Executive assessment

A structural and static integrity audit covered the complete supplied package (671 files, including 210 JS, 32 CSS, 24 HTML, 72 locale directories and 4 WASM resources). The review also examined key filtering, content-script, background, storage, popup, element-picker and custom YouTube paths. Changes were limited to three empirically testable improvements; all other original files are byte-identical. **This is a completed deliverable, not a claim that every possible performance inefficiency has been eliminated.** Full behavioural verification of an MV2 extension inside a compatible browser, including real YouTube playback, was not possible in the test environment.

## Findings and implemented changes

| ID | Priority | Component / file | Root cause | Change | Evidence | Risk / validation |
|---|---|---|---|---|---|---|
| F-01 | P1 | Streaming YouTube `/get_watch`: `js/resources/scriptlets.js`, `streamWatchResponse()` | Original code retains the last eight bytes unconditionally and constructs a combined allocation for every subsequent chunk before searching for the first `"adSlots"` token. | Recognise only a potentially matching partial prefix; forward normal chunks directly; buffer at most eight bytes when a prefix spans a boundary; retain first-match and fail-open behaviour. | Two Chromium 144 microbenchmark batches showed 17.9%–26.0% median improvement across 4–64 KiB chunks, using a synthetic 4 MiB no-match stream. Node timing varied and is explicitly not treated as a universal gain. | Medium: 1,356 baseline-vs-final byte-exact tests, plus JS syntax, intact endpoint restriction. |
| F-02 | P1 | YouTube Promise hook: `js/scriptlets/youtube-player.js`, `Promise.prototype.then` interception | The two-entry MRU repeatedly inspects the same function sources when 3+ distinct callbacks alternate. | Keep the existing two-entry fast path; add weak-key source-match cache for older reused callbacks. | Instrumented scenario: 300 calls to `Function.prototype.toString()` before, 3 after, over 300 `.then` calls with three rotating callback functions. This is an operation count, not a measured 99% reduction in page CPU. | Low/medium: correct callback suppression, nonmatching callbacks and scope changes checked. Weak keys do not strongly retain dead callbacks. |
| F-03 | P2 | Element picker: `js/scriptlets/epicker.js`, `onOptimizeCandidates()` | Builds overlapping CSS selector suffixes via repeated `slice().join()` and short-lived arrays. | Incrementally prepend the selector fragments while preserving exact selector ordering. | 800 generated parity cases; synthetic benchmark observed ~16%–21% lower median runtime (different local runs). DOM query cost on actual websites may dominate. | Low: identical candidate ranking and displayed selector output in the test corpus. |

## Inspected major subsystems

| Subsystem | What was checked | Changes / reason |
|---|---|---|
| Network filtering: static/dynamic matching, request context, redirect, tries | Source structure, critical matching call paths, module linkage and syntax. | Left unchanged: no validated benefit from changing core filtering semantics without a representative filter corpus and end-to-end webRequest tests. |
| Cosmetic filtering, DOM watcher/surveyor | Mutation scheduling, observer subscription and lifecycle cleanup patterns, document-start path. | Left unchanged: changes to observer cadence or CSS injection require live cross-site traces. |
| YouTube MAIN-world injection and player interception | Validation/scope checks, JSON/encoder/XHR/Request interception, SABR UMP framing, fetch response conditions and Promise hook. | Weak-key callback cache; preserve SABR parser and its bounded type-35 policy buffering unchanged. |
| `/get_watch` response rewriter | Chunk boundaries, first-match replacement, buffer retention, fallback and response metadata forwarding. | Prefix-aware streaming replacement (F-01). |
| Filter-list compiler and YouTube Quick Fix | Compiled-rule parsing and targeted replacement logic. | Preserved unchanged; 10 focused tests of conservative Quick Fix matching. |
| Background/events, storage, assets, caches, compression | Source/dependency audit of relevant modules and API references. | Preserved unchanged: no grounded performance profile sufficient to justify rewriting. |
| Fenix popup, dashboard, logger, UI/CSS | Source and resource links, event and polling paths, locale integrity. | Preserved layout and logic unchanged; no accurate live popup latency capture. |
| Element picker/zapper | Candidate generation and selector ranking; related packaging. | Optimised suffix construction only (F-03). |
| Binary assets and internationalisation | WASM magic checks, locale JSON validity, resource existence. | All preserved byte-for-byte. |

## Integrity inventory

- **210/210 JavaScript files:** syntax checks passed.
- **349 static local import paths:** resolved.
- **349 referenced HTML resources:** resolved.
- **15 directly referenced manifest assets:** present.
- **72 locale directories:** `messages.json` present and valid.
- **4 WASM modules:** valid magic headers.
- **671 files:** same complete set before and after; only the three listed JavaScript files changed.
- Original permissions, MV2 manifest, feature options and extension version retained.
- The ZIP passes CRC/data integrity testing; `manifest.json` is at archive root.

## Performance context and limitations

Results are **microbenchmarks**, not whole-extension performance measurements. Chromium 144 can execute isolated stream logic and was used for that purpose, but it did not register this MV2 extension for headless browser testing. Consequently there are no trustworthy whole-extension CPU, heap, filter-list, DOM paint, navigation or real YouTube playback measurements. These are **not marked as passed**. Tests do not establish complete equivalence across every filter list, browser version, or live page.

Node/V8 runs showed environment-dependent variance, including minor regressions for some chunk sizes; Chromium 144 runs consistently improved for the stated synthetic workload. No generalised speedup percentage is claimed for browsing, filtering, or playback.

The core network and cosmetic filtering engines have not been modified. This sharply limits filtering-regression exposure but is not a substitute for an actual browser compatibility test.
