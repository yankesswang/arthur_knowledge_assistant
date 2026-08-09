---
name: google-map-favorites
description: Save batches of addresses, restaurants, or place names into a user's Google Maps saved lists using Chrome or Computer Use. Use when the user asks to add places to Google Maps, keep addresses in their Google account, save many places into a Google Maps list, resolve ambiguous Google Maps place results, move travel addresses into Want to go/Favorites/Starred places, or continue adding remaining places after a partial Google Maps session.
---

# Google Map Favorites

## Overview

Use this skill to reliably add one or many places to Google Maps saved lists while avoiding wrong same-name locations. Prefer saving the exact Google Maps place when available; fall back to saving the precise address only when no trustworthy place result matches.

## Workflow

1. Confirm the user is logged into Google Maps in Chrome. If not logged in, ask the user to log in before proceeding.
2. Normalize the input list into unique rows with:
   - original user text
   - inferred place name, if provided by surrounding notes
   - exact address
   - target Google Maps list, if specified
   - status: pending, saved as place, saved as address, skipped, or needs user input
3. Use Computer Use for Google Maps UI operations. Call `get_app_state` before interacting with Chrome each assistant turn.
4. Save each item into the intended list. If the user does not specify a list, choose the most natural existing default: `Want to go`, `Favorites`, `Starred places`, or the currently implied travel list.
5. Verify completion by checking the `Saved` state, checked list item, or a visible success message.

## Finding The Right Place

Use this order:

1. Search Google Maps for the place name plus city/neighborhood or exact address:

```bash
open -a 'Google Chrome' 'https://www.google.com/maps/search/?api=1&query=<url-encoded-query>'
```

2. Confirm the result by name, address, neighborhood, phone, website, or photos. Do not save a same-name result at a different address.
3. If the Google Maps search result is ambiguous, use web search to infer the canonical name and address, then search Google Maps again with both.
4. Prefer a direct Google Maps place result over a pinned coordinate if the result clearly matches. Prefer the exact address marker if no trustworthy business listing exists.

## Saving A Google Maps Place

Preferred path:

1. Open Google Maps search for the exact place:

```bash
open -a 'Google Chrome' 'https://www.google.com/maps/search/?api=1&query=<url-encoded-place-and-address>'
```

2. Select the matching place result if Google shows a results list.
3. Click `Save` in the place panel. If the button says `Saved`, open it only if you need to verify or change list membership.
4. In the list dialog, check the intended list, such as `Want to go`, `Favorites`, `Starred places`, or a user-named list.
5. Click `Done`, close the dialog, or wait for Google Maps to persist the change if the checkbox saves automatically.
6. Treat a checked list item, `Saved` button state, or visible success confirmation as proof.

## Saving An Address Fallback

Use address fallback only when no trustworthy Google Maps place result exists.

1. Open exact address search:

```bash
open -a 'Google Chrome' 'https://www.google.com/maps/search/?api=1&query=<url-encoded-address>'
```

2. Confirm Google Maps displays the intended address marker and not a nearby business.
3. Click `Save`.
4. Select the intended list and finish the dialog.
5. Tell the user that this item was saved as an address because no exact Google Maps place listing was available.

## Practical Guardrails

- Do not save same-name results if the address, city, or country differs. Search by exact address or ask the user when uncertainty remains.
- Do not edit the user's source spreadsheet, notes, or itinerary while using the browser.
- Prefer `open -a 'Google Chrome' '<url>'` for navigation. It is more reliable than simulated address-bar typing.
- Avoid destructive browser cleanup such as closing many tabs unless the user asks.
- Expect Google Maps UI labels to vary by locale, for example `Save`, `Saved`, `Done`, `Want to go`, `Favorites`, and `Starred places`.
- Some Google Maps list checkboxes autosave immediately; others require `Done`. Verify before moving on.
- If Google Maps opens a coordinate or address pin, be transparent that the item is saved as an address fallback, not a business listing.

## Testing Safely

Adding a saved place changes the user's Google account. For skill testing, first do a dry run that validates:

- the input list can be normalized
- the exact-place path and address-fallback path are both covered
- the final report distinguishes saved places from address fallbacks

Before any live test that changes a saved list, get explicit user approval for the exact place or address to add unless the user has already granted standing permission to run live Google Maps saved-list tests without asking again. Even with standing permission, only save a place or address after checking that it matches the intended item.

## Reporting

At the end, report concise results in the user's language:

- total saved
- target list used
- which items were saved as exact Google Maps places
- which items were saved as address fallbacks
- any unresolved items and why

For Chinese-speaking users, use Traditional Chinese unless they use Simplified Chinese.
