# App Song Functional Requirements

## Purpose

This document defines the functional requirements for `app_song`.

`app_song` owns the global song catalog of `Lyrics Slide Show`.

The module manages songs as reusable global lyrics resources. Songs are not scoped to a group, and there is no concept of song ownership or membership through a group.

Groups organize `animations`, but the song catalog itself is shared across the whole service.

## Documentation Structure

This document defines the global functional contract of `app_song`.

It must describe every functional behavior owned by `app_song`, except UI and template-level details.

Screen-level and template-level behavior must be documented in dedicated Markdown files stored in the same directory:

```text
docs/app_song/template_<X>.<name>.html.md
```

Where:

- `<X>` is a documentation ordering number,
- `01` is reserved for the root view of the app, exposed at `root/songs/`,
- `<name>` is the Django template name, for example `songs.html`.

The ordering number is documentation metadata only. It is not part of the public site behavior, except for the convention that `01` identifies the app root screen.

The UI structure, screen layout, detailed interactions, template-specific forms, and page-level controls belong in those template documentation files, not in this global functional requirements document.

Functional workflows, business rules, permissions, data behavior, and cross-screen behavior belong in this document.

## Song Identity

A song is defined by:

- `title`,
- `subtitle`,
- `description`,
- `status`,
- `licensed`.

The pair `title + subtitle` must be unique.

## Song Validation Status

Song validation is represented by a numeric `status`, not by a boolean.

The supported status values are:

- `0`: not validated,
- `1`: validated,
- `2`: validated with attention or reported concern.

The display marker for validation status is:

- no marker for `status = 0`,
- `✔️` for `status = 1`,
- `✔️⁉️` for `status = 2`.

For permissions, both `status = 1` and `status = 2` count as validated states.

Only moderators and admins can change the validation status of a song.

Validated and non-validated songs are both usable in animations.

## Song Text Model

The song text is structured as ordered text blocks.

Each block supports:

- `text`,
- `chorus`,
- `followed`,
- `not_c_num`,
- `chorus_like`,
- `num`,
- `display_num`.

The chorus is not manually duplicated as independent source content.

`app_song` must preserve the chorus and verse logic described in `docs/general_overview.md`, including repeated chorus rendering and the ability to skip a chorus after a `followed` block.

The lyrics editing workflow must support:

- adding text blocks,
- editing text blocks,
- deleting text blocks,
- reordering text blocks,
- inserting a text block between existing blocks,
- changing all block-level behavior flags.

The technical `num` position is managed by the app and must remain suitable for inserting blocks between existing blocks without requiring a full renumbering after each insertion.

The computed `display_num` is used for user-facing verse numbering and must reflect the chorus, `not_c_num`, and `chorus_like` behavior.

The functional rendering workflow must be previewable before saving or using the song in an animation.

Preview rendering must use the same chorus and verse logic as projection rendering, including:

- initial chorus blocks displayed first when the song starts with a chorus,
- repeated chorus blocks after verses,
- skipped chorus after a `followed` block,
- display numbering that respects `not_c_num`,
- chorus-like visual treatment while preserving verse logic.

## Reference Data

Songs may be linked to supporting reference data:

- `genres`,
- `artists`,
- `bands`,
- `web_links`.

These references are backed by the following database tables:

- `common.genres`,
- `common.artists`,
- `common.bands`,
- `s_song_links`.

The functional metadata scope of `app_song` is limited to those references.

Metadata concepts such as language, theme, tempo, free tags, or source are not part of the current `app_song` scope unless they are introduced later through a separate product decision.

## Song Links

Song links point to safe and legal external or internal sources.

Song links must support a display-oriented type.

Supported link types are:

- internal,
- web,
- score,
- audio-video.

The link type has no business impact. It is used only to help users visually understand the kind of linked resource.

Links to generic deposit or drive-style storage spaces are outside the intended scope.

## File Storage Exclusion

The song module stores only:

- text content,
- structured song metadata,
- links to safe and legal external or internal sources.

`app_song` must not store files on the server or in the database for songs.

This exclusion applies even when the file would be legal to share.

The song module must not store or host:

- score files,
- audio files,
- video files,
- archive files,
- uploaded documents,
- any other song-related file attachment.

## Permissions

`app_song` must use the exact same role terminology and role model as the rest of `Lyrics Slide Show`.

The only roles are:

- `Guest`,
- `Member`,
- `Group Admin`,
- `Moderator`,
- `Admin`.

