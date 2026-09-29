# Design QA — Settings Integrations

## Comparison target

- Source visual truth: `/home/devops/.codex/generated_images/01a0ec74-db0c-7da2-84a1-853e4a46edbd/exec-582eb5fc-ebed-41c7-a8b3-ad17487b4e32.png`
- Implementation screenshot: unavailable
- Intended viewport: 1440 × 1024 CSS pixels
- Source pixels: 1488 × 1024
- Implementation pixels: unavailable
- Density normalization: not performed; no implementation capture exists
- State: default Integrations catalog, with connected and available services visible

## Findings

- [P1] Rendered visual comparison is blocked.
  - Location: `/settings/integrations`
  - Evidence: the source image is available, but the local Next.js dev server cannot bind in this environment (`listen EPERM: operation not permitted 0.0.0.0:3000`) and no browser renderer is available to capture the implementation.
  - Impact: layout fidelity, responsive behavior, focus states, and primary interactions cannot be verified from the rendered page.
  - Fix: run the app in an environment that permits a browser-rendered capture, then compare the same 1440 × 1024 state and test filtering, search, Connect, Manage, and Request an integration.

## Required fidelity surfaces

- Fonts and typography: not assessed from a rendered implementation.
- Spacing and layout rhythm: not assessed from a rendered implementation.
- Colors and visual tokens: not assessed from a rendered implementation.
- Image quality and asset fidelity: not assessed from a rendered implementation.
- Copy and content: source-aligned copy is present in the implementation, but visual wrapping is not assessed.

## Comparison history

- No P0/P1/P2 fix iteration was possible because implementation capture was blocked before comparison.

## Implementation checklist

- [x] Add the protected `/settings/integrations` route.
- [x] Replace the planned Integrations label with a real Settings navigation link.
- [x] Add catalog cards, connected/available grouping, search, category filters, and local preview actions.
- [x] Verify production build and lint.
- [ ] Capture browser-rendered implementation and complete visual QA.

final result: blocked
