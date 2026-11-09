# Data Format Reference

## File location
`~/.claude/flight-tracker/flights.json`

## Top-level structure
```json
{
  "flights": [ /* array of FlightEntry */ ]
}
```

## FlightEntry
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique key: `{ORIGIN}-{DEST}-{DATE}` e.g. `LAX-JFK-2026-03-15` |
| `origin` | string | yes | IATA airport code, uppercase (e.g. `LAX`) |
| `destination` | string | yes | IATA airport code, uppercase (e.g. `JFK`) |
| `date` | string | yes | Travel date, `YYYY-MM-DD` |
| `return_date` | string | no | Return date for round-trips, `YYYY-MM-DD` |
| `airline_pref` | string | no | Preferred airline filter, or `null` for any |
| `label` | string | no | Human-friendly name, e.g. `"Spring break NYC trip"` |
| `added` | string | yes | ISO 8601 timestamp when first added |
| `history` | PriceRecord[] | yes | All price checks, oldest first |
| `cheapest` | PriceRecord | no | The lowest price ever seen (null until first check) |

## PriceRecord
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `checked_at` | string | yes | ISO 8601 timestamp of the check |
| `price_usd` | number | yes | Price in USD (integer or float) |
| `airline` | string | no | Airline name or code |
| `flight_number` | string | no | Flight number if available |
| `source` | string | yes | Where the price came from: `"Google Flights"`, `"Kayak"`, `"manual"`, etc. |
| `url` | string | no | Direct booking URL if found |
| `notes` | string | no | Any extra context (e.g. "1 stop", "basic economy") |

## Example
```json
{
  "flights": [
    {
      "id": "SFO-ORD-2026-04-10",
      "origin": "SFO",
      "destination": "ORD",
      "date": "2026-04-10",
      "return_date": "2026-04-14",
      "label": "Chicago conference",
      "added": "2026-02-19T08:00:00Z",
      "history": [
        {
          "checked_at": "2026-02-19T08:00:00Z",
          "price_usd": 312,
          "airline": "United",
          "source": "Google Flights",
          "url": "https://www.google.com/travel/flights/...",
          "notes": "nonstop"
        },
        {
          "checked_at": "2026-02-21T09:15:00Z",
          "price_usd": 278,
          "airline": "Southwest",
          "source": "Kayak",
          "notes": "1 stop"
        }
      ],
      "cheapest": {
        "checked_at": "2026-02-21T09:15:00Z",
        "price_usd": 278,
        "airline": "Southwest",
        "source": "Kayak",
        "notes": "1 stop"
      }
    }
  ]
}
```
