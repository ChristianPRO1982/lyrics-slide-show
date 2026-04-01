# Popup Message Box Contract

`Lyrics Slide Show` now exposes a global popup API through `window.LSSMessageBox`.

The component is loaded from the shared base template and is available on every page extending `base.html`.

## Loading Contract

- `templates/base.html` loads `static/js/message_box.js`.
- `templates/base.html` exposes a `{% block page_scripts %}` block after shared scripts.
- Page-specific JavaScript should live in its own file and call `window.LSSMessageBox`.

## Public API

### `LSSMessageBox.show(config)`

Returns a `Promise` resolved with:

```js
{
  reason: "button" | "close" | "escape" | "programmatic",
  buttonId: string | null,
  values: { [fieldId]: string },
  payload: unknown
}
```

### `LSSMessageBox.alert(config)`

Convenience wrapper with a default `OK` button.

### `LSSMessageBox.confirm(config)`

Convenience wrapper with default `Oui` / `Non` buttons.

### `LSSMessageBox.prompt(config)`

Convenience wrapper with default `Confirmer` / `Annuler` buttons.

### `LSSMessageBox.close(result?)`

Closes the active popup programmatically.

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

`validate` is optional. If omitted, the popup validates only the default `Enter` action button when fields exist. This keeps cancel-like actions free from validation by default.

## Fields

Version 1 supports up to five text fields:

```js
{
  id: "email",
  label: "Adresse e-mail",
  type: "text" | "email" | "password" | "textarea",
  value: "",
  placeholder: "",
  required: true,
  autocomplete: "email",
  maxLength: 255,
  rows: 4
}
```

If `fields` is provided, at least one button must also be provided.

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

Rules:

- return `false` to keep the popup open;
- call `keepOpen()` to keep it open after async work;
- call `close(payload)` to close with a custom payload;
- use `setFieldError(fieldId, message)` for custom field validation.

## Interaction Rules

- Only one popup is visible at a time.
- Additional popups are queued in `FIFO` order.
- The popup is centered both horizontally and vertically.
- The popup grows until its max size, then only the body scrolls.
- Clicking the backdrop does not close the popup.
- The close cross is shown by default.
- `showCloseButton: false` is honored only when at least one button exists.
- If no button exists, the close cross is forced visible.
- Keyboard defaults:
  - `0` button: `Escape` closes, `Enter` does nothing.
  - `1` button: `Enter` and `Escape` trigger that button.
  - `2+` buttons: `Enter` triggers button 1, `Escape` triggers button 2.
  - `enterButtonId` and `escapeButtonId` override those defaults.
  - `Enter` inside a `textarea` keeps its normal editing behavior.

## Example

```js
window.LSSMessageBox.show({
  title: "Supprimer l'animation",
  messageMarkdown: "Cette action est **irreversible**.",
  showCloseButton: false,
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
