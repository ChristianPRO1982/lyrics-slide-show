# App Member Functional Requirements

## Purpose

This document defines the functional requirements for `app_member`.

`app_member` is the Django app responsible for member-specific persistent data inside `Lyrics Slide Show`.

It is written for implementation agents based on LLM tools such as `Codex`, `Claude Code`, `Codestral`, and similar coding assistants. It must be treated as a functional specification, not as a brainstorming note.

## Functional Role Of `app_member`

`app_member` is not an identity provider and is not a personal profile management app.

Its role is to store and serve the local member-level data required by `Lyrics Slide Show` once identity has been established through `SSO`.

At this stage, the app covers:

- the persistent state of the central `songs` search form for authenticated members,
- the privileged local roles `moderator` and `admin` for authenticated members,
- the local services that expose those roles and permissions to the rest of the Django project,
- the context processor that builds the shared site popup payload from `SiteParams`,
- the forms reused by `app_main` for member search, role updates, popup settings, and full `SiteParams` administration.

## Scope Boundaries

### In Scope

- persistent preferences for authenticated members only,
- local business roles for authenticated members,
- preferences that affect the whole `Lyrics Slide Show` service,
- preferences related to the central `songs` search,
- site-wide privileged permissions attached to `moderator` and `admin`,
- storage of those member data in schema `lss`.

### Out Of Scope

- account creation,
- account edition,
- personal identity data management,
- email, first name, last name, or other sensitive profile data,
- write access to schema `users`,
- write access to schema `common`,
- CRUD ownership helpers coming from schema `common`,
- guest preference persistence on the server,
- external role assignment in `Keycloak`.

## URL And UI Boundary

`app_member` currently exposes no standalone end-user page, no public route, and no dedicated template.

Its Django `views.py` is currently empty.

Its user-facing contribution is indirect:

- reusable forms consumed by `app_main`,
- reusable permission helpers consumed by other apps,
- a shared context processor for site popups,
- local persistence models used by `app_song` and by authentication/runtime services.

## Source Of Truth And Database Boundaries

The Django project only manages tables that belong to its own perimeter in schema `lss`.

`app_member` must never write to:

- schema `users`,
- schema `common`.

`users.users` remains an external read-only reference table.

The authenticated member identifier used by `app_member` is the `Keycloak` UUID stored in `users.users.id`.

`app_member` is also the local source of truth for site-wide privileged roles after authentication. Those roles are business roles of `Lyrics Slide Show`, not identity-provider roles.

## Authentication Rule

`app_member` concerns authenticated members only.

There is no persistent server-side `app_member` data for guests.

If a user is anonymous:

- no persistent preference row is created,
- no search state is saved to the database,
- the central search behaves in guest mode only.

## Data Sensitivity

The data managed by `app_member` is intentionally low-sensitivity.

It stores usage preferences for `Lyrics Slide Show` only.

It does not store:

- first name,
- last name,
- email,
- external identity attributes beyond the UUID key,
- sensitive personal data.

## Site-Wide Privileged Roles

### Functional Meaning

`Lyrics Slide Show` distinguishes between ordinary authenticated members and privileged authenticated members.

The privileged site-wide roles managed locally by the product are:

- `moderator`,
- `admin`.

An `admin` is always and automatically a `moderator`.

These roles are global to the whole service. They are not scoped to a single group, a single song, or a single Django app.

### Ownership Boundary

`app_member` is responsible for the local persistence and exposure of those roles.

Other apps may enforce or consume those permissions, but the privileged site-wide member status itself belongs to `app_member`.

`app_member` must not rely on a write path to `users.users` or on external `Keycloak` role management for those business permissions.

### Moderator Capabilities

A `moderator` must be able to:

- validate songs so they become impossible to modify outside moderator or admin permissions,
- modify a group with the same effective power as a group admin even when not a member of that group,
- publish a popup message on the main pages of the site, currently `homepage`, `groups`, `songs`, and `animations`,
- see notifications related to requests for modifying a song.

### Admin Capabilities

An `admin` must be able to:

- grant or revoke the local `admin` role for an authenticated member identified through `users.users`,
- grant or revoke the local `moderator` role for an authenticated member identified through `users.users`,
- modify the general site settings,
- publish a popup message on all pages of the site,
- inherit all moderator capabilities automatically.

### Persistence Rule

Privileged roles are persistent server-side data for authenticated members only.

Guests never receive a persistent privileged role.

The role data must remain in schema `lss`, with the authenticated member still referenced only by `users.users.id`.

## Administrative Member Search

`app_member` must provide the local service used by administrators to search members in the external directory.

This search:

- reads from `users.users` only,
- never writes to `users.users`,
- searches by `username`, `first_name`, `last_name`, and `email`,
- merges the external identity data with the local role state stored in `lss.m_member_roles`.

The search result is an application-level view model, not a duplicated local identity record.

In the default configuration, this search uses the unmanaged `DirectoryUserRecord` ORM model on `users.users`.

When `USER_SCHEMA` / `USER_TABLE` target another compatible external table, the implementation may fall back to validated SQL queries instead of the ORM model.

