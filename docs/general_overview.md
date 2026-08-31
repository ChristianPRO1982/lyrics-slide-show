# Lyrics Slide Show General Overview

## Product Identity

The main product name is `Lyrics Slide Show`. The short form `LSS` can be used occasionally, but `Lyrics Slide Show` remains the preferred public name.

`Lyrics Slide Show` is a Django-based web service focused on one job: preparing and projecting song lyrics as live slides, with a workflow designed for music sessions, worship nights, rehearsals, spontaneous concerts, and any situation where lyrics must be displayed clearly and controlled quickly.

The spirit of the product is simple:

- project lyrics fast,
- keep the interface easy,
- remove unnecessary friction,
- avoid locking the service behind account creation,
- let people use the core value of the product without "giving away their life" just to start.

The service is meant to feel open and practical. A user who does not want to provide personal information such as an email address must still be able to use the public side of the service, especially for accessible songs and animation creation in open groups.

## Core Promise

The primary promise of `Lyrics Slide Show` is live projection of song lyrics through automatically generated slides.

Product priorities are:

1. live animation and projection,
2. collaborative global song database,
3. complete preparation and diffusion workflow around song sessions.

Groups are structurally important because they organize animations and avoid a single global mess, but the true functional heart of the product is the animation and projection experience.

## Scope

The whole Django project is dedicated to `Lyrics Slide Show`.

All Django apps inside this repository are dedicated to this service only. This repository is not a generic platform for unrelated domains.

## Architecture Principles

The service is built with `Django`.

Identity is handled by `Keycloak` through `SSO`. `Lyrics Slide Show` does not manage local accounts by itself, but it does manage its own business permissions and roles locally once identity has been established.

The product structure is organized around four major business areas:

- songs and lyrics content,
- groups,
- animations,
- projection and remote control.

The project must also rely on Django internationalization features. The codebase is written in English, the default language is French, user-facing text must remain translatable, and labels must not be hardcoded. Translations must be handled with Django i18n mechanisms.

This rule also applies to browser-side JavaScript.

No user-facing text may be hardcoded directly inside front-end JavaScript files.

If JavaScript needs translated text, that text must be provided through Django-rendered templates, localized data attributes, localized JSON payloads, or another application-controlled i18n bridge.

## Access Philosophy

The service is intentionally open.

Being logged in is not required to access the site or its public features. Authentication is only required for specific actions and restricted content.

This philosophy is important:

- guests can use the product in a meaningful way,
- open groups allow full work on animations without login,
- accounts are useful for ownership, persistence, private collaboration, and full catalog access,
- accounts are not required just to try, prepare, or run public-use cases.

In practical terms:

- a guest can create, edit, delete, and run animations inside an `open` group,
- a guest can also do the same in a `private_with_secret` group if they know the secret,
- a member gets stronger persistence and control, including group creation and access to the full song catalog,
- some songs remain hidden from non-authenticated users for licensing reasons.

## Roles

The main roles are:

- `Guest`: non-authenticated user,
- `Member`: authenticated user,
- `Group Admin`: member with management rights inside a given group; the French user-facing label is `responsable de groupe`,
- `Moderator`: authenticated user responsible for song quality and moderation data,
- `Admin`: site administrator; an admin is also a moderator.

## Permission Overview

The following rules describe the current functional intent.

### Groups

- Everyone can access the group list.
- Everyone can select an `open` group.
- Everyone can select a `private_with_secret` group if they know the secret.
- An authenticated member who already belongs to a `private_with_secret` group can also select it without re-entering the secret.
- Only authenticated users can select a `private` group, and they must belong to it.
- Only members and above can join a group.
- A member can create a group.
- Group settings can be modified by group admins, moderators, and admins.
- Group admins, moderators, and admins can validate a new member request for a group.
- Group admins, moderators, and admins can grant or revoke group admin rights for a member of the same group.
- A group may have several group admins, but it must always have at least one.
- The last remaining group admin cannot be revoked through ordinary role-management actions.
- Rare exception: if the last remaining group admin deletes their own account, the group may temporarily have no group admin until a moderator or admin appoints a new one.

### Songs

- Songs are global resources, never scoped to a group.
- Guests can view only the public, non-licensed part of the catalog.
- Members and above can access the full song catalog.
- Guests cannot create, edit, or delete songs.
- Members and above can add songs.
- Members can edit or delete a non-validated song.
- Non-moderator authenticated members without direct edit rights can submit a modification request on a validated song.
- Only moderators and admins can validate a song.
- Once validated, a song becomes a trusted source marked with `✔️` or `✔️⁉️` and can only be directly modified or deleted by moderators and admins.
- Validated and non-validated songs are both usable in animations.
- Songs under license are hidden from non-authenticated users.

### Animations

- To work on an animation, a group must first be selected.
- Animation access always implies full `CRUD` rights within the selected accessible group.
- Guests can create, edit, delete, and run animations inside an `open` group.
- Guests can also create, edit, delete, and run animations inside a `private_with_secret` group if they know the secret.
- Members and privileged roles can do the same according to the currently selected accessible group.

### Moderation and Administration

