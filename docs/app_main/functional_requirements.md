# App Main Functional Requirements

## Purpose

This document defines the current functional requirements for `app_main` as implemented today.

`app_main` is the Django app that provides the shared shell of `Lyrics Slide Show`:

- public entry pages,
- login, callback, and logout flows,
- session-backed request user loading,
- the authenticated `account` page,
- the dedicated `site_params` administration page,
- the theme and language preference pages,
- the Django model that exposes shared site parameters stored in `lss.site_params`,
- the directory-user mapping to `users.users`.

## Functional Role Of `app_main`

`app_main` owns the shared entry points and shared identity integration.

Its responsibility is to:

- expose the homepage and shared informational pages,
- integrate the configured authentication provider,
- resolve authenticated identities against the external user directory,
- expose a session-backed runtime user object on `request.user`,
- render the shared `account` page used by all authenticated members,
- host the privileged account UI used by moderators and administrators,
- expose the site parameter model used by administrative forms and shared popup content,
- expose theme and language preference pages for the current browser.

`app_main` does not own:

- the persistence of privileged member roles,
- the business rules for group, song, or animation management,
- user account creation,
- the persistence of per-member preferences.

Those concerns belong elsewhere, mainly in `app_member` or the other domain apps.

## URL Surface

`app_main` currently exposes these routes:

- `/` as the public homepage,
- `/login/`,
- `/auth/callback/`,
- `/provision/redirect/`,
- `/provision/complete/`,
- `/logout/`,
- `/account/`,
- `/themes/`,
- `/language/`,
- `/privacy-policy/`,
- `/site-params/`,
- `/heavy/` (debug-only),
- `/heavy/assets/<path:asset_path>` (debug-only).

## Authentication

### Source Of Identity

Identity comes from an external authentication flow.

The supported runtime modes are:

- `mock`,
- `keycloak`.

Unsupported authentication modes are rejected at the login entry point.

`app_main` does not create a local Django user account. It resolves the authenticated user in read-only mode against the external directory table, normally `users.users`.

### Login Flow

The login entry point must:

- redirect authenticated users to `account`,
- render a login page when no interactive login has started yet,
- redirect to the mock authentication endpoint when `AUTH_MODE=mock` and `start=1`,
- redirect to the Keycloak authorization URL when `AUTH_MODE=keycloak` and `start=1`,
- redirect back to the homepage with an error message when the auth mode is unsupported,
- redirect back to the homepage with an error message when Keycloak configuration is incomplete.

### Callback Flow

The callback flow must:

- validate the callback payload according to the configured auth mode,
- in mock mode, validate the callback signature, timestamp freshness, and UUID format,
- in keycloak mode, validate `state`, exchange the authorization code, and fetch user info,
- resolve the user from the external directory using the received external identifier,
- reject unknown users in mock mode,
- redirect unknown Keycloak users to an intermediate LSS provisioning page,
- expose an explicit link and automatic redirect from that intermediate page to `home`,
- use only a signed `home` provisioning URL,
- return to the homepage with a configuration error when the signed URL cannot be built,
- reject disabled users,
- cycle the session key on successful login,
- store a session representation of the authenticated user,
- clear the local session user on callback failure,
- redirect to the homepage after local success or failure,
- emit a flash message describing the result,
- log authentication success and failure events.

### Keycloak Expert Diagnostic

When a Keycloak authentication error occurs, `app_main` stores a non-sensitive
diagnostic snapshot in the browser session under `lss_keycloak_diagnostic`.

The diagnostic page `/login/diagnostic/` must:

- remain accessible without authentication,
- show the last Keycloak failure for the current browser session,
- expose only non-sensitive values such as stage, HTTP status, Keycloak error,
  Keycloak server URL, realm, client ID, redirect URI, and secret presence flags,
- never expose client secrets, access tokens, OAuth codes, cookies, or raw
  sensitive payloads,
- show targeted likely causes for common failures such as `token_exchange`
  `401 invalid_client`, `token_exchange` `401 unauthorized_client`,
  `token_exchange` `400 invalid_grant`, and `userinfo` `401`,
