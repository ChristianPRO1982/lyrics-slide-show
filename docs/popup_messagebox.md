# Popup Message Box Contract

`Lyrics Slide Show` exposes a global popup API through `window.LSSMessageBox`.

This document describes the current implementation exactly as it behaves in the codebase.

## Loading Contract

- `templates/base.html` loads `static/js/message_box.js` globally.
- `templates/base.html` exposes `{% block page_scripts %}` after the shared scripts.
- The popup host is a global `<div id="lss-messagebox-root" hidden></div>`.
- The popup uses the current site theme from `window.LSS_THEME_CONFIG`.
- The popup close icon uses the active theme and the browser `prefers-color-scheme` mode.

## Public API

### `window.LSSMessageBox.show(config)`

Returns a `Promise`.

The promise resolves with:

```js
{
  reason: "button" | "close" | "escape" | "programmatic",
  buttonId: string | null,
  values: { [fieldId]: string },
  payload?: unknown
}
```

`payload` is present only when the popup is closed through `close(payload)` inside a button callback or through `window.LSSMessageBox.close(result)`.

### `window.LSSMessageBox.alert(config)`

Convenience wrapper over `show(config)`.

Default behavior when `config.buttons` is not provided:

```js
buttons: [
  { id: "ok", label: "OK", tone: "neutral" }
]
```

If `showCloseButton` is not explicitly provided, the wrapper sets it to `false`.

### `window.LSSMessageBox.confirm(config)`

Convenience wrapper over `show(config)`.

Default behavior when `config.buttons` is not provided:

```js
buttons: [
  { id: "yes", label: "Oui", tone: "success" },
  { id: "no", label: "Non", tone: "neutral" }
]
```

If `showCloseButton` is not explicitly provided, the wrapper sets it to `false`.

### `window.LSSMessageBox.prompt(config)`

Convenience wrapper over `show(config)`.

Default behavior when `config.buttons` is not provided:

```js
buttons: [
  { id: "confirm", label: "Confirmer", tone: "success", validate: true },
  { id: "cancel", label: "Annuler", tone: "neutral", validate: false }
]
```

If `showCloseButton` is not explicitly provided, the wrapper sets it to `false`.

### `window.LSSMessageBox.close(result?)`

Closes the active popup programmatically.

If a popup is open, it resolves the active promise with:

```js
{
  reason: "programmatic",
  buttonId: null,
  values: currentFieldValues,
  ...result
}
```

Returns:

- `true` if a popup was open and has been closed
- `false` if no popup was open

### `window.LSSMessageBox.isOpen()`

Returns `true` when a popup is currently open, otherwise `false`.

## `show(config)` shape

```js
{
  title: "Popup title",
  messageMarkdown: "Message with **Markdown**",
  size: "compact" | "default" | "wide",
  showCloseButton: true,
  initialFocus: "close" | "first-field" | "button:<id>" | "field:<id>",
  enterButtonId: "confirm",
  escapeButtonId: "cancel",
  buttons: [],
  fields: []
}
```

Normalization rules:

- missing or invalid `config` is treated as an empty object
- invalid `size` falls back to `"default"`
- `title` and `messageMarkdown` are always normalized to strings
- `buttons` defaults to `[]`
- `fields` defaults to `[]`
- if `fields` is present and `buttons` is empty, an error is thrown
- if `buttons.length === 0`, `showCloseButton` is forced to `true`
- otherwise `showCloseButton` is `true` unless explicitly set to `false`

## Buttons

Each button supports:

```js
{
  id: "confirm",
  label: "Confirmer",
  tone: "neutral" | "success" | "warning" | "danger",
  disabled: false,
  validate: true,
  onClick(context) {
    // optional
  }
}
```

Normalization rules:

- `id` is required and must be a non-empty string, otherwise an error is thrown
- `label` falls back to `id`
- invalid `tone` falls back to `"neutral"`
- `disabled` is coerced to boolean
- `onClick` is kept only if it is a function, otherwise it becomes `null`
- `validate` is kept only if it is explicitly boolean, otherwise it becomes `null`

