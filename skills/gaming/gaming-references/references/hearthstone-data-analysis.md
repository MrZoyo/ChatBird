# Hearthstone Data Analysis

## Canonical Retrieval Rule

Use `web_search` and `web_extract` as the end-to-end retrieval interface. When validating whether a source is usable, test those tools before reaching a conclusion. A failed direct page route does not prove that search indexing or the configured extraction fallback failed.

Do not repeatedly retry the same failed route. Do not treat an HTTP success response as useful unless it contains the requested data.

## Source Roles

### MetaStats.net

- Use for deck and archetype win rate by rank, popularity, sample size, and deck lists.
- Prefer Diamond-Legend or Legend when the user does not specify a rank.
- Use as the default live statistical source when its requested fields are present.

### HSGuru

- Use for current Meta pages and a second statistical perspective.
- Retrieve through a natural `web_search` query that explicitly names HSGuru. Hermes may use a bounded HSGuru public-index fallback when ordinary results omit the site.
- Treat HSGuru as public-index usable but direct-page unavailable on the production host.
- Do not request its blocked statistics, deck-list, or query-driven automated routes.
- Search snippets can establish indexed page context; do not claim an exact current statistic unless the returned evidence contains it.

### Vicious Syndicate

- Use Data Reaper reports for power rankings, high-rank environment analysis, matchup explanations, counters, and trends.
- First use `web_search` to locate the current clean article URL on `www.vicioussyndicate.com`, then use `web_extract` on that URL.
- The configured extraction path can return article text through an allowlisted read-only fallback even when direct page navigation is challenged.
- Use report dates and rank segments. Do not treat editorial analysis as the only live statistical source.

### Hearthstone-Decks.net

- Use for recent Top Legend lists, player ranks, and short player records.
- A single player's record supports use at high rank, not an overall archetype win rate.

### HSReplay

- Use for card, mulligan, and matchup data only after `web_search` or `web_extract` returns the requested data fields.
- Treat navigation-only or challenge content as unusable.
- Do not infer useful access merely because a rendering component is installed.

## Analysis Flow

1. Query MetaStats for live archetype statistics.
2. Query HSGuru through `web_search` for an indexed second view.
3. Locate the latest relevant Vicious Syndicate article with `web_search`, then read it with `web_extract`.
4. Use Hearthstone-Decks.net for current high-rank list evidence.
5. Add HSReplay only if the canonical tools return useful fields.
6. Reconcile differences in rank, patch, date, archetype definition, and sample size.

## Reporting

For each important number, include the source, rank segment, date or patch, and sample size when available. Separate these conclusions:

- strongest overall archetype;
- practical ladder choice;
- high-Legend environment;
- exact list evidence;
- remaining uncertainty or source disagreement.

When asked to test source accessibility, report route-level results. For example, say that direct navigation was challenged while HSGuru public-index search or Vicious Syndicate `web_extract` succeeded. Do not summarize a route-specific challenge as total source failure.
