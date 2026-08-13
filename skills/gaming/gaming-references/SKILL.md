---
name: gaming-references
description: Research current game statistics and source-specific evidence for Hearthstone and League of Legends, including Meta, win rates, usage, deck lists, matchups, high-rank performance, and ARAM rankings.
---

# Gaming References

Use current evidence and give concrete answers rather than redirecting the user to a data site.

## Hearthstone

Read `references/hearthstone-data-analysis.md` before answering current Hearthstone Meta, deck-strength, win-rate, usage, matchup, build, or high-rank questions.

## League of Legends

For ARAM Mayhem questions, prefer `arammayhem.com` and use `web_extract` on its relevant public page. Report champion names and values directly.

Interpret the Chinese gaming slang term "蛆" as weak or bad, not strong or overpowered.

## Evidence Rules

- State the rank range, patch or date, sample size, and distinction between archetype and exact list when available.
- Cross-check important claims across sources with different roles.
- Distinguish a route-specific retrieval failure from the site's overall usability through `web_search` and `web_extract`.
- If current evidence is incomplete, say exactly which source or field is missing. Do not invent a complete ranking.
