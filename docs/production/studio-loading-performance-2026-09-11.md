# Studio scene loading — 11 September 2026

The page shell and projects endpoint returned in 3–4 ms locally. The Scene 1 package endpoint returned 15,436,691 bytes and took 4.6 seconds warm. This identifies scene-data preparation and transfer as a material cause, rather than the page shell alone.

Implemented:

- JSON transport uses compact separators and negotiated gzip, preserving decoded fields and `no-store`. Clients refusing gzip receive plain JSON.
- Simultaneous reads share one production-state calculation per scene. Invalidation during a calculation prevents republishing it into cache.
- Nested scene-look checks use their caller's package snapshot rather than repeatedly reopening it. A measured preflight previously loaded the package 70 times; the changed path loaded it 28 times, with unchanged signature results in the fixture test.

Live local endpoint measurements after server reload: cold 8.43 seconds, warm 2.19 seconds, 3,493,689 transferred bytes. The compression-only cold comparison was 17.05 seconds and warm 4.59 seconds. These are endpoint measurements, not browser paint timings or a guarantee for every scene. First-load work remains noticeable.

Validation: six transport/concurrency tests, one supplied-package signature-equivalence test, 33 HTTP/auth tests and 25 existing golden-path tests passed. `git diff --check` and Python compilation passed. No production approval or media was changed.
