/* global window, document */
window.LSSUI = window.LSSUI || {};

(function attachLSSUI(ns) {
  "use strict";

  // --- Utils
  function throttle(fn, wait) {
    let t = 0;
    return function (...args) {
      const now = Date.now();
      if (now - t >= wait) {
        t = now; fn.apply(this, args);
      }
    };
  }

  function serializeIds(container, itemSelector, attr) {
    return Array.from(container.querySelectorAll(itemSelector))
      .map(el => el.getAttribute(attr))
      .filter(Boolean)
      .join(",");
  }

  // --- Sortable (drag, touch, keyboard)
  ns.initSortableList = function initSortableList(container, options = {}) {
    if (!container) return;
    const {
      itemSelector = ".dnd-item",
      handleSelector = ".dnd-handle",
      idAttribute = "data-asid",
      hiddenInput = null,             // DOM node input[type=hidden]
      onOrderChange = null,           // (ids: string) => void
      dragClass = "dragging",
      indicatorClass = "drop-indicator",
      indexSelector = ".dnd-index",
    } = options;

    const indicator = document.createElement("div");
    indicator.className = indicatorClass;

    function refreshIndices() {
      Array.from(container.querySelectorAll(`${itemSelector} ${indexSelector}`))
        .forEach((el, i) => { el.textContent = String(i + 1); });
    }

    function updateHidden() {
      if (!hiddenInput) return;
      const ids = serializeIds(container, itemSelector, idAttribute);
      hiddenInput.value = ids;
      if (typeof onOrderChange === "function") onOrderChange(ids);
    }

    function getDragAfterElement(y) {
      const els = [...container.querySelectorAll(`${itemSelector}:not(.${dragClass})`)];
      return els.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) return { offset, element: child };
        return closest;
      }, { offset: Number.NEGATIVE_INFINITY }).element;
    }

    // Pointer-based DnD (works mouse + touch)
    let draggingEl = null;

    function onPointerDown(e) {
      const handle = e.target.closest(handleSelector);
      if (!handle) return;
      const item = handle.closest(itemSelector);
      if (!item) return;

      draggingEl = item;
      draggingEl.classList.add(dragClass);
      draggingEl.setPointerCapture?.(e.pointerId);
      e.preventDefault();
    }

    const onPointerMove = throttle((e) => {
      if (!draggingEl) return;
      const after = getDragAfterElement(e.clientY);
      if (after == null) {
        container.appendChild(indicator);
      } else {
        container.insertBefore(indicator, after);
      }
    }, 16); // ~60fps

    function onPointerUp(e) {
      if (!draggingEl) return;
      draggingEl.classList.remove(dragClass);
      if (indicator.parentNode) {
        container.insertBefore(draggingEl, indicator);
        indicator.parentNode.removeChild(indicator);
      }
      draggingEl.releasePointerCapture?.(e.pointerId);
      draggingEl = null;
      refreshIndices();
      updateHidden();
    }

    container.addEventListener("pointerdown", onPointerDown);
    container.addEventListener("pointermove", onPointerMove);
    container.addEventListener("pointerup", onPointerUp);
    container.addEventListener("pointercancel", onPointerUp);
    container.addEventListener("pointerleave", (e) => { if (draggingEl) onPointerUp(e); });

    // Keyboard fallback (↑/↓)
    container.addEventListener("keydown", (e) => {
      const item = e.target.closest(itemSelector);
      if (!item) return;
      if (e.key === "ArrowUp") {
        e.preventDefault();
        const prev = item.previousElementSibling;
        if (prev) container.insertBefore(item, prev);
        refreshIndices(); updateHidden();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        const next = item.nextElementSibling;
        if (next) container.insertBefore(next, item);
        refreshIndices(); updateHidden();
      }
    });

    // First run
    refreshIndices();
    updateHidden();
  };

  // --- Song picker (réutilisable)
  ns.initSongPicker = function initSongPicker(cfg) {
    const {
      searchInput,           // DOM input
      listContainer,         // DOM ul/ol
      addBtnLabel = "Add",
      allSongs = [],         // [{id, name}]
      maxRender = 100,
      outIdsInput,           // DOM hidden (pipe-separated)
      outNamesInput,         // DOM text (readOnly, ' / '-sep)
      minQuery = 3,
    } = cfg;

    if (!searchInput || !listContainer) return;

    function render(query = "") {
      listContainer.innerHTML = "";
      const q = query.trim().toLowerCase();
      const subset = q.length >= minQuery
        ? allSongs.filter(s => s.name.toLowerCase().includes(q))
        : allSongs.slice(0, maxRender);

      subset.forEach(s => {
        const li = document.createElement("li");
        li.textContent = s.name + " — ";
        const a = document.createElement("a");
        a.href = "javascript:void(0);";
        a.textContent = addBtnLabel;
        a.addEventListener("click", () => addSong(s.id, s.name));
        li.appendChild(a);
        listContainer.appendChild(li);
      });
    }

    function addSong(id, name) {
      const ids = outIdsInput?.value ? outIdsInput.value.split("|") : [];
      const names = outNamesInput?.value ? outNamesInput.value.split(" / ") : [];
      ids.push(String(id)); names.push(name);
      if (outIdsInput) outIdsInput.value = ids.join("|");
      if (outNamesInput) outNamesInput.value = names.join(" / ");
    }

    searchInput.addEventListener("input", (e) => render(e.target.value));
    render("");
  };
})(window.LSSUI);
