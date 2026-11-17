# Writing text for the Open Book

This guide is for anyone preparing a book, article or document for the Open Book reader. You need a plain text editor. You do not need to know how the reader works inside.

I wrote it from the reader's firmware source, not from using a finished device. The pilot reader will confirm or correct it, and anything not yet measured says so.

## How the reader finds your text

The reader looks in the top folder of its microSD card for files that end in `.txt`. It lists each one by title. It does not look inside folders. One work is one file.

## The file name

- Use lower-case letters, digits and hyphens: `moby-dick.txt`, not `Moby Dick (final).txt`.
- Keep it under 80 characters before `.txt`, and never start it with a dot.
- **Never rename a work.** The reader tells works apart by their file name. A renamed file counts as a new book, and the old one loses its place and favorites.

## The header

Every work starts with a short header between two lines of three hyphens:

```
---
id: moby-dick
version: 3
title: Moby-Dick
type: book
language: en
author: Herman Melville
tags: [fiction, sea]
rights: public domain
---
```

| Field | Needed | What it is |
| --- | --- | --- |
| `id` | yes | The file name without `.txt`. Letters, digits and hyphens. Never changes. |
| `version` | yes | A whole number. Raise it every time the text changes. |
| `title` | yes | Shown in the reader's list. |
| `type` | yes | `book`, `article` or `document`. |
| `language` | yes | A language tag such as `en`, `fr` or `ar`. |
| `author` | no | Shown in the reader's list. |
| `tags` | no | Words that group works. You set them here and nowhere else. |
| `rights` | no | Where the text comes from and its license. |

## The text

| You write | The reader shows |
| --- | --- |
| A blank line between paragraphs | A new paragraph. Do not break lines by hand. |
| `# Chapter One` | A chapter title page in large type. Keep titles under 100 characters. |
| `## A section` | A line of bold text. The reader has one level of chapter. |
| `*italic*` | Italic |
| `**bold**` | Bold |
| `***bold italic***` | Bold italic |
| `- an item` | A line beginning with a hyphen |
| `[the link text](https://example.org)` | Only `the link text`. The reader cannot follow links. |
| `> a quotation` | An ordinary paragraph |

## What is turned away

The converter stops and gives you the line number for each of these. It does not drop them without telling you.

- Images, tables, raw HTML, footnotes, math and code blocks. The first batch of readers shows text only.
- A scanned book with no real text. It needs to be turned into text, and corrected by a person, first.
- A stretch of 127 bytes in a row with no space or line break, such as a very long web address. The reader lays text out in pieces of that size and does not handle these well. Languages written without spaces, such as Chinese and Japanese, have not been tested yet, so expect the converter to flag long lines there until a pilot reader shows what works.

## A complete small example

You write `lighthouse.txt`:

```
---
id: lighthouse
version: 1
title: The Lighthouse Keeper
type: article
language: en
author: A. Writer
tags: [stories]
---

# The Lamp

The keeper climbed the stairs *every* evening. It was the **only** thing she was sure of.

# The Storm

- Wind from the north
- Rain by midnight
```

You run `uv run python -m open_book_builder.convert lighthouse.md -o out` (add `--reading-copy` for a plain text copy to read on another device, never to put on the card), and the converter writes a file for the reader with the same name (the example below is its actual output, and a test checks it). In the notation below, `<RS>` is the chapter marker, `<SI>` switches on italic or bold, and `<SO>` switches one step back. You never type these.

```
---
TITL: The Lighthouse Keeper
AUTH: A. Writer
GNRE: stories;type:article
LANG: en
---
<RS>The Lamp
The keeper climbed the stairs <SI>every<SO> evening. It was the <SI><SI>only<SO> thing she was sure of.
<RS>The Storm
- Wind from the north
- Rain by midnight
```

## Trying a file on a reader

1. Copy `babel.bin` (the font file) to the top of the card, then your `.txt` file next to it. The script `scripts/prepare_card.py` does this on Linux and checks the card first; run it without `--write` to see what it would do.
2. Put the card in the reader and turn it on. The first time, the reader loads the fonts.
3. Open the work. The first time, the reader works out where pages break, and it may take a moment. Nobody has measured how long a long book takes yet.
4. Check the chapter pages, the italic and bold, and the end of the text.

If you change a work and keep its name, the reader may keep its old page map and show wrong pages. Readers with the feature firmware rebuild the map on their own. On a stock reader, delete the file with the same name and the ending `.pag` from the card. A saved place can end up in the wrong spot after an edit, because the reader remembers a page number, not a position in the text.

## How big can a work be?

Not measured yet. There is no known limit on the length of a work, on the number of works on a card, or on how many show in the list. The pilot will test a short article, a novel-sized book and a card with a few hundred works, and this guide will state the numbers after that.

## Before you send a work

- The file name matches `id`, and you have not renamed it since an earlier version.
- `version` went up if the text changed.
- The converter reported no rejected lines.
- You tried it on a real reader if you could.
