(() => {
    const root = document.querySelector("[data-lyrics-public-root]");
    if (!(root instanceof HTMLElement)) {
        return;
    }

    const payloadNode = document.getElementById("lss-lyrics-public-songs");
    let songs = [];
    if (payloadNode && payloadNode.textContent) {
        try {
            const parsed = JSON.parse(payloadNode.textContent);
            if (Array.isArray(parsed)) {
                songs = parsed;
            }
        } catch (_error) {
            songs = [];
        }
    }

    const i18n = window.LSS_LYRICS_PUBLIC_I18N || {};
    const label = (key) => String(i18n[key] || "");

    const songSelect = document.querySelector("[data-lyrics-public-song-select]");
    const songTitleNode = document.querySelector("[data-lyrics-public-song-title]");
    const songContentNode = document.querySelector("[data-lyrics-public-song-content]");

    const stateStorageKey = `lss-lyrics-public:${window.location.pathname}`;

    const state = {
        songIndex: 0,
        fontScale: 1,
        darkTheme: false,
    };

    const clampSongIndex = (value) => {
        if (!songs.length) {
            return 0;
        }
        const modulo = value % songs.length;
        return modulo < 0 ? modulo + songs.length : modulo;
    };

    const currentSong = () => songs[clampSongIndex(state.songIndex)] || null;

    const persistState = () => {
        try {
            window.localStorage.setItem(stateStorageKey, JSON.stringify(state));
        } catch (_error) {
            // Ignore storage errors.
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
            if (Number.isInteger(parsed.songIndex)) {
                state.songIndex = parsed.songIndex;
            }
            if (typeof parsed.fontScale === "number") {
                state.fontScale = parsed.fontScale;
            }
            state.darkTheme = Boolean(parsed.darkTheme);
        } catch (_error) {
            // Ignore parsing errors.
        }
    };

    const buildSongBlockNode = (block) => {
        const wrapper = document.createElement("article");
        wrapper.className = "lyrics-public-block";
        wrapper.dataset.kind = String(block.kind || "");

        if (block.label) {
            const heading = document.createElement("h3");
            heading.textContent = String(block.label || "");
            wrapper.appendChild(heading);
        }

        const text = document.createElement("p");
        text.textContent = String(block.text || "");
        wrapper.appendChild(text);
        return wrapper;
    };

    const applyTheme = () => {
        document.body.classList.toggle("is-public-dark", state.darkTheme);
    };

    const renderSong = () => {
        const song = currentSong();
        if (!(songTitleNode instanceof HTMLElement) || !(songContentNode instanceof HTMLElement)) {
            return;
        }

        songContentNode.replaceChildren();

        if (!song) {
            songTitleNode.textContent = label("noSongLabel");
            const p = document.createElement("p");
            p.textContent = label("noContentLabel");
            songContentNode.appendChild(p);
            return;
        }

        songTitleNode.textContent = String(song.songTitle || "");
        const blocks = Array.isArray(song.blocks) ? song.blocks : [];
        if (!blocks.length) {
            const p = document.createElement("p");
            p.textContent = label("noContentLabel");
            songContentNode.appendChild(p);
        } else {
            blocks.forEach((block) => {
                songContentNode.appendChild(buildSongBlockNode(block));
            });
        }

        songContentNode.style.fontSize = `${state.fontScale}rem`;

        if (songSelect instanceof HTMLSelectElement) {
            songSelect.value = String(clampSongIndex(state.songIndex));
        }
    };

    const setSongIndex = (targetIndex) => {
        state.songIndex = clampSongIndex(targetIndex);
        renderSong();
        persistState();
    };

    const adjustFontScale = (delta) => {
        const next = Math.max(0.75, Math.min(2.2, state.fontScale + delta));
        state.fontScale = Number(next.toFixed(2));
        renderSong();
        persistState();
    };

    const toggleTheme = () => {
        state.darkTheme = !state.darkTheme;
        applyTheme();
        persistState();
    };

    document.querySelectorAll("[data-lyrics-public-action]").forEach((button) => {
        button.addEventListener("click", () => {
            const action = String(button.getAttribute("data-lyrics-public-action") || "");
            if (action === "prev-song") {
                setSongIndex(state.songIndex - 1);
                return;
            }
            if (action === "next-song") {
                setSongIndex(state.songIndex + 1);
                return;
            }
            if (action === "decrease-size") {
                adjustFontScale(-0.1);
                return;
            }
            if (action === "increase-size") {
                adjustFontScale(0.1);
                return;
            }
            if (action === "toggle-theme") {
                toggleTheme();
            }
        });
    });

    if (songSelect instanceof HTMLSelectElement) {
        songSelect.addEventListener("change", () => {
            const target = Number.parseInt(String(songSelect.value || "0"), 10);
            setSongIndex(Number.isInteger(target) ? target : 0);
        });
    }

    restoreState();
    state.songIndex = clampSongIndex(state.songIndex);
    applyTheme();
    renderSong();
})();