- show a link to relaunch Keycloak login.

A global link to this diagnostic page is eligible when a diagnostic snapshot is
present in the session.

### Logout Flow

The logout entry point must:

- clear the local session user,
- cycle the session key,
- redirect to the homepage by default,
- redirect to the Keycloak logout URL when `AUTH_MODE=keycloak` and logout configuration is complete,
- fall back to the homepage if the Keycloak logout URL cannot be built.

### Home Provisioning Redirect

When a Keycloak callback is valid but the user does not yet exist in `users.users`,
`app_main` stores a temporary provisioning target in the session and redirects to
`/provision/redirect/`.

The intermediate page must:

- keep the user anonymous in LSS,
- show a visible link to cARThographie,
- trigger an automatic browser redirect to the same target,
- target the signed `home` provisioning URL only.

If the signed provisioning URL cannot be built, the callback must keep the user
anonymous and return to the homepage with a configuration error instead of
linking to the generic `home` homepage.

When only the Home provisioning secret is missing, the error message must identify
that missing server-side secret explicitly.

`HOME_PROVISION_RETURN_URL` is a dedicated provisioning-resume URL. It must not
reuse the logout redirect URL and, for `LSS`, it must be an absolute HTTPS URL
that targets `/provision/complete/` exactly.

When the same callback also proves a valid Keycloak identity for an unknown local
user, `app_main` must store a temporary `lss_pending_provision` session payload
containing:

- the validated `external_id`,
- a creation timestamp,
- `auth_mode=keycloak`.

That pending state must never authenticate the user by itself.

The pending provisioning state must expire after 15 minutes.

### Home Provisioning Completion

The signed `HOME_PROVISION_RETURN_URL` used for `LSS` must target
`/provision/complete/`.

The completion entry point must:

- remain accessible without authentication,
- require the same browser session that previously received
  `lss_pending_provision`,
- retry the `users.users` lookup using the `external_id` stored in that session,
- open the normal local session when the user now exists and is enabled,
- clear `lss_pending_provision` and the temporary provisioning target on success,
- keep the user anonymous and show recovery actions when the user is still
  absent,
- clear `lss_pending_provision` and refuse access when the user exists but is
  disabled,
- clear expired `lss_pending_provision` state and ask for a fresh login flow.

## Directory User Resolution

`app_main` owns the runtime mapping between an external authenticated identifier and the site user record.

The directory resolution layer must:

- support the default `users.users` table through the unmanaged `DirectoryUserRecord` model,
- support custom `USER_SCHEMA` and `USER_TABLE` values through SQL fallback queries,
- validate schema, table, and column identifiers before building SQL,
- normalize the external identifier as a UUID,
- expose the fields `external_id`, `username`, `email`, `first_name`, `last_name`, and `enabled`,
- treat a missing `enabled` column in a legacy table as logically enabled,
- raise a specific error for unknown users,
- raise a specific error for disabled users.

## Request User Contract

`app_main` is responsible for exposing a runtime user object on `request.user` through middleware.

The effective request user contract includes:

- `is_authenticated`,
- `is_anonymous`,
- `external_id`,
- `username`,
- `email`,
- `first_name`,
- `last_name`,
- `is_moderator`,
- `is_admin`.

Anonymous requests receive an anonymous runtime object instead of a Django ORM user instance.

Refreshing the request user must:

- reload the current directory user from the external directory table,
- clear the session if the user is no longer found,
- clear the session if the user is disabled,
- refresh the local moderator and admin flags from `app_member`,
- guarantee that an admin is exposed as a moderator,
- write the refreshed role flags back into the session snapshot.

## Shared Site Parameters

`app_main` owns the Django model mapped to `lss.site_params`.

This table stores language-scoped shared site parameters, including:

- `title`,
- `title_h1`,
- `signup_url`,
- `home_text`,
- `bloc1_text`,
- `bloc2_text`,
- `verse_max_lines`,
- `verse_max_characters_for_a_line`,
- `chorus_prefix`,
- `verse_prefix1`,
- `verse_prefix2`,
- `admin_message`,
- `moderator_message`,
- `admin_message_cooldown_minutes`,
- `moderator_message_cooldown_minutes`,
- background image size, dimension, ratio, extension, and MIME constraints.

