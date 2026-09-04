(() => {
    const root = document.querySelector("[data-remote-access-root]");
    const statusNode = document.querySelector("[data-remote-access-status]");
    if (!(root instanceof HTMLElement) || !(statusNode instanceof HTMLElement)) {
        return;
    }
    const i18n = window.LSS_REMOTE_ACCESS_I18N || {};
    const preferenceKey = "lss.remote.access.preferences.v1";
    let token = new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
    const sessionId = String(root.dataset.sessionId || "");
    const menu = root.querySelector("[data-remote-menu]");
    const menuToggle = root.querySelector("[data-remote-menu-toggle]");
    const menuClose = root.querySelector("[data-remote-menu-close]");
    const menuStatus = root.querySelector("[data-remote-menu-status]");
    const feedback = root.querySelector("[data-remote-feedback]");
    const preferences = { "next-slide": true, "song-select": true, chorus: true };
    let latestState = null;
    let latestStatus = "AUTHENTICATING";
    let remote = null;

    try {
        Object.assign(preferences, JSON.parse(window.localStorage.getItem(preferenceKey) || "{}"));
    } catch (_error) {
        // Invalid local preferences must not prevent the remote from operating.
    }

    const setText = (node, value) => {
        if (node instanceof HTMLElement) {
            node.textContent = String(value || "");
        }
    };

    const statusLabel = (status) => {
        const labels = {
            AUTHENTICATING: i18n.connecting,
            CONNECTED: i18n.connected,
            RECONNECTING: i18n.reconnecting,
            MASTER_UNAVAILABLE: i18n.unavailable,
            DISABLED: i18n.disabled,
            ERROR: i18n.unavailable,
        };
        return String(labels[status] || i18n.unavailable || "Master indisponible");
    };

    const renderStatus = () => {
        const label = statusLabel(latestStatus);
        setText(statusNode, label);
        setText(menuStatus, label);
    };

    const showFeedback = (message) => {
        if (!(feedback instanceof HTMLElement)) {
            return;
        }
        feedback.textContent = String(message || "");
        feedback.hidden = !message;
    };

    const canSend = () => latestStatus === "CONNECTED" && remote !== null;

    const sendCommand = (command, target) => {
        if (!canSend() || !remote.sendCommand(command, target)) {
            showFeedback(i18n.unavailable || "Master indisponible");
        }
    };

    const applyPreferences = () => {
        Object.entries(preferences).forEach(([name, visible]) => {
            const section = root.querySelector(`[data-remote-section="${name}"]`);
            const input = root.querySelector(`[data-remote-preference="${name}"]`);
            if (section instanceof HTMLElement) {
                section.hidden = !visible;
            }
            if (input instanceof HTMLInputElement) {
                input.checked = Boolean(visible);
            }
        });
    };

    const savePreferences = () => {
        try {
            window.localStorage.setItem(preferenceKey, JSON.stringify(preferences));
        } catch (_error) {
            // Storage can be unavailable in private browsing contexts.
        }
    };

    const populateSelect = (selector, songs, selectedId) => {
        const select = root.querySelector(selector);
        if (!(select instanceof HTMLSelectElement)) {
            return;
        }
        select.replaceChildren();
        songs.forEach((song) => {
            const option = document.createElement("option");
            option.value = String(song.animation_song_id);
            option.textContent = String(song.title || i18n.noSong || "Aucun chant");
            option.selected = song.animation_song_id === selectedId;
            select.append(option);
        });
        select.disabled = !canSend() || songs.length === 0;
    };

    const renderState = (state, isFreshState = false) => {
        if (!state || typeof state !== "object") {
            return;
        }
        const revision = Number(state.revision);
        const currentRevision = latestState === null ? null : Number(latestState.revision);
        if (!Number.isInteger(revision) || revision < 0) {
            return;
        }
        if (
            isFreshState
            &&
            currentRevision !== null
            && Number.isInteger(currentRevision)
            && revision <= currentRevision
        ) {
            return;
        }
        latestState = state;
        const selectedSong = state.current_song || {};
        const previousSong = state.previous_song || null;
        const nextSong = state.next_song || null;
        const nextStep = state.next_projection_step || null;
        setText(root.querySelector("[data-remote-next-slide]"), nextStep?.excerpt || nextStep?.label || i18n.noNextSlide || "Aucune slide suivante");
        setText(root.querySelector("[data-remote-previous-song]"), previousSong?.title || i18n.noSong || "Aucun chant");
        setText(root.querySelector("[data-remote-next-song]"), nextSong?.title || i18n.noSong || "Aucun chant");
        const blackButton = root.querySelector("[data-remote-command=\"TOGGLE_BLACK\"]");
        if (blackButton instanceof HTMLButtonElement) {
            blackButton.classList.toggle("is-active", Boolean(state.black_mode));
            blackButton.setAttribute("aria-pressed", String(Boolean(state.black_mode)));
        }
        setText(root.querySelector("[data-remote-black-mode-state]"), state.black_mode ? i18n.blackActive : i18n.blackInactive);
        populateSelect("[data-remote-song-select]", Array.isArray(state.songs) ? state.songs : [], selectedSong.animation_song_id);
        populateSelect("[data-remote-menu-song-select]", Array.isArray(state.songs) ? state.songs : [], selectedSong.animation_song_id);

        const transitionSelect = root.querySelector("[data-remote-transition-select]");
        if (transitionSelect instanceof HTMLSelectElement) {
            transitionSelect.replaceChildren();
            (Array.isArray(state.available_transitions) ? state.available_transitions : []).forEach((transition) => {
                const option = document.createElement("option");
                option.value = String(transition.transition_id);
                option.textContent = String(transition.label || transition.transition_id);
                option.selected = transition.transition_id === state.current_transition?.transition_id;
                transitionSelect.append(option);
            });
            transitionSelect.disabled = !canSend() || transitionSelect.options.length === 0;
        }

        root.querySelectorAll("[data-remote-command]").forEach((button) => {
            if (!(button instanceof HTMLButtonElement)) {
                return;
            }
            const command = button.dataset.remoteCommand;
            const enabled = canSend()
                && (!command.includes("PREVIOUS_SONG") || previousSong)
                && (!command.includes("NEXT_SONG") || nextSong)
                && (!command.includes("GO_TO_CHORUS") || state.chorus_available);
            button.disabled = !enabled;
        });
        if (isFreshState && state.master_status === "MASTER_CONNECTED") {
            if (latestStatus === "MASTER_UNAVAILABLE") {
                latestStatus = "CONNECTED";
            }
        } else if (isFreshState) {
            latestStatus = "MASTER_UNAVAILABLE";
        }
        renderStatus();
    };

    const updateControls = () => {
        if (latestState) {
            renderState(latestState);
        }
    };

    if (!sessionId || !token || !window.LSSRemoteTransport) {
        latestStatus = "ERROR";
        renderStatus();
        return;
    }
    window.history.replaceState(null, "", window.location.pathname);
    root.querySelectorAll("[data-remote-hide-section]").forEach((button) => {
        button.addEventListener("click", () => {
            const section = button.dataset.remoteHideSection;
            if (section in preferences) {
                preferences[section] = false;
                savePreferences();
                applyPreferences();
            }
        });
    });
    root.querySelectorAll("[data-remote-preference]").forEach((input) => {
        input.addEventListener("change", () => {
            const name = input.dataset.remotePreference;
            if (name in preferences) {
                preferences[name] = Boolean(input.checked);
                savePreferences();
                applyPreferences();
            }
        });
    });
    root.querySelectorAll("[data-remote-command]").forEach((button) => {
        button.addEventListener("click", () => sendCommand(button.dataset.remoteCommand));
    });
    root.querySelectorAll("[data-remote-song-select], [data-remote-menu-song-select]").forEach((select) => {
        select.addEventListener("change", () => {
            const animationSongId = Number.parseInt(select.value, 10);
            if (Number.isInteger(animationSongId)) {
                sendCommand("GO_TO_SONG", { animation_song_id: animationSongId });
            }
        });
    });
    root.querySelector("[data-remote-transition-select]")?.addEventListener("change", (event) => {
        const transitionId = String(event.currentTarget.value || "");
        if (transitionId) {
            sendCommand("SET_TRANSITION", { transition_id: transitionId });
        }
    });
    const setMenuOpen = (open) => {
        if (menu instanceof HTMLElement) {
            menu.hidden = !open;
        }
        if (menuToggle instanceof HTMLButtonElement) {
            menuToggle.setAttribute("aria-expanded", String(open));
        }
    };
    menuToggle?.addEventListener("click", () => setMenuOpen(menu?.hidden));
    menuClose?.addEventListener("click", () => setMenuOpen(false));
    root.querySelector("[data-remote-quit]")?.addEventListener("click", () => {
        token = "";
        remote?.disconnect();
        remote = null;
        latestStatus = "DISABLED";
        updateControls();
        renderStatus();
        setMenuOpen(false);
    });
    applyPreferences();
    remote = window.LSSRemoteTransport.connectRemote({
        sessionId,
        accessToken: token,
        onState: (state) => renderState(state, true),
        onStatus: (status) => {
            latestStatus = status;
            renderStatus();
            updateControls();
        },
        onCommandAccepted: () => showFeedback(i18n.accepted || "Commande acceptée"),
        onCommandRejected: (message) => {
            showFeedback(message.reason === "COOLDOWN" ? i18n.cooldown : i18n.rejected);
            updateControls();
        },
    });
})();
