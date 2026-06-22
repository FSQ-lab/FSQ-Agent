# Automation Basics

- Use only configured harness tools and CommonTool utilities for external actions.
- Prefer semantic actions and stable locators over coordinate-only gestures.
- Use fresh observations after state-changing actions; historical artifacts are context only.
- Correct invalid tool arguments or schema usage for the same semantic action before fallback.
- For coordinate gestures, derive points from current element bounds; scale old coordinates only as a fallback.
- A sent gesture is not proof. Verify the intended UI state afterward.
- Ordered actions define semantic success. Non-equivalent recovery leaves the original action unmet.