Language lookup must:

- first try the current request language,
- then fall back to the default Django language,
- then fall back to the first available `SiteParams` row,
- return `None` if the lookup fails completely.

`app_main` currently edits these site parameters from the `account` page. In its own UI, it directly uses the popup-related fields and the language-based row selection. Other stored fields are administered here and are available for the rest of the project.

Administrators can also edit the same `SiteParams` content from the dedicated `/site-params/` page with explicit language selection (`fr` or `en`), including row creation when the selected language row does not exist yet.

## Public Pages

### Homepage

The homepage remains accessible to guests.

It renders shared navigation and language-scoped marketing content from `SiteParams`. It must continue to:

- expose login access for guests,
- expose the signup link for guests from `SiteParams.signup_url`, with empty fallback when unset,
- expose account and logout access for authenticated users,
- expose links to theme, language, and privacy pages,
- load the shared popup root and popup client-side configuration,
- load the shared theme configuration used by the whole site shell,
- use `title` and `title_h1` from `SiteParams` when available (fallback to `Lyrics Slide Show`),
- parse `home_text` as either plain text or JSON cards payload (`{"cards":[...]}`) and expose up to six cards.

### Login Page

The login page must:

- explain whether the project is currently running in mock mode or Keycloak mode,
- offer the appropriate interactive login entry point.

### Privacy Policy Page

The privacy policy page is a public informational page rendered by `app_main`.

### Heavy Debug Page

`/heavy/` and `/heavy/assets/...` are debug-only routes and must return `404` when `DEBUG=False`.

In debug mode:

- `/heavy/` lists discoverable image assets from `<BASE_DIR>/LSS` first, then `<BASE_DIR>/static` as fallback,
- `/heavy/assets/...` serves files only from `<BASE_DIR>/LSS`,
- path traversal is rejected,
- only image extensions in `{.gif, .jpeg, .jpg, .png, .svg, .webp}` are served.

### Theme Preferences Page

The theme page is a browser-level preference page.

It must:

- expose the list of available visual themes,
- let the user activate a theme immediately on the client side,
- rely on the shared base template theme system,
- keep the chosen theme in browser storage as the current runtime source of truth.

The current shared shell does not implement server-side theme synchronization for authenticated members.

The currently available themes are:

- `normal`,
- `scout`,
- `taize`,
- `me†al`.

### Language Preferences Page

The language page is a browser-level preference page.

It must:

- expose French and English as the current interface choices,
- post to Django `set_language`,
- redirect back to the language page after a language change,
- make clear that the choice applies to the current browser rather than to the authenticated profile.

## Account Page

The authenticated `account` page is the single privileged entry point currently exposed by `app_main`.

There is no separate admin dashboard route.

The dedicated `/site-params/` route exists and is restricted to site-setting administrators.

### Access Rules

- anonymous users are redirected to `login`,
- authenticated members can access `account`,
- moderators see additional moderation tools,
- administrators see both the moderation tools and the administration tools.

### Base Member View

The base `account` page for an authenticated member shows:

- the current member identity summary,
- privacy and personal-data information,
- a link to the privacy policy,
- the external authenticated identifier,
- the effective site role summary,
- the current UI language summary,
- the active visual theme summary for the current browser.

When `request.user.is_moderator` is true, the account page header also shows the explicit marker `⚖️ Modérateur` directly below the main `Mon profil` title, inside the main header rather than in the summary aside.

When `request.user.is_admin` is true, the same header shows two role markers in this order:

- `👑 Administrateur`,
- `⚖️ Modérateur`.

These header role markers use the same visual style as the `app_song` tag badges and are rendered inline in reading order when both are present.

### Moderator Section

When `request.user.is_moderator` is true, the account page must expose a moderation section.

This section currently includes:

- editing the public moderator popup message,
- editing `moderator_message_cooldown_minutes`.

The public homepage may also expose moderation-specific song signals for moderators:

