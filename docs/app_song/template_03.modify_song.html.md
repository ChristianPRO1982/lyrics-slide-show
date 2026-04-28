# Design of Template `modify_song.html`

## Guiding Idea

C'est la page d'édition principale d'un chant.

Elle doit permettre de modifier l'identité textuelle du chant et sa structure en blocs de paroles, sans modifier les métadonnées du chant.

Cette page est centrale dans `Lyrics Slide Show` parce que la qualité du rendu projeté dépend directement de la bonne structuration du chant.

L'utilisateur ne doit pas éditer une suite technique de champs abstraits. Il doit voir le chant presque comme il sera rendu, puis ouvrir uniquement le bloc qu'il veut corriger.

La page doit donc rester orientée métier :

- modifier le titre, le sous-titre et la description,
- modifier les couplets, refrains et sections spéciales,
- réorganiser les blocs de paroles,
- vérifier les problèmes de longueur,
- prévisualiser le rendu complet dans une popup,
- sauvegarder clairement les modifications.

La page ne doit pas permettre de modifier les métadonnées.

Les métadonnées restent visibles pour contexte, mais elles sont en lecture seule.

## Scope

### Editable on this page

The template allows editing:

- song title,
- song subtitle,
- song description,
- lyric blocks,
- block text,
- block business type,
- block prefix where relevant,
- block behavior options,
- lyric block order.

### Not editable on this page

The template must not allow editing:

- genres,
- artists,
- bands,
- song links,
- validation status,
- licensed status,
- song messages,
- favorites.

Metadata editing belongs to another screen.

## Section Panel

Must be aligned with `app_song/templates/song/song.html` for uniform UX.

Use the same block strategy as the reading page:

- `section_title`,
- `section_nav`.

The section title must display the selected group name when a group is selected.

If no group is selected, the section title must use a translated label equivalent to:

TEXT: `Chants`

The section icon must use the songs icon with the normal theme-aware image system.

Required icon source (same visual contract as `song.html`):

- `static/icons/ui/normal/512/light/songs.png` as fallback `<img src>`,
- dark variant for dark mode source,
- `<picture>` with theme-aware sources exactly like the reading template pattern.

The selected group name must be visually coupled with this icon panel, exactly like the section presentation pattern used in `song.html`.

## Tools Panel

Must be aligned with `app_song/templates/song/song.html` for uniform UX.

The tools panel must reuse the same include strategy as the reading page (`song/includes/_song_actions.html`) with template context adapted to edit mode.

The tool that points to the current page (`modify_song`) must be hidden when rendering this page.

All other relevant song actions from the same actions component must remain visible.

Expected actions:

- TEXT: `← Retour au chant`
- TEXT: `← Retour à la liste`
- TEXT: `<hr>`
- TEXT: `Aperçu du rendu`
- TEXT: `Enregistrer`
- TEXT: `Enregistrer et quitter`

The preview action opens the site popup/messagebox module.

The save actions submit the form.

The tools panel must not expose metadata editing actions.

Implementation anchor:

- use `tools_title` and `page_tools` blocks with the same structure as the reading template.

## Main Header

Must be aligned with `app_song/templates/song/song.html` for uniform UX and page rhythm.

### Kicker

Use the same block (`page_kicker`) and visual style as `song.html`.

The content is still edit-context specific (for example `Modification du chant`), but the container and typography treatment must remain identical.

### Title

Display the full song title.

The title should include:

- title,
- subtitle when present,
- validation marker when relevant,
- license marker when relevant.

This title is contextual. The real editable title fields are inside the form body.

### Summary

Use the same summary container behavior as `song.html` (`page_summary`).

If a description exists, display a short summary of the current description with the same truncation and popup-open pattern used on the reading page when relevant.

The summary is informational only. The editable description field is inside the form body.

## Mobile Panel

Must be aligned with `app_song/templates/song/song.html` for uniform UX.

Use the same mobile side blocks and behavior:

- `mobile_side_title`,
- `mobile_side_content`,
- mobile actions toggle button with `aria-expanded`,
- collapsible actions area.

