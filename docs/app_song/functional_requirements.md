# App Song Functional Requirements

## Purpose

This document defines the functional requirements for `app_song`.

`app_song` owns the global song catalog of `Lyrics Slide Show`.

Until this document is expanded further, `docs/general_overview.md` remains the authoritative cross-app reference.

## Functional Role

`app_song` manages songs as reusable global lyrics resources.

Songs are not scoped to a group.

Groups organize `animations`, but the song catalog itself is shared across the whole service.

## Song Identity

A song is defined by:

- `title`,
- `subtitle`,
- `description`,
- `validated`,
- `licensed`.

The pair `title + subtitle` must be unique.

## Song Text Model

The song text is structured as ordered text blocks.

Each block supports the behavior defined in `docs/general_overview.md`, including:

- `text`,
- `chorus`,
- `followed`,
- `not_c_num`,
- `chorus_like`,
- `num`,
- `display_num`.

The chorus is not manually duplicated as independent source content.

`app_song` must preserve the chorus and verse logic described in the overview, including repeated chorus rendering and the ability to skip a chorus after a `followed` block.

## Reference Data

Songs may be linked to supporting reference data:

- `genres`,
- `artists`,
- `bands`,
- `web_links`.

`app_song` does not own file attachments such as sheet music or uploaded score files.

## Permissions

The global permission contract is:

- guests can view only the public part of the song catalog,
- members and above can access the full catalog,
- guests cannot create, edit, or delete songs,
- members and above can add songs,
- members and above can edit or delete a non-validated song,
- everyone can leave a message on a validated song,
- only moderators and admins can validate a song,
- once validated, a song is locked against regular member edits and deletes,
- songs under license are hidden from non-authenticated users.

Validated and non-validated songs are both usable in animations.

## Search And Reuse

The song catalog is meant to be searched and reused across many animations.

`app_song` therefore depends on:

- a central search experience that remains friendly for real users,
- reusable global song entries instead of group-scoped duplicates,
- compatibility with the member search-state persistence described in `docs/app_member/functional_requirements.md`.

## Non-Goals

`app_song` must not become:

- a group-owned song store,
- a sheet-music repository,
- a generic file library,
- a free-form slide editor.