- when at least one song is pending moderation, the homepage main content starts with a `Chants à modérer` card,
- this card lists up to 5 songs ordered by most recent unread correction request first,
- `[...]` opens a popup with the exhaustive list.

If no `SiteParams` row can be resolved for the active language context, moderator message editing is temporarily unavailable.

### Admin Section

When `request.user.is_admin` is true, the account page must expose an administration section.

This section currently includes:

- editing the shared site parameters for the active language,
- editing the administrator popup message and its cooldown,
- editing text, formatting, and background-image constraints stored in `lss.site_params`,
- searching directory members by username, first name, last name, or email,
- viewing whether a matched directory member is enabled in `users.users`,
- granting or revoking the local `moderator` role,
- granting or revoking the local `admin` role.

When an administrator edits site settings for a language that does not yet have a `SiteParams` row, saving the form creates that row.

## Shared Navigation Role Marker

The shared navigation keeps the `account` link available to authenticated members.

When `request.user.is_moderator` is true, the navigation rail account button shows a `⚖️` marker positioned on the lower edge of the button.

When `request.user.is_admin` is true, the same account button also shows a `👑` marker positioned on the upper edge of the button.

Because `admin` implies `moderator`, an administrator sees both markers on the account button:

- `👑` on the upper edge,
- `⚖️` on the lower edge.

## Dedicated Site Params Page

`/site-params/` is a dedicated administration page for full `SiteParams` editing.

Rules:

- anonymous users are redirected to `login`,
- authenticated users without site-settings permission receive `404`,
- language context is selected by query string (`?language=fr|en`), defaults to current language then `fr`,
- invalid language values are normalized to `fr`,
- POST saves the selected language row and redirects back to the same page/language,
- validation failures show a flash error with invalid field labels when available.

## Account POST Actions

The `account` page currently processes distinct POST actions server-side.

Supported actions are:

- `save_moderation_settings`,
- `save_site_settings`,
- `update_member_role`.

The server-side processing must:

- enforce permission checks for each privileged action,
- return HTTP `403` when the current user lacks permission,
- re-render the account page with form errors when validation fails,
- redirect back to `account` after a successful update,
- preserve the current `member_search` query through redirects and follow-up forms,
- reject unknown actions with an error message.

Role updates must preserve the local business invariant that `admin` implies `moderator`.

Removing `moderator` must also remove `admin` when necessary to keep the role state coherent.

## Member Search And Role Management

The account administration flow includes directory member search.

This capability must:

- search the external directory in read-only mode,
- support both ORM lookup on `DirectoryUserRecord` and SQL fallback lookup,
- limit the result set,
- enrich each result with local role flags from `app_member`,
- clearly separate the external directory status from the local role state,
- never write back to the external directory.

## Popup Integration

The shared base template loads popup client-side support on all pages.

The popup content currently comes from the site popup context processor and the `SiteParams` row selected for the current language.

`app_main` edits popup texts and cooldown fields, while popup eligibility/rendering remains driven by shared shell logic.

### Popup Scope

- the administrator popup is eligible on all pages when `admin_message` is non-empty,
- the moderator popup is eligible only on `homepage`, `groups`, `songs`, and `animations` when `moderator_message` is non-empty,
- the popup payload is injected into the base template as JSON.

### Popup Versioning And Cooldown

Each popup section must:

- carry its own section identifier,
- carry its own cooldown in minutes,
- derive a content version from a hash of the message body,
- allow the front-end to invalidate a previous local defer state when the message changes.

## Shared Base Template Responsibilities

Although not all of the implementation lives inside `app_main`, the shared pages served by `app_main` depend on the common base template shell.

That shared shell must:

- expose global flash messages,
- expose shared navigation links,
- expose the theme configuration object and initial theme selection,
- expose the popup configuration object and popup JSON payload,
- expose logout links marked for client-side confirmation.

## Boundaries

`app_main` must not:

- write to `users.users`,
- own the persistence of member roles,
- own the persistence of member preferences,
- implement song, group, or animation domain logic,
- implement signup or external identity provisioning.

It may consume services from other apps and expose shared UI entry points for them.
