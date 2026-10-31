# Three.js optimization

Applied the `threejs-performance`, `threejs-geometry` and `threejs-lighting` skills from [CloudAI-X/threejs-skills](https://github.com/CloudAI-X/threejs-skills), pinned to commit `0e181866f095b5f06d005133876e926515390d95`. The clone is in the ignored `artifacts/threejs-skills/` directory. The three skills are also installed in the local Codex skill directory.

The guidance targets r186. This demo retains its vendored r170 runtime. Instancing, dynamic instance buffers, conservative culling bounds, shadow caching and shared resources were checked against that runtime; no r186-only APIs were introduced.

## Changes

- All 98 vehicles use eleven instanced batches sharing one box geometry. Vehicle parts keep their original scale, color, roof and windshield shape.
- Route positions and tangents are cached at load time. Frame updates interpolate typed arrays and reuse a transform and matrix.
- The fixed instance bounding spheres cover every route and vehicle extent. Frustum culling remains enabled.
- Station, stadium and landmark boxes share a unit geometry. Repeated materials and park geometry are reused, and the ocean strokes are one line-segment object.
- Building and landmark shadow maps are generated once. Moving vehicles do not cast into that cache, avoiding stale vehicle shadows.
- Static object matrices are frozen. Map labels are reprojected only after camera or layout changes.
- A settled, paused scene submits no new renders. UI playback text updates at most ten times per second; vehicle motion continues at the normal animation cadence.
- Shared resources are disposed once, including instance buffers and the directional shadow map.

## Structural comparison

Measured using the real r170 scene graph with a mocked GPU renderer and DOM harness. The draw estimate assumes every scene primitive is submitted, includes material groups, and excludes shadow passes and frustum rejection. It is not a GPU draw-call reading or an FPS measurement.

| Measure | Before | After |
| --- | ---: | ---: |
| Mesh objects | 282 | 82 |
| Unique geometries | 211 | 44 |
| Unique materials | 105 | 53 |
| Main-pass draw upper bound | 310 | 101 |
| Shadow-casting mesh objects | 139 | 41 |
| Submissions across 120 settled paused updates | 120 | 0 |

Direct browser/GPU profiling remains unavailable in this environment. To inspect actual WebGL counters after rendering, open the demo with `?lang=fr&perf=1` and evaluate `rabatFlowPerformance()` in the browser console. It returns actual `renderer.info` counters, the vehicle batch count and the shadow-cache setting.

## Verification

`npm test` builds the offline bundle and covers the bilingual scenario plus the fleet's movement, paused state, rerouting, mode filters, reset, conservative culling bounds and shared-resource ownership. No network or additional runtime dependency is required.
