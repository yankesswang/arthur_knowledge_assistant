# Web Search Strategies for Flight Prices

## Recommended query patterns

Use these in order of reliability. Stop when you get a clear price.

### 1. Google Flights-style query
```
cheapest flights {ORIGIN} to {DEST} {DATE}
```
Example: `cheapest flights LAX to JFK March 15 2026`

### 2. Route + date specific
```
{ORIGIN} {DEST} flight {DATE} price $
```
Example: `LAX JFK flight 2026-03-15 price $`

### 3. Aggregator sites
```
{ORIGIN} to {DEST} {DATE} site:kayak.com OR site:expedia.com OR site:skyscanner.com
```

### 4. Specific airline (if user has a preference)
```
{AIRLINE} {ORIGIN} to {DEST} {DATE} fare
```

## Extracting prices from results

Look for patterns in search snippets:
- `$NNN` or `$N,NNN` — dollar amounts
- `from $NNN` — lowest available price
- `USD NNN` — alternate format
- Ignore prices that are clearly per-person for groups or round-trip totals when user wants one-way (and vice versa)

## When search results are stale or unhelpful

1. Try a broader date range query and then mention to the user that exact prices for their date were unavailable.
2. Tell the user to verify the price directly and report back — you can accept manual entries.
3. Note in the history record that the source is `"web_search_estimated"` or `"manual"`.

## Seasonal pricing notes

- Prices typically drop 6–8 weeks before domestic US flights.
- Holiday travel (Thanksgiving, Christmas, spring break) books up early — check more frequently.
- Tuesday/Wednesday departures are often cheaper than Friday/Sunday.
- These are heuristics — always check actual data rather than assuming.

## Rate limiting consideration

Since Claude uses WebSearch (not automated scraping), there's no rate limiting concern. But remind users that prices change constantly and a "check" is a snapshot, not a live feed. Recommend re-checking every few days for the best results.
