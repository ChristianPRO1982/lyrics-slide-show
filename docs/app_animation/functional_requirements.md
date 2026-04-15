# App Animation Functional Requirements

## Purpose

This document defines the functional requirements for `app_animation`.

`app_animation` owns the preparation, ordering, and live use of `animations` in `Lyrics Slide Show`.

Until this document is expanded further, `docs/general_overview.md` remains the authoritative cross-app reference.

## Functional Role

`Animation` is the official business term.

An animation is:

- an ordered playlist of songs,
- attached to a selected group,
- configured with projection-oriented visual settings.

Animations contain songs only.

There is no dedicated animation status such as draft or archived in the current product definition.

Past animations are hidden by default in the main interface, but they remain available through an explicit history view.

## Access Rules

A group must be selected before a user can work on an animation.

Animation access implies full `CRUD` rights inside the currently selected accessible group.

The access contract is:

- guests can create, edit, delete, and run animations inside an `open` group,
- guests can also do the same inside a `private_with_secret` group if they know the secret,
- members and privileged roles can do the same according to the currently selected accessible group,
- a `private` group remains restricted to authenticated group members.

## Projection Model

`app_animation` is central to the product promise.

From an animation's ordered list of songs, the site generates slides dynamically.

The product must not rely on:

- external PowerPoint preparation,
- `.pptx` export,
- static slide decks stored ahead of time,
- automatic verse splitting.

If a verse is too long, the user must structure it correctly during song preparation.

## Visual Preparation

The animation level provides the default projection settings, including:

- text color,
- slide background color,
- background image,
- title,
- description,
- shared horizontal padding,
- font size,
- font selection.

Song-level and verse-level overrides may further refine these settings according to the rules in `docs/general_overview.md`.

## Remote And Projected Screen

The operating model is based on two synchronized browser pages on the same computer:

- the `remote`,
- the `projected screen`.

The current intended usage is one computer with one active operator.

The remote is not a simple linear slideshow controller. It must expose navigation aware of songs, verses, choruses, and repeated chorus logic.

The feature set includes at least:

- current slide controls,
- next slide preview,
- smart previous, next, and chorus navigation,
- previous and next song navigation,
- keyboard shortcuts,
- black mode,
- chorus display toggling,
- scroll mode toggling,
- QR code access for the spectator lyrics page,
- direct access to songs and slides in the animation.

Reopening and regaining control of an existing projected display is desirable. There is no unique live-session lock per animation in the current product definition.

## Spectator Smartphone View

`app_animation` also exposes the public spectator smartphone view linked by QR code.

This page is:

- public,
- stable for the animation before, during, and after the live session,
- intentionally minimal,
- not synchronized with the current projected slide.

Spectators can read the songs in sequence, including explicit repeated choruses in the reading flow.

## Non-Goals

`app_animation` must not evolve into:

- a general-purpose slide editor,
- a PowerPoint replacement based on arbitrary slide placement,
- a video-editing workflow,
- a streaming-first product.