Behavior rules:

- disabled buttons are rendered disabled
- disabled buttons cannot be triggered by click or keyboard shortcuts
- if a button callback throws, the error is logged with `console.error`, busy state is removed, and the popup stays open

## Fields

Version 1 supports up to five text fields:

```js
{
  id: "email",
  label: "Adresse e-mail",
  type: "text" | "email" | "password" | "textarea",
  value: "",
  readonly: false,
  placeholder: "",
  required: true,
  autocomplete: "email",
  maxLength: 255,
  rows: 4
}
```

Normalization rules:

- maximum supported field count is `5`, otherwise an error is thrown
- `id` is required and must be a non-empty string, otherwise an error is thrown
- invalid `type` falls back to `"text"`
- `label` falls back to `id`
- `value`, `placeholder`, and `autocomplete` are normalized to strings
- `readonly` is coerced to boolean
- `required` is coerced to boolean
- `maxLength` is used only if it is a positive integer
- `rows` is used only for `textarea` and only if it is a positive integer, otherwise it defaults to `4`

Rendered field behavior:

- fields are rendered inside a `<form novalidate>`
- textareas are vertically resizable
- `readonly: true` makes `input` and `textarea` fields non-editable while keeping their value focusable and selectable
- validation errors are rendered inline below the field
- current field values are always returned as strings

## Callback Context

Button callbacks receive:

```js
{
  buttonId,
  values,
  close(payload),
  keepOpen(),
  setFieldError(fieldId, message)
}
```

Behavior rules:

- `values` contains current field values at callback time
- `close(payload)` closes immediately with the current `reason`, `buttonId`, current field values, and `payload`
- `keepOpen()` marks the popup to stay open after the callback resolves
- `setFieldError(fieldId, message)` marks the target field invalid if it exists
- if a callback returns `false`, the popup stays open
- if a callback resolves to anything other than `false`, the popup closes unless `keepOpen()` was called

## Validation Rules

Validation only exists when fields are present.

Validation target selection:

- if `button.validate` is explicitly `true` or `false`, that value is used
- otherwise only the default `Enter` action button validates

Built-in validation rules:

- `required: true` checks that the trimmed value is not empty
- `type: "email"` checks validity via the native browser email validity

Built-in validation error messages:

- required: `Ce champ est obligatoire.`
- invalid email: `Veuillez saisir une adresse e-mail valide.`

If validation fails:

- the popup stays open
- the invalid field gets focus
- errors are displayed inline

## Markdown Support

`messageMarkdown` is rendered client-side by the popup component itself.

Supported formatting:

- paragraphs
- headings `#` to `######`
- unordered lists using `-` or `*`
- ordered lists using `1.`
- blockquotes using `>`
- fenced code blocks using triple backticks
- inline code using backticks
- links `[label](url)`
- bold with `**text**`
- emphasis with `*text*` or `_text_`

Security and sanitization rules:

- all raw HTML is escaped
- links are allowed only for:
  - `http:`
  - `https:`
  - `mailto:`
  - `tel:`
  - local anchors starting with `#`
  - local paths starting with `/`, `./`, or `../`
  - relative URLs that resolve safely against the current page
- invalid links are rendered as plain escaped text

This is not a full Markdown engine. The supported syntax is only the subset implemented in `static/js/message_box.js`.

## Interaction Rules

- Only one popup is visible at a time.
- Additional popups are queued in `FIFO` order.
- Opening a popup adds `body.lss-messagebox-open`, which disables page scrolling.
- Closing the popup removes that body class.
- The popup promise resolves only when that popup actually closes.
- Focus is restored to the element that had focus before the popup opened, if it is still focusable.

## Focus Rules

Explicit focus:

- `initialFocus: "close"` focuses the close button if it exists
- `initialFocus: "first-field"` focuses the first field if fields exist
- `initialFocus: "button:<id>"` focuses that button if it exists
- `initialFocus: "field:<id>"` focuses that field if it exists

Default focus fallback order when `initialFocus` is missing or invalid:

