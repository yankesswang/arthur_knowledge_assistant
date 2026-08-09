---
name: kakao-map-favorites
description: Save batches of addresses, restaurants, or place names into a user's Kakao Map favorites using Chrome or Computer Use. Use when the user asks to add Korean/Seoul places to Kakao Map, keep addresses in their Kakao account, save multiple places into a Kakao favorites group, resolve ambiguous Kakao place results, or continue adding remaining places after a partial Kakao Maps session.
---

# Kakao Map Favorites

## Overview

Use this skill to reliably add one or many places to Kakao Map favorites while avoiding wrong same-name locations. Prefer saving the exact Kakao place when available; fall back to saving the precise address only when Kakao does not expose a matching place result.

## Workflow

1. Confirm the target account is already logged into Kakao Map in Chrome. If not logged in, ask the user to log in before proceeding.
2. Normalize the input list into unique rows with:
   - original user text
   - inferred place name, if provided by surrounding notes
   - exact address
   - status: pending, saved as place, saved as address, skipped, or needs user input
3. Use Computer Use for Kakao UI operations. Call `get_app_state` before interacting with Chrome each assistant turn.
4. Save each item into the intended group, usually `기본 그룹` unless the user names another group.
5. Verify completion by checking the success toast or the group's displayed count.

## Finding The Right Place

Use this order:

1. Search Kakao Map for the Korean place name plus neighborhood or address.
2. If Kakao returns a result, confirm both the name and address. Do not save a same-name result at a different address.
3. If Kakao search is ambiguous, use web search to infer the Korean name and current address. Useful queries:
   - quoted English name plus quoted street number
   - Korean name plus street address
   - `site:place.map.kakao.com <name> <address>`
   - third-party pages that expose Kakao short links (`kko.to`)
4. Resolve Kakao short links with:

```bash
curl -L -s -o /dev/null -w '%{url_effective}\n%{http_code}\n' 'https://kko.to/...'
```

If the resolved URL includes `itemId=<id>`, try opening `https://place.map.kakao.com/<id>` or `https://map.kakao.com/?item&urlLevel=3&itemId=<id>&action=addFavorite`.

## Saving A Kakao Place

Preferred path:

1. Open the place page:

```bash
open -a 'Google Chrome' 'https://place.map.kakao.com/<place-id>'
```

2. Click `즐겨찾기` on the place page or map card.
3. In the save modal, select the desired group. For the default private group, choose `기본 그룹`.
4. Click `완료`.
5. Treat the success toast `비공개 그룹 < 기본 그룹 > 에 즐겨찾기가 저장되었습니다.` or a `즐겨찾기 1` marker as confirmation.

Direct add-favorite URL, when the place page works poorly:

```bash
open -a 'Google Chrome' 'https://map.kakao.com/?item&urlLevel=3&itemId=<place-id>&action=addFavorite'
```

## Saving An Address Fallback

Use address fallback only when no trustworthy Kakao place result exists.

1. Open the exact address search:

```bash
open -a 'Google Chrome' 'https://map.kakao.com/?q=<url-encoded-address>'
```

2. Confirm Kakao displays the exact address marker and not a nearby business with a different floor or name.
3. Click the marker/card `즐겨찾기`.
4. Select the intended group and click `완료`.
5. Tell the user that this item was saved as an address because no exact Kakao place page was available.

## Practical Guardrails

- Do not save same-name results if the address differs. Search by address or ask the user when uncertainty remains.
- Do not edit the user's source spreadsheet or notes while using the browser.
- Prefer `open -a 'Google Chrome' '<url>'` for navigation. It is more reliable than simulated address-bar typing.
- Avoid destructive browser cleanup such as closing many tabs unless the user asks.
- Expect Kakao accessibility labels to be Korean: `즐겨찾기` means favorite, `완료` means done, `기본 그룹` means default group.
- If a save modal appears, the group count shown beside `기본 그룹` is a useful before/after verification signal.
- If Chrome or Kakao blocks scripted JavaScript, continue with normal UI clicks instead of bookmarklets or injected scripts.

## Testing Safely

Adding a favorite changes the user's Kakao account. For skill testing, first do a dry run that validates:

- the input list can be normalized
- the exact-place path and address-fallback path are both covered
- the final report distinguishes saved places from address fallbacks

Before any live test that clicks `완료`, get explicit user approval for the exact place or address to add unless the user has already granted standing permission to run live Kakao favorite tests without asking again. Even with standing permission, only save a place or address after checking that it matches the intended item.

## Reporting

At the end, report concise results in the user's language:

- total saved
- which items were saved as exact Kakao places
- which items were saved as address fallbacks
- any unresolved items and why

For Chinese-speaking users, use Traditional Chinese unless they use Simplified Chinese.
