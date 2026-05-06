(() => {
    const i18n = window.LSS_ANIMATION_I18N || {};
    const label = (key) => String(i18n[key] || "");
    const normalizeSearch = (value) => {
        return String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .trim();
    };

    const playlist = document.querySelector("[data-animation-playlist]");
    const orderedMixInput = document.querySelector("[data-animation-ordered-mix]");

    const updateOrderedMix = () => {
        if (!playlist || !orderedMixInput) {
            return;
        }
        const tokens = Array.from(playlist.querySelectorAll("[data-reorder-item]"))
            .map((item) => String(item.getAttribute("data-token") || "").trim())
            .filter((token) => token.length > 0);
        orderedMixInput.value = tokens.join("|");

        const emptyPlaceholder = playlist.querySelector("[data-animation-playlist-empty]");
        if (emptyPlaceholder) {
            emptyPlaceholder.hidden = tokens.length > 0;
        }
    };

    const createPlaylistItem = (songId, songTitle) => {
        const item = document.createElement("article");
        item.className = "animation-playlist-item";
        item.setAttribute("data-reorder-item", "");

        const token = `sid:${songId}`;
        const uniqueId = `${token}:${Date.now()}:${Math.floor(Math.random() * 100000)}`;
        item.setAttribute("data-id", uniqueId);
        item.setAttribute("data-token", token);

        const compact = document.createElement("div");
        compact.className = "animation-playlist-item-compact";
        compact.setAttribute("data-reorder-drag-view", "");
        compact.hidden = true;

        const compactHandle = document.createElement("button");
        compactHandle.type = "button";
        compactHandle.className = "animation-reorder-handle";
        compactHandle.setAttribute("data-reorder-handle", "");
        compactHandle.textContent = "☰";

        const compactTitle = document.createElement("strong");
        compactTitle.textContent = songTitle;

        compact.append(compactHandle, compactTitle);

        const full = document.createElement("div");
        full.className = "animation-playlist-item-full";
        full.setAttribute("data-reorder-normal-view", "");

        const header = document.createElement("div");
        header.className = "animation-playlist-item-head";

        const fullHandle = document.createElement("button");
        fullHandle.type = "button";
        fullHandle.className = "animation-reorder-handle";
        fullHandle.setAttribute("data-reorder-handle", "");
        fullHandle.textContent = "☰";

        const fullTitle = document.createElement("strong");
        fullTitle.textContent = songTitle;
        header.append(fullHandle, fullTitle);

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "animation-secondary-action";
        removeButton.setAttribute("data-animation-remove-item", "");
        removeButton.textContent = label("removeFromPlaylist");

        const positionInput = document.createElement("input");
        positionInput.type = "hidden";
        positionInput.setAttribute("data-reorder-position", "");
        positionInput.value = "0";

        full.append(header, removeButton, positionInput);
        item.append(compact, full);
        return item;
    };

    if (playlist) {
        playlist.addEventListener("click", (event) => {
            const removeButton = event.target.closest("[data-animation-remove-item]");
            if (!removeButton) {
                return;
            }
            const item = removeButton.closest("[data-reorder-item]");
            if (!item) {
                return;
            }
            item.remove();
            updateOrderedMix();
        });

        document.querySelectorAll("[data-add-song-button]").forEach((button) => {
            button.addEventListener("click", () => {
                const songId = button.getAttribute("data-song-id");
                const songTitle = button.getAttribute("data-song-title") || "";
                if (!songId) {
                    return;
                }
                playlist.appendChild(createPlaylistItem(songId, songTitle));
                updateOrderedMix();
            });
        });

        updateOrderedMix();
    }

    const localSearchInput = document.querySelector("[data-animation-song-local-search]");
    const candidateCards = Array.from(document.querySelectorAll("[data-animation-song-candidate]"));
    if (localSearchInput && candidateCards.length) {
        const applyLocalFilter = () => {
            const query = normalizeSearch(localSearchInput.value);
            const shouldFilter = query.length >= 2;
            candidateCards.forEach((card) => {
                const haystack = normalizeSearch(card.getAttribute("data-search-text"));
                const isVisible = !shouldFilter || haystack.includes(query);
                card.style.display = isVisible ? "" : "none";
            });
        };

        localSearchInput.addEventListener("input", applyLocalFilter);
        applyLocalFilter();
    }

    window.LSSAnimationPage = {
        updateOrderedMix,
    };
})();