The mobile panel must expose the same action list logic as desktop tools, with the current-page action hidden and other actions visible.

## Main Form

The whole editable area must be contained in one form.

The form must include CSRF protection.

The form must support two submit intents:

- save and stay on the edit page,
- save and leave the edit page.

The submit intent must be explicit through a named submit field or hidden field.

Suggested values:

- `save`
- `save_and_exit`

## HTML Layout Contract

The page should define a clear top-level DOM structure so template and JavaScript stay aligned.

Recommended order:

1. section panel,
2. tools panel,
3. main header,
4. main form,
5. sticky save bar,
6. popup mount points if required by the site messagebox system.

Recommended semantic skeleton:

```html
<section data-song-edit-page>
  <header data-section-panel>
    <!-- Section title + icon -->
  </header>

  <aside data-tools-panel>
    <!-- Back actions, preview, save actions -->
  </aside>

  <header data-main-header>
    <!-- Kicker, contextual title, summary -->
  </header>

  <form method="post" data-song-edit-form>
    {% csrf_token %}

    <div data-song-edit-layout>
      <article data-card="identity">
        <!-- title / subtitle / description -->
      </article>

      <article data-card="metadata-readonly">
        <!-- validation/license/genres/artists/bands/links -->
      </article>

      <article data-card="lyrics-structure">
        <!-- reorder controls, insertion controls, lyric list -->
      </article>
    </div>

    <input type="hidden" name="submit_intent" value="save">
  </form>

  <div data-sticky-savebar>
    <!-- save / save_and_exit -->
  </div>
</section>
```

This layout contract is functional documentation, not a strict pixel layout.

### Layout expectations by viewport

- Desktop: tools panel may be lateral, main form occupies the content column, sticky save bar remains visible.
- Mobile: tools panel may collapse into stacked buttons; sticky save bar may become a compact bottom bar.
- At all sizes: reorder handles, block open controls, and save actions must remain reachable and not hidden by sticky UI.

### Base Template Block Mapping

To avoid ambiguity, `modify_song.html` should map to the same base template block layout as `song.html`:

1. `section_title`
2. `section_intro`
3. `section_nav`
4. `tools_title`
5. `page_tools`
6. `mobile_side_title`
7. `mobile_side_content`
8. `page_kicker`
9. `page_title`
10. `page_summary`
11. `content`
12. `content_footer`
13. `page_scripts`

`content_footer` is the dedicated area for the lyric reorder panel.

### Required functional hooks

To avoid ambiguity between CSS classes and JavaScript wiring, each major zone must expose at least one stable hook:

- page root: `data-song-edit-page`,
- main form: `data-song-edit-form`,
- identity card: `data-card="identity"`,
- readonly metadata card: `data-card="metadata-readonly"`,
- lyric structure card: `data-card="lyrics-structure"`,
- sticky bar: `data-sticky-savebar`.

Additional classes and wrappers are allowed, but these functional hooks should stay stable across visual refactors.

## Sticky Save Bar

The page must include a sticky save bar.

The sticky save bar must remain available while editing long song structures.

It must provide:

- primary action: `Enregistrer`,
- secondary action: `Enregistrer et quitter`,
- optional status text when there are unsaved changes.

The sticky save bar must not hide important content on small screens.

On mobile, it may become a compact bottom action bar.

## Unsaved Changes Behavior

As soon as the user changes any editable field, the page must be considered dirty.

Dirty state applies to:

- title changes,
- subtitle changes,
- description changes,
- lyric block text changes,
- block type changes,
- block option changes,
- prefix changes,
- block insertion,
- block deletion,
- block reordering.

When the user tries to leave the page with unsaved changes, the site popup/messagebox module must open.

The popup must offer exactly these choices:

1. abandon current modifications,
2. save and leave,
3. stay on the page.

The popup must use translated user-facing text.

No user-facing popup text may be hardcoded inside static JavaScript.

## Content Card 1: Song Identity

This card contains the editable identity fields of the song.

Fields:

- title,
- subtitle,
- description.

The description must allow line breaks.

The description must not allow rich text formatting.

