(() => {
    const root = document.querySelector("[data-lyrics-master-root]");
    if (!(root instanceof HTMLElement)) {
        return;
    }

    const payloadNode = document.getElementById("lss-lyrics-runtime-payload");
    if (!(payloadNode instanceof HTMLScriptElement) || !payloadNode.textContent) {
        return;
    }

    let payload = null;
    try {
        payload = JSON.parse(payloadNode.textContent);
    } catch (_error) {
        return;
    }
    if (!payload || !Array.isArray(payload.slides) || !Array.isArray(payload.songs)) {
        return;
    }

    const i18n = window.LSS_LYRICS_I18N || {};
    const label = (key) => String(i18n[key] || "");

    const animationId = Number.parseInt(String(root.getAttribute("data-animation-id") || ""), 10) || 0;
    const displayUrlBase = String(root.getAttribute("data-display-url-base") || "").trim();
    const defaultSessionId = String(root.getAttribute("data-display-session-id") || "").trim();

    const slides = payload.slides;
    const songs = payload.songs;
    const publicUrl = String(payload.publicUrl || "");
    const qrCodePngBase64 = String(payload.qrCodePngBase64 || "");
    const backgroundUrls = Array.isArray(payload.backgroundUrls) ? payload.backgroundUrls.map((url) => String(url || "").trim()).filter(Boolean) : [];

    const stateStorageKey = `lss-lyrics-master-state:${animationId}`;
    const bridgeStorageKeyPrefix = "lss-lyrics-bridge:";

    const songTitleNode = document.querySelector("[data-lyrics-current-song-title]");
    const slideLabelNode = document.querySelector("[data-lyrics-current-slide-label]");
    const displaySessionNode = document.querySelector("[data-lyrics-display-session]");
    const prevSongTitleNode = document.querySelector("[data-lyrics-prev-song-title]");
    const nextSongTitleNode = document.querySelector("[data-lyrics-next-song-title]");
    const chorusVisibilityNode = document.querySelector("[data-lyrics-chorus-visibility-state]");
    const scrollModeNode = document.querySelector("[data-lyrics-scroll-mode-state]");
    const previewCurrentLabelNode = document.querySelector("[data-lyrics-current-label]");
    const previewCurrentTextNode = document.querySelector("[data-lyrics-current-text]");
    const previewNextLabelNode = document.querySelector("[data-lyrics-next-label]");
    const previewNextTextNode = document.querySelector("[data-lyrics-next-text]");

    const messageBox = window.LSSMessageBox;

    const state = {
        sessionId: defaultSessionId,
        currentSongIndex: 0,
        currentSlideGlobalIndex: null,
        blackMode: false,
        qrMode: false,
        hideChorusesInGrid: false,
        blockScrollKeys: true,
        chorusCursorBySong: {},
    };

    const bridge = {
        broadcastChannel: null,
        storageKey: "",
    };

    const slideCards = Array.from(document.querySelectorAll("[data-lyrics-slide-card]"));

    const getSongByIndex = (songIndex) => {
        if (!Number.isInteger(songIndex) || songIndex < 0 || songIndex >= songs.length) {
            return null;
        }
        return songs[songIndex] || null;
    };

    const normalizeSongIndex = (songIndex) => {
        if (!songs.length) {
            return 0;
        }
        const modulo = songIndex % songs.length;
        return modulo < 0 ? modulo + songs.length : modulo;
    };

    const songIndexByAnimationSongId = new Map();
    songs.forEach((song, index) => {
        songIndexByAnimationSongId.set(Number(song.animationSongId), index);
    });

    const slideByGlobalIndex = (globalIndex) => {
        if (!Number.isInteger(globalIndex) || globalIndex < 0 || globalIndex >= slides.length) {
            return null;
        }
        return slides[globalIndex] || null;
    };

    const getCurrentSong = () => getSongByIndex(state.currentSongIndex);

    const getSongSlideIndexes = (songIndex) => {
        const song = getSongByIndex(songIndex);
        if (!song || !Array.isArray(song.slideIndexes)) {
            return [];
        }
        return song.slideIndexes
            .map((value) => Number.parseInt(String(value || ""), 10))
            .filter((value) => Number.isInteger(value));
    };

    const getSongChorusIndexes = (songIndex) => {
        const song = getSongByIndex(songIndex);
        if (!song || !Array.isArray(song.chorusIndexes)) {
            return [];
        }
        return song.chorusIndexes
            .map((value) => Number.parseInt(String(value || ""), 10))
            .filter((value) => Number.isInteger(value));
    };

    const getCurrentSlideInSongPosition = () => {
        const indexes = getSongSlideIndexes(state.currentSongIndex);
        if (!indexes.length || !Number.isInteger(state.currentSlideGlobalIndex)) {
            return -1;
        }
        return indexes.indexOf(state.currentSlideGlobalIndex);
    };

    const persistState = () => {
        const payloadToStore = {
            sessionId: state.sessionId,
            currentSongIndex: state.currentSongIndex,
            currentSlideGlobalIndex: state.currentSlideGlobalIndex,
            blackMode: state.blackMode,
            qrMode: state.qrMode,
            hideChorusesInGrid: state.hideChorusesInGrid,
            blockScrollKeys: state.blockScrollKeys,
            chorusCursorBySong: state.chorusCursorBySong,
        };
        try {
            window.localStorage.setItem(stateStorageKey, JSON.stringify(payloadToStore));
        } catch (_error) {
            // Ignore localStorage write failures.
        }
    };

    const restoreState = () => {
        try {
            const raw = window.localStorage.getItem(stateStorageKey);
            if (!raw) {
                return;
            }
            const parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== "object") {
                return;
            }
            if (typeof parsed.sessionId === "string" && parsed.sessionId.trim()) {
                state.sessionId = parsed.sessionId.trim();
            }
            if (Number.isInteger(parsed.currentSongIndex)) {
                state.currentSongIndex = normalizeSongIndex(parsed.currentSongIndex);
            }
            if (Number.isInteger(parsed.currentSlideGlobalIndex)) {
                state.currentSlideGlobalIndex = parsed.currentSlideGlobalIndex;
            }
            state.blackMode = Boolean(parsed.blackMode);
            state.qrMode = Boolean(parsed.qrMode);
            state.hideChorusesInGrid = Boolean(parsed.hideChorusesInGrid);
            state.blockScrollKeys = Boolean(parsed.blockScrollKeys);
            if (parsed.chorusCursorBySong && typeof parsed.chorusCursorBySong === "object") {
                state.chorusCursorBySong = parsed.chorusCursorBySong;
            }
        } catch (_error) {
            // Ignore localStorage parsing errors.
        }
    };

    const normalizeState = () => {
        state.currentSongIndex = normalizeSongIndex(state.currentSongIndex);
        const currentSlide = slideByGlobalIndex(state.currentSlideGlobalIndex);
        if (!currentSlide) {
            state.currentSlideGlobalIndex = null;
        }
        if (state.blackMode) {
            state.qrMode = false;
        }
    };

    const ensureBridge = () => {
        bridge.storageKey = `${bridgeStorageKeyPrefix}${state.sessionId}`;
        if (bridge.broadcastChannel) {
            try {
                bridge.broadcastChannel.close();
            } catch (_error) {
                // noop
            }
        }
        bridge.broadcastChannel = null;
        if (typeof window.BroadcastChannel === "function") {
            try {
                bridge.broadcastChannel = new window.BroadcastChannel(bridge.storageKey);
            } catch (_error) {
                bridge.broadcastChannel = null;
            }
        }
    };

    const sendBridgeMessage = (message) => {
        const enriched = {
            ...message,
            sessionId: state.sessionId,
            sentAt: Date.now(),
            nonce: `${Date.now()}-${Math.random()}`,
        };
        if (bridge.broadcastChannel) {
            try {
                bridge.broadcastChannel.postMessage(enriched);
            } catch (_error) {
                // Keep storage fallback below.
            }
        }
        try {
            window.localStorage.setItem(bridge.storageKey, JSON.stringify(enriched));
            window.localStorage.removeItem(bridge.storageKey);
        } catch (_error) {
            // Ignore storage failures.
        }
    };

    const frameFromState = () => {
        if (state.blackMode) {
            return { mode: "black" };
        }

        if (state.qrMode) {
            return {
                mode: "qr",
                qrCodePngBase64,
                publicUrl,
            };
        }

        const slide = slideByGlobalIndex(state.currentSlideGlobalIndex);
        if (!slide) {
            return { mode: "idle" };
        }

        return {
            mode: "slide",
            songTitle: slide.songTitle,
            slide,
        };
    };

    const sendInit = () => {
        sendBridgeMessage({
            type: "init",
            animationId,
            frame: frameFromState(),
        });
    };

    const sendFrame = () => {
        sendBridgeMessage({
            type: "frame",
            animationId,
            frame: frameFromState(),
        });
    };

    const sendHeartbeat = () => {
        sendBridgeMessage({
            type: "heartbeat",
            animationId,
            frame: frameFromState(),
        });
    };

    const syncSongContextFromCurrentSlide = () => {
        const slide = slideByGlobalIndex(state.currentSlideGlobalIndex);
        if (!slide) {
            return;
        }
        const resolvedSongIndex = songIndexByAnimationSongId.get(Number(slide.animationSongId));
        if (Number.isInteger(resolvedSongIndex)) {
            state.currentSongIndex = resolvedSongIndex;
        }
    };

    const setCurrentSong = (songIndex) => {
        state.currentSongIndex = normalizeSongIndex(songIndex);
        state.currentSlideGlobalIndex = null;
        state.blackMode = false;
        state.qrMode = false;
        persistState();
        refreshUI();
        sendFrame();
    };

    const projectSlide = (globalIndex) => {
        const slide = slideByGlobalIndex(globalIndex);
        if (!slide) {
            return;
        }
        const resolvedSongIndex = songIndexByAnimationSongId.get(Number(slide.animationSongId));
        if (Number.isInteger(resolvedSongIndex)) {
            state.currentSongIndex = resolvedSongIndex;
        }
        state.currentSlideGlobalIndex = globalIndex;
        state.blackMode = false;
        state.qrMode = false;
        persistState();
        refreshUI();
        sendFrame();
    };

    const navigateSlide = (direction) => {
        const indexes = getSongSlideIndexes(state.currentSongIndex);
        if (!indexes.length) {
            return;
        }

        const currentPosition = getCurrentSlideInSongPosition();
        let nextPosition;
        if (currentPosition < 0) {
            nextPosition = direction > 0 ? 0 : indexes.length - 1;
        } else {
            const raw = currentPosition + direction;
            if (raw < 0) {
                nextPosition = indexes.length - 1;
            } else if (raw >= indexes.length) {
                nextPosition = 0;
            } else {
                nextPosition = raw;
            }
        }
        projectSlide(indexes[nextPosition]);
    };

    const navigateChorus = () => {
        const chorusIndexes = getSongChorusIndexes(state.currentSongIndex);
        if (!chorusIndexes.length) {
            return;
        }
        const songKey = String(state.currentSongIndex);
        const currentCursor = Number.parseInt(String(state.chorusCursorBySong[songKey] || "0"), 10) || 0;
        const normalizedCursor = currentCursor >= chorusIndexes.length ? 0 : currentCursor;
        const targetIndex = chorusIndexes[normalizedCursor];
        state.chorusCursorBySong[songKey] = (normalizedCursor + 1) % chorusIndexes.length;
        projectSlide(targetIndex);
    };

    const toggleBlackMode = () => {
        state.blackMode = !state.blackMode;
        if (state.blackMode) {
            state.qrMode = false;
        }
        persistState();
        refreshUI();
        sendFrame();
    };

    const toggleQrMode = () => {
        state.qrMode = !state.qrMode;
        if (state.qrMode) {
            state.blackMode = false;
        }
        persistState();
        refreshUI();
        sendFrame();
    };

    const toggleChorusVisibility = () => {
        state.hideChorusesInGrid = !state.hideChorusesInGrid;
        persistState();
        refreshUI();
    };

    const toggleScrollMode = () => {
        state.blockScrollKeys = !state.blockScrollKeys;
        persistState();
        refreshUI();
    };

    const formatSlideLabel = (slide) => {
        if (!slide) {
            return label("noneLabel");
        }
        const rawLabel = String(slide.label || "").trim();
        if (rawLabel) {
            return rawLabel;
        }
        return label("noneLabel");
    };

    const setText = (node, text) => {
        if (node instanceof HTMLElement) {
            node.textContent = text;
        }
    };

    const refreshPreview = () => {
        const currentSlide = slideByGlobalIndex(state.currentSlideGlobalIndex);
        const songIndexes = getSongSlideIndexes(state.currentSongIndex);
        let nextSlide = null;

        if (songIndexes.length) {
            if (!currentSlide) {
                nextSlide = slideByGlobalIndex(songIndexes[0]);
            } else {
                const position = songIndexes.indexOf(state.currentSlideGlobalIndex);
                if (position >= 0) {
                    nextSlide = slideByGlobalIndex(songIndexes[(position + 1) % songIndexes.length]);
                } else {
                    nextSlide = slideByGlobalIndex(songIndexes[0]);
                }
            }
        }

        setText(previewCurrentLabelNode, currentSlide ? formatSlideLabel(currentSlide) : label("currentSlidePlaceholder"));
        setText(previewCurrentTextNode, currentSlide ? String(currentSlide.text || "") : label("currentSlidePlaceholder"));
        setText(previewNextLabelNode, nextSlide ? formatSlideLabel(nextSlide) : label("nextSlidePlaceholder"));
        setText(previewNextTextNode, nextSlide ? String(nextSlide.text || "") : label("nextSlidePlaceholder"));
    };

    const refreshSongNavigationLabels = () => {
        const currentSong = getCurrentSong();
        if (!currentSong) {
            setText(prevSongTitleNode, label("noneLabel"));
            setText(nextSongTitleNode, label("noneLabel"));
            return;
        }
        const prevSong = getSongByIndex(normalizeSongIndex(state.currentSongIndex - 1));
        const nextSong = getSongByIndex(normalizeSongIndex(state.currentSongIndex + 1));

        setText(prevSongTitleNode, prevSong ? String(prevSong.songTitle || "") : label("noneLabel"));
        setText(nextSongTitleNode, nextSong ? String(nextSong.songTitle || "") : label("noneLabel"));
    };

    const refreshSelectionStyles = () => {
        slideCards.forEach((card) => {
            if (!(card instanceof HTMLElement)) {
                return;
            }
            const globalIndex = Number.parseInt(String(card.getAttribute("data-global-index") || ""), 10);
            const isActive = Number.isInteger(state.currentSlideGlobalIndex) && globalIndex === state.currentSlideGlobalIndex;
            card.classList.toggle("is-active", isActive);

            const kind = String(card.getAttribute("data-kind") || "");
            const hide = state.hideChorusesInGrid && kind === "chorus";
            card.hidden = hide;
        });

        document.querySelectorAll("[data-lyrics-song-group]").forEach((groupNode) => {
            if (!(groupNode instanceof HTMLElement)) {
                return;
            }
            const asid = Number.parseInt(String(groupNode.getAttribute("data-animation-song-id") || ""), 10);
            const songIndex = songIndexByAnimationSongId.get(asid);
            groupNode.classList.toggle("is-current-song", Number.isInteger(songIndex) && songIndex === state.currentSongIndex);
        });
    };

    const refreshSummary = () => {
        const currentSong = getCurrentSong();
        setText(songTitleNode, currentSong ? String(currentSong.songTitle || "") : label("noneLabel"));
        setText(displaySessionNode, state.sessionId);

        const currentSlide = slideByGlobalIndex(state.currentSlideGlobalIndex);
        setText(slideLabelNode, currentSlide ? formatSlideLabel(currentSlide) : label("noneLabel"));

        setText(chorusVisibilityNode, state.hideChorusesInGrid ? label("hiddenChorusLabel") : "");
        setText(scrollModeNode, state.blockScrollKeys ? label("scrollLockedLabel") : label("scrollUnlockedLabel"));
    };

    const refreshUI = () => {
        syncSongContextFromCurrentSlide();
        refreshSongNavigationLabels();
        refreshSelectionStyles();
        refreshSummary();
        refreshPreview();
    };

    const maybeShowPopup = async (title, message) => {
        if (!messageBox || typeof messageBox.alert !== "function") {
            return;
        }
        await messageBox.alert({
            title,
            messageMarkdown: message,
            showCloseButton: true,
            buttons: [{ id: "ok", label: label("okLabel"), tone: "neutral" }],
        });
    };

    const openDisplayWindow = async () => {
        if (!displayUrlBase) {
            return;
        }
        const query = new URLSearchParams({ session: state.sessionId });
        const targetUrl = `${displayUrlBase}?${query.toString()}`;
        const openedWindow = window.open(targetUrl, "LSSLyricsDisplay", "noopener,noreferrer");
        if (!openedWindow) {
            await maybeShowPopup(label("popupBlockedTitle"), label("popupBlockedMessage"));
            return;
        }
        sendInit();
        sendFrame();
        try {
            openedWindow.focus();
        } catch (_error) {
            // noop
        }
    };

    const runPreload = async () => {
        if (!backgroundUrls.length) {
            return;
        }
        const preloadPromises = backgroundUrls.map((url) => {
            return new Promise((resolve) => {
                const img = new Image();
                img.onload = () => resolve(true);
                img.onerror = () => resolve(false);
                img.src = url;
            });
        });
        const results = await Promise.all(preloadPromises);
        if (results.every(Boolean)) {
            return;
        }
        await maybeShowPopup(label("preloadWarningTitle"), label("preloadWarningMessage"));
    };

    const handleAction = async (action) => {
        if (action === "open-display" || action === "reopen-display") {
            await openDisplayWindow();
            return;
        }
        if (action === "show-shortcuts") {
            await maybeShowPopup(label("shortcutsPopupTitle"), label("shortcutsPopupMessage"));
            return;
        }
        if (action === "black") {
            toggleBlackMode();
            return;
        }
        if (action === "prev-slide") {
            navigateSlide(-1);
            return;
        }
        if (action === "next-slide") {
            navigateSlide(1);
            return;
        }
        if (action === "chorus") {
            navigateChorus();
            return;
        }
        if (action === "prev-song") {
            setCurrentSong(state.currentSongIndex - 1);
            return;
        }
        if (action === "next-song") {
            setCurrentSong(state.currentSongIndex + 1);
            return;
        }
        if (action === "toggle-scroll") {
            toggleScrollMode();
            return;
        }
        if (action === "toggle-chorus") {
            toggleChorusVisibility();
            return;
        }
        if (action === "toggle-qr") {
            toggleQrMode();
        }
    };

    document.querySelectorAll("[data-lyrics-action]").forEach((button) => {
        button.addEventListener("click", async () => {
            const action = String(button.getAttribute("data-lyrics-action") || "");
            await handleAction(action);
        });
    });

    slideCards.forEach((card) => {
        card.addEventListener("click", () => {
            const globalIndex = Number.parseInt(String(card.getAttribute("data-global-index") || ""), 10);
            if (!Number.isInteger(globalIndex)) {
                return;
            }
            projectSlide(globalIndex);
        });
    });

    const shouldIgnoreKeydownTarget = (target) => {
        if (!(target instanceof HTMLElement)) {
            return false;
        }
        if (target.isContentEditable) {
            return true;
        }
        const tagName = target.tagName.toLowerCase();
        return ["input", "textarea", "select", "button"].includes(tagName);
    };

    const keydownHandler = async (event) => {
        if (shouldIgnoreKeydownTarget(event.target)) {
            return;
        }

        const key = String(event.key || "").toLowerCase();
        const scrollBlockKeys = ["arrowup", "arrowdown", "arrowleft", "arrowright", " "];
        if (state.blockScrollKeys && scrollBlockKeys.includes(key)) {
            event.preventDefault();
        }

        if (key === "escape" || key === "m") {
            toggleBlackMode();
            return;
        }
        if (key === "arrowup" || key === "b") {
            navigateSlide(-1);
            return;
        }
        if (key === "arrowdown" || key === "s" || key === "v" || key === " ") {
            navigateSlide(1);
            return;
        }
        if (key === "c" || key === "r") {
            navigateChorus();
            return;
        }
        if (key === "arrowleft" || key === "f") {
            setCurrentSong(state.currentSongIndex - 1);
            return;
        }
        if (key === "arrowright" || key === "enter" || key === "n") {
            setCurrentSong(state.currentSongIndex + 1);
            return;
        }
        if (key === "a" || key === "d") {
            toggleChorusVisibility();
            return;
        }
        if (key === "l") {
            toggleScrollMode();
            return;
        }
        if (key === "q") {
            toggleQrMode();
            return;
        }
        if (key === "o") {
            await openDisplayWindow();
        }
    };

    window.addEventListener("keydown", (event) => {
        void keydownHandler(event);
    }, { passive: false });

    restoreState();
    normalizeState();
    ensureBridge();
    refreshUI();
    persistState();
    sendInit();
    sendFrame();

    window.setInterval(() => {
        sendHeartbeat();
    }, 8000);

    void runPreload();
})();