## Preference Persistence Model

This section concerns member preferences only.

Privileged roles are part of `app_member` scope, but they must use their own local persistence design in schema `lss`.

They must not be folded into `m_preferences`.

The active documented preference contract is currently centered on the persistent `songs` search state.

`app_member` owns the persistence schema and validation contract for that search state.

The current load/save helpers that apply this contract at runtime live in `app_song.search`, not in `app_member.views`.

The presence of a `theme_slug` column in the schema does not by itself make `app_member` the runtime source of truth for theme selection. That behavior must stay aligned with `docs/app_main/functional_requirements.md`.

The preferred table name is:

- `lss.m_preferences`

The privileged role table is:

- `lss.m_member_roles`

The name `g_users` from the legacy MySQL application should not be kept.

`m_preferences` is preferred because the table stores member preferences, not user identity data.

## Target PostgreSQL Table For Preferences

The current PostgreSQL table used for member preferences is equivalent to the following model:

```sql
CREATE TABLE lss.m_preferences (
  member_id uuid PRIMARY KEY,
  theme_slug varchar(32) NOT NULL DEFAULT 'normal',
  song_search jsonb NOT NULL DEFAULT '{
    "text": "",
    "everywhere": false,
    "match_all_selected_refs": false,
    "genre_ids": [],
    "band_ids": [],
    "artist_ids": [],
    "validation": "all",
    "favorites_only": false
  }'::jsonb,
  CONSTRAINT m_preferences_user_fk
    FOREIGN KEY (member_id)
    REFERENCES users.users (id)
    ON DELETE CASCADE
);
```

## Table Design Rules

- `member_id` is the `Keycloak` UUID and also the primary key,
- the foreign key points to `users.users(id)`,
- deleting the external user row deletes the corresponding preference row through `ON DELETE CASCADE`,
- if a theme slug is stored, it is stored as a theme slug, not as a CSS filename,
- the `songs` search state is stored as one JSON block,
- the table must stay focused on member preferences only.

## Target PostgreSQL Table For Roles

The functional target for privileged roles is a PostgreSQL table equivalent to the following model:

```sql
CREATE TABLE lss.m_member_roles (
  member_id uuid PRIMARY KEY,
  is_moderator boolean NOT NULL DEFAULT false,
  is_admin boolean NOT NULL DEFAULT false,
  CONSTRAINT m_member_roles_user_fk
    FOREIGN KEY (member_id)
    REFERENCES users.users (id)
    ON DELETE CASCADE,
  CONSTRAINT m_member_roles_admin_requires_moderator
    CHECK (NOT is_admin OR is_moderator)
);
```

## Role Table Design Rules

- `member_id` is the same authenticated UUID as in `m_preferences`,
- the foreign key points to `users.users(id)`,
- deleting the external user row deletes the corresponding role row through `ON DELETE CASCADE`,
- `is_admin` implies `is_moderator`,
- removing `moderator` from a member must also remove `admin`,
- if both role flags become false, the role row should be removed instead of being kept as an all-false record.

## Runtime Role Exposure

`app_member` must expose the local privileged roles to the rest of the Django project through dedicated services.

The effective runtime flags consumed by other apps are:

- `is_moderator`,
- `is_admin`.

Those flags must come from local `lss` business data, not from `Keycloak` role claims and not from writes to `users.users`.

When a member is `admin`, the effective runtime contract must always expose both:

- `is_admin = true`,
- `is_moderator = true`.

## Permission Helpers

`app_member` is also responsible for providing reusable permission helpers for the rest of the project.

At minimum, the app must expose helpers for:

- managing site members,
- managing site settings,
- managing the global administrator popup,
- managing the moderator popup,
- validating songs,
- managing groups globally with moderator authority.

The current concrete helpers are:

- `can_manage_site_members`,
- `can_manage_site_settings`,
- `can_manage_global_popup`,
- `can_manage_moderator_popup`,
- `can_validate_songs`,
- `can_manage_groups_globally`.

Current effective rules:

- site member management, site settings, and the global admin popup require `admin`,
- the moderator popup, song validation, and cross-group moderation powers require `moderator`,
- an `admin` satisfies all moderator-level checks automatically because runtime flags always expose `is_moderator = true` for admins.

## Theme Preference Boundary

### Current Runtime Rule

The current shared site shell applies the active visual theme from browser storage.

That browser-level behavior is documented in `docs/app_main/functional_requirements.md` and in the shared front-end shell.

`app_member` does not currently own the runtime source of truth for theme selection.

### Schema Boundary

The `theme_slug` field may exist in `lss.m_preferences` as a low-sensitivity preference slot, but it must not be treated as the active theme contract unless both `app_main` and `app_member` are updated together to document a server-side synchronization flow.

### Storage Rule

If `theme_slug` is stored, the value must be the functional theme identifier, for example:

- `normal`,
- `scout`,
- `taize`,
- `me†al`

The stored value must not be a legacy CSS filename such as `normal.css`.

For guests, theme handling remains outside the scope of `app_member`.

## Persistent `songs` Search

### Functional Meaning

The `songs` search is a central feature of the product.

