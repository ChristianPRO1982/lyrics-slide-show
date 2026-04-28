const MODE_DISABLED = "disabled";
const MODE_ENABLED_PERSISTENT = "enabled-persistent";
const MODE_ENABLED_TEMPORARY = "enabled-temporary";
const MODE_DRAGGING = "dragging";

const CLASS_ENABLED = "is-reorder-enabled";
const CLASS_DRAGGING = "is-reorder-dragging";
const CLASS_GHOST = "is-reorder-ghost";
const CLASS_DROPZONE = "is-reorder-dropzone";
const CLASS_DROPZONE_ACTIVE = "is-reorder-dropzone-active";
const CLASS_COMPACT = "is-reorder-compact";

const CLASS_PLACEHOLDER = "is-reorder-placeholder";

const SELECTOR_ITEM = "[data-reorder-item]";
const SELECTOR_HANDLE = "[data-reorder-handle]";
const SELECTOR_DRAG_VIEW = "[data-reorder-drag-view]";
const SELECTOR_NORMAL_VIEW = "[data-reorder-normal-view]";
const SELECTOR_POSITION = "[data-reorder-position]";

const POINTER_START_THRESHOLD = 6;
const AUTOSCROLL_EDGE_PX = 64;
const AUTOSCROLL_MAX_STEP = 16;

const noop = () => {};