`app_song` must not introduce local song-specific roles such as `Editor`.

This keeps the site simple and preserves uniform behavior across all apps. Any song-related capability must be expressed through the global role model.

`Admin` inherits all moderator capabilities.

The global permission contract is expressed through song-level `CRUD` rules:

- `Guest`: read-only access to songs that are not marked as `licensed`.
- `Guest`: no access to songs marked as `licensed`.
- `Guest`: may leave a change request message through the song feedback form.
- `Member`: create and read access to songs, including songs marked as `licensed`.
- `Member`: update and delete access to songs with `status = 0`, including songs marked as `licensed`.
- `Member`: no direct update or delete access to songs with `status = 1` or `status = 2`.
- `Member`: may leave a change request message through the same song feedback form when a song has `status = 1` or `status = 2`.
- `Moderator`: full `CRUD` access to all songs.
- `Admin`: full `CRUD` access to all songs because admins inherit moderator capabilities.

Once a song has `status = 1` or `status = 2`, it is locked against regular member edits and deletes, regardless of its `licensed` value.

## Song Change Requests

`app_song` must provide a feedback form allowing users without direct edit rights to report a required change on a song.

This form is available to:

- guests, for songs they are allowed to read,
- authenticated non-moderator members, when the song has `status = 1` or `status = 2`.

The form is intended for corrections such as typo reports, formatting issues, wrong metadata, or any other song-related change request.

Submitted change requests must be notified to moderators.

Change requests are stored in `s_song_messages`.

Each request must include:

- the related song,
- the submitted message,
- a timestamp,
- a status.

The expected status workflow is:

- `new`: the request has been submitted and still requires moderator attention,
- `handled`: a moderator has reviewed the request and considers it handled,
- `rejected`: a moderator has reviewed the request and rejected it.

A moderator may edit the related song after reading a request, but this is not mandatory.

The moderator can mark the request as `handled` or `rejected` independently from whether a song modification was actually made.

There is no requirement to track who submitted the request.

There is no requirement to track who edited the song after a request.

The complete change request history remains attached to the song.

Authenticated members can view the full request history of a song.

## Search And Reuse

The song catalog is meant to be searched and reused across many animations.

`app_song` therefore depends on:

- a central search experience that remains friendly for real users,
- reusable global song entries instead of group-scoped duplicates,
- compatibility with the member search-state persistence described in `docs/app_member/functional_requirements.md`.

The song search must support the following criteria:

- text search,
- search scope,
- genre filters,
- band filters,
- artist filters,
- validation status filter,
- favorites filter for authenticated members.

Text search must be accent-insensitive.

By default, text search applies to:

- `title`,
- `subtitle`.

When the user enables extended search, text search also applies to:

- `description`,
- text blocks containing the lyrics.

The song catalog must enforce the visibility rule before returning search results:

- unauthenticated users can only receive songs that are not marked as `licensed`,
- authenticated users can receive both licensed and non-licensed songs.

Genre, band, and artist filters must support multiple selected values.

The filter behavior must support two modes:

- default mode: a song matches when it belongs to at least one selected value for each active filter category,
- strict logic mode: a song must match every selected genre, every selected band, and every selected artist.

The validation status filter must support at least:

- all songs,
- validated songs,
- non-validated songs.

The favorites filter must support at least:

- all songs,
- favorite songs only.

Favorites are member-specific and therefore only meaningful for authenticated users.

Search results must be ordered by:

- `title`,
- `subtitle`.

Search results must expose enough display data for the song list, including:

- song identity fields,
- a computed display title,
- linked genres,
- linked bands,
- linked artists,
- favorite state for the current member when authenticated.

The computed display title must include:

- `title`,
- `subtitle` when present,
- a validation status marker when the song has `status = 1` or `status = 2`,
- a license marker when the song is marked as `licensed`.

## Favorites

`app_song` includes song favorites as a member feature.

Authenticated members can mark songs as favorites and remove songs from their favorites.

Favorites are personal to the authenticated member.

Guests cannot have persistent favorites.

Favorites must be usable in the song list and search experience:

- search results must expose whether each song is a favorite of the current member,
- authenticated members can filter the catalog to show favorite songs only,
- guests must not see a persistent favorite state or favorite-only filtering behavior.

## Non-Goals

`app_song` must not become:

- a group-owned song store,
- a sheet-music repository,
- a generic file library,
- a free-form slide editor,
- a hosting service for song-related files, including legal score, audio, video, archive, or document files.
