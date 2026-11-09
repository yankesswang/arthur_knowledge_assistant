---
name: flight-tracker
description: Track flight prices over time and surface the cheapest options. Use this skill when the user wants to monitor airfare for a specific route and date, check current prices, review price history, or get notified of the lowest price found so far.
metadata:
  tags: flights, travel, price-tracking, airfare
---

## Purpose

Help the user track prices for specific flights and store a history so they can buy at the lowest price. All data is stored locally at `~/.claude/flight-tracker/flights.json`.

## Data File

All tracked flights and their price history are stored in:

```
~/.claude/flight-tracker/flights.json
```

Schema:
```json
{
  "flights": [
    {
      "id": "LAX-JFK-2026-03-15",
      "origin": "LAX",
      "destination": "JFK",
      "date": "2026-03-15",
      "label": "Optional human-friendly label",
      "added": "2026-02-19T10:00:00Z",
      "history": [
        {
          "checked_at": "2026-02-19T10:00:00Z",
          "price_usd": 249,
          "airline": "Delta",
          "source": "Google Flights",
          "url": "https://..."
        }
      ],
      "cheapest": {
        "checked_at": "2026-02-19T10:00:00Z",
        "price_usd": 249,
        "airline": "Delta",
        "source": "Google Flights"
      }
    }
  ]
}
```

## Commands

The user will invoke this skill with `/flight-tracker` followed by a subcommand. Detect intent from their message:

- **add** – add a new flight to track
- **check** – look up current prices for one or all tracked flights
- **history** – show the price history for a flight
- **list** – show all tracked flights and their cheapest price found
- **remove** – stop tracking a flight
- **cheapest** – show the single best deal across all tracked flights

## Workflow for Each Command

### `add`
1. Parse: origin airport code, destination airport code, travel date (YYYY-MM-DD). Optional: return date, airline preference, label.
2. Generate a unique ID: `{ORIGIN}-{DEST}-{DATE}` (e.g. `LAX-JFK-2026-03-15`).
3. Read `flights.json` (create it if missing with `{"flights":[]}`).
4. Check for duplicates by ID; if already tracked, inform the user.
5. Append the new entry with an empty `history` array.
6. Write the updated file.
7. Confirm to the user and suggest running `/flight-tracker check` to fetch the first price.

### `check`
1. Read `flights.json`.
2. For each flight being checked (all, or one specified by the user):
   a. Use **WebSearch** with a query like:
      `cheapest flights {ORIGIN} to {DEST} on {DATE} site:google.com/travel/flights OR kayak.com OR expedia.com`
   b. Also try:
      `"{ORIGIN}" to "{DEST}" "{DATE}" flight price`
   c. Extract the best price found (lowest USD amount), airline, and source URL.
   d. If no price is found, note that and skip updating.
   e. Append a new entry to `history[]` with `checked_at` = current ISO timestamp, price, airline, source.
   f. Update `cheapest` if the new price is lower than the current cheapest (or if no cheapest exists yet).
3. Write the updated `flights.json`.
4. Display a summary table:
   | Flight | Date | Current Price | Cheapest Ever | Change |
   |--------|------|--------------|--------------|--------|
5. Highlight any flight where the current price equals the cheapest ever.

### `history`
1. Ask the user which flight (by ID or origin/destination/date).
2. Read `flights.json` and find the matching entry.
3. Display the full price history as a table sorted by date, including airline and source.
4. Show a mini trend: are prices going up, down, or flat?

### `list`
1. Read `flights.json`.
2. Display all tracked flights in a table with: ID, route, travel date, # of checks, cheapest price found, last checked.
3. If empty, guide the user to use `add`.

### `remove`
1. Ask the user which flight to remove.
2. Read `flights.json`, filter out the matching entry, write back.
3. Confirm removal.

### `cheapest`
1. Read `flights.json`.
2. Find the flight with the lowest `cheapest.price_usd`.
3. Display it prominently along with a booking link if available.

## Price Searching Guidelines

- Use WebSearch to find real-time prices. Good query patterns:
  - `cheapest flight {ORIGIN} {DEST} {DATE}`
  - `{ORIGIN} to {DEST} flights {DATE} price`
  - Include sites like Google Flights, Kayak, Expedia, Skyscanner in queries.
- Extract price from search snippets — look for `$NNN` patterns.
- If multiple prices are found, record the lowest.
- Always record the source so the user knows where to book.
- If live prices can't be retrieved, tell the user and suggest they manually check and report back (you can accept a manual price entry: "the price is $289 on Delta").

## Accepting Manual Price Entry

If the user says something like "I checked and it's $189 on Southwest", treat that as a `check` with a manual entry: record it in history with `source: "manual"` and update cheapest if applicable.

## Output Style

- Always show a clear summary after any write operation.
- Use tables for list/history/check outputs.
- Flag the cheapest price in green ✓ or with a `← BEST` marker.
- Show the % change from the cheapest ever when displaying current price.
- Keep responses concise; don't repeat the full history unless the user asked for it.

## Detailed rules

- [rules/data-format.md](rules/data-format.md) – full JSON schema and field definitions
- [rules/search-tips.md](rules/search-tips.md) – effective web search strategies for flight prices
