# Reorder List Module (ESM)

Standalone drag-and-drop reordering module for vertical lists.

- No dependencies.
- No business logic.
- No automatic save.
- Only reorders DOM items and updates hidden position inputs.

## File

- Module: `static/js/reorder-list.module.js`

## HTML Contract (minimal)

```html
<form>
  <button type="button" data-reorder-toggle>Reorder mode</button>
  <button type="button" data-reorder-cancel hidden>Cancel</button>

  <div data-reorder-list>
    <article data-reorder-item data-id="song-42">
      <button type="button" data-reorder-handle>Move</button>

      <div data-reorder-drag-view hidden>Compact drag view</div>
      <div data-reorder-normal-view>Normal content view</div>

      <input
        type="hidden"
        data-reorder-position
        name="items[42][position]"
        value="2"
      >
    </article>
  </div>

  <button type="submit">Save</button>
</form>
```

## Django Usage (`<script type="module">`)

```django
{% load static %}
<script type="module">
  import { init } from "{% static 'js/reorder-list.module.js' %}";

  const controller = init({
    list: document.querySelector("[data-reorder-list]"),
    toggleButton: document.querySelector("[data-reorder-toggle]"),
    cancelButton: document.querySelector("[data-reorder-cancel]"),
    startPosition: 2,
    positionStep: 2,
    vibrateOnTargetChange: false,
    scrollToMovedItemAfterDrop: true,
    onStart: (payload) => console.log("start", payload),
    onChange: (payload) => console.log("change", payload),
    onEnd: (payload) => console.log("end", payload),
    onCancel: (payload) => console.log("cancel", payload),
  });

  // Example API calls:
  // controller.enable();
  // controller.disable();
  // controller.cancel();
  // console.log(controller.getOrder());
  // controller.destroy();
</script>
```

## Minimal CSS Example

```css
[data-reorder-handle] {
  touch-action: none;
}

.is-reorder-enabled [data-reorder-item] {
  cursor: grab;
}

.is-reorder-dragging [data-reorder-item] {
  transition: transform 160ms ease;
}

.is-reorder-compact [data-reorder-normal-view] {
  display: none;
}

.is-reorder-dropzone {
  height: 0.75rem;
  margin: 0.25rem 0;
  border-radius: 999px;
  border: 1px dashed currentColor;
  opacity: 0.45;
}

.is-reorder-dropzone-active {
  opacity: 1;
  border-style: solid;
  box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.15);
}

.is-reorder-ghost {
  opacity: 0.92;
}
```

## Public API

```js
import { init } from "/static/js/reorder-list.module.js";

const controller = init(options);
controller.enable();
controller.disable();
controller.cancel();
controller.getOrder(); // string[]
controller.destroy();
```

### `init(options)`

- `list` (`HTMLElement`, required)
- `toggleButton?` (`HTMLElement`)
- `cancelButton?` (`HTMLElement`)
- `positionStep` (`number`, default: `2`)
- `startPosition` (`number`, default: `2`)
- `vibrateOnTargetChange` (`boolean`, default: `false`)
- `scrollToMovedItemAfterDrop` (`boolean`, default: `true`)
- `onStart?`, `onChange?`, `onEnd?`, `onCancel?` (`function`)

## Callback Payload

All callbacks receive:

```js
{
  movedId: string | null,
  fromIndex: number,
  toIndex: number,
  order: string[],
  persistentMode: boolean
}
```

## Behavior Notes

- Drag starts with `pointerdown` on handle + movement threshold (`6px`).
- Supports mouse, touch, stylus via Pointer Events.
- Dropzones are explicit and shown during drag (before, between, after items).
- Autoscroll runs near viewport/container edges.
- On drop, hidden positions are recalculated with `startPosition + index * positionStep`.
- In persistent mode, `pointerup` ends drag only (does not disable reorder mode).
- `cancel()` restores the initial snapshot (order, inputs, and view states).
- `Escape`:
  - If dragging: cancels current drag.
  - If persistent mode active and not dragging: restores initial snapshot (`cancel()`).
