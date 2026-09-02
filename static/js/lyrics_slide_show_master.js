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
    const shortcutsConfigNode = document.getElementById("lss-lyrics-shortcuts-config");
    let shortcutsConfig = {};
    if (shortcutsConfigNode && shortcutsConfigNode.textContent) {
        try {
            shortcutsConfig = JSON.parse(shortcutsConfigNode.textContent);
        } catch (_error) {
            shortcutsConfig = {};
        }
    }

    const i18n = window.LSS_LYRICS_I18N || {};
    const label = (key) => String(i18n[key] || "");
    const shortcutActionLabels = shortcutsConfig && typeof shortcutsConfig === "object" && shortcutsConfig.actionLabels
        ? shortcutsConfig.actionLabels
        : {};

    const warnDroppedIndex = (context, value, reason) => {
        console.warn(`[LSS remote] Ignored index (${context}):`, value, `(${reason})`);
    };

    const toIntegerOrNull = (value) => {
        if (typeof value === "number") {
            return Number.isInteger(value) ? value : null;
        }
        if (typeof value === "string") {
            const trimmed = value.trim();
            if (!trimmed || !/^[-+]?\d+$/.test(trimmed)) {
                return null;
            }
            const parsed = Number.parseInt(trimmed, 10);
            return Number.isInteger(parsed) ? parsed : null;
        }
        return null;
    };

    const toNonNegativeIndexOrNull = (value) => {
        const parsed = toIntegerOrNull(value);
        if (!Number.isInteger(parsed) || parsed < 0) {
            return null;
        }
        return parsed;
    };

    const getCsrfToken = () => {
        const field = document.querySelector("input[name=csrfmiddlewaretoken]");
        if (field instanceof HTMLInputElement && field.value) {
            return field.value;
        }
        return "";
    };

    const sanitizeIndexList = (values, options = {}) => {
        if (!Array.isArray(values)) {
            return [];
        }
        const context = String(options.context || "index-list");
        const maxExclusive = Number.isInteger(options.maxExclusive) ? options.maxExclusive : null;
        const seen = new Set();
        const sanitized = [];

        values.forEach((rawValue, rawPosition) => {
            const parsed = toNonNegativeIndexOrNull(rawValue);
            if (!Number.isInteger(parsed)) {
                warnDroppedIndex(`${context}@${rawPosition}`, rawValue, "not-a-non-negative-integer");
                return;
            }
            if (Number.isInteger(maxExclusive) && parsed >= maxExclusive) {
                warnDroppedIndex(`${context}@${rawPosition}`, rawValue, "out-of-range");
                return;
            }
            if (seen.has(parsed)) {
                warnDroppedIndex(`${context}@${rawPosition}`, rawValue, "duplicate");
                return;
            }
            seen.add(parsed);
            sanitized.push(parsed);
        });

        return sanitized;
    };

    const animationId = Number.parseInt(String(root.getAttribute("data-animation-id") || ""), 10) || 0;
    const displayUrlBase = String(root.getAttribute("data-display-url-base") || "").trim();
    const defaultSessionId = String(root.getAttribute("data-display-session-id") || "").trim();

    const slides = payload.slides;
    const songs = payload.songs;
    const buildFallbackProjectionSteps = () => {
        return slides.map((slide, index) => ({
            projectionIndex: index,
            animationSongId: slide.animationSongId,
            songId: slide.songId,
            songTitle: slide.songTitle,
            mode: "simple",
            left: slide,
            right: null,
            primarySourceGlobalIndex: slide.globalIndex,
            sourceGlobalIndexes: [slide.globalIndex],
        }));
    };
    const projectionSteps = Array.isArray(payload.projectionSteps) && payload.projectionSteps.length
        ? payload.projectionSteps
        : buildFallbackProjectionSteps();
    const publicUrl = String(payload.publicUrl || "");
    const qrCodePngBase64 = String(payload.qrCodePngBase64 || "");
    const backgroundUrls = Array.isArray(payload.backgroundUrls) ? payload.backgroundUrls.map((url) => String(url || "").trim()).filter(Boolean) : [];
    const transitions = Array.isArray(payload.transitions)
        ? payload.transitions
            .map((item) => {
                const id = String(item?.id || "").trim();
                if (!id) {
                    return null;
                }
                return {
                    id,
                    label: String(item?.label || id),
                    params: item?.params && typeof item.params === "object" ? { ...item.params } : {},
                };
            })
            .filter(Boolean)
        : [];
    const transitionById = new Map(transitions.map((item) => [item.id, item]));
    const defaultTransitionId = transitionById.has(String(payload.defaultTransitionId || "").trim())
        ? String(payload.defaultTransitionId || "").trim()
        : transitionById.has("direct")
            ? "direct"
            : transitions[0]?.id || "direct";

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
    const previewCurrentPanelNode = document.querySelector("[data-lyrics-preview-current-panel]");
    const previewNextPanelNode = document.querySelector("[data-lyrics-preview-next-panel]");
    const toolbarNode = document.querySelector(".lyrics-master-toolbar");
    const previewsCardNode = document.querySelector("[data-lyrics-previews-card]");
    const slidesAnchorNode = document.querySelector("[data-lyrics-slides-anchor]");
    const floatingNavNode = document.querySelector("[data-lyrics-floating-nav]");
    const floatingSlidesLinkNode = document.querySelector("[data-lyrics-floating-slides-link]");
    const floatingUpButtonNode = document.querySelector("[data-lyrics-floating-up]");
    const floatingDownButtonNode = document.querySelector("[data-lyrics-floating-down]");
    const floatingSongLinksNode = document.querySelector("[data-lyrics-floating-song-links]");
    const blackModeButtonNode = document.querySelector("[data-lyrics-action='black']");
    const qrToggleButtonNode = document.querySelector("[data-lyrics-action='toggle-qr']");
    const blackoutFrameNode = document.querySelector("[data-lyrics-blackout-frame]");
    if (floatingNavNode && document.body && floatingNavNode.parentElement !== document.body) {
        document.body.appendChild(floatingNavNode);
    }
    const prevSongButton = document.querySelector("[data-lyrics-action='prev-song']");
    const nextSongButton = document.querySelector("[data-lyrics-action='next-song']");
    const scrollToggleEmojiNode = document.querySelector("[data-lyrics-scroll-emoji]");
    const scrollToggleTextNode = document.querySelector("[data-lyrics-scroll-text]");
    const chorusToggleEmojiNode = document.querySelector("[data-lyrics-chorus-toggle-emoji]");
    const chorusToggleTextNode = document.querySelector("[data-lyrics-chorus-toggle-text]");
    const qrButtonImageNode = document.querySelector("[data-lyrics-qr-button-image]");
    const qrFallbackEmojiNode = document.querySelector("[data-lyrics-qr-fallback-emoji]");
    const qrFallbackTextNode = document.querySelector("[data-lyrics-qr-fallback-text]");
    const transitionSelectNode = document.querySelector("[data-lyrics-transition-select]");

    const messageBox = window.LSSMessageBox;

    const state = {
        sessionId: defaultSessionId,
        selectedSongIndex: 0,
        projectedProjectionIndex: null,
        pendingSongRestartIndex: null,
        blackMode: false,
        qrMode: false,
        hideChorusesInGrid: false,
        blockScrollKeys: true,
        chorusCursorBySong: {},
        progressCursorBySong: {},
        activeTransitionId: defaultTransitionId,
        f11ReminderActive: false,
        shortcuts: {
            siteBindings: shortcutsConfig.siteBindings || {},
            effectiveBindings: shortcutsConfig.effectiveBindings || {},
            formBindings: shortcutsConfig.formBindings || {},
            actionOrder: Array.isArray(shortcutsConfig.actionOrder) ? shortcutsConfig.actionOrder : [],
            actionToRemoteAction: shortcutsConfig.actionToRemoteAction || {},
            canCustomizeShortcuts: Boolean(shortcutsConfig.canCustomizeShortcuts),
            customizeUrl: String(shortcutsConfig.customizeUrl || "").trim(),
        },
    };

    const bridge = {
        broadcastChannel: null,
        storageKey: "",
    };

    const floatingSongWindowSize = 10;
    const floatingSongWindowStep = 3;
    let floatingSongWindowStart = 0;

    const slideCards = Array.from(document.querySelectorAll("[data-lyrics-slide-card]"));

    const normalizeShortcutToken = (value) => {
        const raw = String(value ?? "");
        if (raw === " ") {
            return "space";
        }
        const trimmed = raw.trim().toLowerCase();
        if (!trimmed) {
            return "";
        }
        const aliases = {
            "space bar": "space",
            espace: "space",
            entrée: "enter",
            entree: "enter",
            "↑": "arrowup",
            "↓": "arrowdown",
            "←": "arrowleft",
            "→": "arrowright",
            "⬆️": "arrowup",
            "⬇️": "arrowdown",
            "⬅️": "arrowleft",
            "➡️": "arrowright",
        };
        return aliases[trimmed] || trimmed;
    };

    const formatShortcutToken = (value) => {
        const token = normalizeShortcutToken(value);
        const labels = {
            escape: "Esc",
            space: "Espace",
            enter: "Enter",
            tab: "Tab",
            arrowup: "↑",
            arrowdown: "↓",
            arrowleft: "←",
            arrowright: "→",
            delete: "Suppr",
            backspace: "Retour arrière",
            pageup: "Page Up",
            pagedown: "Page Down",
            capslock: "Caps Lock",
        };
        if (labels[token]) {
            return labels[token];
        }
        if (token.length === 1 && /[a-z]/.test(token)) {
            return token.toUpperCase();
        }
        if (/^f\d+$/i.test(token)) {
            return token.toUpperCase();
        }
        return token;
    };

    const serializeBindingsForField = (values) => {
        if (!Array.isArray(values) || !values.length) {
            return "";
        }
        return values.join(",");
    };

    const buildSiteDefaultFieldValues = () => {
        const actionOrder = Array.isArray(state.shortcuts.actionOrder) ? state.shortcuts.actionOrder : [];
        const values = {};
        actionOrder.forEach((action) => {
            const siteValues = Array.isArray(state.shortcuts.siteBindings?.[action])
                ? state.shortcuts.siteBindings[action].filter((token) => !(action === "black" && token === "escape"))
                : [];
            values[action] = serializeBindingsForField(siteValues);
        });
        return values;
    };

    const normalizeBindingsMap = (rawBindings) => {
        const normalized = {};
        const actionOrder = Array.isArray(state.shortcuts.actionOrder) ? state.shortcuts.actionOrder : [];
        actionOrder.forEach((action) => {
            const rawValues = Array.isArray(rawBindings?.[action]) ? rawBindings[action] : [];
            const seen = new Set();
            normalized[action] = rawValues
                .map((value) => normalizeShortcutToken(value))
                .filter((value) => {
                    if (!value || seen.has(value)) {
                        return false;
                    }
                    seen.add(value);
                    return true;
                });
        });
        return normalized;
    };

    const buildShortcutActionIndex = () => {
        const index = new Map();
        const actionOrder = Array.isArray(state.shortcuts.actionOrder) ? state.shortcuts.actionOrder : [];
        actionOrder.forEach((action) => {
            const remoteAction = String(state.shortcuts.actionToRemoteAction?.[action] || "").trim();
            if (!remoteAction) {
                return;
            }
            const tokens = Array.isArray(state.shortcuts.effectiveBindings?.[action])
                ? state.shortcuts.effectiveBindings[action]
                : [];
            tokens.forEach((token) => {
                const normalized = normalizeShortcutToken(token);
                if (!normalized || index.has(normalized)) {
                    return;
                }
                index.set(normalized, remoteAction);
            });
        });
        return index;
    };

    const resolveTransitionId = (value) => {
        const transitionId = String(value || "").trim();
        if (transitionById.has(transitionId)) {
            return transitionId;
        }
        return defaultTransitionId;
    };

    const getActiveTransition = () => {
        const transitionId = resolveTransitionId(state.activeTransitionId);
        return transitionById.get(transitionId) || {
            id: "direct",
            label: "direct",
            params: { duration_ms: 0 },
        };
    };

    const transitionFromState = () => {
        const transition = getActiveTransition();
        return {
            id: transition.id,
            params: transition.params && typeof transition.params === "object" ? { ...transition.params } : {},
        };
    };

    const setActiveTransition = (transitionId) => {
        state.activeTransitionId = resolveTransitionId(transitionId);
        persistState();
        refreshUI();
    };

    const cycleTransition = () => {
        if (!transitions.length) {
            setActiveTransition(defaultTransitionId);
            return;
        }
        const activeTransitionId = resolveTransitionId(state.activeTransitionId);
        const activeIndex = transitions.findIndex((item) => item.id === activeTransitionId);
        const nextIndex = activeIndex >= 0 ? (activeIndex + 1) % transitions.length : 0;
        setActiveTransition(transitions[nextIndex].id);
    };

    const renderTransitionChoices = () => {
        if (!(transitionSelectNode instanceof HTMLSelectElement)) {
            return;
        }
        const fragment = document.createDocumentFragment();
        transitions.forEach((transition) => {
            const option = document.createElement("option");
            option.value = transition.id;
            option.textContent = transition.label;
            fragment.appendChild(option);
        });
        transitionSelectNode.replaceChildren(fragment);
        transitionSelectNode.disabled = transitions.length <= 1;
    };

    const setCustomizationPopupFeedback = (message, isError = false) => {
        const rootNode = document.getElementById("lss-messagebox-root");
        if (!(rootNode instanceof HTMLElement)) {
            return;
        }
        const contentNode = rootNode.querySelector(".lss-messagebox-content");
        if (!(contentNode instanceof HTMLElement)) {
            return;
        }
        let feedbackNode = contentNode.querySelector(".lss-lyrics-shortcuts-feedback");
        if (!message) {
            if (feedbackNode instanceof HTMLElement) {
                feedbackNode.remove();
            }
            return;
        }
        if (!(feedbackNode instanceof HTMLElement)) {
            feedbackNode = document.createElement("p");
            feedbackNode.className = "lss-lyrics-shortcuts-feedback";
            contentNode.insertBefore(feedbackNode, contentNode.querySelector(".lss-messagebox-form"));
        }
        feedbackNode.textContent = String(message);
        feedbackNode.style.color = isError ? "var(--site-color-danger, #b00020)" : "";
        feedbackNode.style.fontWeight = isError ? "600" : "";
    };

    const clearCustomizationPopupFieldErrors = () => {
        const rootNode = document.getElementById("lss-messagebox-root");
        if (!(rootNode instanceof HTMLElement)) {
            return;
        }
        rootNode.querySelectorAll(".lss-messagebox-field.is-invalid").forEach((wrapper) => {
            wrapper.classList.remove("is-invalid");
        });
        rootNode.querySelectorAll(".lss-messagebox-error").forEach((errorNode) => {
            if (errorNode instanceof HTMLElement) {
                errorNode.textContent = "";
            }
        });
        rootNode.querySelectorAll("[aria-invalid='true']").forEach((input) => {
            if (input instanceof HTMLElement) {
                input.removeAttribute("aria-invalid");
                input.removeAttribute("aria-describedby");
            }
        });
    };

    const buildShortcutHelpMarkdown = () => {
        const lines = [];
        const actionOrder = Array.isArray(state.shortcuts.actionOrder) ? state.shortcuts.actionOrder : [];
        actionOrder.forEach((action) => {
            const values = Array.isArray(state.shortcuts.effectiveBindings?.[action])
                ? state.shortcuts.effectiveBindings[action]
                : [];
            if (!values.length) {
                return;
            }
            lines.push(`- \`${values.map((value) => formatShortcutToken(value)).join("`, `")}\` : ${String(shortcutActionLabels[action] || action)}`);
        });
        const footer = label("shortcutsPopupFooter");
        if (footer) {
            lines.push("", footer);
        }
        return lines.join("\n");
    };

    const updateShortcutStateFromPayload = (payloadValue) => {
        if (!payloadValue || typeof payloadValue !== "object") {
            return;
        }
        if (payloadValue.siteBindings && typeof payloadValue.siteBindings === "object") {
            state.shortcuts.siteBindings = normalizeBindingsMap(payloadValue.siteBindings);
        }
        if (payloadValue.effectiveBindings && typeof payloadValue.effectiveBindings === "object") {
            state.shortcuts.effectiveBindings = normalizeBindingsMap(payloadValue.effectiveBindings);
        }
        if (payloadValue.savedBindings && typeof payloadValue.savedBindings === "object") {
            state.shortcuts.formBindings = normalizeBindingsMap(payloadValue.savedBindings);
        }
        if (payloadValue.formBindings && typeof payloadValue.formBindings === "object") {
            state.shortcuts.formBindings = normalizeBindingsMap(payloadValue.formBindings);
        }
    };

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
        const animationSongId = toIntegerOrNull(song.animationSongId);
        if (!Number.isInteger(animationSongId)) {
            warnDroppedIndex(`songs[${index}].animationSongId`, song.animationSongId, "invalid-animation-song-id");
            return;
        }
        songIndexByAnimationSongId.set(animationSongId, index);
    });
    const songGroupNodeByAnimationSongId = new Map();
    document.querySelectorAll("[data-lyrics-song-group]").forEach((groupNode) => {
        if (!(groupNode instanceof HTMLElement)) {
            return;
        }
        const rawAnimationSongId = groupNode.getAttribute("data-animation-song-id");
        const animationSongId = toIntegerOrNull(rawAnimationSongId);
        if (Number.isInteger(animationSongId)) {
            songGroupNodeByAnimationSongId.set(animationSongId, groupNode);
        } else {
            warnDroppedIndex("data-animation-song-id", rawAnimationSongId, "invalid-dom-animation-song-id");
        }
    });

    const slideByGlobalIndex = (globalIndex) => {
        if (!Number.isInteger(globalIndex) || globalIndex < 0 || globalIndex >= slides.length) {
            return null;
        }
        return slides[globalIndex] || null;
    };

    const projectionStepByIndex = (projectionIndex) => {
        if (!Number.isInteger(projectionIndex) || projectionIndex < 0 || projectionIndex >= projectionSteps.length) {
            return null;
        }
        return projectionSteps[projectionIndex] || null;
    };

    const getPrimaryRenderable = (projectionStep) => {
        if (!projectionStep || typeof projectionStep !== "object") {
            return null;
        }
        const right = projectionStep.right;
        if (projectionStep.mode === "double" && right && typeof right === "object") {
            return right;
        }
        return projectionStep.left && typeof projectionStep.left === "object" ? projectionStep.left : null;
    };

    const findProjectionIndexBySourceGlobalIndex = (globalIndex) => {
        if (!Number.isInteger(globalIndex)) {
            return null;
        }
        for (let index = 0; index < projectionSteps.length; index += 1) {
            const step = projectionSteps[index];
            if (!step || !Array.isArray(step.sourceGlobalIndexes)) {
                continue;
            }
            if (step.sourceGlobalIndexes.includes(globalIndex)) {
                return index;
            }
        }
        return null;
    };

    const getCurrentSong = () => getSongByIndex(state.selectedSongIndex);

    const getProjectedSongIndex = () => {
        const projectionStep = projectionStepByIndex(state.projectedProjectionIndex);
        if (!projectionStep) {
            return -1;
        }
        const animationSongId = toIntegerOrNull(projectionStep.animationSongId);
        if (!Number.isInteger(animationSongId)) {
            warnDroppedIndex("projectionStep.animationSongId", projectionStep.animationSongId, "invalid-projection-animation-song-id");
            return -1;
        }
        const resolvedSongIndex = songIndexByAnimationSongId.get(animationSongId);
        return Number.isInteger(resolvedSongIndex) ? resolvedSongIndex : -1;
    };

    const getSongSlideIndexes = (songIndex) => {
        const song = getSongByIndex(songIndex);
        if (!song || !Array.isArray(song.slideIndexes)) {
            return [];
        }
        return sanitizeIndexList(song.slideIndexes, {
            context: `songs[${songIndex}].slideIndexes`,
            maxExclusive: slides.length,
        });
    };

    const getSongProjectionIndexes = (songIndex) => {
        const song = getSongByIndex(songIndex);
        if (!song) {
            return [];
        }
        const rawIndexes = Array.isArray(song.projectionIndexes) && song.projectionIndexes.length
            ? song.projectionIndexes
            : getSongSlideIndexes(songIndex);
        return sanitizeIndexList(rawIndexes, {
            context: `songs[${songIndex}].projectionIndexes`,
            maxExclusive: projectionSteps.length,
        });
    };

    const getSongChorusProjectionIndexes = (songIndex) => {
        const song = getSongByIndex(songIndex);
        if (!song || !Array.isArray(song.chorusProjectionIndexes)) {
            return [];
        }
        return sanitizeIndexList(song.chorusProjectionIndexes, {
            context: `songs[${songIndex}].chorusProjectionIndexes`,
            maxExclusive: projectionSteps.length,
        });
    };

    const getPreparedProjectionPosition = (songIndex) => {
        const indexes = getSongProjectionIndexes(songIndex);
        if (!indexes.length) {
            return -1;
        }

        if (!Number.isInteger(state.projectedProjectionIndex)) {
            return -1;
        }

        if (Number.isInteger(state.pendingSongRestartIndex) && state.pendingSongRestartIndex === songIndex) {
            return -1;
        }

        const projectedPosition = indexes.indexOf(state.projectedProjectionIndex);
        if (projectedPosition >= 0) {
            return projectedPosition;
        }

        return -1;
    };

    const persistState = () => {
        const payloadToStore = {
            sessionId: state.sessionId,
            selectedSongIndex: state.selectedSongIndex,
            projectedProjectionIndex: state.projectedProjectionIndex,
            projectedSlideGlobalIndex: (() => {
                const currentStep = projectionStepByIndex(state.projectedProjectionIndex);
                const primarySourceGlobalIndex = currentStep ? toNonNegativeIndexOrNull(currentStep.primarySourceGlobalIndex) : null;
                return Number.isInteger(primarySourceGlobalIndex) ? primarySourceGlobalIndex : null;
            })(),
            blackMode: state.blackMode,
            qrMode: state.qrMode,
            hideChorusesInGrid: state.hideChorusesInGrid,
            blockScrollKeys: state.blockScrollKeys,
            chorusCursorBySong: state.chorusCursorBySong,
            progressCursorBySong: state.progressCursorBySong,
            activeTransitionId: state.activeTransitionId,
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
            const restoredSelectedSongIndex = toIntegerOrNull(parsed.selectedSongIndex);
            const legacySelectedSongIndex = toIntegerOrNull(parsed.currentSongIndex);
            if (Number.isInteger(restoredSelectedSongIndex)) {
                state.selectedSongIndex = normalizeSongIndex(restoredSelectedSongIndex);
            } else if (Number.isInteger(legacySelectedSongIndex)) {
                state.selectedSongIndex = normalizeSongIndex(legacySelectedSongIndex);
            }
            const restoredProjectedProjectionIndex = toNonNegativeIndexOrNull(parsed.projectedProjectionIndex);
            const restoredProjectedSlideIndex = toNonNegativeIndexOrNull(parsed.projectedSlideGlobalIndex);
            const legacyProjectedSlideIndex = toNonNegativeIndexOrNull(parsed.currentSlideGlobalIndex);
            if (Number.isInteger(restoredProjectedProjectionIndex)) {
                state.projectedProjectionIndex = restoredProjectedProjectionIndex;
            } else if (Number.isInteger(restoredProjectedSlideIndex)) {
                state.projectedProjectionIndex = findProjectionIndexBySourceGlobalIndex(restoredProjectedSlideIndex);
            } else if (Number.isInteger(legacyProjectedSlideIndex)) {
                state.projectedProjectionIndex = findProjectionIndexBySourceGlobalIndex(legacyProjectedSlideIndex);
            }
            state.blackMode = Boolean(parsed.blackMode);
            state.qrMode = Boolean(parsed.qrMode);
            state.hideChorusesInGrid = Boolean(parsed.hideChorusesInGrid);
            state.blockScrollKeys = Boolean(parsed.blockScrollKeys);
            state.activeTransitionId = resolveTransitionId(parsed.activeTransitionId);
            if (parsed.chorusCursorBySong && typeof parsed.chorusCursorBySong === "object") {
                state.chorusCursorBySong = parsed.chorusCursorBySong;
            }
            if (parsed.progressCursorBySong && typeof parsed.progressCursorBySong === "object") {
                state.progressCursorBySong = parsed.progressCursorBySong;
            }
        } catch (_error) {
            // Ignore localStorage parsing errors.
        }
    };

    const normalizeState = () => {
        state.selectedSongIndex = normalizeSongIndex(state.selectedSongIndex);
        const currentProjectionStep = projectionStepByIndex(state.projectedProjectionIndex);
        if (!currentProjectionStep) {
            state.projectedProjectionIndex = null;
        }
        if (state.blackMode) {
            state.qrMode = false;
        }
        state.activeTransitionId = resolveTransitionId(state.activeTransitionId);
        const projectedSongIndex = getProjectedSongIndex();
        if (projectedSongIndex >= 0) {
            const indexes = getSongProjectionIndexes(projectedSongIndex);
            const projectedPosition = indexes.indexOf(state.projectedProjectionIndex);
            if (projectedPosition >= 0) {
                state.progressCursorBySong[String(projectedSongIndex)] = projectedPosition;
            }
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
        if (state.f11ReminderActive) {
            return { mode: "f11-reminder" };
        }
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

        const projectionStep = projectionStepByIndex(state.projectedProjectionIndex);
        if (!projectionStep) {
            return { mode: "idle" };
        }

        return {
            mode: "slide",
            songTitle: String(projectionStep.songTitle || ""),
            projectionStep,
        };
    };

    const sendInit = () => {
        sendBridgeMessage({
            type: "init",
            animationId,
            frame: frameFromState(),
            transition: transitionFromState(),
        });
    };

    const sendFrame = () => {
        sendBridgeMessage({
            type: "frame",
            animationId,
            frame: frameFromState(),
            transition: transitionFromState(),
        });
    };

    const sendF11ReminderFrame = () => {
        const reminderFrame = { mode: "f11-reminder" };
        sendBridgeMessage({
            type: "init",
            animationId,
            frame: reminderFrame,
            transition: transitionFromState(),
        });
        sendBridgeMessage({
            type: "frame",
            animationId,
            frame: reminderFrame,
            transition: transitionFromState(),
        });
    };

    const sendHeartbeat = () => {
        sendBridgeMessage({
            type: "heartbeat",
            animationId,
            frame: frameFromState(),
        });
    };

    const setCurrentSong = (songIndex) => {
        if (!Number.isInteger(songIndex) || songIndex < 0 || songIndex >= songs.length) {
            return;
        }
        state.selectedSongIndex = songIndex;
        state.pendingSongRestartIndex = songIndex;
        persistState();
        refreshUI();
    };

    const projectProjectionStep = (projectionIndex, options = {}) => {
        const projectionStep = projectionStepByIndex(projectionIndex);
        if (!projectionStep) {
            warnDroppedIndex("projectProjectionStep", projectionIndex, "unknown-projection-step");
            return;
        }
        const preserveProgress = Boolean(options.preserveProgress);
        const updateSelected = options.updateSelected !== false;
        const animationSongId = toIntegerOrNull(projectionStep.animationSongId);
        const resolvedSongIndex = Number.isInteger(animationSongId)
            ? songIndexByAnimationSongId.get(animationSongId)
            : null;
        if (updateSelected && Number.isInteger(resolvedSongIndex)) {
            state.selectedSongIndex = resolvedSongIndex;
        }
        state.projectedProjectionIndex = projectionIndex;
        state.blackMode = false;
        state.qrMode = false;
        state.f11ReminderActive = false;
        if (Number.isInteger(resolvedSongIndex) && state.pendingSongRestartIndex === resolvedSongIndex) {
            state.pendingSongRestartIndex = null;
        }
        if (!preserveProgress && Number.isInteger(resolvedSongIndex)) {
            const indexes = getSongProjectionIndexes(resolvedSongIndex);
            const projectedPosition = indexes.indexOf(projectionIndex);
            if (projectedPosition >= 0) {
                state.progressCursorBySong[String(resolvedSongIndex)] = projectedPosition;
            }
        }
        persistState();
        refreshUI();
        sendFrame();
    };

    const navigateSlide = (direction) => {
        const indexes = getSongProjectionIndexes(state.selectedSongIndex);
        if (!indexes.length) {
            return;
        }

        const currentPosition = getPreparedProjectionPosition(state.selectedSongIndex);
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
        state.progressCursorBySong[String(state.selectedSongIndex)] = nextPosition;
        const targetProjectionIndex = indexes[nextPosition];
        if (!Number.isInteger(targetProjectionIndex)) {
            warnDroppedIndex("navigateSlide.targetProjectionIndex", targetProjectionIndex, "invalid-target-index");
            return;
        }
        projectProjectionStep(targetProjectionIndex, { preserveProgress: true, updateSelected: false });
    };

    const navigateChorus = () => {
        const chorusIndexes = getSongChorusProjectionIndexes(state.selectedSongIndex);
        if (!chorusIndexes.length) {
            return;
        }

        const currentProjectionStep = projectionStepByIndex(state.projectedProjectionIndex);
        const currentSong = getCurrentSong();
        const currentProjectionAnimationSongId = currentProjectionStep ? toIntegerOrNull(currentProjectionStep.animationSongId) : null;
        const selectedAnimationSongId = currentSong ? toIntegerOrNull(currentSong.animationSongId) : null;
        const isProjectedFromSelectedSong = currentProjectionAnimationSongId === selectedAnimationSongId;
        const projectedChorusPosition = isProjectedFromSelectedSong
            ? chorusIndexes.indexOf(state.projectedProjectionIndex)
            : -1;

        let targetPosition = 0;
        if (projectedChorusPosition >= 0) {
            targetPosition = (projectedChorusPosition + 1) % chorusIndexes.length;
        }

        const targetIndex = chorusIndexes[targetPosition];
        if (!Number.isInteger(targetIndex)) {
            warnDroppedIndex("navigateChorus.targetIndex", targetIndex, "invalid-target-index");
            return;
        }
        state.chorusCursorBySong[String(state.selectedSongIndex)] = (targetPosition + 1) % chorusIndexes.length;
        projectProjectionStep(targetIndex, { preserveProgress: true, updateSelected: false });
    };

    const toggleBlackMode = () => {
        if (state.blackMode) {
            state.blackMode = false;
            state.qrMode = false;
        } else {
            state.blackMode = true;
            state.qrMode = false;
        }
        state.f11ReminderActive = false;
        persistState();
        refreshUI();
        sendFrame();
    };

    const toggleQrMode = () => {
        if (state.qrMode) {
            state.qrMode = false;
            state.blackMode = false;
        } else {
            state.qrMode = true;
            state.blackMode = false;
        }
        state.f11ReminderActive = false;
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

    const formatProjectionStepLabel = (projectionStep) => {
        if (!projectionStep) {
            return label("noneLabel");
        }
        const leftLabel = formatSlideLabel(projectionStep.left);
        if (projectionStep.mode !== "double" || !projectionStep.right) {
            return leftLabel;
        }
        const rightLabel = formatSlideLabel(projectionStep.right);
        return `${leftLabel} | ${rightLabel}`;
    };

    const formatProjectionStepPreviewText = (projectionStep) => {
        if (!projectionStep) {
            return label("nextSlidePlaceholder");
        }
        const leftText = String(projectionStep.left?.text || "");
        if (projectionStep.mode !== "double" || !projectionStep.right) {
            return leftText;
        }
        const rightText = String(projectionStep.right.text || "");
        return [leftText, rightText].filter(Boolean).join("\n\n");
    };

    const setText = (node, text) => {
        if (node instanceof HTMLElement) {
            node.textContent = text;
        }
    };

    const getToolbarScrollOffset = () => {
        if (!(toolbarNode instanceof HTMLElement)) {
            return 0;
        }
        const toolbarHeight = toolbarNode.getBoundingClientRect().height;
        return Math.max(0, Math.ceil(toolbarHeight + 8));
    };

    const scrollToElementWithToolbarOffset = (targetNode) => {
        if (!(targetNode instanceof HTMLElement)) {
            return;
        }
        const scrollTop = window.scrollY + targetNode.getBoundingClientRect().top - getToolbarScrollOffset();
        window.scrollTo({
            top: Math.max(0, Math.floor(scrollTop)),
            behavior: "smooth",
        });
    };

    const trimFloatingSongLabel = (songIndex, rawTitle) => {
        const title = String(rawTitle || "").trim();
        const prefix = `${songIndex + 1}. `;
        if (!title) {
            return `${prefix}${label("noneLabel")}`;
        }
        if (title.length <= 10) {
            return `${prefix}${title}`;
        }
        return `${prefix}${title.slice(0, 10)}…`;
    };

    const clampFloatingWindowStart = (candidateStart) => {
        const maxStart = Math.max(0, songs.length - floatingSongWindowSize);
        if (candidateStart <= 0) {
            return 0;
        }
        if (candidateStart >= maxStart) {
            return maxStart;
        }
        return candidateStart;
    };

    const renderFloatingSongLinks = () => {
        if (!(floatingSongLinksNode instanceof HTMLElement)) {
            return;
        }

        const hasWindowNavigation = songs.length > floatingSongWindowSize;
        floatingSongWindowStart = hasWindowNavigation ? clampFloatingWindowStart(floatingSongWindowStart) : 0;

        if (floatingUpButtonNode instanceof HTMLButtonElement) {
            if (hasWindowNavigation) {
                floatingUpButtonNode.removeAttribute("hidden");
            } else {
                floatingUpButtonNode.setAttribute("hidden", "hidden");
            }
            floatingUpButtonNode.disabled = !hasWindowNavigation || floatingSongWindowStart === 0;
        }
        if (floatingDownButtonNode instanceof HTMLButtonElement) {
            const maxStart = clampFloatingWindowStart(Number.MAX_SAFE_INTEGER);
            if (hasWindowNavigation) {
                floatingDownButtonNode.removeAttribute("hidden");
            } else {
                floatingDownButtonNode.setAttribute("hidden", "hidden");
            }
            floatingDownButtonNode.disabled = !hasWindowNavigation || floatingSongWindowStart >= maxStart;
        }

        const songsStart = floatingSongWindowStart;
        const songsEnd = Math.min(songsStart + floatingSongWindowSize, songs.length);
        const fragment = document.createDocumentFragment();

        for (let songIndex = songsStart; songIndex < songsEnd; songIndex += 1) {
            const song = getSongByIndex(songIndex);
            if (!song) {
                continue;
            }
            const animationSongId = toIntegerOrNull(song.animationSongId);
            if (!Number.isInteger(animationSongId)) {
                warnDroppedIndex(`songs[${songIndex}].animationSongId`, song.animationSongId, "invalid-floating-link-animation-song-id");
                continue;
            }
            const targetNode = songGroupNodeByAnimationSongId.get(animationSongId);
            if (!(targetNode instanceof HTMLElement)) {
                continue;
            }

            const link = document.createElement("a");
            link.href = `#lyrics-song-group-${animationSongId}`;
            link.className = "site-floating-action lyrics-master-floating-song-link";
            link.textContent = trimFloatingSongLabel(songIndex, song.songTitle);
            link.dataset.songIndex = String(songIndex);
            link.addEventListener("click", (event) => {
                event.preventDefault();
                setCurrentSong(songIndex);
                scrollToElementWithToolbarOffset(targetNode);
            });
            fragment.appendChild(link);
        }

        floatingSongLinksNode.replaceChildren(fragment);
    };

    const refreshFloatingSongSelection = () => {
        if (!(floatingSongLinksNode instanceof HTMLElement)) {
            return;
        }
        const selectedSongIndex = String(state.selectedSongIndex);
        floatingSongLinksNode.querySelectorAll("[data-song-index]").forEach((linkNode) => {
            if (!(linkNode instanceof HTMLElement)) {
                return;
            }
            const rawSongIndex = linkNode.getAttribute("data-song-index");
            const parsedSongIndex = toNonNegativeIndexOrNull(rawSongIndex);
            const isCurrent = Number.isInteger(parsedSongIndex) && String(parsedSongIndex) === selectedSongIndex;
            if (rawSongIndex !== null && !Number.isInteger(parsedSongIndex)) {
                warnDroppedIndex("data-song-index", rawSongIndex, "invalid-floating-song-index");
            }
            linkNode.classList.toggle("is-current-song", isCurrent);
            if (isCurrent) {
                linkNode.setAttribute("aria-current", "true");
            } else {
                linkNode.removeAttribute("aria-current");
            }
        });
    };

    const refreshPreview = () => {
        const currentProjectionStep = projectionStepByIndex(state.projectedProjectionIndex);
        const songIndexes = getSongProjectionIndexes(state.selectedSongIndex);
        let nextProjectionStep = null;
        let nextProjectionIndex = null;

        if (songIndexes.length) {
            const preparedPosition = getPreparedProjectionPosition(state.selectedSongIndex);
            if (preparedPosition < 0) {
                nextProjectionIndex = songIndexes[0];
                nextProjectionStep = projectionStepByIndex(nextProjectionIndex);
            } else {
                nextProjectionIndex = songIndexes[(preparedPosition + 1) % songIndexes.length];
                nextProjectionStep = projectionStepByIndex(nextProjectionIndex);
            }
        }

        setText(
            previewCurrentLabelNode,
            currentProjectionStep
                ? formatProjectionStepLabel(currentProjectionStep)
                : label("currentSlidePlaceholder"),
        );
        setText(
            previewCurrentTextNode,
            currentProjectionStep
                ? formatProjectionStepPreviewText(currentProjectionStep)
                : label("currentSlidePlaceholder"),
        );
        setText(
            previewNextLabelNode,
            nextProjectionStep
                ? formatProjectionStepLabel(nextProjectionStep)
                : label("nextSlidePlaceholder"),
        );
        setText(
            previewNextTextNode,
            nextProjectionStep
                ? formatProjectionStepPreviewText(nextProjectionStep)
                : label("nextSlidePlaceholder"),
        );

        if (previewCurrentPanelNode instanceof HTMLElement) {
            if (Number.isInteger(state.projectedProjectionIndex)) {
                previewCurrentPanelNode.dataset.targetProjectionIndex = String(state.projectedProjectionIndex);
                previewCurrentPanelNode.classList.remove("is-disabled");
                previewCurrentPanelNode.setAttribute("aria-disabled", "false");
            } else {
                delete previewCurrentPanelNode.dataset.targetProjectionIndex;
                previewCurrentPanelNode.classList.add("is-disabled");
                previewCurrentPanelNode.setAttribute("aria-disabled", "true");
            }
        }

        if (previewNextPanelNode instanceof HTMLElement) {
            if (Number.isInteger(nextProjectionIndex)) {
                previewNextPanelNode.dataset.targetProjectionIndex = String(nextProjectionIndex);
                previewNextPanelNode.classList.remove("is-disabled");
                previewNextPanelNode.setAttribute("aria-disabled", "false");
            } else {
                delete previewNextPanelNode.dataset.targetProjectionIndex;
                previewNextPanelNode.classList.add("is-disabled");
                previewNextPanelNode.setAttribute("aria-disabled", "true");
            }
        }
    };

    const refreshSongNavigationLabels = () => {
        const hasPrev = state.selectedSongIndex > 0;
        const hasNext = state.selectedSongIndex < songs.length - 1;
        const prevSong = hasPrev ? getSongByIndex(state.selectedSongIndex - 1) : null;
        const nextSong = hasNext ? getSongByIndex(state.selectedSongIndex + 1) : null;

        setText(prevSongTitleNode, prevSong ? String(prevSong.songTitle || "") : label("noneLabel"));
        setText(nextSongTitleNode, nextSong ? String(nextSong.songTitle || "") : label("noneLabel"));
        if (prevSongButton instanceof HTMLButtonElement) {
            prevSongButton.disabled = !hasPrev;
        }
        if (nextSongButton instanceof HTMLButtonElement) {
            nextSongButton.disabled = !hasNext;
        }
    };

    const refreshSelectionStyles = () => {
        slideCards.forEach((card) => {
            if (!(card instanceof HTMLElement)) {
                return;
            }
            const rawProjectionIndex = card.getAttribute("data-projection-index");
            const projectionIndex = toNonNegativeIndexOrNull(rawProjectionIndex);
            const isActive = Number.isInteger(state.projectedProjectionIndex) && projectionIndex === state.projectedProjectionIndex;
            card.classList.toggle("is-active", isActive);
            if (rawProjectionIndex !== null && !Number.isInteger(projectionIndex)) {
                warnDroppedIndex("data-projection-index", rawProjectionIndex, "invalid-slide-card-projection-index");
            }

            const kind = String(card.getAttribute("data-kind") || "");
            const hide = state.hideChorusesInGrid && kind === "chorus";
            card.hidden = hide;
        });

        document.querySelectorAll("[data-lyrics-song-group]").forEach((groupNode) => {
            if (!(groupNode instanceof HTMLElement)) {
                return;
            }
            const rawAnimationSongId = groupNode.getAttribute("data-animation-song-id");
            const asid = toIntegerOrNull(rawAnimationSongId);
            const songIndex = songIndexByAnimationSongId.get(asid);
            groupNode.classList.toggle("is-current-song", Number.isInteger(songIndex) && songIndex === state.selectedSongIndex);
            if (rawAnimationSongId !== null && !Number.isInteger(asid)) {
                warnDroppedIndex("data-animation-song-id", rawAnimationSongId, "invalid-song-group-animation-song-id");
            }
        });
    };

    const refreshSummary = () => {
        const projectedSongIndex = getProjectedSongIndex();
        const projectedSong = projectedSongIndex >= 0 ? getSongByIndex(projectedSongIndex) : null;
        const selectedSong = getCurrentSong();
        setText(songTitleNode, projectedSong ? String(projectedSong.songTitle || "") : selectedSong ? String(selectedSong.songTitle || "") : label("noneLabel"));
        setText(displaySessionNode, state.sessionId);

        const currentProjectionStep = projectionStepByIndex(state.projectedProjectionIndex);
        setText(
            slideLabelNode,
            currentProjectionStep ? formatProjectionStepLabel(currentProjectionStep) : label("noneLabel"),
        );

        setText(chorusVisibilityNode, state.hideChorusesInGrid ? label("hiddenChorusLabel") : "");
        setText(scrollModeNode, state.blockScrollKeys ? label("scrollLockedLabel") : label("scrollUnlockedLabel"));
    };

    const refreshToggleButtons = () => {
        setText(scrollToggleEmojiNode, state.blockScrollKeys ? label("scrollStopEmoji") : label("scrollAllowEmoji"));
        setText(scrollToggleTextNode, state.blockScrollKeys ? label("scrollStopText") : label("scrollAllowText"));
        setText(chorusToggleEmojiNode, state.hideChorusesInGrid ? label("chorusHideEmoji") : label("chorusShowEmoji"));
        setText(chorusToggleTextNode, state.hideChorusesInGrid ? label("chorusHideText") : label("chorusShowText"));
        if (blackModeButtonNode instanceof HTMLElement) {
            blackModeButtonNode.classList.toggle("is-alert-active", state.blackMode);
            blackModeButtonNode.setAttribute("aria-pressed", state.blackMode ? "true" : "false");
        }
        if (qrToggleButtonNode instanceof HTMLElement) {
            qrToggleButtonNode.classList.toggle("is-alert-active", state.qrMode);
            qrToggleButtonNode.setAttribute("aria-pressed", state.qrMode ? "true" : "false");
        }
        if (blackoutFrameNode instanceof HTMLElement) {
            blackoutFrameNode.classList.toggle("is-visible", state.blackMode);
        }
    };

    const refreshQrButton = () => {
        const hasQrCode = Boolean(qrCodePngBase64);
        if (qrButtonImageNode instanceof HTMLImageElement) {
            if (hasQrCode) {
                qrButtonImageNode.src = `data:image/png;base64,${qrCodePngBase64}`;
                qrButtonImageNode.hidden = false;
            } else {
                qrButtonImageNode.hidden = true;
                qrButtonImageNode.removeAttribute("src");
            }
        }
        if (qrFallbackEmojiNode instanceof HTMLElement) {
            qrFallbackEmojiNode.hidden = hasQrCode;
        }
        if (qrFallbackTextNode instanceof HTMLElement) {
            qrFallbackTextNode.hidden = hasQrCode;
        }
    };

    const refreshTransitionControl = () => {
        if (!(transitionSelectNode instanceof HTMLSelectElement)) {
            return;
        }
        const activeTransitionId = resolveTransitionId(state.activeTransitionId);
        if (transitionSelectNode.value !== activeTransitionId) {
            transitionSelectNode.value = activeTransitionId;
        }
    };

    const refreshUI = () => {
        refreshSongNavigationLabels();
        refreshSelectionStyles();
        refreshSummary();
        refreshPreview();
        refreshToggleButtons();
        refreshQrButton();
        refreshTransitionControl();
        refreshFloatingSongSelection();
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

    const openShortcutsGuestInfoPopup = async () => {
        await maybeShowPopup(
            label("shortcutsGuestCustomizeTitle"),
            label("shortcutsGuestCustomizeMessage"),
        );
    };

    const buildShortcutFormFields = () => {
        const actionOrder = Array.isArray(state.shortcuts.actionOrder) ? state.shortcuts.actionOrder : [];
        return actionOrder.map((action) => ({
            id: action,
            label: String(shortcutActionLabels[action] || action),
            type: "shortcut-slots",
            value: serializeBindingsForField(state.shortcuts.formBindings?.[action]),
            emptySlotLabel: "",
            captureSlotLabel: label("shortcutsCaptureLabel"),
            clearSlotLabel: label("shortcutsClearSlotLabel"),
            required: false,
        }));
    };

    const saveShortcutBindings = async (values, options = {}) => {
        const endpoint = String(state.shortcuts.customizeUrl || "").trim();
        const csrfToken = getCsrfToken();
        if (!endpoint || !csrfToken) {
            throw new Error("Missing shortcut customization endpoint.");
        }
        const body = new URLSearchParams();
        const actionOrder = Array.isArray(state.shortcuts.actionOrder) ? state.shortcuts.actionOrder : [];
        actionOrder.forEach((action) => {
            body.set(action, String(values?.[action] || ""));
        });
        if (options.useSiteDefaults) {
            body.set("use_site_defaults", "1");
        }
        const response = await fetch(endpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-CSRFToken": csrfToken,
                "X-Requested-With": "XMLHttpRequest",
            },
            body: body.toString(),
        });
        if (!response.ok) {
            throw new Error("Unable to save shortcut bindings.");
        }
        return await response.json();
    };

    const openCustomizeShortcutsPopup = async () => {
        if (!messageBox || typeof messageBox.show !== "function") {
            return;
        }

        await messageBox.show({
            title: label("shortcutsCustomizeTitle"),
            messageMarkdown: label("shortcutsCustomizeHelp"),
            size: "wide",
            showCloseButton: true,
            buttons: [
                {
                    id: "save",
                    label: label("shortcutsSaveLabel"),
                    tone: "success",
                    validate: false,
                    onClick: async ({ values, keepOpen, setFieldError, setFieldValue }) => {
                        keepOpen();
                        clearCustomizationPopupFieldErrors();
                        setCustomizationPopupFeedback("");
                        try {
                            const siteDefaultFieldValues = buildSiteDefaultFieldValues();
                            const useSiteDefaults = Object.keys(siteDefaultFieldValues).every(
                                (action) => String(values?.[action] || "").trim() === String(siteDefaultFieldValues[action] || "").trim(),
                            );
                            const payloadValue = await saveShortcutBindings(values, { useSiteDefaults });
                            updateShortcutStateFromPayload(payloadValue);
                            const actionOrder = Array.isArray(state.shortcuts.actionOrder) ? state.shortcuts.actionOrder : [];
                            actionOrder.forEach((action) => {
                                setFieldValue(action, serializeBindingsForField(state.shortcuts.formBindings?.[action]));
                            });
                            const fieldErrors = payloadValue && typeof payloadValue === "object" && payloadValue.fieldErrors
                                ? payloadValue.fieldErrors
                                : {};
                            const hasFieldErrors = Object.keys(fieldErrors).length > 0;
                            Object.entries(fieldErrors).forEach(([fieldId, message]) => {
                                setFieldError(fieldId, String(message || ""));
                            });
                            setCustomizationPopupFeedback(
                                String(payloadValue?.globalMessage || ""),
                                hasFieldErrors,
                            );
                            if (!hasFieldErrors) {
                                state.shortcuts.formBindings = normalizeBindingsMap(state.shortcuts.formBindings);
                                window.LSSMessageBox.close({
                                    shortcutsSaved: true,
                                });
                            }
                            return false;
                        } catch (_error) {
                            setCustomizationPopupFeedback(label("shortcutsSaveFailedMessage"), true);
                            return false;
                        }
                    },
                },
                {
                    id: "reset",
                    label: label("shortcutsResetLabel"),
                    tone: "warning",
                    validate: false,
                    onClick: ({ keepOpen, setFieldValue }) => {
                        keepOpen();
                        clearCustomizationPopupFieldErrors();
                        setCustomizationPopupFeedback("");
                        const siteFieldValues = buildSiteDefaultFieldValues();
                        const actionOrder = Array.isArray(state.shortcuts.actionOrder) ? state.shortcuts.actionOrder : [];
                        actionOrder.forEach((action) => {
                            setFieldValue(action, String(siteFieldValues[action] || ""));
                        });
                        return false;
                    },
                },
                {
                    id: "cancel",
                    label: label("shortcutsCancelLabel"),
                    tone: "neutral",
                    validate: false,
                },
            ],
            fields: buildShortcutFormFields(),
        });
    };

    const openShortcutsHelpPopup = async () => {
        if (!messageBox || typeof messageBox.show !== "function") {
            return;
        }

        const result = await messageBox.show({
            title: label("shortcutsPopupTitle"),
            messageMarkdown: buildShortcutHelpMarkdown(),
            showCloseButton: true,
            size: "wide",
            buttons: [
                {
                    id: "customize",
                    label: label("shortcutsCustomizeButtonLabel"),
                    tone: "success",
                    validate: false,
                },
                { id: "ok", label: label("okLabel"), tone: "neutral", validate: false },
            ],
        });
        if (result.buttonId !== "customize") {
            return;
        }
        if (!state.shortcuts.canCustomizeShortcuts) {
            await openShortcutsGuestInfoPopup();
            return;
        }
        await openCustomizeShortcutsPopup();
    };

    const openDisplayWindow = async () => {
        if (!displayUrlBase) {
            return;
        }
        const query = new URLSearchParams({ session: state.sessionId, remind: "1" });
        const targetUrl = `${displayUrlBase}?${query.toString()}`;
        const windowName = `LSSLyricsDisplay-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
        const popupFeatures = "popup=yes,width=1280,height=720,left=80,top=40,resizable=yes,scrollbars=no";
        const openedWindow = window.open(targetUrl, windowName, popupFeatures);
        if (!openedWindow) {
            await maybeShowPopup(label("popupBlockedTitle"), label("popupBlockedMessage"));
            return;
        }
        state.blockScrollKeys = true;
        state.f11ReminderActive = true;
        persistState();
        refreshUI();
        sendF11ReminderFrame();
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
            await openShortcutsHelpPopup();
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
            setCurrentSong(state.selectedSongIndex - 1);
            return;
        }
        if (action === "next-song") {
            setCurrentSong(state.selectedSongIndex + 1);
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
            return;
        }
        if (action === "next-transition") {
            cycleTransition();
            return;
        }
        if (action === "force-direct") {
            setActiveTransition("direct");
        }
    };

    document.querySelectorAll("[data-lyrics-action]").forEach((button) => {
        button.addEventListener("click", async () => {
            const action = String(button.getAttribute("data-lyrics-action") || "");
            await handleAction(action);
        });
    });
    if (transitionSelectNode instanceof HTMLSelectElement) {
        transitionSelectNode.addEventListener("change", () => {
            setActiveTransition(transitionSelectNode.value);
        });
    }

    slideCards.forEach((card) => {
        card.addEventListener("click", () => {
            const rawProjectionIndex = card.getAttribute("data-projection-index");
            const projectionIndex = toNonNegativeIndexOrNull(rawProjectionIndex);
            if (!Number.isInteger(projectionIndex)) {
                warnDroppedIndex("slide-card-click", rawProjectionIndex, "invalid-projection-index");
                return;
            }
            projectProjectionStep(projectionIndex);
        });
    });

    const activatePreviewPanel = (panelNode) => {
        if (!(panelNode instanceof HTMLElement)) {
            return;
        }
        const projectionIndex = toNonNegativeIndexOrNull(panelNode.dataset.targetProjectionIndex);
        if (!Number.isInteger(projectionIndex)) {
            warnDroppedIndex("preview-panel-target", panelNode.dataset.targetProjectionIndex, "invalid-projection-index");
            return;
        }
        projectProjectionStep(projectionIndex, { preserveProgress: true });
    };

    [previewCurrentPanelNode, previewNextPanelNode].forEach((panelNode) => {
        if (!(panelNode instanceof HTMLElement)) {
            return;
        }
        panelNode.addEventListener("click", () => {
            activatePreviewPanel(panelNode);
        });
        panelNode.addEventListener("keydown", (event) => {
            const key = String(event.key || "").toLowerCase();
            if (key !== "enter" && key !== " ") {
                return;
            }
            event.preventDefault();
            activatePreviewPanel(panelNode);
        });
    });

    if (floatingNavNode instanceof HTMLElement) {
        floatingNavNode.hidden = songs.length === 0;
    }
    if (floatingSlidesLinkNode instanceof HTMLElement) {
        floatingSlidesLinkNode.addEventListener("click", (event) => {
            event.preventDefault();
            const targetNode = previewsCardNode instanceof HTMLElement
                ? previewsCardNode
                : slidesAnchorNode instanceof HTMLElement
                    ? slidesAnchorNode
                    : null;
            scrollToElementWithToolbarOffset(targetNode);
        });
    }
    if (floatingUpButtonNode instanceof HTMLButtonElement) {
        floatingUpButtonNode.addEventListener("click", () => {
            floatingSongWindowStart = clampFloatingWindowStart(floatingSongWindowStart - floatingSongWindowStep);
            renderFloatingSongLinks();
            refreshFloatingSongSelection();
        });
    }
    if (floatingDownButtonNode instanceof HTMLButtonElement) {
        floatingDownButtonNode.addEventListener("click", () => {
            floatingSongWindowStart = clampFloatingWindowStart(floatingSongWindowStart + floatingSongWindowStep);
            renderFloatingSongLinks();
            refreshFloatingSongSelection();
        });
    }

    const shouldIgnoreKeydownTarget = (target) => {
        if (!(target instanceof HTMLElement)) {
            return false;
        }
        if (target.isContentEditable) {
            return true;
        }
        const popupRoot = target.closest("#lss-messagebox-root");
        if (popupRoot instanceof HTMLElement && !popupRoot.hidden) {
            return true;
        }
        const tagName = target.tagName.toLowerCase();
        if (["input", "textarea", "select"].includes(tagName)) {
            return true;
        }
        if (tagName === "button") {
            return !Boolean(target.closest("[data-lyrics-master-root]"));
        }
        return false;
    };

    const keydownHandler = async (event) => {
        if (shouldIgnoreKeydownTarget(event.target)) {
            return;
        }

        const key = normalizeShortcutToken(event.key || "");
        const scrollBlockKeys = [
            "arrowup",
            "arrowdown",
            "arrowleft",
            "arrowright",
            "space",
            "pageup",
            "pagedown",
        ];
        if (state.blockScrollKeys && scrollBlockKeys.includes(key)) {
            event.preventDefault();
        }

        const actionByKey = buildShortcutActionIndex();
        const resolvedAction = actionByKey.get(key);
        if (resolvedAction) {
            await handleAction(resolvedAction);
        }
    };

    window.addEventListener("keydown", (event) => {
        void keydownHandler(event);
    }, { passive: false });

    state.shortcuts.siteBindings = normalizeBindingsMap(state.shortcuts.siteBindings);
    state.shortcuts.effectiveBindings = normalizeBindingsMap(state.shortcuts.effectiveBindings);
    state.shortcuts.formBindings = normalizeBindingsMap(state.shortcuts.formBindings);

    renderTransitionChoices();
    restoreState();
    normalizeState();
    ensureBridge();
    renderFloatingSongLinks();
    refreshUI();
    persistState();
    sendInit();
    sendFrame();

    window.setInterval(() => {
        sendHeartbeat();
    }, 8000);

    void runPreload();
})();