Its state must persist for authenticated members so they can leave the page, use another app, come back later, reconnect later, and recover the same search context.

This persistence is intentionally stronger than the behavior of ordinary website search forms.

### Search Scope

The preferences stored by `app_member` concern the persistent central `songs` search state used by the product.

`app_member` defines the persistence contract only.

It does not define the full UI behavior of other apps that may read or update that state.

The stored preference contract is global to the authenticated member and is not split by group, app, or browser session.

### Stored Fields

The full search form state must be persisted, not just a subset.

The persisted search structure must support:

- `text`: text entered by the member,
- `everywhere`: whether the text search is limited to title and subtitle or extended to wider song content,
- `match_all_selected_refs`: strict logic for selected reference filters,
- `genre_ids`: selected genre identifiers,
- `band_ids`: selected band identifiers,
- `artist_ids`: selected artist identifiers,
- `validation`: validation filter state,
- `favorites_only`: favorite filter state.

### Validation Filter Semantics

The legacy field `search_song_approved` must not be modeled as a boolean because its functional meaning has three states:

- `all`: all songs,
- `validated_only`: only validated songs,
- `non_validated_only`: only non-validated songs.

Any implementation must preserve this three-state behavior.

### Reference Filter Semantics

`genre_ids`, `band_ids`, and `artist_ids` must store identifier lists, not free text labels.

These identifiers refer to the related reference tables used by the song catalog.

### Strict Reference Logic

The legacy field `search_logic` does not mean a generic SQL `AND` over the whole form.

Its functional meaning is:

- when disabled, selected reference filters may match broadly,
- when enabled, each selected genre, band, and artist must be individually present on the song.

This behavior must be preserved conceptually, even if the implementation is modernized.

## Search Execution Boundary

`app_member` does not implement the actual song-catalog matching algorithm.

Concerns such as:

- accent-insensitive matching,
- apostrophe handling,
- special-character escaping,
- exact SQL query construction,
- guest-side query-string behavior,

belong to the search implementation layer currently carried by `app_song`.

`app_member` is responsible only for the persisted structure and validation of the saved member search state.

## Guest Mode Versus Authenticated Mode

### Guest Mode

When the user is not authenticated:

- there is no database persistence for search,
- only the `text` field is used,
- that `text` field applies only to song title and subtitle,
- navigation causes the search state to be lost,
- other persistent member filters are not restored.

### Authenticated Member Mode

When the user is authenticated:

- the member's last saved search state must be loaded,
- this restored state replaces any transient guest-side state,
- there is no merge between guest state and member persistent state,
- the full persisted form becomes the active search context.

In the current implementation, that load/replace behavior is exercised by `app_song.search`.

## App Boundaries

`app_member` is responsible for storing and returning persistent member preferences only.

It is not responsible for defining complete search workflows, tabs, pages, or UI interactions in other apps.

The following boundary rules apply:

- the central persistent `songs` search state may be read and updated by other apps,
- the exact search interface and reset workflow are outside the responsibility of `app_member`,
- `app_member` must not define local non-persistent search modes that belong to another app,
- if another app provides temporary in-memory search modes, those modes are outside the persistence contract of `app_member`.

## Reset Responsibility

Persistent search is a cross-app capability, but `app_member` only stores and returns the last known member search state.

An explicit manual reset may exist elsewhere in the product, but the reset user experience itself is outside the scope of `app_member`.

## Persistence Timing

The persisted member search state represents the last saved known state for that member.

The exact save trigger is not implemented inside `app_member` itself.

The functional result expected by the persistence contract remains:

- a member returns later and gets the same saved state,
- a member can rely on that state across connections,
- the product does not reset the form automatically on ordinary navigation.

The current save triggers are handled by the app that owns the central search workflow, currently `app_song`.

## Non-Goals

`app_member` must not evolve into:

- a local account system,
- a duplicate of `users.users`,
- a holder of profile identity fields,
- a generic preference dumping ground without functional justification.

Any new preference stored in `m_preferences` must be justified as a durable member-specific `Lyrics Slide Show` usage preference.

## Vocabulary

The following terms should be used consistently in implementation and documentation:

- `member`: authenticated user accepted into `Lyrics Slide Show`,
- `member preferences`: persistent low-sensitivity preferences stored in `lss`,
- `theme_slug`: reserved theme identifier column in `m_preferences`, not the current runtime source of truth,
- `song_search`: persistent JSON search state for the central `songs` search,
- `guest mode`: anonymous behavior without member persistence,
- `authenticated member mode`: behavior with persistent member preferences loaded from `lss.m_preferences` when relevant.

## Popup Integration Boundary

`app_member` currently contributes the shared popup payload through its `site_popup` context processor.

That payload:

- reads the current language-scoped `SiteParams` row,
- always exposes `signup_url` as shared shell context,
- exposes the administrator popup on every page when `admin_message` is non-empty,
- exposes the moderator popup only on the main pages whose Django route names are currently:
  - `homepage`,
  - `groups`,
  - `songs`,
  - `animations`.

The popup rendering shell itself remains outside `app_member`.
