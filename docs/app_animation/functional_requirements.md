# App Animation Functional Requirements

## Purpose

This document defines the functional requirements for `app_animation`.

`app_animation` owns the preparation, ordering, projection, and live runtime behavior of `animations` in `Lyrics Slide Show`.

Very important boundary:

- `app_animation` does not own song source content.

Song source content and lyrics structure are owned by `app_song`. `app_animation` consumes that content to build ordered playlists and generated projection slides.

## Documentation Structure

This document defines global functional behavior for `app_animation`.

UI layout, page composition, and template-specific controls must be documented in dedicated template documentation files under `docs/app_animation/` when those screens are formally documented.

Functional workflows, permissions, projection behavior, runtime behavior, and data contracts belong in this document.

`docs/general_overview.md` remains the authoritative cross-app reference and must stay consistent with this document.

## Core Concepts

### Animation

An `Animation` is:

- an ordered playlist of songs,
- attached to a selected group,
- configured with projection-oriented visual defaults,
- scheduled with an animation date stored as timezone-aware datetime.

Animations contain songs only.

There is no dedicated animation status such as draft or archived in the current product definition.

Past animations are hidden by default in the main interface, but they remain available through an explicit history view.

### Animation Song

An `Animation Song` is one usage instance of a global song inside one animation.

The same global song may appear multiple times in the same animation, at different positions, with potentially different local visual overrides.

### Rendered Slide

A `Rendered Slide` is a runtime-generated projection view derived from:

- selected animation songs,
- selected verse flow and chorus logic from the song model,
- visual inheritance rules.

Rendered slides are not standalone editable content entities.

### Projection Runtime

The `Projection Runtime` is the browser-side local runtime used during live projection.

It must support stable navigation without depending on per-slide server roundtrips.

## Access Rules

A group must be selected before a user can work on an animation.

Animation permissions depend on the selected accessible group context, not only on user identity alone.

Animation access implies full `CRUD` rights inside the currently selected accessible group.

The access contract is:

- guests can create, edit, delete, and run animations inside an `open` group,
- guests can also do the same inside a `private_with_secret` group if they know the secret,
- members and privileged roles can do the same according to the currently selected accessible group,
- a `private` group remains restricted to authenticated group members.

## Animation Structure

An animation supports:

- ordered song sequence,
- song insertion at any position,
- song removal,
- song reordering,
- repeated usage of the same song,
- visual override configuration on animation song instances,
- verse-level display selection control where supported by projection rules.

`app_animation` must preserve deterministic ordering. Given the same animation configuration and same song source content, generated slide order must be stable.

## Projection Model

`app_animation` is central to the product promise.

From an animation's ordered list of songs, the site generates slides dynamically at runtime.

The product must not rely on:

- external PowerPoint preparation,
- `.pptx` export,
- static slide decks stored ahead of time,
- automatic verse splitting.

If a verse is too long, users must structure song source content correctly in `app_song`.

## Offline Projection Philosophy

Projection runtime is local-browser first.

Required behavior:

- projection navigation must run from precomputed or preloaded runtime data,
- no blocking network dependency should be required between slide changes,
- runtime must stay usable even when transient network issues occur after preload,
- server interactions are acceptable for editing, preparing, or publishing updates, not for every next/previous action during live projection.

## Slide Generation Rules

Slides are generated runtime views, not manually edited slide documents.

Generation rules:

- slide sequence is derived from animation song order plus song block flow,
- repeated chorus logic is preserved from song model behavior,
- verse inclusion/exclusion is derived from configured display selection flags,
- visual inheritance is applied at generation time,
- generation remains deterministic for a given input state.

Core invariant:

- slides are generated runtime views,
- slides are not standalone editable content entities.

## Visual Preparation

The animation level provides default projection settings, including:

- text color,
- slide background color,
- background image,
- title,
- description,
- shared horizontal padding,
- font size,
- font selection.

Song-level and verse-level overrides may refine these settings according to the rules in `docs/general_overview.md`.

## Visual Inheritance Model

Visual properties are resolved with top-down inheritance:

```text
animation defaults
-> animation-song overrides
-> verse-level overrides
-> rendered slide
```

This inheritance applies to projection-oriented properties such as:

- font family,
- font size,
- text color,
- background color,
- background image,
- horizontal padding.

## Projection Rendering Rules

Projection rendering rules are constrained by product scope:

- text placement is centered horizontally and vertically,
- free manual text positioning is out of scope,
- rendering must favor stable readability for live singing contexts,
- long verses are not auto-split during projection runtime,
- projection must avoid visible loading interruptions during navigation after preload.

## Background Images

Background handling requirements:

- only valid application-managed image references can be used,
- runtime should preload required background assets before or during initialization,
- projection navigation should avoid runtime stalls due to background fetches,
- fallback behavior must keep projection readable if one background fails,
- background handling must preserve visual stability and readability.

## Runtime Navigation Model

Navigation is intentionally non-linear and music-flow aware.

Required capabilities include at least:

- current slide controls,
- next slide preview,
- smart previous/next navigation,
- chorus-aware navigation,
- previous/next song navigation,
- direct song and slide access,
- keyboard shortcut support,
- black mode toggle,
- chorus display toggle,
- scroll mode toggle.

The remote must optimize operator flow without requiring manual duplication of chorus slides.

## Projection Runtime Session

The operating model uses two synchronized browser pages on the same computer:

- the `remote`,
- the `projected screen`.

Current target usage is one computer and one active operator.

There is no unique live-session lock per animation in the current product definition.

Reopening and regaining control of an existing projected display is desirable.

## Live Editing During Runtime

When animation content or settings are updated during an active usage window, runtime behavior should preserve continuity:

- updated runtime bundle is prepared before activation,
- projection should switch only when a coherent new state is ready,
- failures in update preparation should keep the current projection state usable,
- projection continuity has priority over aggressive live refresh behavior.

## Search And Song Selection Boundary

`app_animation` depends on the global song catalog owned by `app_song`.

`app_animation` is responsible for song selection into animations, but not for:

- global song content authoring rules,
- global song search ownership beyond integration points,
- song validation lifecycle ownership.

## Spectator Smartphone View

`app_animation` exposes a public spectator smartphone view linked by QR code.

This page is:

- public,
- stable for the animation before, during, and after the live session,
- intentionally minimal,
- not synchronized with the current projected slide.

Spectators can read songs in sequence, including explicit repeated choruses in the reading flow.

## Database Reference

`app_animation` owns the animation-side persistence needed for:

- animation identity and group linkage,
- animation song ordering and overrides,
- verse-level projection selections and overrides,
- runtime projection relations where applicable.

Table and schema-level SQL contracts may be expanded in this document as the implementation reference is finalized.

## Non-Goals

`app_animation` must not evolve into:

- a general-purpose slide editor,
- a free-form text placement editor,
- a PowerPoint replacement with standalone authored slides,
- a collaborative realtime editor as primary model,
- a video-editing workflow,
- a streaming-first product,
- a generic media hosting platform.
