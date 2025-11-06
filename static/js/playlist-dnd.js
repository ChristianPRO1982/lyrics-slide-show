/* global document, window */
(function () {
  "use strict";

  function $(sel, root = document) { return root.querySelector(sel); }
  function $all(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }
  function joinPipe(arr) { return arr.join("|"); }
  function splitPipe(v) { return v ? v.split("|").filter(Boolean) : []; }

  // Existing items only (server V1 expects these ASIDs)
  function serializeExistingOrder(listEl) {
    return $all(".dnd-item", listEl)
      .filter(li => !li.classList.contains("is-deleted"))
      .filter(li => li.dataset.kind !== "new")
      .map(li => li.getAttribute("data-asid"))
      .filter(Boolean)
      .join(",");
  }

  function renumberAll(listEl) {
    $all(".dnd-item .dnd-index", listEl)
      .forEach((el, i) => { el.textContent = String(i + 1); });
  }

  function mkHiddenDelete(asid) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = `box_delete_song_${asid}`;
    input.value = "on";
    input.dataset.deleteFor = asid;
    return input;
  }

  function removeHiddenDelete(formEl, asid) {
    const el = formEl.querySelector(`input[data-delete-for="${asid}"]`);
    if (el) el.remove();
  }

  function createNewDraggableItem(songId, title) {
    const li = document.createElement("li");
    li.className = "L_DIV_BORDER dnd-item";
    li.draggable = true;
    li.dataset.kind = "new";
    li.dataset.songId = String(songId);

    const left = document.createElement("span");
    left.className = "dnd-handle-num";

    const handle = document.createElement("span");
    handle.className = "dnd-handle";
    handle.textContent = "⠿";

    const idx = document.createElement("span");
    idx.className = "dnd-index";

    const titleEl = document.createElement("span");
    titleEl.className = "dnd-title";
    titleEl.textContent = title;

    const del = document.createElement("button");
    del.type = "button";
    del.className = "dnd-x";
    del.setAttribute("aria-label", "Remove");
    del.textContent = "×";

    left.append(handle, idx);
    li.append(left, titleEl, del);
    return li;
  }

  function updateNewSongsInput(listEl, inputEl) {
    if (!inputEl) return;
    const ids = $all(".dnd-item", listEl)
      .filter(li => li.dataset.kind === "new")
      .filter(li => !li.classList.contains("is-deleted"))
      .map(li => li.dataset.songId)
      .filter(Boolean);
    inputEl.value = joinPipe(ids);
  }

  function initPlaylistDnd(opts) {
    const {
      sourceList,            // #add-songs
      targetList,            // #dndList
      formEl,                // <form>
      inputOrderedIds,       // #ordered_ids
      inputNewSongs,         // #txt_new_songs
    } = opts;

    if (!sourceList || !targetList || !formEl || !inputOrderedIds || !inputNewSongs) return;

    // track whether the drag was initiated from the handle so we do not start
    // dragging when the user simply clicks the row to focus / select text.
    let activeHandleItem = null;
    targetList.addEventListener("pointerdown", (e) => {
      const handle = e.target.closest(".dnd-handle");
      activeHandleItem = handle ? handle.closest(".dnd-item") : null;
    });
    window.addEventListener("pointerup", () => { activeHandleItem = null; });

    // Delete (×)
    targetList.addEventListener("click", (e) => {
      const btn = e.target.closest(".dnd-x");
      if (!btn) return;
      const li = btn.closest(".dnd-item");
      if (!li) return;

      const shouldDelete = !li.classList.contains("is-deleted");
      if (shouldDelete) {
        li.classList.add("is-deleted", "strike");
      } else {
        li.classList.remove("is-deleted", "strike");
      }

      if (li.dataset.kind === "new") {
        updateNewSongsInput(targetList, inputNewSongs);
      } else {
        const asid = li.getAttribute("data-asid");
        if (!asid) return;
        const delHiddenName = `box_delete_song_${asid}`;
        const existingHidden = formEl.querySelector(`input[name="${delHiddenName}"]`);
        if (shouldDelete) {
          if (!existingHidden) formEl.appendChild(mkHiddenDelete(asid));
        } else {
          existingHidden?.remove();
        }
      }

      inputOrderedIds.value = serializeExistingOrder(targetList);
      renumberAll(targetList);
      updateNewSongsInput(targetList, inputNewSongs);
    });

    // Drag & drop (all items participate)
    let draggingEl = null;
    let indicator = null;

    function ensureIndicator() {
      if (!indicator) {
        indicator = document.createElement("div");
        indicator.className = "drop-indicator";
      }
      return indicator;
    }

    // Limit drag start to the handle for better UX (optional: remove the guard if you want full-row drag)
    targetList.addEventListener("dragstart", (e) => {
      const li = e.target.closest(".dnd-item");
      if (!li) return;
      if (activeHandleItem && activeHandleItem !== li) {
        activeHandleItem = null;
        e.preventDefault();
        return;
      }
      if (!activeHandleItem) {
        e.preventDefault();
        return;
      }
      draggingEl = li;
      activeHandleItem = null;
      li.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", li.dataset.kind === "new"
        ? (li.dataset.songId || "")
        : (li.getAttribute("data-asid") || ""));
    });

    targetList.addEventListener("dragend", () => {
      if (draggingEl) draggingEl.classList.remove("dragging");
      if (indicator && indicator.parentNode) indicator.parentNode.removeChild(indicator);
      draggingEl = null;
      inputOrderedIds.value = serializeExistingOrder(targetList);
      renumberAll(targetList);
      updateNewSongsInput(targetList, inputNewSongs);
    });

    function getAfter(container, y) {
      const els = $all(".dnd-item:not(.dragging)", container);
      return els.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) return { offset, element: child };
        return closest;
      }, { offset: Number.NEGATIVE_INFINITY, element: null }).element;
    }

    targetList.addEventListener("dragover", (e) => {
      e.preventDefault();
      if (!draggingEl) return;
      const y = e.clientY;
      const after = getAfter(targetList, y);
      const ind = ensureIndicator();
      if (after == null) targetList.appendChild(ind);
      else targetList.insertBefore(ind, after);
    });

    targetList.addEventListener("drop", (e) => {
      e.preventDefault();
      if (!draggingEl) {
        // Source → Target drop (copy)
        try {
          const data = JSON.parse(e.dataTransfer.getData("text/plain") || "{}");
          if (data && data.type === "song" && data.id) stageNew(String(data.id), data.title);
        } catch (_err) { /* noop */ }
        return;
      }
      const y = e.clientY;
      const after = getAfter(targetList, y);
      if (after == null) targetList.appendChild(draggingEl);
      else targetList.insertBefore(draggingEl, after);
      updateNewSongsInput(targetList, inputNewSongs);
    });

    // Add: double-click source or drag from source
    sourceList.addEventListener("dblclick", (e) => {
      const li = e.target.closest(".dnd-item");
      if (!li) return;
      const sid = li.getAttribute("data-asid");
      const title = li.textContent.trim();
      stageNew(sid, title);
    });

    sourceList.addEventListener("dragstart", (e) => {
      const li = e.target.closest(".dnd-item");
      if (!li) return;
      e.dataTransfer.setData("text/plain", JSON.stringify({
        type: "song",
        id: li.getAttribute("data-asid"),
        title: li.textContent.trim()
      }));
      e.dataTransfer.effectAllowed = "copy";
    });

    targetList.addEventListener("dragover", (e) => { e.preventDefault(); }); // allow drop from source

    function stageNew(songId, title) {
      const ids = splitPipe(inputNewSongs.value);
      const sid = String(songId);
      if (!ids.includes(sid)) ids.push(sid);
      inputNewSongs.value = joinPipe(ids);

      const li = createNewDraggableItem(songId, title);
      li.tabIndex = 0;
      targetList.appendChild(li);

      inputOrderedIds.value = serializeExistingOrder(targetList);
      renumberAll(targetList);
      updateNewSongsInput(targetList, inputNewSongs);
    }

    // Keyboard fallback
    targetList.addEventListener("keydown", (e) => {
      const li = e.target.closest(".dnd-item");
      if (!li) return;
      if (e.key === "ArrowUp") {
        e.preventDefault();
        const prev = li.previousElementSibling;
        if (prev) targetList.insertBefore(li, prev);
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        const next = li.nextElementSibling;
        if (next) targetList.insertBefore(next, li);
      }
      inputOrderedIds.value = serializeExistingOrder(targetList);
      renumberAll(targetList);
      updateNewSongsInput(targetList, inputNewSongs);
    });

    // Focusable items
    $all(".dnd-item", targetList).forEach(li => { li.tabIndex = 0; });

    // Initial state
    inputOrderedIds.value = serializeExistingOrder(targetList);
    renumberAll(targetList);
    updateNewSongsInput(targetList, inputNewSongs);
  }

  window.initPlaylistDnd = initPlaylistDnd;
})();
