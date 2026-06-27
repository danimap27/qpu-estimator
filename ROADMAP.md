# QPU-Estimator Roadmap

## Phase 0 — MVP (Current)

- [x] Core architecture: analyzer, profiler, transpiler, estimator
- [x] Circuit analysis: gate counts, depth, CNOT count, measurement count
- [x] Backend profiling: mock IBM backend properties (T1, T2, gate errors, connectivity)
- [x] Transpilation estimation: basis gate conversion, swap insertion heuristic
- [x] Resource estimation: execution time, optimal shots, fidelity, credits
- [x] CLI entry point
- [x] Unit tests with pytest
- [x] GitHub repo + initial README

## Phase 1 — IBM Integration (✅ COMPLETE)

- [x] Live backend profiling via `qiskit-ibm-runtime`
- [x] Real transpilation with `qiskit.transpiler`
- [x] Dynamic error rate fetching from IBM calibration data (T1, T2, gate errors, readout)
- [x] Fallback to mock profiles when live data unavailable
- [x] Multi-backend comparison with live data
- [ ] IBM credit pricing table (manual + scrape fallback) — moved to Phase 2

## Phase 2 — Advanced Estimation

- [ ] Noise-aware fidelity prediction (depolarizing + thermal relaxation)
- [ ] Shot optimization for desired precision (Hoeffding / Chernoff bounds)
- [ ] Multi-backend comparison (rank backends by estimated fidelity/cost)
- [ ] Queue time estimation (historical data + heuristics)

## Phase 3 — QML Specialization

- [ ] VQC-specific estimators (parameterized circuits, repeated evaluations)
- [ ] MAML/QMAML multi-task cost estimation
- [ ] Transfer learning overhead: classical + quantum partition analysis
- [ ] Batch evaluation cost for training loops

## Phase 4 — Ecosystem

- [ ] Web dashboard for visual comparison
- [ ] CI integration: fail if estimated cost exceeds budget
- [ ] Export to LaTeX tables for papers
- [ ] Plugin system for custom backends (IonQ, Rigetti, etc.)

## Backlog

- Caching backend profiles to avoid repeated API calls
- Parallel estimation across multiple backends
- Historical tracking: store estimations vs actual execution metrics
