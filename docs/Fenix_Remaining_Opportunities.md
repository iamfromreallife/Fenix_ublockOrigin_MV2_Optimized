# Remaining Opportunities, Unverified Paths and Risks

The following areas are intentionally **not represented as fixed**. They require a loaded MV2 runtime, live traces and/or representative filter corpora before source changes can be defended:

1. **Network filter hot paths and compilation:** Record per-request latency p50/p95/p99 on real navigation and controlled ad-filter corpora. Do not alter trie format, filter precedence or redirect matching without differential outputs.
2. **Cosmetic filtering:** Capture DOM mutations, observer count, stylesheet changes and paint timing on pages with tens of thousands of elements. Avoid changing scheduling heuristics based solely on static inspection.
3. **YouTube streaming:** Validate live SABR requests, `get_watch` chunk shape, playback startup, seeking, playlists, fullscreen, Shorts and live sessions on current YouTube versions.
4. **Background and storage:** Profile cold start, compiled list caching, IndexedDB and Chrome storage activity in a compatible browser using realistic filter-list sizes and update cycles.
5. **Fenix popup and logger:** Measure popup first contentful render, layout and polling costs with live tab data; DOM query stubs do not capture real browser layout costs.
6. **Memory:** Run heap snapshots and long-session navigation churn with normal, blocked and trusted sites. WeakMap callback keys do not strongly retain handlers, but runtime memory remains unmeasured.
7. **Compatibility:** Repeat the tests in the actual browser that will install the MV2 build; Chromium 144 here does not register MV2. No supported-browser compatibility conclusion is possible from syntax and archive integrity alone.

The final ZIP retains the original filters, settings, user data compatibility structures and all unmodified upstream code. This reduces regression exposure but cannot guarantee correctness in every environment.
