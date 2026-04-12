# Static Theme Guide

This directory contains the static assets used by the site themes.

## Theme Model

A site theme is made of:

- one CSS file in [`css/`](/home/utilisateur/Documents/projects/perso/cARThographie/lyrics-slide-show/static/css),
- its themed icons in [`icons/ui/`](/home/utilisateur/Documents/projects/perso/cARThographie/lyrics-slide-show/static/icons/ui),
- optional shared images in [`images/`](/home/utilisateur/Documents/projects/perso/cARThographie/lyrics-slide-show/static/images),
- shared frontend logic in [`js/`](/home/utilisateur/Documents/projects/perso/cARThographie/lyrics-slide-show/static/js).

Current themes:

- `normal`
- `scout`
- `taize`

## CSS Rules

Theme stylesheets are:

- [`css/normal.css`](/home/utilisateur/Documents/projects/perso/cARThographie/lyrics-slide-show/static/css/normal.css)
- [`css/scout.css`](/home/utilisateur/Documents/projects/perso/cARThographie/lyrics-slide-show/static/css/scout.css)
- [`css/taize.css`](/home/utilisateur/Documents/projects/perso/cARThographie/lyrics-slide-show/static/css/taize.css)

Important rules:

- `normal.css` is the base theme.
- `scout.css` and `taize.css` import `normal.css` and override only what they need.
- A user selects the visual theme (`normal`, `scout`, or `taize`).
- The browser controls `light` or `dark` mode automatically through `prefers-color-scheme`.
- Do not create separate user-selectable themes for `light` and `dark`.

## Icon Rules

The icon tree is:

```text
static/icons/ui/<theme>/<size>/<mode>/<icon>.png
```

Example:

```text
static/icons/ui/normal/128/dark/home.png
```

Where:

- `<theme>` is `normal`, `scout`, or `taize`
- `<size>` is `64`, `128`, or `512`
- `<mode>` is `light` or `dark`

Current responsive usage:

- desktop PC: `128`
- smartphone and tablet: `64`
- `512` is used for dedicated page illustrations, but not for navigation menus

Templates do not hardcode one final icon path anymore. They render responsive `<picture>` blocks, and `static/js/base.js` rewrites icon paths according to the active theme.

## Template Behavior

General templates use:

- [`templates/base.html`](/home/utilisateur/Documents/projects/perso/cARThographie/lyrics-slide-show/templates/base.html)
- [`templates/includes/nav.html`](/home/utilisateur/Documents/projects/perso/cARThographie/lyrics-slide-show/templates/includes/nav.html)
- [`templates/includes/themed_icon.html`](/home/utilisateur/Documents/projects/perso/cARThographie/lyrics-slide-show/templates/includes/themed_icon.html)

Important behavior:

- `base.html` loads the selected theme stylesheet.
- The active theme slug is stored in local storage under `lss-theme`.
- `themed_icon.html` provides the responsive icon markup.
- `base.js` updates icon paths when the user changes theme.
- The browser still decides whether `light` or `dark` assets are used.

## Language Button

The language button is a special case:

- it uses the generic themed icon `button.png`,
- a flag is displayed above the icon in the template,
- `fr` displays `🇫🇷`,
- `en` displays `🇬🇧`.

This is intentional. Do not replace it with a regular dedicated icon unless the UX rule changes.

## When Adding a New Theme

To add a new theme:

1. Add `static/css/<theme>.css`.
2. Add the icon set under `static/icons/ui/<theme>/`.
3. Provide both `light` and `dark` icons.
4. Provide at least the responsive sizes currently used: `64` and `128`.
5. Register the stylesheet in [`templates/base.html`](/home/utilisateur/Documents/projects/perso/cARThographie/lyrics-slide-show/templates/base.html).
6. Make sure the theme selection UI exposes the new slug if needed.

## Editing Rules

When changing themes or icons:

- keep the business theme choice separate from browser `light/dark`,
- preserve the folder contract `ui/<theme>/<size>/<mode>/`,
- avoid hardcoding `normal` inside templates except as a safe fallback,
- update both `normal` and `scout` asset sets when required,
- keep desktop/mobile icon sizes aligned with the current responsive rule.

If this guide conflicts with `docs/`, the documentation in `docs/` remains the source of truth for product intent.