- Moderators can manage the moderators' popup message displayed on the site's main pages.
- Moderators can validate songs.
- Moderators can act with global moderation power across the service where business rules require moderator authority.
- Admins can manage site members and grant or revoke `moderator` or `admin` privileges.
- Admins can manage site-level settings stored in `lss.site_params`, including home page content and global image constraints.
- Admins can manage the administrators' popup message displayed on all pages.
- Admins automatically inherit all moderator capabilities.

### Account And Privileged UI

- The authenticated account page is the primary entry point for privileged member tools.
- A simple `Member` sees identity and preference-oriented account information only.
- A `Moderator` sees the moderation section on the account page.
- An `Admin` sees both the moderation section and the administration section on the account page.
- A dedicated `/site-params/` page may be used for detailed site-parameter editing by admins, without changing the account page's role as the main privileged hub.

### Site Popup Messages

- The site supports two independent popup messages stored in `lss.site_params`.
- The administrator message is eligible on all pages.
- The moderator message is eligible only on the main pages: `homepage`, `groups`, `songs`, and `animations`.
- If both messages are eligible on the current page, they are merged into one popup with two sections.
- Popup dismissal is deferred locally in the browser with a configurable cooldown per message type.
- Changing the message content invalidates the previous local defer state and makes the popup eligible again immediately.

## Groups

Groups exist to organize animations.

Songs do not belong to groups. Groups are used to avoid a chaotic global space for animations and to provide a collaboration perimeter.

Official group statuses are:

- `open`: accessible without authentication,
- `private`: authentication and group membership required,
- `private_with_secret`: accessible through a secret even without authentication.

The `private_with_secret` mode exists to reduce friction and allow people to use a group's animations without requiring an account for every participant.

## Songs

The song catalog is global.

A song is defined by:

- `title`,
- `subtitle`,
- `description`,
- `status` (`0` non validé, `1` validé, `2` validé avec attention/messages),
- `licensed`,
- `slide_display_mode`.

The pair `title + subtitle` must be unique.

### Song Text Model

Each song is composed of text blocks representing verses and chorus logic. The overview intentionally includes the technical content model because it is central to the product behavior.

Each text block includes:

- `text`,
- `chorus` (`bool`),
- `followed` (`bool`): do not display the chorus after this block,
- `not_c_num` (`bool`): do not continue verse numbering, useful when a long verse is split across several slides,
- `chorus_like` (`bool`): display the block like a chorus while still treating it as a verse for logic and numbering,
- `num`: technical position in database, managed by the app and spaced by 2 to simplify insertion and repositioning,
- `display_num`: computed display number used in the interface.

### Chorus and Verse Logic

The chorus is not duplicated manually in the source text.

The intended behavior is:

- if the first text block is a chorus, all chorus blocks are displayed first,
- then verse 1 is displayed,
- then all chorus blocks are displayed again,
- then verse 2,
- and so on.

If a verse is marked as `followed`, the chorus is skipped after that block and the flow moves directly to the next verse.

If numbering continuity is disabled with `not_c_num`, the displayed verse number does not continue. This allows a single verse to be split into several slides without producing misleading numbering.

For chorus-like sections such as pre-choruses or bridges, the user may type a custom prefix manually on the block itself.

The product also supports an official prefix catalog managed by moderators and administrators.

This official catalog is only a shared suggestion list for faster input in the editor.

It never prevents free manual input on the block itself, and a custom prefix typed by a member does not automatically become part of the official catalog.

### Song Metadata

Songs may also be linked to supporting reference data:

- `genres` (`0-n`),
- `artists` (`0-n`),
- `bands` (`0-n`),
- `links` (`0-n`, internal or external, typed as `score`, `audio`, `youtube`, `web`, `internal`).

The service does not store sheet music files or other file-based attachments as part of its core scope, though external links are allowed.

### Song-Level Slide Mode

Each song also carries a preferred slide display mode used as a default by `app_animation`.

Current values are:

- `single`,
- `chorus_then_parallel`,
- `chorus_always_parallel`,
- `verses_by_pairs`.

## Animations

`Animation` is the official business term.

An animation is an ordered playlist of songs plus projection settings.

Animations contain songs only.

An animation is prepared ahead of time and includes an animation date stored as `datetimeTZ`.

Past animations are hidden by default in the interface, but they remain accessible through an explicit history view.

There is no dedicated animation status such as draft or archived in the current product definition.

## Projection and Slide Generation

This is the core of the product.

From an animation's ordered list of songs, the site generates slides on the fly. There is no PowerPoint file, no `.pptx` export, and no static slide deck to prepare externally.

Key principles:

- slides are generated dynamically only,
- text placement is always centered horizontally and vertically,
- users do not control arbitrary text positioning,
- the product is made for singing and projection, not for general-purpose slide design,
- songs must be structured correctly when created,
- long verses are never automatically split by the system.

If a verse is too long, the user must structure it properly during song creation. The service can warn about this during editing, but it must not auto-cut the content into several slides.

## Visual Preparation

Visual customization is supported, but inside a controlled projection-oriented model.

### Animation-Level Settings

The animation level provides the mandatory default projection configuration:

- text color,
- slide background color,
- background image,
- title,
- description,
- left/right margins through one shared padding setting,
- font size,
- font from the application catalog.

### Song-Level Overrides

A song inside an animation may override:

- text color,
- slide background color,
- background image,
- font size,
- font.

### Verse-Level Overrides

A verse may override:

- text color,
- slide background color,
- background image,
- font size,
- font,
- display selection through a boolean deciding whether the verse is shown.

Chorus styling is managed at song level rather than as an individual chorus-block override.

## Remote and Projected Screen

The operating model is based on two synchronized browser pages on the same computer:

- page 1: the remote control,
- page 2: the projected fullscreen display for the video projector.

The current intended usage is one computer and one active operator.

The remote is not a simple linear slideshow controller. Its value comes from a smarter navigation model aware of songs, verses, choruses, and repeated chorus logic.

The remote can expose:

- current slide controls,
- next slide preview,
- smart navigation to previous slide, next slide, or chorus,
- previous and next song navigation,
- keyboard shortcuts,
- black mode,
- chorus display toggling,
- scroll mode toggle,
- QR code access for the spectator lyrics page,
- direct access to songs and slides in the animation.

There is no concept of a unique live session per animation. Reopening and regaining control of an existing projected display is desirable.

## Non-Linear Navigation

This non-linear navigation behavior is an important differentiator from generic presentation tools such as PowerPoint, Google Slides, or Canva.

The product knows the internal structure of songs. It does not depend on manually duplicated chorus slides in the source content.

This allows the operator to move more naturally through a song flow like:

- verse 1,
- chorus,
- verse 2,
- chorus,
- bridge,
- chorus.

The operator stays focused on the music and the room rather than on a manually maintained sequence of duplicated slides.

## Spectator Smartphone View

A QR code is available from the remote during an animation.

That QR code opens a public smartphone page intended for spectators, not for projection control.

This mobile view is always public and uses a stable public URL for the animation, valid before, during, and after the animation.

The smartphone experience is intentionally minimal and has no main menu.

Spectators can access:

- the songs one after another,
- each song title,
- the full song text,
- repeated choruses rendered explicitly in the reading flow.

Available controls are:

- shareable QR code,
- dark or light mode, defaulting to the smartphone/browser preference at each page load,
- larger text,
- smaller text,
- previous song,
- next song,
- song dropdown list.

The spectator smartphone lyrics view keeps one shared text-size preference across lyrics pages.
Its light/dark override is never persisted across reloads: each reload starts from the current browser preference.

This spectator view is not synchronized with the live projected animation.

## Internationalization

The product is international.

The default language is French, but the interface must support language switching. The language choice is exposed in the UI, currently through a flag selector in the top-right area.

Technical implications:

- source code stays in English,
- user-facing text is written in French first,
- UI labels must not be hardcoded,
- Django translation dictionaries are required,
- Django i18n must be used consistently.

## Language Discipline

The project follows a strict language discipline.

For anything visible to the end user, French is the source language. This includes labels, titles, help text, placeholders, navigation text, accessible labels such as `aria-label`, meaningful `title` attributes, image `alt` text, and visible runtime messages.

Those strings must be passed through Django internationalization mechanisms. They must not be left as raw hardcoded text in templates, JavaScript-generated UI, or other presentation layers when they belong to the product interface.

Technical code remains English-only. This applies to Python, HTML structure, CSS classes, JavaScript identifiers, Django block names, template variable names, slugs, route names, aliases, and other implementation-facing identifiers.

`Lyrics Slide Show` remains a product name and brand marker. It may appear as-is in the UI and documentation and does not need to be translated.

Temporary or exploratory templates may be tolerated outside the full discipline only when they are explicitly identified as out of product scope. Stable product-facing templates must follow the discipline completely.

## Non-Goals

The following items are explicitly outside the main scope of `Lyrics Slide Show`:

- local account management,
- storage of sheet music files or similar file attachments,
- advanced PowerPoint-like slide editing,
- free text placement on slides,
- `.pptx` export,
- video editing,
- streaming as a primary objective.

Streaming is not excluded forever, but it is not a version-1 objective.

## Vocabulary

The following business terms should be used consistently in the project:

- `Lyrics Slide Show`: preferred product name,
- `LSS`: occasional short form,
- `song`: a global lyrics resource,
- `animation`: an ordered playlist of songs with projection settings,
- `group`: a collaboration and storage perimeter for animations,
- `group admin`: technical and documentation term for the role shown to French users as `responsable de groupe`,
- `remote`: the operator page controlling projection,
- `projected screen`: the fullscreen display page for the audience,
- `validated song`: a moderator-approved song locked against regular edits,
- `private_with_secret`: a group accessible through a secret without mandatory login.

## Documentation Rule

The `docs/` directory is the source of truth for the project documentation.

The GitHub `README.md` is intended for external presentation and must stay aligned with the documentation stored in `docs/`.

Popup interactions are documented only in `docs/popup_messagebox.md`.

That file defines the dedicated popup/message box contract used by the project for user interactions that require a popup-style dialog. It is the single documentation entry point for that UI mechanism and must be updated whenever that popup contract changes.