The description textarea may be resized or auto-sized by CSS/JS, but the stored content remains plain text.

## Content Card 2: Read-only Metadata

This card displays current song metadata in read-only mode.

Display:

- validation label,
- license label,
- genres,
- artists,
- bands,
- links associated with the song.

The card must make clear that metadata cannot be changed on this page.

Suggested helper text:

TEXT: `Les métadonnées sont visibles ici pour contexte. Elles se modifient depuis l'écran dédié.`

The template may include the existing metadata display partial if it does not expose edit controls.

## Content Card 3: Lyric Structure

This card is the main editing area.

It contains:

- a short explanation of lyric structure,
- length recommendation rules,
- the reorder controls,
- the lyric block list,
- contextual insertion controls,
- warning indicators for each block.

### Length recommendation helper

The card must display the current recommended limits configured by the application.

Example user-facing text:

TEXT:

```text
Il est conseillé de suivre les règles suivantes pour créer un couplet ou un refrain afin que le texte ne déborde pas des diapos, que les diapos ne soient pas trop lourdes et que le texte ne soit pas trop petit :
📏 Nombre de lignes maximum (saut de ligne compris) : 10
📏 Nombre de caractères maximum pour une ligne (espaces et ponctuation compris) : 50
```

The numeric values must come from backend context.

They must not be hardcoded in the template.

These limits are warnings only. They must not block saving.

## Lyric Block Display Model

Each lyric block is displayed first in a rendered reading mode.

The reading mode must show:

- the block label,
- the block text,
- the visual treatment matching its type,
- the drag handle.

The displayed label depends on the block:

- regular verse: visible verse number,
- chorus: `R.` or the configured chorus label,
- chorus-like block: prefix if present,
- chorus-like block without prefix: a suitable translated generic label.

The block text must appear as it will be displayed, including line breaks.

Chorus and chorus-like blocks must use the visual emphasis expected by the song rendering rules.

The goal is that the user recognizes the song structure visually before opening the edit controls.

## Lyric Block Editing Interaction

Clicking on the rendered text area of a block opens that block's editing panel.

Only one lyric block editing panel may be open at a time.

Opening a block must close all other open block editing panels.

Clicking outside any block editing panel must close all open block editing panels.

Clicking a drag handle must close all open block editing panels before drag logic starts.

The drag handle itself must remain visible even when the block is not open.

## Lyric Block Editing Panel

The editing panel contains the editable fields for the selected block.

Fields must be presented with business vocabulary, not raw technical flags.

The user must not manipulate the technical fields directly.

### Required fields

Each block editing panel must include:

- block type selector,
- optional prefix field or selector when relevant,
- text textarea,
- business options,
- delete button.

### Block type selector

Use a guided business UI.

Suggested block types:

- `Couplet`,
- `Refrain`,
- `Section spéciale`.

A section spéciale corresponds to a chorus-like block.

The UI must map these choices to the underlying fields:

- regular verse: `chorus = false`, `chorus_like = false`,
- chorus: `chorus = true`, `chorus_like = false`,
- special section: `chorus = false`, `chorus_like = true`.

The user-facing UI must not expose the names `chorus`, `chorus_like`, `followed`, or `not_c_num` as raw labels.

### Business options

Business options must be shown conditionally according to the selected block type.

Expected options include:

- do not play the refrain after this block,
- do not continue verse numbering,
- display with a custom section label or prefix.

The option `do not play the refrain after this block` maps to `followed = true`.

The option `do not continue verse numbering` maps to `not_c_num = true`.

The prefix field is especially relevant for special sections such as:

- pont,
- pré-refrain,
- refrain final,
- coda.

If moderator-defined prefixes are available, the UI may offer them as suggestions.

Manual prefix input must remain possible unless the backend contract later forbids it.

## Textarea Rules

The lyric text field is a plain textarea.

The user must not have access to rich formatting.

Allowed formatting:

- line breaks only.

Not allowed:

- bold,
- italic,
- underline,
- colors,
- manual font size,
- HTML tags,
- Markdown formatting as formatting.

Users may insert empty lines.

