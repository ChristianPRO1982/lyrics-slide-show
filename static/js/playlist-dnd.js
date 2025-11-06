/* global document, window */
(function () {
  "use strict";

  function $(sel, root = document) { return root.querySelector(sel); }
  function $all(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

  function joinPipe(arr) { return arr.join("|"); }
  function splitPipe(v) { return v ? v.split("|").filter(Boolean) : []; }

  function serializeExistingOrder(listEl) {
    // On ne prend PAS les éléments "temp" (ajouts en attente)
    return $all(".dnd-item:not(.is-temp)", listEl)
      .map(li => li.getAttribute("data-asid"))
      .filter(Boolean)
      .join(",");
  }

  function renumber(listEl) {
    $all(".dnd-item:not(.is-temp) .dnd-index", listEl)
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

  function createExistingItemDom(asid, title) {
    const li = document.createElement("li");
    li.className = "dnd-item";
    li.setAttribute("data-asid", asid);
    li.draggable = true;

    const handle = document.createElement("span");
    handle.className = "dnd-handle";
    handle.textContent = "⠿";

    const idx = document.createElement("span");
    idx.className = "dnd-index";
    idx.style.width = "2ch";
    idx.style.textAlign = "right";

    const divTitle = document.createElement("div");
    divTitle.className = "dnd-title";
    divTitle.textContent = title;

    const del = document.createElement("button");
    del.type = "button";
    del.className = "dnd-x";
    del.setAttribute("aria-label", "Supprimer");
    del.textContent = "×";

    li.append(handle, idx, divTitle, del);
    return li;
  }

  function createTempItemDom(songId, title) {
    const li = document.createElement("li");
    li.className = "dnd-item is-temp";
    li.dataset.songId = String(songId);
    li.draggable = false; // staging non réordonnable V1
    const badge = document.createElement("span");
    badge.textContent = "new";
    badge.style.fontSize = ".75rem";
    badge.style.border = "1px solid #bbb";
    badge.style.borderRadius = "4px";
    badge.style.padding = "0 .25rem";
    const divTitle = document.createElement("div");
    divTitle.className = "dnd-title";
    divTitle.textContent = title;
    const del = document.createElement("button");
    del.type = "button"; del.className = "dnd-x"; del.textContent = "×";
    del.setAttribute("aria-label", "Retirer (ajout en attente)");
    li.append(badge, divTitle, del);
    return li;
  }

  function initPlaylistDnd(opts) {
    const {
      sourceList,      // ex: document.getElementById('add-songs')
      targetList,      // ex: document.getElementById('dndList')
      formEl,          // ex: targetList.closest('form')
      inputOrderedIds, // ex: document.getElementById('ordered_ids')
      inputNewSongs,   // ex: document.getElementById('txt_new_songs')
    } = opts;

    if (!sourceList || !targetList || !formEl || !inputOrderedIds || !inputNewSongs) return;

    // --- 1) Supprimer (×) un item existant
    targetList.addEventListener("click", (e) => {
      const btn = e.target.closest(".dnd-x");
      if (!btn) return;
      const li = btn.closest(".dnd-item");
      if (!li) return;

      if (li.classList.contains("is-temp")) {
        // retirer l'ajout en attente
        const sid = li.dataset.songId;
        const ids = splitPipe(inputNewSongs.value);
        const idx = ids.indexOf(String(sid));
        if (idx >= 0) ids.splice(idx, 1);
        inputNewSongs.value = joinPipe(ids);
        li.remove();
        return;
      }

      // marquer la suppression d'un item existant (animation_song_id)
      const asid = li.getAttribute("data-asid");
      if (!asid) return;
      // si déjà en suppression: annuler
      const isStriked = li.classList.toggle("strike");
      if (isStriked) {
        // Ajout d'un hidden pour suppression
        formEl.appendChild(mkHiddenDelete(asid));
      } else {
        // Retrait du hidden suppression
        removeHiddenDelete(formEl, asid);
      }
    });

    // --- 2) Drag & drop: réordonner les items existants
    let draggingEl = null;
    let indicator = null;

    function ensureIndicator() {
      if (!indicator) {
        indicator = document.createElement("div");
        indicator.className = "drop-indicator";
      }
      return indicator;
    }

    targetList.addEventListener("dragstart", (e) => {
      const li = e.target.closest(".dnd-item");
      if (!li || li.classList.contains("is-temp")) return; // on ne déplace pas les temp
      draggingEl = li;
      li.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", li.getAttribute("data-asid") || "");
    });

    targetList.addEventListener("dragend", () => {
      if (draggingEl) draggingEl.classList.remove("dragging");
      if (indicator && indicator.parentNode) indicator.parentNode.removeChild(indicator);
      draggingEl = null;
      // serialize
      inputOrderedIds.value = serializeExistingOrder(targetList);
      renumber(targetList);
    });

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
      if (!draggingEl) return;
      const y = e.clientY;
      const after = getAfter(targetList, y);
      if (after == null) targetList.appendChild(draggingEl);
      else targetList.insertBefore(draggingEl, after);
    });

    function getAfter(container, y) {
      const els = $all(".dnd-item:not(.is-temp):not(.dragging)", container);
      return els.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) return { offset, element: child };
        return closest;
      }, { offset: Number.NEGATIVE_INFINITY, element: null }).element;
    }

    // --- 3) Ajout: double-clic ou drag depuis la source
    // a) double-clic source → ajoute en fin (staging)
    sourceList.addEventListener("dblclick", (e) => {
      const li = e.target.closest(".dnd-item");
      if (!li) return;
      const sid = li.getAttribute("data-asid");
      const title = li.textContent.trim();
      stageNew(sid, title);
    });

    // b) DnD source → target (ajout en fin)
    sourceList.addEventListener("dragstart", (e) => {
      const li = e.target.closest(".dnd-item");
      if (!li) return;
      e.dataTransfer.setData("text/plain", JSON.stringify({
        type: "song", id: li.getAttribute("data-asid"), title: li.textContent.trim()
      }));
      e.dataTransfer.effectAllowed = "copy";
    });

    targetList.addEventListener("dragover", (e) => {
      // autoriser le drop depuis la source même si pas en mode reorder
      e.preventDefault();
    });

    targetList.addEventListener("drop", (e) => {
      // Cas d'un drop depuis la source
      try {
        const data = JSON.parse(e.dataTransfer.getData("text/plain") || "{}");
        if (data && data.type === "song" && data.id) {
          e.preventDefault();
          stageNew(data.id, data.title);
        }
      } catch (_err) { /* noop */ }
    });

    function stageNew(songId, title) {
      const ids = splitPipe(inputNewSongs.value);
      ids.push(String(songId));
      inputNewSongs.value = joinPipe(ids);

      // visuel: item "temp" ajouté en fin
      const temp = createTempItemDom(songId, title);
      targetList.appendChild(temp);
      // on ne touche PAS à ordered_ids (les temp n'entrent pas dedans)
    }

    // --- 4) Init ordre existant
    inputOrderedIds.value = serializeExistingOrder(targetList);
    renumber(targetList);

    // --- 5) Accessibilité : handle clavier basique
    targetList.addEventListener("keydown", (e) => {
      const li = e.target.closest(".dnd-item");
      if (!li || li.classList.contains("is-temp")) return;
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
      renumber(targetList);
    });

    // Rendre focusable
    $all(".dnd-item", targetList).forEach(li => { li.tabIndex = 0; });
  }

  // Expose
  window.initPlaylistDnd = initPlaylistDnd;
})();
