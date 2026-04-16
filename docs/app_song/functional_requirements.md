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

## Database Reference

This section documents database structures relevant to `app_song`.

The schema is intentionally included in this functional document because database design is part of the controlled product contract for this project.

### Shared `common` Schema

The following tables belong to the shared `common` schema.

They are not owned by this project, but `Lyrics Slide Show` has `CRUD` access to them.

`app_song` uses these tables for song metadata and search filters.

```sql
CREATE TABLE common.genres (
    genre_id int4 GENERATED ALWAYS AS IDENTITY(
        INCREMENT BY 1
        MINVALUE 1
        MAXVALUE 2147483647
        START 1
        CACHE 1
        NO CYCLE
    ) NOT NULL,
    "group" varchar(255) NOT NULL,
    "name" varchar(255) NOT NULL,
    CONSTRAINT genres_pkey PRIMARY KEY (genre_id),
    CONSTRAINT genres_unique UNIQUE ("group", name)
);

CREATE TABLE common.bands (
    band_id int4 GENERATED ALWAYS AS IDENTITY(
        INCREMENT BY 1
        MINVALUE 1
        MAXVALUE 2147483647
        START 1
        CACHE 1
        NO CYCLE
    ) NOT NULL,
    "name" varchar(255) NOT NULL,
    CONSTRAINT bands_pkey PRIMARY KEY (band_id),
    CONSTRAINT bands_unique UNIQUE (name)
);

CREATE TABLE common.band_links (
    band_id int4 NOT NULL,
    link varchar(255) NOT NULL,
    CONSTRAINT band_links_pkey PRIMARY KEY (band_id, link),
    CONSTRAINT band_links_bands_fk
        FOREIGN KEY (band_id)
        REFERENCES common.bands(band_id)
        ON DELETE CASCADE
);

CREATE TABLE common.artists (
    artist_id int4 GENERATED ALWAYS AS IDENTITY(
        INCREMENT BY 1
        MINVALUE 1
        MAXVALUE 2147483647
        START 1
        CACHE 1
        NO CYCLE
    ) NOT NULL,
    "name" varchar(255) NOT NULL,
    CONSTRAINT artists_pkey PRIMARY KEY (artist_id),
    CONSTRAINT artists_unique UNIQUE (name)
);

CREATE TABLE common.artist_links (
    artist_id int4 NOT NULL,
    link varchar(255) NOT NULL,
    CONSTRAINT artist_links_pkey PRIMARY KEY (artist_id, link),
    CONSTRAINT artist_links_artists_fk
        FOREIGN KEY (artist_id)
        REFERENCES common.artists(artist_id)
        ON DELETE CASCADE
);
```

### `app_song` Schema

The following tables are owned by this project and more specifically by `app_song`.

All foreign keys controlled by `app_song` must use `ON DELETE CASCADE`.

#### `s_songs`

`s_songs` stores the main song identity and access fields.

```sql
CREATE TABLE s_songs (
    song_id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
    title varchar(255) NOT NULL,
    sub_title varchar(255) NOT NULL,
    description text,
    status integer NOT NULL DEFAULT 0,
    licensed boolean NOT NULL DEFAULT false,
    CONSTRAINT s_songs_pkey PRIMARY KEY (song_id),
    CONSTRAINT s_songs_unique UNIQUE (title, sub_title)
);
```

Functional notes:

- `sub_title` is the database column for the functional `subtitle` field.
- `status` follows the validation status contract defined in this document.
- `licensed` controls guest visibility.

#### `s_song_messages`

`s_song_messages` stores song change requests.

```sql
CREATE TABLE s_song_messages (
    message_id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
    song_id integer NOT NULL,
    message text NOT NULL,
    status integer NOT NULL DEFAULT 0,
    date timestamp with time zone NOT NULL,
    CONSTRAINT s_song_messages_pkey PRIMARY KEY (message_id),
    CONSTRAINT s_song_messages_songs_fk
        FOREIGN KEY (song_id)
        REFERENCES s_songs(song_id)
        ON DELETE CASCADE
);
```

Functional notes:

- `status = 0` means the request is new.
- `status = 1` means the request has been handled.
- `status = 2` means the request has been rejected.
- `date` stores the request timestamp.

#### `s_song_links`

`s_song_links` stores links attached to songs.

```sql
CREATE TABLE s_song_links (
    song_id integer NOT NULL,
    link varchar(255) NOT NULL,
    CONSTRAINT s_song_links_pkey PRIMARY KEY (song_id, link),
    CONSTRAINT s_song_links_songs_fk
        FOREIGN KEY (song_id)
        REFERENCES s_songs(song_id)
        ON DELETE CASCADE
);
```

Functional notes:

- The link type described in this document is a visual classification for users.
- The physical storage of that type must remain compatible with this functional requirement.

#### `s_verses`

`s_verses` stores ordered lyric text blocks.

```sql
CREATE TABLE s_verses (
    verse_id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
    song_id integer NOT NULL,
    num integer NOT NULL DEFAULT 1000,
    num_verse integer NOT NULL DEFAULT 1000,
    chorus boolean NOT NULL DEFAULT false,
    followed boolean NOT NULL DEFAULT false,
    notcontinuenumbering boolean NOT NULL DEFAULT false,
    text text,
    prefix varchar(50) DEFAULT NULL,
    CONSTRAINT s_verses_pkey PRIMARY KEY (verse_id),
    CONSTRAINT s_verses_songs_fk
        FOREIGN KEY (song_id)
        REFERENCES s_songs(song_id)
        ON DELETE CASCADE
);

CREATE INDEX s_verses_song_id_idx ON s_verses(song_id);
CREATE INDEX s_verses_num_idx ON s_verses(num);
CREATE INDEX s_verses_chorus_idx ON s_verses(chorus);
```

Functional notes:

- `num` is the technical ordering position.
- `num_verse` stores the display verse number.
- `notcontinuenumbering` is the database column for the functional `not_c_num` behavior.
- `prefix` supports custom or controlled display prefixes for sections such as bridges or pre-choruses.
- The functional `chorus_like` behavior is handled through prefix/display behavior rather than a dedicated column in this table.
- The functional `display_num` is represented by `num_verse`.

#### `s_verse_prefixes`

`s_verse_prefixes` stores controlled prefixes that can be used when editing verse-like blocks.

```sql
CREATE TABLE s_verse_prefixes (
    prefix_id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
    prefix varchar(15) NOT NULL,
    comment varchar(100) DEFAULT NULL,
    CONSTRAINT s_verse_prefixes_pkey PRIMARY KEY (prefix_id),
    CONSTRAINT s_verse_prefixes_unique UNIQUE (prefix)
);
```

Functional notes:

- Prefixes are reusable helpers for song editing.
- Moderators can use this reference data to normalize recurring section labels.

#### Song Relation Tables

`app_song` also owns relation tables between `s_songs` and shared or user-owned reference tables.

Required relation targets are:

- `common.genres.genre_id`,
- `common.artists.artist_id`,
- `common.bands.band_id`,
- `users.users.id` for member favorites.

Each relation table must:

- reference `s_songs.song_id`,
- reference the related target table,
- use a composite primary key preventing duplicate relations,
- use `ON DELETE CASCADE` on all foreign keys.

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
