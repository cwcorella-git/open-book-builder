# Reader features spec (draft)

Prepared 2026-11-17. **Spec only: no firmware was written.** Someone else writes the code, and nothing here has been built or tried on a device. Costs are estimates from reading the source, not measurements.

Baseline: libros base `3be5d84` with PR #10 and PR #11 (branch `obb-pilot`, `5196839`, in `/data/checkouts/libros`). The facts about today's behavior are in `docs/markdown-profile.md`. The pilot runs this baseline unchanged; the other nine run it plus the features below.

## What you asked for

Filter by tag, filter by type, sort by title or author, favorites and recent first, plus resume and percent read from the earlier rulings. You asked for more ideas, so the second half of the list is mine.

## Shared pieces the features rely on

**Card state file, `_STATE`.** One small file in the card root. A header (version, record count) and one fixed-size record per book, keyed by the same 8-byte name hash the firmware already uses (the first 8 bytes of SHA-256 of the file name). Each record: favorite flag, finished flag, last-opened counter, saved page, one bookmark page, cached page count. It survives the `_LIBRARY` rebuild because that rebuild writes only `_LIBRARY`. The state follows the card, as ruled. A newer or unknown version is ignored, never repaired by guessing.

**Atomic writes.** Write `_STATETMP`, then rename it over `_STATE`, the way the firmware already swaps `_LIBRARY` using `renameFile` and `removeFile`. Today `.obp` is truncated and then written with 4 bytes, so a power cut between the two leaves an empty file, which reads back as page 0.

**Stale page maps.** Today `.pag` is trusted if the file exists. Store the book's file size and a checksum of its first and last 4 KB in the page-map header, and rebuild when they differ. This is needed before any book is updated in the field.

**Cached list data.** Reading a title opens the book file, so sorting and filtering must read titles, authors and tags once at scan time and hold them in memory. A hundred books at about 100 bytes each is small next to the Pico's 264 KB of RAM, but the real limit is unmeasured.

**Tags and types in one place.** `GNRE` already carries one string. Put tags there separated by semicolons, with the type as a tag with a fixed prefix, for example `type:article`. One mechanism then serves both filters and needs no change to the library file layout.

## The features

Size is S (a few hours), M (a day or two) or L (several days) for someone who knows the code. Estimates only.

### Requested

| # | Feature | What the reader does | Needs | Size |
| --- | --- | --- | --- | --- |
| 1 | Reliable resume | Saves the page after a short delay, every few turns and on sleep, not only on Lock or return home. A "Continue reading" row sits at the top of the list. | `_STATE`, atomic writes | S-M |
| 2 | Percent read in the list | Shows `42%` beside each title, from the saved page and the cached page count. A book never opened shows a dash. | Cached page count in `_STATE` | M |
| 3 | Favorites | A menu item in the reader and the list toggles a star. A Favorites filter shows only starred books. | `_STATE` | M |
| 4 | Recent first | An open counter is stored per book; the list can sort by it. | `_STATE` | S |
| 5 | Filter by tag | A filter picker lists the tags found at scan time. The choice is remembered. | Cached tags, new list-screen UI | L |
| 6 | Filter by type | Book, article or document, using the `type:` tag, through the same picker as tags. | Item 5 | S after 5 |
| 7 | Sort by title or author | Alphabetical by code point. Plain code-point order is wrong for some languages. | Cached metadata | S-M |

### My ideas

| # | Idea | What the reader does | Needs | Size |
| --- | --- | --- | --- | --- |
| 8 | Reading status | Unread, In progress, Finished (Finished at about 98% of the pages). A filter by status. | `_STATE` | S |
| 9 | Chapter list | A menu lists chapters and jumps to one. The page map already stores chapter positions. | Page lookup by file position | M |
| 10 | One bookmark per book | Mark a page, jump back to it. | `_STATE` | S |
| 11 | Sleep screen | When it sleeps, the display shows the current title, author and percent. E-paper holds the image with no power, so a shelf unit says what it was reading. | The firmware already has a lock screen | S-M |
| 12 | Empty-card guide | If the card has no books, show one screen: where to put `.txt` files and where to download collections. | None | S |
| 13 | Stale page-map protection | The check described above. | Page-map header change | S-M |
| 14 | Battery warning | Show a low-battery mark. A power-monitor class exists in the firmware, but its use was not traced. | Read the power monitor code first | S |
| 15 | List paging | A clear "page 2 of 4" for long libraries. The creator's 2022 guide mentions 15 listed works; the source read shows no such constant, so test the real limit. | Pilot measurement | S-M |

Suggested order, if the nine ship together: 13, 1, 3, 4, 2, 7 first because they touch card state and sorting only; then 5, 6, 8; then 11, 12 as cheap wins; 9, 10, 14, 15 later.

## Card layout for a buyer

```
/                      root of the card
  babel.bin            font data, loaded into the flash chip on first boot
  <id>.txt             one file per work, name from the Markdown profile
  <id>.pag, <id>.obp   made by the reader
  _LIBRARY, _STATE     made by the reader
```

Everything must stay in the root: the firmware does not read folders.

## To test on the pilot before trusting any of it

- Power cut during a save: pull the batteries while turning pages and while the state file is being written, then check nothing is lost but the last few pages.
- Updating a book: replace a text file with a longer one under the same name and check the page map rebuilds (item 13).
- Renaming a file: confirm progress is lost, as the identity rule says.
- A card with 100 and with 500 books: time the scan, the list and a sort. Measure RAM.
- A long book: time the first-open pagination on a novel-sized file. It was never measured.
- Button mapping: which buttons are free for filter and sort, given what Lock, the menu and page turning already use.

## Related, not written

- An **author's guide** for formatting text for the reader, as the site plan calls for. The rules are in `docs/markdown-profile.md`.
- Updating `docs/markdown-profile.md` for the `type:` tag, `_STATE` and the stale-map rule if these features go ahead.
