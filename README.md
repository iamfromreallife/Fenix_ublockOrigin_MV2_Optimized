# Fenix uBlock Origin MV2 — Optimized

Custom Manifest V2 Chromium build based on upstream [gorhill/uBlock](https://github.com/gorhill/uBlock), with fixes for speed, cpu and memory usage. Also contains fixes specifically made for youtube.

## Installation

Download a published zip file from relases, unpack it, and load it as an unpacked extension in an MV2-capable browser. Modern Chromium versions may refuse to load MV2 extensions; check browser support before installing.

## Attribution

uBlock Origin is developed by Raymond Hill and contributors. This project retains the original upstream licensing notices and is a separately maintained derivative. No official association is implied.


# Fenix Optimized MV2 — Changes Compared with Official uBlock Origin

**Base version:** uBlock Origin 1.76.6  
**Extension architecture:** Chromium Manifest V2  
**Comparison source:** Official `gorhill/uBlock` release tag `1.76.6`

## 1. YouTube advertisement handling and player performance

The most substantial Fenix-specific changes concern YouTube video playback, advertisement-related player requests and the SABR streaming protocol.

**Files:** `js/scriptlets/youtube-player.js`, `js/scriptlet-filtering.js`, `js/resources/scriptlets.js`, `js/storage.js`.

Unlike the official release, Fenix includes a dedicated YouTube player interception module.

This module intercepts selected JavaScript operations involving `JSON.stringify`, `TextEncoder`, `Request`, `XMLHttpRequest`, `fetch` and `Promise.prototype.then`.

Its main functions are:

- Identify qualifying YouTube `/youtubei/vN/player` and `/youtubei/vN/get_watch` requests.
- Modify compatible player request fields to request an advertisement-free playback context.
- Avoid unnecessary parsing and object allocation for unrelated requests.
- Preserve selected playback restrictions and ignore unsupported request contexts.
- Intercept qualifying SABR streams and modify validated backoff policies without buffering the complete media response.
- Avoid repeatedly inspecting the source of reusable player callbacks.

### SABR streaming optimisation

The custom SABR implementation processes UMP response parts incrementally.

It specifically examines type 35 `NEXT_REQUEST_POLICY` messages, buffering qualifying policy payloads of at most 4 KiB.

When a recognised backoff value is found, it can be rewritten to zero without changing the overall packet length or UMP framing.

Other media parts are forwarded without deliberate modification.

This is intended to reduce unnecessary playback delays associated with the relevant SABR backoff mechanism.

### `/get_watch` response streaming

The official generic `replace-fetch-response` mechanism may wait for a complete response body before replacing text.

Fenix introduces a targeted incremental streaming implementation for replacing `"adSlots"` with `"no_ads"`.

The latest optimisation avoids repeatedly allocating combined buffers for nonmatching chunks. It retains only the bytes potentially needed to recognise a match crossing a chunk boundary.

**Measured result:** In isolated Chromium 144 benchmarks, this streaming operation was approximately 18–26% faster in the tested synthetic workload.

These results do not establish an equivalent improvement in real-world video startup time.

## 2. Faster cosmetic filtering and element hiding

**Files:** `js/contentscript.js`, `js/cosmetic-filtering.js`.

The official uBlock Origin already contains sophisticated cosmetic filtering. Fenix modifies selected scheduling, data structures and caching mechanisms.

The main changes include:

- Scheduling DOM mutation processing directly through animation-frame batching, avoiding an intermediate timer in the relevant path.
- Using a `Set` for stylesheet deduplication instead of repeatedly searching an array.
- Hiding confirmed blocked DOM resources promptly while the normal CSS injection completes.
- Reducing repeated DOM-survey array allocations.
- Using queue indexes and offsets instead of repeated array `shift()` and `slice()` operations.
- Avoiding unnecessary resolved-Promise allocations for empty survey results.
- Consolidating bursts of resource-error processing to reduce extension messaging.
- Releasing observers, queued nodes and pending timers when processing stops.

Fenix also introduces two bounded cosmetic-filter caches.

The generic selector bucket cache can retain up to 96 entries within approximately 256 KiB.

The specific candidate cache can retain up to 32 entries within approximately 128 KiB, and only caches sufficiently expensive selector collections.

The intended benefits are lower garbage-collection pressure, reduced repetitive selector processing and faster application of relevant cosmetic rules.

## 3. Network filtering and HTTP-header processing

**Files:** `js/static-net-filtering.js`, `js/traffic.js`, `js/pagestore.js`.

Fenix retains the official network-filtering architecture but modifies selected header-processing paths.

### Header matching

Official code combines response and request headers into a flattened collection before evaluating header rules.

Fenix keeps the original arrays separate and searches them directly.

When sufficiently many different header lookups are needed, a temporary index is constructed for the current request.

This avoids unconditional array merging while retaining the intended header lookup precedence.

### Resource-type prefiltering

Fenix introduces a header-rule type mask.

Before performing certain header-related operations, the extension checks whether the loaded filtering rules could match that request's resource type.

If no applicable header rule exists, the unnecessary matching work can be skipped.

### Network event handling

The modified traffic module reduces unnecessary work by:

- Avoiding header retention for requests that cannot match relevant header rules.
- Limiting the Chromium response-start listener to main-frame requests.
- Skipping some MIME processing for nontext resource types.
- Avoiding repeated trust checks that a caller has already performed.
- Reusing a shared empty-header collection.

### Blocked-resource cache

The page-store module replaces a timestamp-based cache revision identifier with a revision counter updated when the blocked-resource set changes.

This prevents separate changes occurring within the same millisecond from accidentally sharing the same revision identifier.

Together, these changes target repeated overhead in network-request processing.

## 4. Trusted-site matching optimisation

**File:** `js/trusted-sites.js`.

Official code constructs regular expressions when matching wildcard or regex-based trusted-site directives.

Fenix introduces a bounded cache holding up to 64 compiled expressions.

Repeated evaluations of the same directive can reuse the cached expression instead of compiling it again.

Exact-string matching remains unchanged.

## 5. My Filters editor optimisation

**File:** `js/1p-filters.js`.

The official implementation determines whether the user's filter-editor configuration has changed by serialising complete state objects with `JSON.stringify()`.

Fenix instead compares the two relevant checkbox settings directly and then compares editor text.

This removes unnecessary serialisation of potentially large custom-filter documents during editor interactions.

No additional filtering syntax or new editor controls are introduced by this change.

## 6. Element-picker optimisation

**File:** `js/scriptlets/epicker.js`.

Official code generates overlapping selector suffixes using repeated `Array.slice()` and `Array.join()` operations.

Fenix builds these selector strings incrementally from right to left.

This removes repeated intermediate array allocations while retaining the candidate selection algorithm.

**Measured result:** The final optimisation showed approximately 16–21% faster selector generation in synthetic tests, with 800 generated equivalence cases passing.

The element-picker UI resources themselves were not changed relative to the corresponding official sources.

## 7. YouTube Quick Fix compilation

**File:** `js/storage.js`.

Fenix selectively modifies recognised versions of the upstream YouTube recovery rule during filter compilation.

The modifications target repeated callback source inspection, unnecessary recovery-script executions and redundant logging operations.

The implementation requires the expected rule fragments to be present before applying substitutions.

Unrecognised upstream Quick Fix variants remain unchanged.

This is important for compatibility because upstream YouTube recovery rules can change independently of extension releases.

## 8. Internal cache compatibility

**File:** `js/background.js`.

Fenix updates the compiled-filter and engine-snapshot compatibility markers:

| Marker | Official | Fenix |
|---|---:|---:|
| `compiledMagic` | 72 | 74 |
| `selfieMagic` | 72 | 73 |

These changes prevent incompatible cached data from being reused after modifications to the relevant filtering internals.

They do not change the public extension version or browser permissions.

## 9. Changes introduced in the latest optimisation pass

Compared with the immediately preceding Fenix merged build, only three files were modified:

- `js/resources/scriptlets.js` — prefix-aware incremental `/get_watch` processing.
- `js/scriptlets/youtube-player.js` — weak-reference cache for repeated Promise callbacks.
- `js/scriptlets/epicker.js` — incremental selector suffix construction.

All other files remained identical to the preceding Fenix build.

## 10. What remains identical to official uBlock Origin

The current Fenix build does not replace the official filtering engine with a separate implementation.

Most of the core filtering parser, trie-based matching, redirect handling and extension resources remain unchanged.

Importantly, `popup-fenix.html`, `js/popup-fenix.js` and `css/popup-fenix.css` are identical to the corresponding official tagged sources. The official Chromium manifest already uses the Fenix popup.

Therefore, the popup design itself is not a distinguishing modification in this release.

## Conclusion

The intended result is reduced CPU and memory overhead, lower latency and more efficient YouTube handling while retaining the core uBlock Origin architecture.

These are implementation-level differences. Selected benchmarks and regression tests passed, but complete live MV2 browser compatibility and whole-extension performance improvements have not been independently established.