function isElement(value) {
    return value instanceof HTMLElement;
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function callCallback(callback, payload) {
    if (typeof callback !== "function") {
        return;
    }
    try {
        callback(payload);
    } catch (_error) {
        // Callbacks should not break the reorder engine.
    }
}

function getDirectItems(listElement) {
    return Array.from(listElement.children).filter((child) => {
        return child.matches(SELECTOR_ITEM);
    });
}

function getItemId(itemElement) {
    const value = itemElement?.dataset?.id;
    return value == null ? "" : String(value);
}

function getOrderFromList(listElement) {
    return getDirectItems(listElement)
        .map((item) => getItemId(item))
        .filter((id) => id.length > 0);
}

function findScrollableAncestor(element) {
    let node = element;
    while (node && node !== document.body) {
        const style = window.getComputedStyle(node);
        const overflowY = style.overflowY || "";
        const canScroll = /(auto|scroll|overlay)/.test(overflowY);
        if (canScroll && node.scrollHeight > node.clientHeight) {
            return node;
        }
        node = node.parentElement;
    }
    return null;
}

function edgeStep(pointerY, top, bottom, edgeSize, maxStep) {
    if (pointerY < top + edgeSize) {
        const ratio = clamp((top + edgeSize - pointerY) / edgeSize, 0, 1);
        return -ratio * maxStep;
    }
    if (pointerY > bottom - edgeSize) {
        const ratio = clamp((pointerY - (bottom - edgeSize)) / edgeSize, 0, 1);
        return ratio * maxStep;
    }
    return 0;
}

function safeVibrate(enabled) {
    if (!enabled || typeof navigator === "undefined" || typeof navigator.vibrate !== "function") {
        return;
    }
    try {
        navigator.vibrate(10);
    } catch (_error) {
        // Silent failure by design.
    }
}

function normalizeNumber(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function assertOptionalElement(value, optionName) {
    if (value == null) {
        return null;
    }
    if (!isElement(value)) {
        throw new Error(`Invalid "${optionName}" option: HTMLElement expected.`);
    }
    return value;
}

function createDropzone(index) {
    const zone = document.createElement("div");
    zone.className = CLASS_DROPZONE;
    zone.dataset.dropIndex = String(index);
    zone.setAttribute("aria-hidden", "true");
    return zone;
}

function createGhost(itemElement, rect) {
    const ghost = itemElement.cloneNode(true);
    ghost.classList.add(CLASS_GHOST);
    ghost.style.position = "fixed";
    ghost.style.top = "0";
    ghost.style.left = "0";
    ghost.style.width = `${rect.width}px`;
    ghost.style.margin = "0";
    ghost.style.pointerEvents = "none";
    ghost.style.zIndex = "9999";
    ghost.style.willChange = "transform";
    document.body.appendChild(ghost);
    return ghost;
}

function createPlaceholder(rect) {
    const placeholder = document.createElement("div");
    placeholder.className = CLASS_PLACEHOLDER;
    placeholder.setAttribute("aria-hidden", "true");
    placeholder.style.height = `${rect.height}px`;
    placeholder.style.boxSizing = "border-box";
    return placeholder;
}

export function init(rawOptions) {
    if (!rawOptions || !isElement(rawOptions.list)) {
        throw new Error('Missing or invalid "list" option. Expected an HTMLElement.');
    }

    const options = {
        list: rawOptions.list,
        toggleButton: assertOptionalElement(rawOptions.toggleButton, "toggleButton"),
        cancelButton: assertOptionalElement(rawOptions.cancelButton, "cancelButton"),
        positionStep: normalizeNumber(rawOptions.positionStep, 2),
        startPosition: normalizeNumber(rawOptions.startPosition, 2),
        vibrateOnTargetChange: Boolean(rawOptions.vibrateOnTargetChange),
        scrollToMovedItemAfterDrop: rawOptions.scrollToMovedItemAfterDrop !== false,
        onStart: typeof rawOptions.onStart === "function" ? rawOptions.onStart : noop,
        onChange: typeof rawOptions.onChange === "function" ? rawOptions.onChange : noop,
        onEnd: typeof rawOptions.onEnd === "function" ? rawOptions.onEnd : noop,
        onCancel: typeof rawOptions.onCancel === "function" ? rawOptions.onCancel : noop,
    };

    const state = {
        mode: MODE_DISABLED,
        destroyed: false,
        snapshot: null,
        pendingPointer: null,
        drag: null,
    };

    const removers = [];
    let pointerWindowListenersAttached = false;

    const addListener = (target, eventName, handler, config) => {
        target.addEventListener(eventName, handler, config);
        removers.push(() => target.removeEventListener(eventName, handler, config));
    };

    function buildPayload({ movedId = null, fromIndex = -1, toIndex = -1, persistentMode = false }) {
        return {
            movedId,
            fromIndex,
            toIndex,
            order: getOrderFromList(options.list),
            persistentMode,
        };
    }

    function captureSnapshot() {
        const items = getDirectItems(options.list);
        const inputValues = new Map();
        const hiddenStates = new Map();
        const compactStates = new Map();

        items.forEach((item) => {
            compactStates.set(item, item.classList.contains(CLASS_COMPACT));

            const positionInput = item.querySelector(SELECTOR_POSITION);
            if (positionInput) {
                inputValues.set(positionInput, positionInput.value);
            }

            item.querySelectorAll(`${SELECTOR_DRAG_VIEW}, ${SELECTOR_NORMAL_VIEW}`).forEach((element) => {
                hiddenStates.set(element, element.hidden);
            });
        });

        return {
            items,
            inputValues,
            hiddenStates,
            compactStates,
            listHadEnabledClass: options.list.classList.contains(CLASS_ENABLED),
        };
    }

    function ensureSnapshot() {
        if (!state.snapshot) {
            state.snapshot = captureSnapshot();
        }
    }

    function restoreSnapshot() {
        if (!state.snapshot) {
            return;
        }

        const snapshot = state.snapshot;
        snapshot.items.forEach((item) => {
            options.list.appendChild(item);
        });

        snapshot.inputValues.forEach((value, input) => {
            input.value = value;
        });

        snapshot.compactStates.forEach((wasCompact, item) => {
            item.classList.toggle(CLASS_COMPACT, wasCompact);
        });

        snapshot.hiddenStates.forEach((wasHidden, element) => {
            element.hidden = wasHidden;
        });

        options.list.classList.toggle(CLASS_ENABLED, snapshot.listHadEnabledClass);
    }

    function applyCompactLayout() {
        options.list.classList.add(CLASS_ENABLED);
        getDirectItems(options.list).forEach((item) => {
            item.classList.add(CLASS_COMPACT);
            item.querySelectorAll(SELECTOR_DRAG_VIEW).forEach((element) => {
                element.hidden = false;
            });
            item.querySelectorAll(SELECTOR_NORMAL_VIEW).forEach((element) => {
                element.hidden = true;
            });
        });
    }

    function applyDefaultLayout() {
        options.list.classList.remove(CLASS_ENABLED);
        getDirectItems(options.list).forEach((item) => {
            item.classList.remove(CLASS_COMPACT);
            item.querySelectorAll(SELECTOR_DRAG_VIEW).forEach((element) => {
                element.hidden = true;
            });
            item.querySelectorAll(SELECTOR_NORMAL_VIEW).forEach((element) => {
                element.hidden = false;
            });
        });
    }

    function isPersistentModeActive() {
        if (state.mode === MODE_ENABLED_PERSISTENT) {
            return true;
        }
        if (state.mode === MODE_DRAGGING && state.drag?.sourceMode === MODE_ENABLED_PERSISTENT) {
            return true;
        }
        return false;
    }

    function syncButtons() {
        const persistent = isPersistentModeActive();

        if (options.toggleButton) {
            options.toggleButton.setAttribute("aria-pressed", persistent ? "true" : "false");
        }

        if (options.cancelButton) {
            options.cancelButton.hidden = !persistent;
        }
    }

    function updatePositionInputs() {
        const items = getDirectItems(options.list);
        items.forEach((item, index) => {
            const input = item.querySelector(SELECTOR_POSITION);
            if (!input) {
                return;
            }
            input.value = String(options.startPosition + index * options.positionStep);
        });
    }

    function cleanupDropzones(dragState = state.drag) {
        if (!dragState) {
            return;
        }
        dragState.dropzones.forEach((zone) => {
            zone.remove();
        });
        dragState.dropzones = [];
    }

    function updateGhostPosition(clientX, clientY) {
        if (!state.drag?.ghost) {
            return;
        }
        const x = clientX - state.drag.offsetX;
        const y = clientY - state.drag.offsetY;
        state.drag.ghost.style.transform = `translate3d(${x}px, ${y}px, 0)`;
    }

    function captureItemRects() {
        const map = new Map();
        getDirectItems(options.list).forEach((item) => {
            map.set(item, item.getBoundingClientRect());
        });
        return map;
    }

    function animateFlip(beforeRects, afterRects) {
        afterRects.forEach((afterRect, element) => {
            const beforeRect = beforeRects.get(element);
            if (!beforeRect) {
                return;
            }
            const deltaY = beforeRect.top - afterRect.top;
            if (Math.abs(deltaY) < 0.5) {
                return;
            }

            element.style.transition = "none";
            element.style.transform = `translateY(${deltaY}px)`;

            window.requestAnimationFrame(() => {
                element.style.transition = "transform 160ms ease";
                element.style.transform = "";

                window.setTimeout(() => {
                    if (!element.style.transform) {
                        element.style.transition = "";
                    }
                }, 180);
            });
        });
    }

    function movePlaceholderToIndex(dropIndex, withAnimation) {
        const dragState = state.drag;
        if (!dragState) {
            return;
        }

        const realItems = getDirectItems(options.list);
        const nextIndex = clamp(dropIndex, 0, realItems.length);
        const beforeRects = withAnimation ? captureItemRects() : null;
        const reference = realItems[nextIndex] || null;

        if (reference) {
            options.list.insertBefore(dragState.placeholder, reference);
        } else {
            options.list.appendChild(dragState.placeholder);
        }

        if (withAnimation && beforeRects) {
            animateFlip(beforeRects, captureItemRects());
        }
    }

    function setActiveDropzone(index, withAnimation) {
        const dragState = state.drag;
        if (!dragState || dragState.dropzones.length === 0) {
            return;
        }

        const bounded = clamp(index, 0, dragState.dropzones.length - 1);
        const changed = bounded !== dragState.activeDropIndex;
        dragState.activeDropIndex = bounded;

        dragState.dropzones.forEach((zone, zoneIndex) => {
            zone.classList.toggle(CLASS_DROPZONE_ACTIVE, zoneIndex === bounded);
        });

        movePlaceholderToIndex(bounded, withAnimation && changed);

        if (changed) {
            safeVibrate(options.vibrateOnTargetChange);
        }
    }

    function renderDropzones() {
        const dragState = state.drag;
        if (!dragState) {
            return;
        }

        cleanupDropzones(dragState);
        const realItems = getDirectItems(options.list);
        const zones = [];

        if (realItems.length === 0) {
            const zone = createDropzone(0);
            options.list.appendChild(zone);
            zones.push(zone);
        } else {
            const firstZone = createDropzone(0);
            options.list.insertBefore(firstZone, realItems[0]);
            zones.push(firstZone);

            realItems.forEach((item, index) => {
                const zone = createDropzone(index + 1);
                options.list.insertBefore(zone, item.nextSibling);
                zones.push(zone);
            });
        }

        dragState.dropzones = zones;
    }

    function nearestDropzoneIndex(pointerY) {
        const dragState = state.drag;
        if (!dragState || dragState.dropzones.length === 0) {
            return 0;
        }

        let minDistance = Number.POSITIVE_INFINITY;
        let closestIndex = dragState.activeDropIndex ?? 0;

        dragState.dropzones.forEach((zone, index) => {
            const rect = zone.getBoundingClientRect();
            const centerY = rect.top + rect.height / 2;
            const distance = Math.abs(pointerY - centerY);
            if (distance < minDistance) {
                minDistance = distance;
                closestIndex = index;
            }
        });

        return closestIndex;
    }

    function updateActiveDropzoneFromPointer(pointerY) {
        setActiveDropzone(nearestDropzoneIndex(pointerY), true);
    }

    function stopAutoScrollLoop() {
        const dragState = state.drag;
        if (!dragState) {
            return;
        }
        if (dragState.autoScrollFrame) {
            window.cancelAnimationFrame(dragState.autoScrollFrame);
            dragState.autoScrollFrame = 0;
        }
    }

    function applyAutoScroll(pointerY) {
        const dragState = state.drag;
        if (!dragState) {
            return false;
        }

        let changed = false;

        const viewportDelta = edgeStep(pointerY, 0, window.innerHeight, AUTOSCROLL_EDGE_PX, AUTOSCROLL_MAX_STEP);
        if (viewportDelta !== 0) {
            const before = window.scrollY;
            window.scrollBy(0, viewportDelta);
            changed = changed || window.scrollY !== before;
        }

        if (dragState.scrollContainer) {
            const rect = dragState.scrollContainer.getBoundingClientRect();
            const containerDelta = edgeStep(pointerY, rect.top, rect.bottom, AUTOSCROLL_EDGE_PX, AUTOSCROLL_MAX_STEP);
            if (containerDelta !== 0) {
                const before = dragState.scrollContainer.scrollTop;
                dragState.scrollContainer.scrollTop += containerDelta;
                changed = changed || dragState.scrollContainer.scrollTop !== before;
            }
        }

        return changed;
    }

    function autoScrollTick() {
        if (state.mode !== MODE_DRAGGING || !state.drag) {
            return;
        }

        const pointerY = state.drag.pointerY;
        const scrolled = applyAutoScroll(pointerY);
        if (scrolled) {
            updateActiveDropzoneFromPointer(pointerY);
            updateGhostPosition(state.drag.pointerX, pointerY);
        }

        state.drag.autoScrollFrame = window.requestAnimationFrame(autoScrollTick);
    }

    function startAutoScrollLoop() {
        if (!state.drag) {
            return;
        }
        stopAutoScrollLoop();
        state.drag.autoScrollFrame = window.requestAnimationFrame(autoScrollTick);
    }

    function insertItemAtIndex(item, index) {
        const realItems = getDirectItems(options.list);
        const bounded = clamp(index, 0, realItems.length);
        const reference = realItems[bounded] || null;
        if (reference) {
            options.list.insertBefore(item, reference);
        } else {
            options.list.appendChild(item);
        }
    }

    function cleanupDragArtifacts() {
        const dragState = state.drag;
        if (!dragState) {
            return;
        }

        stopAutoScrollLoop();
        cleanupDropzones(dragState);

        if (dragState.placeholder.isConnected) {
            dragState.placeholder.remove();
        }

        if (dragState.ghost.isConnected) {
            dragState.ghost.remove();
        }

        dragState.item.classList.remove(CLASS_DRAGGING);
        options.list.classList.remove(CLASS_DRAGGING);
        document.body.style.userSelect = dragState.previousUserSelect;
        state.drag = null;
    }

    function finalizeDrag({ keepPersistentMode }) {
        const dragState = state.drag;
        if (!dragState) {
            return;
        }

        const movedId = getItemId(dragState.item);
        const fromIndex = dragState.fromIndex;
        const toIndex = dragState.activeDropIndex;

        if (dragState.placeholder.isConnected) {
            options.list.insertBefore(dragState.item, dragState.placeholder);
        } else {
            insertItemAtIndex(dragState.item, toIndex);
        }

        cleanupDragArtifacts();
        updatePositionInputs();

        if (!keepPersistentMode) {
            applyDefaultLayout();
            state.mode = MODE_DISABLED;
            state.snapshot = null;
        } else {
            state.mode = MODE_ENABLED_PERSISTENT;
        }

        const payload = buildPayload({
            movedId,
            fromIndex,
            toIndex,
            persistentMode: keepPersistentMode,
        });

        if (fromIndex !== toIndex) {
            callCallback(options.onChange, payload);
        }
        callCallback(options.onEnd, payload);

        if (options.scrollToMovedItemAfterDrop) {
            window.requestAnimationFrame(() => {
                try {
                    dragState.item.scrollIntoView({
                        block: "center",
                        behavior: "smooth",
                    });
                } catch (_error) {
                    // Silent failure.
                }
            });
        }

        syncButtons();
    }

    function cancelCurrentDrag({ emitEnd = true }) {
        const dragState = state.drag;
        if (!dragState) {
            return;
        }

        insertItemAtIndex(dragState.item, dragState.fromIndex);
        cleanupDragArtifacts();

        const keepPersistentMode = dragState.sourceMode === MODE_ENABLED_PERSISTENT;
        if (!keepPersistentMode) {
            applyDefaultLayout();
            state.mode = MODE_DISABLED;
            state.snapshot = null;
        } else {
            state.mode = MODE_ENABLED_PERSISTENT;
        }

        if (emitEnd) {
            callCallback(
                options.onEnd,
                buildPayload({
                    movedId: getItemId(dragState.item),
                    fromIndex: dragState.fromIndex,
                    toIndex: dragState.fromIndex,
                    persistentMode: keepPersistentMode,
                })
            );
        }

        syncButtons();
    }

    function beginPersistentMode() {
        if (state.mode === MODE_ENABLED_PERSISTENT) {
            return;
        }

        if (state.mode === MODE_DRAGGING && state.drag) {
            state.drag.sourceMode = MODE_ENABLED_PERSISTENT;
            syncButtons();
            return;
        }

        ensureSnapshot();
        applyCompactLayout();
        state.mode = MODE_ENABLED_PERSISTENT;
        syncButtons();
    }

    function beginTemporaryMode() {
        if (state.mode !== MODE_DISABLED) {
            return;
        }
        ensureSnapshot();
        applyCompactLayout();
        state.mode = MODE_ENABLED_TEMPORARY;
        syncButtons();
    }

    function clearPendingPointer() {
        const pending = state.pendingPointer;
        if (pending?.handle && typeof pending.handle.releasePointerCapture === "function") {
            try {
                if (pending.handle.hasPointerCapture(pending.pointerId)) {
                    pending.handle.releasePointerCapture(pending.pointerId);
                }
            } catch (_error) {
                // Capture is optional.
            }
        }

        state.pendingPointer = null;
        if (pointerWindowListenersAttached) {
            window.removeEventListener("pointermove", onWindowPointerMove);
            window.removeEventListener("pointerup", onWindowPointerUp);
            window.removeEventListener("pointercancel", onWindowPointerCancel);
            pointerWindowListenersAttached = false;
        }
    }

    function startDrag(pointerEvent) {
        const pending = state.pendingPointer;
        if (!pending) {
            return;
        }

        if (state.mode === MODE_DISABLED) {
            beginTemporaryMode();
        }

        if (state.mode !== MODE_ENABLED_PERSISTENT && state.mode !== MODE_ENABLED_TEMPORARY) {
            return;
        }

        const item = pending.item;
        const currentItems = getDirectItems(options.list);
        const fromIndex = currentItems.indexOf(item);
        if (fromIndex < 0) {
            return;
        }

        const rect = item.getBoundingClientRect();
        const placeholder = createPlaceholder(rect);
        const ghost = createGhost(item, rect);

        options.list.insertBefore(placeholder, item);
        item.remove();

        state.drag = {
            pointerId: pending.pointerId,
            sourceMode: state.mode,
            item,
            ghost,
            placeholder,
            fromIndex,
            activeDropIndex: fromIndex,
            pointerX: pointerEvent.clientX,
            pointerY: pointerEvent.clientY,
            offsetX: pointerEvent.clientX - rect.left,
            offsetY: pointerEvent.clientY - rect.top,
            dropzones: [],
            scrollContainer: findScrollableAncestor(options.list),
            autoScrollFrame: 0,
            previousUserSelect: document.body.style.userSelect || "",
        };

        state.mode = MODE_DRAGGING;
        options.list.classList.add(CLASS_DRAGGING);
        item.classList.add(CLASS_DRAGGING);
        document.body.style.userSelect = "none";

        renderDropzones();
        setActiveDropzone(fromIndex, false);
        updateGhostPosition(pointerEvent.clientX, pointerEvent.clientY);
        startAutoScrollLoop();

        callCallback(
            options.onStart,
            buildPayload({
                movedId: getItemId(item),
                fromIndex,
                toIndex: fromIndex,
                persistentMode: state.drag.sourceMode === MODE_ENABLED_PERSISTENT,
            })
        );
    }

    function enable() {
        if (state.destroyed) {
            return;
        }
        beginPersistentMode();
    }

    function disable() {
        if (state.destroyed || state.mode === MODE_DISABLED) {
            return;
        }

        if (state.mode === MODE_DRAGGING) {
            finalizeDrag({ keepPersistentMode: false });
            return;
        }

        applyDefaultLayout();
        state.mode = MODE_DISABLED;
        state.snapshot = null;
        syncButtons();
    }

    function cancel() {
        if (state.destroyed || state.mode === MODE_DISABLED) {
            return;
        }

        if (state.mode === MODE_DRAGGING) {
            cleanupDragArtifacts();
        }

        restoreSnapshot();
        options.list.classList.remove(CLASS_DRAGGING);
        state.mode = MODE_DISABLED;
        state.snapshot = null;
        syncButtons();

        callCallback(
            options.onCancel,
            buildPayload({
                movedId: null,
                fromIndex: -1,
                toIndex: -1,
                persistentMode: false,
            })
        );
    }

    function getOrder() {
        return getOrderFromList(options.list);
    }

    function destroy() {
        if (state.destroyed) {
            return;
        }

        if (state.mode === MODE_DRAGGING) {
            cancelCurrentDrag({ emitEnd: false });
        } else if (state.mode !== MODE_DISABLED) {
            applyDefaultLayout();
        }

        clearPendingPointer();
        removers.splice(0).forEach((remove) => remove());

        state.snapshot = null;
        state.mode = MODE_DISABLED;
        state.destroyed = true;
        syncButtons();
    }

    function onWindowPointerMove(event) {
        const pending = state.pendingPointer;
        if (!pending || event.pointerId !== pending.pointerId) {
            return;
        }

        pending.lastX = event.clientX;
        pending.lastY = event.clientY;

        if (state.mode !== MODE_DRAGGING) {
            const dx = pending.lastX - pending.startX;
            const dy = pending.lastY - pending.startY;
            const movedDistance = Math.hypot(dx, dy);
            if (movedDistance >= POINTER_START_THRESHOLD) {
                startDrag(event);
            }
        }

        if (state.mode === MODE_DRAGGING && state.drag && event.pointerId === state.drag.pointerId) {
            state.drag.pointerX = event.clientX;
            state.drag.pointerY = event.clientY;
            updateGhostPosition(event.clientX, event.clientY);
            updateActiveDropzoneFromPointer(event.clientY);
            event.preventDefault();
        }
    }

    function onWindowPointerUp(event) {
        const pending = state.pendingPointer;
        if (!pending || event.pointerId !== pending.pointerId) {
            return;
        }

        if (state.mode === MODE_DRAGGING && state.drag && event.pointerId === state.drag.pointerId) {
            state.drag.pointerX = event.clientX;
            state.drag.pointerY = event.clientY;
            const keepPersistentMode = state.drag.sourceMode === MODE_ENABLED_PERSISTENT;
            finalizeDrag({ keepPersistentMode });
        }

        clearPendingPointer();
    }

    function onWindowPointerCancel(event) {
        const pending = state.pendingPointer;
        if (!pending || event.pointerId !== pending.pointerId) {
            return;
        }

        if (state.mode === MODE_DRAGGING && state.drag && event.pointerId === state.drag.pointerId) {
            cancelCurrentDrag({ emitEnd: true });
        }

        clearPendingPointer();
    }

    function onPointerDown(event) {
        if (state.destroyed || state.mode === MODE_DRAGGING) {
            return;
        }

        if (event.button !== undefined && event.button !== 0) {
            return;
        }

        const handle = event.target.closest(SELECTOR_HANDLE);
        if (!handle) {
            return;
        }

        const item = handle.closest(SELECTOR_ITEM);
        if (!item || item.parentElement !== options.list) {
            return;
        }

        state.pendingPointer = {
            pointerId: event.pointerId,
            handle,
            item,
            startX: event.clientX,
            startY: event.clientY,
            lastX: event.clientX,
            lastY: event.clientY,
        };

        if (typeof handle.setPointerCapture === "function") {
            try {
                handle.setPointerCapture(event.pointerId);
            } catch (_error) {
                // Ignore optional capture errors.
            }
        }

        if (!pointerWindowListenersAttached) {
            window.addEventListener("pointermove", onWindowPointerMove, { passive: false });
            window.addEventListener("pointerup", onWindowPointerUp);
            window.addEventListener("pointercancel", onWindowPointerCancel);
            pointerWindowListenersAttached = true;
        }

        event.preventDefault();
    }

    function onKeyDown(event) {
        if (event.key !== "Escape" || state.destroyed) {
            return;
        }

        if (state.mode === MODE_DRAGGING) {
            event.preventDefault();
            cancelCurrentDrag({ emitEnd: true });
            return;
        }

        if (state.mode === MODE_ENABLED_PERSISTENT) {
            event.preventDefault();
            cancel();
        }
    }

    function onToggleClick(event) {
        event.preventDefault();
        if (state.destroyed || state.mode === MODE_DRAGGING) {
            return;
        }

        if (isPersistentModeActive()) {
            disable();
        } else {
            enable();
        }
    }

    function onCancelClick(event) {
        event.preventDefault();
        if (state.destroyed) {
            return;
        }
        cancel();
    }

    addListener(options.list, "pointerdown", onPointerDown);
    addListener(document, "keydown", onKeyDown);

    if (options.toggleButton) {
        addListener(options.toggleButton, "click", onToggleClick);
    }

    if (options.cancelButton) {
        addListener(options.cancelButton, "click", onCancelClick);
    }

    syncButtons();

    return {
        enable,
        disable,
        cancel,
        getOrder,
        destroy,
    };
}
