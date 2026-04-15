# App Main Functional Requirements

## Purpose

This document defines the current functional requirements for `app_main`.

`app_main` is the Django app that provides the shared entry points of `Lyrics Slide Show`:

- public landing pages,
- authentication entry and callback flow,
- session-backed request user loading,
- the authenticated `account` page,
- global site parameters exposed to the UI,
- base-template integration for site-wide popup messages.

## Functional Role Of `app_main`

`app_main` is the shell of the site.

It does not own the member preference data model and it does not own the privileged role persistence model. Those belong to `app_member`.

Its responsibility is to:

- integrate identity coming from `SSO`,
- expose the current authenticated user on `request.user`,
- expose site-level content and constraints stored in `lss.site_params`,
- render the shared pages and account page used across the whole project,
- host the privileged `account` UI used by moderators and administrators.

## Authentication

### Source Of Identity

Identity comes from external `SSO`.

The supported runtime modes are:

- `mock`,
- `keycloak`.

`app_main` does not create local user accounts.

The local authenticated identity is resolved in read-only mode against `users.users`.

### Login Flow

The login entry point must:

- redirect authenticated users to `account`,
- redirect to the mock SSO entry point when `AUTH_MODE=mock` and login is explicitly started,
- redirect to the Keycloak authorization URL when `AUTH_MODE=keycloak` and login is explicitly started,
- reject unsupported authentication modes by redirecting to the homepage with an error message.

The callback flow must:

- validate the callback payload according to the configured auth mode,
- resolve the user from `users.users`,
- reject unknown or disabled users,
- cycle the session key on successful login,
- persist a session representation of the authenticated user,
- redirect to the homepage after success.

### Logout Flow

The logout entry point must:

- clear the local session user,
- cycle the session key,
- redirect to the homepage in mock mode,
- redirect to Keycloak logout when `AUTH_MODE=keycloak` and configuration is complete.

## Request User Contract

`app_main` is responsible for exposing a runtime user object on `request.user` through middleware.

The effective request user contract includes:

- `is_authenticated`,
- `external_id`,
- `username`,
- `email`,
- `first_name`,
- `last_name`,
- `is_moderator`,
- `is_admin`.

The privileged flags are local business flags loaded from `app_member`, not directly from the identity provider.

Refreshing the request user must:

- reload the current directory user from `users.users`,
- clear the session if the user is no longer found or is disabled,
- refresh the local `admin` and `moderator` flags from `app_member`,
- guarantee that an `admin` is also exposed as `moderator`.

## Site Parameters

`app_main` owns the Django model mapped to `lss.site_params`.

This model stores shared site content and constraints, including:

- `title`,
- `title_h1`,
- `home_text`,
- `bloc1_text`,
- `bloc2_text`,
- verse formatting limits,
- chorus and verse prefixes,
- image background constraints,
- `admin_message`,
- `moderator_message`,
- `admin_message_cooldown_minutes`,
- `moderator_message_cooldown_minutes`.

The model is keyed by language and is used as the site-level content source for the current language.

## Homepage And Public Pages

`app_main` provides the public homepage and supporting public pages such as:

- login,
- language selection,
- privacy policy.

The homepage remains accessible to guests.

The homepage must continue to present the product as an open service where authentication is not required for basic discovery and public use cases.

## Account Page

The authenticated `account` page is the single privileged entry point in the current product.

There is no dedicated admin page in the navigation.

### Access Rules

- anonymous users are redirected to `login`,
- authenticated members can access `account`,
- moderators and admins see additional privileged sections on the same page.

### Base Member View

The base `account` page for an authenticated member shows:

- the current member identity summary,
- privacy-related information,
- the external authenticated identifier,
- the effective site role summary.

### Moderator Section

When `request.user.is_moderator` is true, the account page must expose a moderation section.

This section currently includes:

- editing the public moderator popup message,
- editing `moderator_message_cooldown_minutes`,
- a reserved placeholder block for future song modification notifications.

### Admin Section

When `request.user.is_admin` is true, the account page must expose an administration section.

This section currently includes:

- editing shared site parameters for the current language,
- editing the public administrator popup message,
- editing `admin_message_cooldown_minutes`,
- searching members in `users.users`,
- granting or revoking `moderator`,
- granting or revoking `admin`.

An admin also sees the moderation section.

## Privileged Actions On Account Page

The `account` page must process distinct POST actions server-side.

Current actions are:

- saving moderation settings,
- saving administrator site settings,
- updating a member role.

Each privileged action must enforce server-side permission checks and return `403` for insufficient privileges.

Role updates must remain coherent with the business invariant that `admin` implies `moderator`.

## Site Popup Integration

`app_main` must expose the global popup configuration to the base template for all pages.

The UI implementation uses `window.LSSMessageBox` as the only popup mechanism.

### Popup Scope

- the administrator popup is eligible on all pages when `admin_message` is non-empty,
- the moderator popup is eligible only on `homepage`, `groups`, `songs`, and `animations` when `moderator_message` is non-empty.

### Popup Combination

If both popups are eligible on the current page:

- only one popup is shown,
- the popup contains two sections,
- each section keeps its own cooldown and version.

### Popup Defer Rules

After the user clicks `OK`:

- the popup is deferred locally in the browser,
- defer state is stored separately for `admin` and `moderator`,
- the defer duration is based on the corresponding cooldown in `lss.site_params`,
- changing the message content must invalidate the previous defer state through content hashing.

## Boundaries

`app_main` must not:

- write to `users.users`,
- own the persistence of member preferences,
- own the persistence of privileged roles,
- implement song, group, or animation business logic that belongs to other apps.

It may consume those services and expose them through shared pages and shared UI.
