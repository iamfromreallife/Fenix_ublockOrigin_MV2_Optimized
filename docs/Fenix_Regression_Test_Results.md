# Fenix MV2 — Regression Test Results

## Completed checks

| Test | Result | Details |
|---|---|---|
| Package/manifest integrity | PASS | 671 files, valid MV2 manifest at ZIP root, unchanged version/permissions/entrypoints; CRC verified. |
| JavaScript parsing | PASS | All 210 `.js` files passed `node --check`. |
| Module and HTML references | PASS | All 349 selected local JS imports and 349 static HTML resource references resolved. |
| Localisation and WASM | PASS | 72 locale JSON files parsed; 4 WASM headers checked. |
| `/get_watch` chunk streaming | PASS | 1,356 deterministic baseline-vs-final byte-for-byte cases (random payloads, random boundary sizes, no/one/multiple matches, missing/empty bodies). |
| YouTube player hooks and SABR framing | PASS | 37 VM/stream cases covering player request scoping, Request/XHR/encoder/JSON, 20 chunk-size permutations, malformed frames, policy >4 KiB, truncated headers, incremental output and reader cancellation. |
| Promise callback suppression and scoping | PASS | 300 alternating callbacks, 3 source inspections versus 300 baseline; out-of-scope route remains unaffected. |
| Quick Fix preservation | PASS | 10 conservative replacement and bypass checks extracted from the unchanged `js/storage.js`. |
| Element picker selector output | PASS | 800 generated parity cases, identical selected filters, ordering and outgoing messages. |
| Chromium stream microbenchmark | COMPLETED | Two synthetic benchmark batches in Chromium 144; see Performance Comparison. |
| Full MV2 extension in a browser | **NOT VERIFIED** | Chromium 144 did not register the MV2 extension in the test profile, including with tested command-line flags. |
| Live YouTube playback / ad blocking / filter list update | **NOT VERIFIED** | Requires a supported MV2 Chromium environment and a realistic live browsing/profile setup. |
| End-to-end CPU and memory usage | **NOT MEASURED** | Cannot reliably attribute or compare without the loaded extension. |

## Runtime used

- Node.js 22.16.0 with V8 12.4 for fast execution and byte-equivalence checks.
- Headless Chromium 144.0.7559.96 with V8 14.4 for isolated stream benchmarks.
- No telemetry, external services or test-only code added to the shipped extension.

## How to reproduce

Download the test-suite archive and extract `tests/` next to two unpacked directories named `base/` and `optimized/` containing the original and final extension source trees. Run:

```bash
node tests/watch-stream-test.mjs
node tests/youtube-player-test.mjs
node tests/promise-hook-test.mjs
node tests/epicker-test.mjs
node tests/quickfix-test.mjs
python tests/package-audit.py
node --expose-gc tests/watch-benchmark.mjs
python tests/browser-stream-benchmark.py
```

The last script requires Python Playwright and a Chromium executable at `/usr/bin/chromium` (adjust locally if needed).