Empty lines count in the line count warning.

The textarea should have a stable and readable size.

The application may add live counters for:

- number of lines,
- maximum line length.

## Block Length Warnings

Each block can display zero, one, or two warnings.

Supported warnings:

TEXT: `📏 Trop de lignes`

TEXT: `📏 Trop de caractères sur une ligne`

Warnings are non-blocking.

They inform the user that the block may display badly in projected slides.

Warnings must update when the block text changes.

Warnings must also be computed on the backend during save or validation.

The frontend warning is a convenience. It must not be the only source of truth.

## Text Normalization on Save

Text normalization must be handled automatically by the backend in Python when saving.

It must be transparent to the user.

The template documentation records the expected behavior, but the template must not be responsible for final normalization.

Normalization applies at least to:

- song title,
- song subtitle,
- song description,
- lyric block text,
- lyric block prefix when relevant.

Expected normalization:

- trim leading and trailing whitespace,
- trim each line where appropriate,
- collapse repeated ordinary spaces inside a line,
- preserve user-created line breaks,
- preserve intentional empty lines in lyric text,
- add French non-breaking spaces before punctuation that requires it.

French non-breaking spaces must be applied before punctuation marks such as:

- `!`,
- `?`,
- `:`,
- `;`,
- and any other same-family French punctuation marks supported by the backend normalization helper.

The intended result is to avoid line breaks between a word and the punctuation mark in projected lyrics.

The backend may store non-breaking spaces as Unicode non-breaking spaces such as `\u00A0` or narrow non-breaking spaces such as `\u202F`, depending on the typography decision made in Python code.

The template must not insert raw `&nbsp;` entities into textarea content.

## Block Insertion

New blocks are inserted contextually.

The page must not rely on one global `add block at end` action only.

Between every two existing blocks, display an insertion separator.

Also display an insertion separator before the first block and after the last block.

The separator should visually look like a horizontal line with a plus button centered in it.

Example visual intention:

TEXT: `<hr> + <hr>`

Clicking the plus button inserts a new block at that position.

The new block should open directly in edit mode.

If there is no existing block, display one large central call-to-action inviting the user to create the first block.

Suggested text:

TEXT: `Créer le premier bloc de paroles`

## Block Deletion

Deleting a block is available only from the block editing panel.

The delete action must not be displayed in the collapsed reading mode.

Deleting a block requires confirmation through the site popup/messagebox module.

The confirmation popup must use a yes/no decision.

The confirmation popup must not use a close cross as the primary decision mechanism.

The frontend may remove the block from the DOM after confirmation, but the form submission must still communicate the deletion clearly to the backend.

Recommended implementation:

- mark the block with a hidden delete flag,
- hide it from the visible list,
- let the backend process the deletion on save.

This avoids accidental loss of data before the full form is submitted.

## Reordering Lyric Blocks

Lyric block ordering must use the standalone ESM module:

```text
static/js/reorder-list.module.js
```

The module must be imported as a native ES module.

Do not use a global bridge unless a later architectural decision requires it.

The reorder module must remain business-logic free.

It only reorders DOM items and updates hidden position inputs.

The backend remains responsible for validating, saving, and recalculating final lyric numbering.

`content_footer` must host the rendered lyric blocks for drag and drop, with the same UX intent as the prototype in `app_song/templates/song/modify_song.html` and the functional contract from `docs/reorder-list.md`.

### Reorder controls

The lyric structure card must include:

- reorder mode toggle button,
- reorder cancel button.

Suggested labels:

TEXT: `Réorganiser les blocs`

TEXT: `Annuler la réorganisation`

The cancel button is hidden when persistent reorder mode is inactive.

### HTML contract

The lyric block list must respect the module contract.

The list container must have:

```html
[data-reorder-list]
```

Each direct item must have:

```html
[data-reorder-item]
[data-id]
```

Each item must contain:

```html
[data-reorder-handle]
[data-reorder-drag-view]
[data-reorder-normal-view]
[data-reorder-position]
```

Example structure:

```html
<div data-reorder-list>
  <article data-reorder-item data-id="verse-42">
    <button type="button" data-reorder-handle>
      Déplacer
    </button>

    <div data-reorder-drag-view hidden>
      Vue compacte du bloc
    </div>

    <div data-reorder-normal-view>
      Vue normale et panneau d'édition du bloc
    </div>

    <input
      type="hidden"
      data-reorder-position
      name="verses[42][position]"
      value="2"
    >
  </article>
</div>
```

The content footer panel must display lyric blocks in rendered business form (verse/chorus visual style) while still exposing the reorder module hooks.

### Reorder behavior

When reorder mode starts:

- close all open block editing panels,
- show compact drag views,
- keep drag handles visible,
- preserve a snapshot so cancel can restore the initial order.

When the user releases a dragged item in persistent reorder mode:

- the drag ends,
- reorder mode remains enabled,
- the page scrolls to the moved item if needed,
- hidden positions are updated.

When the user cancels reorder mode:

- restore the initial order,
- restore hidden position values,
- restore normal views.

The module configuration should use:

```js
startPosition: 2,
positionStep: 2,
scrollToMovedItemAfterDrop: true
```

It should also set `vibrateOnTargetChange: false` by default to match the current song prototype behavior unless a product decision changes that default.

The template-specific JavaScript must attach dirty-state tracking to reorder changes.

## Preview Popup

The page must provide a preview action.

The preview opens the site popup/messagebox module.

The preview popup displays a simple full rendered preview of the song.

The preview must use the current unsaved form state.

It must not be limited to the last saved database state.

The preview is a reading preview only.

It must not provide print actions, copy actions, or alternate rendering modes.

The preview rendering must use the same functional rules as normal song rendering:

- verses,
- choruses,
- repeated choruses,
- skipped chorus after followed blocks,
- chorus-like blocks,
- prefixes,
- visible verse numbering.

If the preview is generated by JavaScript, all user-facing text must still come from Django-rendered translated strings.

If the preview requires backend rendering, the template must provide enough serialized form data or endpoint wiring for the request.

## Accessibility

Interactive elements must use real buttons.

The drag handle must be a button.

The block opening interaction must be keyboard accessible.

The rendered block header or text area that opens the edit panel must be reachable by keyboard.

ARIA expanded state should be used for collapsible editing panels.

Popup confirmations must trap focus according to the existing site popup/messagebox contract.

The reorder mode toggle must expose its pressed state with `aria-pressed`.

## Internationalization

All visible user-facing strings must use Django i18n.

This includes:

- labels,
- helper text,
- placeholders,
- button text,
- warning text,
- popup text,
- aria-label values,
- title attributes.

No user-facing text may be hardcoded inside static JavaScript.

If JavaScript needs labels, the template must provide them through:

- data attributes,
- JSON script payload,
- translated inline configuration,
- or the existing site i18n bridge.

## Page Scripts

The page must load the song-specific JavaScript needed for:

- opening and closing lyric block edit panels,
- dirty state tracking,
- unsaved changes popup,
- preview popup,
- warning counters,
- block insertion UI,
- block deletion confirmation,
- reorder module initialization.

The reorder module must be loaded with:

```html
<script type="module">
  import { init } from "{% static 'js/reorder-list.module.js' %}";
</script>
```

The page may also load a dedicated static JavaScript file for `modify_song.html` behavior.

If a dedicated file is used, it must not contain hardcoded user-facing French strings.

## Backend Expectations Exposed by the Template

The template expects backend context for:

- selected group,
- song object,
- full display title with markers,
- read-only metadata display data,
- ordered lyric blocks,
- display label for each lyric block,
- rendered collapsed block text,
- editable block fields,
- configured maximum line count,
- configured maximum line length,
- translated labels for JavaScript behavior,
- preview endpoint or preview rendering payload if needed.

The backend remains responsible for:

- permission checks,
- saving the song identity,
- saving lyric blocks,
- inserting new blocks,
- deleting blocks,
- applying text normalization,
- recalculating technical positions,
- recalculating displayed verse numbers,
- validating warnings server-side,
- rendering the final preview according to song rendering rules.