1. first field, if fields exist
2. default `Enter` action button, if it exists
3. close button, if it exists
4. first remaining focusable element
5. dialog panel itself

Implications:

- if the popup has action buttons, the close button does not receive initial focus by default
- the close button remains reachable through `Tab`
- if the popup has no buttons, the close button may receive initial focus

## Keyboard Rules

Focus trap:

- `Tab` and `Shift+Tab` are trapped inside the popup
- if no focusable element exists, focus falls back to the dialog panel

Busy state:

- while a button callback is running, non-Tab keyboard handling is blocked
- buttons and the close button are disabled during that busy state

Escape behavior:

- if the close button is present, `Escape` closes the popup with:

```js
{ reason: "escape", buttonId: null, values }
```

- when the close button is present, `escapeButtonId` is ignored
- if there is no button, `Escape` closes the popup with:

```js
{ reason: "escape", buttonId: null, values }
```

- if the close button is not present and there is one button, `Escape` triggers that button
- if the close button is not present and there are at least two buttons, `Escape` triggers button 2 by default
- if the close button is not present and `escapeButtonId` is provided and matches an existing button, it overrides the default
- if the close button is not present and `escapeButtonId` is provided but does not match an existing button, the normal default fallback is used

Enter behavior:

- `Enter` does nothing if there is no button
- if there is one button, `Enter` triggers that button
- if there are at least two buttons, `Enter` triggers button 1 by default
- if `enterButtonId` is provided and matches an existing button, it overrides the default
- if `enterButtonId` is provided but does not match an existing button, the normal default fallback is used
- `Enter` inside a `textarea` keeps its normal editing behavior
- `Enter` does not auto-trigger when focus is already on:
  - a button
  - a link
  - an input of type `button`, `submit`, or `reset`

## Mouse Rules

- clicking the backdrop does not close the popup
- clicking the backdrop moves focus back into the popup according to the normal initial-focus logic
- clicking the close button closes the popup with:

```js
{ reason: "close", buttonId: null, values }
```

- clicking a button triggers that button normally

## Layout and Size Rules

The current CSS behavior is:

- popup horizontal padding inside the viewport: `16px`
- popup vertical position: top-aligned with `12.5vh` margin above and below
- popup maximum height: `75vh`
- popup minimum height: `200px`
- width depends on `size`:
  - `compact`: min `320px`, max `460px`
  - `default`: min `320px`, max `680px`
  - `wide`: min `360px`, max `920px`

Content growth behavior:

- the popup panel itself grows naturally with content
- it does not have a fixed height
- once content would exceed `75vh`, only the body section scrolls
- header and footer stay visible because the panel uses a vertical flex layout with:
  - header fixed in flex
  - body flexible and scrollable
  - footer fixed in flex

## Visual Rules

- close control uses the themed `close.png` icon from the active theme and current light/dark mode
- the close control has no visible framed button style by default
- focus visible styling still applies to the close control
- neutral, success, warning, and danger buttons use the semantic popup theme variables
- `scout.css` overrides popup tokens from `normal.css` the same way as the rest of the site theme

## Accessibility Rules

- the popup panel uses `role="dialog"`
- the popup panel uses `aria-modal="true"`
- if a title is present, the dialog uses `aria-labelledby`
- if no title is present, the dialog uses `aria-label` with the configured dialog label
- the close icon image has empty `alt` and `aria-hidden="true"`
- field error messages use `aria-live="polite"`
- invalid fields get `aria-invalid="true"` and `aria-describedby`

## Example

```js
window.LSSMessageBox.show({
  title: "Supprimer l'animation",
  messageMarkdown: "Cette action est **irreversible**.",
  buttons: [
    {
      id: "delete",
      label: "Supprimer",
      tone: "danger",
      onClick({ values }) {
        console.log(values);
      }
    },
    {
      id: "cancel",
      label: "Annuler",
      tone: "neutral"
    }
  ],
  enterButtonId: "delete",
  escapeButtonId: "cancel"
}).then((result) => {
  console.log(result);
});
```
