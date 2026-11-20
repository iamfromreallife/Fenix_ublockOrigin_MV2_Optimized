# Before/after performance comparison

Benchmarks compare functions extracted from the original and final sources; they do not measure entire-extension performance. All times are measured in milliseconds. Lower is better.

## Chromium 144 / V8 14.4: `/get_watch` stream processing

4 MiB synthetic stream with no match, streaming via `ReadableStream` and `TransformStream`. Twenty-one interleaved timing samples per version and chunk size, after three warm-up iterations per version. Two independent headless Chromium runs:

| Chunk size | Run 1 baseline | Run 1 final | Run 1 change | Run 2 baseline | Run 2 final | Run 2 change |
|---:|---:|---:|---:|---:|---:|---:|
| 4 KiB | 26.5 | 20.7 | +21.9% | 21.2 | 16.1 | +24.1% |
| 16 KiB | 20.2 | 16.3 | +19.3% | 16.6 | 12.4 | +25.3% |
| 64 KiB | 12.3 | 10.1 | +17.9% | 13.1 | 9.7 | +26.0% |

**Important:** The Chromium timings are synthetic, and Node 22/V8 12.4 measurements varied by run, sometimes showing no speedup or a small slowdown. Performance will depend on chunk shape, browser version, memory pressure and the surrounding extension/page workload.

## Element-picker selector generation

| Benchmark | Baseline median | Final median | Difference |
|---|---:|---:|---:|
| Synthetic 130 candidates × 25 fragments, repeated batches, one test run | 383.99 ms | 302.83 ms | +21.1% faster |

The test uses a deterministic stub for `document.querySelectorAll()`. It validates string-building and message generation; it **does not** measure real DOM query latency.

## Reused Promise callbacks

| Scenario | Baseline source inspections | Final source inspections | Difference |
|---|---:|---:|---:|
| 100 cycles through 3 distinct callbacks | 300 | 3 | 297 avoided source conversions |

This is an instrumented call count, not a whole-page CPU or memory benchmark.

## Full-extension metrics

Startup, network filtering, ad blocking, DOM paint time, per-tab CPU/memory, actual YouTube TTFB/playback and popup opening: **not measured** (no compatible runtime for extension load). No values or improvements have been inferred.
