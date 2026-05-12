(() => {
    const form = document.querySelector("[data-animation-edit-form]");
    if (!(form instanceof HTMLFormElement)) {
        return;
    }

    const messageBox = window.LSSMessageBox;
    if (!messageBox || typeof messageBox.show !== "function") {
        return;
    }

    const i18n = window.LSS_MODIFY_ANIMATION_I18N || {};
    const label = (key) => String(i18n[key] || "");

    const popupDataNode = document.getElementById("lss-modify-animation-data");
    let popupData = {};
    if (popupDataNode && popupDataNode.textContent) {
        try {
            popupData = JSON.parse(popupDataNode.textContent);
        } catch (_error) {
            popupData = {};
        }
    }

    const fontChoices = Array.isArray(popupData.fontChoices) ? popupData.fontChoices : [];
    const fontPreviews = Array.isArray(popupData.fontPreviews) ? popupData.fontPreviews : [];
    const legacySongCatalog = Array.isArray(popupData.songCatalog) ? popupData.songCatalog : [];
    const advancedSongCatalog = Array.isArray(popupData.advancedSongCatalog) ? popupData.advancedSongCatalog : [];
    const favoriteSongCatalog = Array.isArray(popupData.favoriteSongCatalog) ? popupData.favoriteSongCatalog : [];
    const allSongCatalog = Array.isArray(popupData.allSongCatalog) ? popupData.allSongCatalog : legacySongCatalog;
    const canUseMemberSongTabs = Boolean(popupData.canUseMemberSongTabs);

    const hiddenFieldNames = [
        "title",
        "description",
        "scheduled_at",
        "text_color",
        "bg_color",
        "font_family",
        "font_size",
        "horizontal_padding",
        "background_asset_code",
    ];

    const hiddenFields = Object.fromEntries(
        hiddenFieldNames
            .map((name) => [name, document.getElementById(`id_${name}`)])
            .filter((item) => item[1] instanceof HTMLInputElement)
    );

    const orderedMixInput = document.querySelector("[data-animation-ordered-mix]");
    const songsPayloadInput = document.querySelector("[data-animation-songs-payload]");
    const modeToggleButton = document.querySelector("[data-animation-mode-toggle]");
    const mainModePanel = document.querySelector("[data-animation-edit-mode='main']");
    const secondaryModePanel = document.querySelector("[data-animation-edit-mode='secondary']");
    const secondaryList = document.querySelector("[data-animation-secondary-list]");
    const siteMainContent = document.querySelector(".site-main-content");

    let reorderController = null;
    let tempSongCounter = 0;
    let dirty = false;
    let isSubmitting = false;

    const summaryNodes = {
        title: document.querySelector("[data-animation-summary-title]"),
        scheduled: document.querySelector("[data-animation-summary-scheduled]"),
        description: document.querySelector("[data-animation-summary-description]"),
        textDot: document.querySelector("[data-animation-summary-text-dot]"),
        bgDot: document.querySelector("[data-animation-summary-bg-dot]"),
        font: document.querySelector("[data-animation-summary-font]"),
        fontSize: document.querySelector("[data-animation-summary-font-size]"),
        padding: document.querySelector("[data-animation-summary-padding]"),
        live: document.querySelector("[data-animation-summary-live]"),
        preview: document.querySelector("[data-animation-summary-preview]"),
    };

    const initialValues = Object.fromEntries(
        hiddenFieldNames.map((name) => [name, String(hiddenFields[name]?.value || "")])
    );

    const hexPattern = /^#([0-9a-fA-F]{6})$/;
    const fallbackValues = {
        text_color: "#FFFFFF",
        bg_color: "#000000",
        font_family: "Source Sans Pro",
        font_size: 72,
        horizontal_padding: 80,
    };
    const previewFontSizePx = 34;

    const validHex = (value) => {
        const candidate = String(value || "").trim();
        if (!hexPattern.test(candidate)) {
            return null;
        }
        return candidate.toUpperCase();
    };

    const clampNumber = (value, fallback, min, max) => {
        const parsed = Number.parseInt(String(value || ""), 10);
        if (Number.isNaN(parsed)) {
            return fallback;
        }
        return Math.min(max, Math.max(min, parsed));
    };

    const readCurrentValues = () => {
        return Object.fromEntries(
            hiddenFieldNames.map((name) => [name, String(hiddenFields[name]?.value || "")])
        );
    };

    const writeValues = (values) => {
        hiddenFieldNames.forEach((name) => {
            if (!hiddenFields[name]) {
                return;
            }
            hiddenFields[name].value = String(values[name] ?? "");
        });
    };

    const formatDateTime = (rawValue) => {
        const value = String(rawValue || "").trim();
        if (!value) {
            return "";
        }
        const asDate = new Date(value);
        if (Number.isNaN(asDate.getTime())) {
            return value.replace("T", " ");
        }
        return asDate.toLocaleString("fr-FR", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    const applySummaryPreview = () => {
        const values = readCurrentValues();
        const textColor = validHex(values.text_color) || fallbackValues.text_color;
        const bgColor = validHex(values.bg_color) || fallbackValues.bg_color;
        const fontFamily = String(values.font_family || fallbackValues.font_family).trim() || fallbackValues.font_family;
        const fontSize = clampNumber(values.font_size, fallbackValues.font_size, 10, 300);
        const horizontalPadding = clampNumber(values.horizontal_padding, fallbackValues.horizontal_padding, 0, 600);

        if (summaryNodes.title) {
            summaryNodes.title.textContent = "Test";
        }
        if (summaryNodes.description) {
            summaryNodes.description.textContent = String(values.description || "").trim() || label("noDescriptionLabel");
        }
        if (summaryNodes.scheduled) {
            summaryNodes.scheduled.textContent = formatDateTime(values.scheduled_at);
        }
        if (summaryNodes.textDot) {
            summaryNodes.textDot.style.backgroundColor = textColor;
        }
        if (summaryNodes.bgDot) {
            summaryNodes.bgDot.style.backgroundColor = bgColor;
        }
        if (summaryNodes.font) {
            summaryNodes.font.textContent = fontFamily;
        }
        if (summaryNodes.fontSize) {
            summaryNodes.fontSize.textContent = String(fontSize);
        }
        if (summaryNodes.padding) {
            summaryNodes.padding.textContent = String(horizontalPadding);
        }
        if (summaryNodes.live) {
            summaryNodes.live.style.color = textColor;
            summaryNodes.live.style.fontFamily = `'${fontFamily}', sans-serif`;
            summaryNodes.live.style.fontSize = `${fontSize}px`;
            summaryNodes.live.textContent = "Test";
        }
        if (summaryNodes.preview) {
            summaryNodes.preview.style.background = bgColor;
            summaryNodes.preview.style.paddingLeft = `${horizontalPadding}px`;
            summaryNodes.preview.style.paddingRight = `${horizontalPadding}px`;
        }
    };

    const visualPreviewUpdater = (context) => {
        if (!context || !(context.previewElement instanceof HTMLElement)) {
            return;
        }
        const values = context.values || {};
        const textColor = validHex(values.text_color) || fallbackValues.text_color;
        const bgColor = validHex(values.bg_color) || fallbackValues.bg_color;
        const fontFamily = String(values.font_family || fallbackValues.font_family).trim() || fallbackValues.font_family;
        const fontSize = clampNumber(values.font_size, fallbackValues.font_size, 10, 300);
        const horizontalPadding = clampNumber(values.horizontal_padding, fallbackValues.horizontal_padding, 0, 600);

        context.previewElement.style.color = textColor;
        context.previewElement.style.background = bgColor;
        context.previewElement.style.fontFamily = `'${fontFamily}', sans-serif`;
        context.previewElement.style.fontSize = `${fontSize}px`;
        context.previewElement.style.paddingLeft = `${horizontalPadding}px`;
        context.previewElement.style.paddingRight = `${horizontalPadding}px`;
        context.previewElement.textContent = label("previewText");
    };

    const makeResetButton = (fieldsToReset) => {
        return {
            id: "reset",
            label: label("resetLabel"),
            tone: "warning",
            validate: false,
            onClick: ({ setFieldValue, keepOpen }) => {
                fieldsToReset.forEach((fieldId) => {
                    if (typeof setFieldValue === "function") {
                        setFieldValue(fieldId, initialValues[fieldId] || "");
                    }
                });
                if (typeof keepOpen === "function") {
                    keepOpen();
                }
                return false;
            },
        };
    };

    const openGeneralPopup = async () => {
        const values = readCurrentValues();
        const result = await messageBox.show({
            title: label("generalPopupTitle"),
            showCloseButton: true,
            buttons: [
                { id: "ok", label: label("okLabel"), tone: "success", validate: true },
                { id: "cancel", label: label("cancelLabel"), tone: "warning", validate: false },
                makeResetButton(["title", "description", "scheduled_at"]),
            ],
            fields: [
                {
                    id: "title",
                    label: label("labelTitle"),
                    type: "text",
                    value: values.title,
                    required: true,
                    maxLength: 255,
                },
                {
                    id: "description",
                    label: label("labelDescription"),
                    type: "textarea",
                    value: values.description,
                    rows: 4,
                },
                {
                    id: "scheduled_at",
                    label: label("labelDateTime"),
                    type: "datetime-local",
                    value: values.scheduled_at,
                    required: true,
                },
            ],
            enterButtonId: "ok",
            escapeButtonId: "cancel",
        });

        if (result.buttonId !== "ok") {
            return;
        }

        writeValues({
            ...readCurrentValues(),
            title: String(result.values?.title || "").trim(),
            description: String(result.values?.description || ""),
            scheduled_at: String(result.values?.scheduled_at || "").trim(),
        });
        applySummaryPreview();
        refreshDirtyState();
    };

    const openVisualPopup = async () => {
        const values = readCurrentValues();
        const result = await messageBox.show({
            title: label("visualPopupTitle"),
            showCloseButton: true,
            buttons: [
                { id: "ok", label: label("okLabel"), tone: "success", validate: true },
                { id: "cancel", label: label("cancelLabel"), tone: "warning", validate: false },
                makeResetButton(["text_color", "bg_color", "font_family", "font_size", "horizontal_padding"]),
            ],
            preview: {
                label: label("previewLabel"),
                text: label("previewText"),
                className: "animation-live-preview",
            },
            onFieldChange: visualPreviewUpdater,
            fields: [
                {
                    id: "text_color",
                    label: label("labelTextColor"),
                    type: "color",
                    value: validHex(values.text_color) || fallbackValues.text_color,
                    required: true,
                },
                {
                    id: "bg_color",
                    label: label("labelBgColor"),
                    type: "color",
                    value: validHex(values.bg_color) || fallbackValues.bg_color,
                    required: true,
                },
                {
                    id: "font_family",
                    label: label("labelFontFamily"),
                    type: "select",
                    value: String(values.font_family || ""),
                    required: true,
                    options: fontChoices,
                },
                {
                    id: "font_size",
                    label: label("labelFontSize"),
                    type: "number",
                    value: String(values.font_size || ""),
                    required: true,
                    min: 10,
                    max: 300,
                    step: 1,
                },
                {
                    id: "horizontal_padding",
                    label: label("labelHorizontalPadding"),
                    type: "number",
                    value: String(values.horizontal_padding || ""),
                    required: true,
                    min: 0,
                    max: 600,
                    step: 1,
                },
            ],
            enterButtonId: "ok",
            escapeButtonId: "cancel",
        });

        if (result.buttonId !== "ok") {
            return;
        }

        writeValues({
            ...readCurrentValues(),
            text_color: validHex(result.values?.text_color) || "",
            bg_color: validHex(result.values?.bg_color) || "",
            font_family: String(result.values?.font_family || "").trim(),
            font_size: String(result.values?.font_size || "").trim(),
            horizontal_padding: String(result.values?.horizontal_padding || "").trim(),
        });
        applySummaryPreview();
        refreshAllSongCardPreviews();
        refreshDirtyState();
    };

    const openFontListPopup = async () => {
        await messageBox.show({
            title: label("fontListPopupTitle"),
            fontSamples: fontPreviews,
            showCloseButton: true,
            size: "wide",
            buttons: [{ id: "ok", label: label("okLabel"), tone: "neutral" }],
        });
    };

    const confirmUnsavedChanges = async () => {
        if (!dirty) {
            return true;
        }
        const result = await messageBox.show({
            title: label("unsavedChangesTitle"),
            messageMarkdown: label("unsavedChangesMessage"),
            showCloseButton: true,
            buttons: [
                { id: "yes", label: label("yesLabel"), tone: "danger" },
                { id: "no", label: label("noLabel"), tone: "neutral" },
            ],
            enterButtonId: "no",
            escapeButtonId: "no",
        });
        return result.buttonId === "yes";
    };

    document.querySelectorAll("[data-animation-action]").forEach((button) => {
        button.addEventListener("click", async () => {
            const confirmed = await confirmUnsavedChanges();
            if (!confirmed) {
                return;
            }
            const action = String(button.getAttribute("data-animation-action") || "");
            if (action === "open-general") {
                await openGeneralPopup();
                return;
            }
            if (action === "open-visual") {
                await openVisualPopup();
                return;
            }
            if (action === "open-font-list") {
                await openFontListPopup();
            }
        });
    });

    const getSecondaryItems = () => {
        if (!(secondaryList instanceof HTMLElement)) {
            return [];
        }
        return Array.from(secondaryList.children).filter((node) => {
            return node instanceof HTMLElement && node.matches("[data-animation-song-item]");
        });
    };

    const updateOrderedMix = () => {
        if (!(orderedMixInput instanceof HTMLInputElement)) {
            return;
        }
        const tokens = getSecondaryItems()
            .map((item) => String(item.getAttribute("data-animation-token") || "").trim())
            .filter((token) => /^(asid|sid):\d+$/.test(token));
        orderedMixInput.value = tokens.join("|");
    };

    const countPlaylistSongOccurrences = () => {
        const counts = new Map();
        getSecondaryItems().forEach((item) => {
            const songId = Number.parseInt(String(item.getAttribute("data-animation-song-id") || ""), 10);
            if (Number.isNaN(songId) || songId <= 0) {
                return;
            }
            counts.set(songId, (counts.get(songId) || 0) + 1);
        });
        return counts;
    };

    const buildSongOptionsForPopup = (catalogEntries) => {
        const counts = countPlaylistSongOccurrences();
        return catalogEntries.map((entry) => {
            const songId = Number.parseInt(String(entry.id || ""), 10);
            const title = String(entry.title || "").trim();
            if (Number.isNaN(songId) || songId <= 0 || !title) {
                return null;
            }
            const alreadyChosenCount = counts.get(songId) || 0;
            const suffix = alreadyChosenCount > 0
                ? ` (${label("alreadyInPlaylistLabel")} x${alreadyChosenCount})`
                : "";
            return {
                value: String(songId),
                label: `${title}${suffix}`,
            };
        }).filter((option) => option !== null);
    };

    const normalizeSecondaryItemCompact = (itemElement) => {
        if (!(itemElement instanceof HTMLElement)) {
            return;
        }
        itemElement.classList.add("is-reorder-compact");
        itemElement.querySelectorAll("[data-reorder-drag-view]").forEach((node) => {
            if (node instanceof HTMLElement) {
                node.hidden = false;
            }
        });
        itemElement.querySelectorAll("[data-reorder-normal-view]").forEach((node) => {
            if (node instanceof HTMLElement) {
                node.hidden = true;
            }
        });
    };

    const createSongItemElement = (token, songId, songTitle) => {
        const article = document.createElement("article");
        article.className = "site-theme-card animation-song-secondary-card";
        article.setAttribute("data-animation-song-item", "");
        article.setAttribute("data-animation-token", token);
        article.setAttribute("data-animation-song-id", String(songId));
        article.setAttribute("data-animation-song-title", songTitle);
        article.setAttribute("data-reorder-item", "");

        const uniqueId = token.startsWith("asid:")
            ? token
            : `sid:${songId}:tmp:${tempSongCounter++}`;
        article.setAttribute("data-id", uniqueId);

        const dragView = document.createElement("div");
        dragView.className = "animation-song-secondary-drag-view";
        dragView.setAttribute("data-reorder-drag-view", "");
        dragView.hidden = true;

        const dragHandle = document.createElement("button");
        dragHandle.type = "button";
        dragHandle.className = "animation-tool-button animation-reorder-handle";
        dragHandle.setAttribute("data-reorder-handle", "");
        dragHandle.setAttribute("aria-label", label("moveLabel"));
        dragHandle.textContent = "⋮↕⋮";

        const dragTitle = document.createElement("strong");
        dragTitle.textContent = songTitle;

        const dragRemove = document.createElement("button");
        dragRemove.type = "button";
        dragRemove.className = "animation-danger-action";
        dragRemove.setAttribute("data-animation-song-remove", "");
        dragRemove.textContent = label("removeSongActionLabel");

        dragView.append(dragHandle, dragTitle, dragRemove);

        const normalView = document.createElement("div");
        normalView.className = "animation-song-secondary-normal-view";
        normalView.setAttribute("data-reorder-normal-view", "");
        normalView.hidden = true;

        article.append(dragView, normalView);
        normalizeSecondaryItemCompact(article);
        return article;
    };

    const insertSongAtIndex = (songId, insertIndex) => {
        if (!(secondaryList instanceof HTMLElement)) {
            return;
        }
        const song = allSongCatalog.find((item) => Number.parseInt(String(item.id || ""), 10) === songId);
        if (!song) {
            return;
        }

        const itemElement = createSongItemElement(`sid:${songId}`, songId, String(song.title || ""));
        secondaryList.classList.add("is-reorder-enabled");

        const items = getSecondaryItems();
        if (insertIndex <= 0 || !items.length) {
            secondaryList.insertBefore(itemElement, secondaryList.firstChild);
        } else if (insertIndex >= items.length) {
            secondaryList.appendChild(itemElement);
        } else {
            secondaryList.insertBefore(itemElement, items[insertIndex]);
        }
    };

    const openSongPickerPopup = async (insertIndex) => {
        const tabs = [];
        if (canUseMemberSongTabs) {
            tabs.push({
                id: "advanced",
                label: label("songTabAdvancedLabel"),
                options: buildSongOptionsForPopup(advancedSongCatalog),
            });
            tabs.push({
                id: "favorites",
                label: label("songTabFavoritesLabel"),
                options: buildSongOptionsForPopup(favoriteSongCatalog),
            });
        }
        tabs.push({
            id: "all",
            label: label("songTabAllLabel"),
            options: buildSongOptionsForPopup(allSongCatalog),
        });

        if (!tabs.some((tab) => tab.options.length > 0)) {
            await messageBox.alert({
                title: label("addSongPopupTitle"),
                messageMarkdown: label("noAccessibleSongMessage"),
                showCloseButton: true,
            });
            return;
        }

        const initialTabId = canUseMemberSongTabs ? "advanced" : "all";
        const initialTab = tabs.find((tab) => tab.id === initialTabId) || tabs[0];

        const result = await messageBox.show({
            title: label("addSongPopupTitle"),
            messageMarkdown: label("addSongPopupMessage"),
            showCloseButton: true,
            buttons: [
                { id: "add", label: label("addSongActionLabel"), tone: "success", validate: true },
                { id: "cancel", label: label("cancelLabel"), tone: "warning", validate: false },
            ],
            fields: [
                {
                    id: "song_id",
                    label: label("songChoiceLabel"),
                    type: "select",
                    required: true,
                    size: 10,
                    options: initialTab.options,
                    value: initialTab.options[0]?.value || "",
                },
            ],
            tabbedSelect: {
                fieldId: "song_id",
                fieldLabel: label("songChoiceLabel"),
                size: 10,
                initialTabId,
                submitButtonId: "add",
                tabs: tabs.map((tab) => ({
                    id: tab.id,
                    label: tab.label,
                    options: tab.options,
                    emptyMessage: label("songTabEmptyLabel"),
                })),
            },
            enterButtonId: "add",
            escapeButtonId: "cancel",
        });

        if (result.buttonId !== "add") {
            return;
        }

        const songId = Number.parseInt(String(result.values?.song_id || ""), 10);
        if (Number.isNaN(songId) || songId <= 0) {
            return;
        }
        insertSongAtIndex(songId, insertIndex);
        renderInsertSlots();
        updateOrderedMix();
        refreshDirtyState();
    };

    const buildInsertSlot = (index) => {
        const slot = document.createElement("div");
        slot.className = "animation-insert-slot";
        slot.setAttribute("data-animation-insert-slot", "");
        slot.setAttribute("data-insert-index", String(index));
        slot.innerHTML = `<button type="button" class="animation-insert-slot-button" data-animation-insert-trigger data-insert-index="${index}" aria-label="${label("insertSongLabel")}">➕</button>`;
        return slot;
    };

    function renderInsertSlots() {
        if (!(secondaryList instanceof HTMLElement)) {
            return;
        }
        secondaryList.querySelectorAll("[data-animation-insert-slot]").forEach((slot) => slot.remove());
        const items = getSecondaryItems();
        if (!items.length) {
            secondaryList.appendChild(buildInsertSlot(0));
            return;
        }

        items.forEach((item, index) => {
            secondaryList.insertBefore(buildInsertSlot(index), item);
        });
        secondaryList.appendChild(buildInsertSlot(items.length));
    }

    const updateModeButtonLabel = (mode) => {
        if (!(modeToggleButton instanceof HTMLButtonElement)) {
            return;
        }
        if (mode === "main") {
            modeToggleButton.textContent = String(modeToggleButton.getAttribute("data-mode-secondary-label") || "");
            return;
        }
        modeToggleButton.textContent = String(modeToggleButton.getAttribute("data-mode-main-label") || "");
    };

    const setMode = (mode) => {
        const selectedMode = mode === "secondary" ? "secondary" : "main";
        if (mainModePanel instanceof HTMLElement) {
            mainModePanel.hidden = selectedMode !== "main";
        }
        if (secondaryModePanel instanceof HTMLElement) {
            secondaryModePanel.hidden = selectedMode !== "secondary";
        }
        if (siteMainContent instanceof HTMLElement) {
            siteMainContent.style.display = selectedMode === "secondary" ? "none" : "";
        }
        updateModeButtonLabel(selectedMode);
    };

    const ensureModeOnLoad = () => {
        const hasSongs = getSecondaryItems().length > 0;
        if (hasSongs) {
            setMode("main");
            return;
        }
        setMode("secondary");
    };

    const removeItem = async (item) => {
        if (!(item instanceof HTMLElement)) {
            return;
        }
        const title = item.querySelector("strong")?.textContent || "";
        const result = await messageBox.confirm({
            title: label("removeSongTitle"),
            messageMarkdown: `${label("removeSongMessage")} **${title}**`,
            showCloseButton: false,
            buttons: [
                { id: "yes", label: label("yesLabel"), tone: "danger" },
                { id: "no", label: label("noLabel"), tone: "neutral" },
            ],
        });
        if (result.buttonId !== "yes") {
            return;
        }
        item.remove();
        renderInsertSlots();
        updateOrderedMix();
        refreshDirtyState();
        if (getSecondaryItems().length === 0) {
            setMode("secondary");
        }
    };

    const colorValueOrFallback = (value, fallback) => validHex(value) || fallback;

    const gatherMainSongsPayload = () => {
        const cards = Array.from(document.querySelectorAll("[data-main-song-card]"));
        const items = cards.map((card) => {
            const animationSongId = Number.parseInt(String(card.getAttribute("data-animation-song-id") || ""), 10);
            const songId = Number.parseInt(String(card.getAttribute("data-song-id") || ""), 10);
            const visibleSet = new Set();

            card.querySelectorAll("[data-main-verse-checkbox]").forEach((checkbox) => {
                if (!(checkbox instanceof HTMLInputElement)) {
                    return;
                }
                if (!checkbox.checked) {
                    return;
                }
                const verseId = Number.parseInt(String(checkbox.getAttribute("data-verse-id") || ""), 10);
                if (Number.isNaN(verseId) || verseId <= 0) {
                    return;
                }
                visibleSet.add(verseId);
            });

            const songFontFamily = card.querySelector("[data-song-font-family]");
            const songFontSizeDelta = card.querySelector("[data-song-font-size-delta]");

            const verseStyles = {};
            card.querySelectorAll("[data-main-verse-row]").forEach((row) => {
                if (!(row instanceof HTMLElement)) {
                    return;
                }
                const verseId = Number.parseInt(String(row.getAttribute("data-verse-id") || ""), 10);
                if (Number.isNaN(verseId) || verseId <= 0) {
                    return;
                }
                const verseFontFamily = row.querySelector("[data-verse-font-family]");
                const verseFontSizeDelta = row.querySelector("[data-verse-font-size-delta]");
                verseStyles[String(verseId)] = {
                    font_family_override: String(verseFontFamily?.value || "").trim(),
                    font_size_delta: Number.parseInt(String(verseFontSizeDelta?.value || "0"), 10) || 0,
                    text_color_override: String(row.getAttribute("data-verse-text-color") || "").trim(),
                    bg_color_override: String(row.getAttribute("data-verse-bg-color") || "").trim(),
                };
            });

            return {
                animation_song_id: Number.isNaN(animationSongId) ? 0 : animationSongId,
                song_id: Number.isNaN(songId) ? 0 : songId,
                visible_verse_ids: Array.from(visibleSet).sort((a, b) => a - b),
                song_style: {
                    font_family_override: String(songFontFamily?.value || "").trim(),
                    font_size_delta: Number.parseInt(String(songFontSizeDelta?.value || "0"), 10) || 0,
                    text_color_override: String(card.getAttribute("data-song-text-color") || "").trim(),
                    bg_color_override: String(card.getAttribute("data-song-bg-color") || "").trim(),
                },
                verse_styles: verseStyles,
            };
        }).filter((item) => item.animation_song_id > 0 && item.song_id > 0);

        return { items };
    };

    const updateSongsPayloadInput = () => {
        if (!(songsPayloadInput instanceof HTMLInputElement)) {
            return;
        }
        songsPayloadInput.value = JSON.stringify(gatherMainSongsPayload());
    };

    const getCurrentSnapshot = () => {
        return JSON.stringify({
            fields: readCurrentValues(),
            orderedMix: String(orderedMixInput?.value || ""),
            songsPayload: String(songsPayloadInput?.value || ""),
        });
    };

    let initialSnapshot = getCurrentSnapshot();

    function refreshDirtyState() {
        dirty = getCurrentSnapshot() !== initialSnapshot;
    }

    const readAnimationBaseStyle = () => {
        const values = readCurrentValues();
        return {
            textColor: validHex(values.text_color) || fallbackValues.text_color,
            bgColor: validHex(values.bg_color) || fallbackValues.bg_color,
            fontFamily: String(values.font_family || fallbackValues.font_family).trim() || fallbackValues.font_family,
        };
    };

    const resolveSongEffectiveColors = (card, baseStyle) => {
        return {
            textColor: validHex(card.getAttribute("data-song-text-color")) || baseStyle.textColor,
            bgColor: validHex(card.getAttribute("data-song-bg-color")) || baseStyle.bgColor,
        };
    };

    const resolveVerseEffectiveColors = (row, songColors) => {
        return {
            textColor: validHex(row.getAttribute("data-verse-text-color")) || songColors.textColor,
            bgColor: validHex(row.getAttribute("data-verse-bg-color")) || songColors.bgColor,
        };
    };

    const clearSongColorOverrides = (card) => {
        if (!(card instanceof HTMLElement)) {
            return;
        }
        card.setAttribute("data-song-text-color", "");
        card.setAttribute("data-song-bg-color", "");
    };

    const clearVerseColorOverrides = (row) => {
        if (!(row instanceof HTMLElement)) {
            return;
        }
        row.setAttribute("data-verse-text-color", "");
        row.setAttribute("data-verse-bg-color", "");
    };

    const resetSongStyleToParent = (card) => {
        if (!(card instanceof HTMLElement)) {
            return;
        }
        const songFontFamily = card.querySelector("[data-song-font-family]");
        const songFontSizeDelta = card.querySelector("[data-song-font-size-delta]");
        if (songFontFamily instanceof HTMLSelectElement) {
            songFontFamily.value = "";
        }
        if (songFontSizeDelta instanceof HTMLSelectElement) {
            songFontSizeDelta.value = "0";
        }
        clearSongColorOverrides(card);
    };

    const resetVerseStyleToParent = (row) => {
        if (!(row instanceof HTMLElement)) {
            return;
        }
        const verseFontFamily = row.querySelector("[data-verse-font-family]");
        const verseFontSizeDelta = row.querySelector("[data-verse-font-size-delta]");
        if (verseFontFamily instanceof HTMLSelectElement) {
            verseFontFamily.value = "";
        }
        if (verseFontSizeDelta instanceof HTMLSelectElement) {
            verseFontSizeDelta.value = "0";
        }
        clearVerseColorOverrides(row);
    };

    const confirmParentReset = async () => {
        const result = await messageBox.show({
            title: label("parentResetTitle"),
            messageMarkdown: label("parentResetMessage"),
            showCloseButton: true,
            buttons: [
                { id: "yes", label: label("yesLabel"), tone: "danger" },
                { id: "no", label: label("noLabel"), tone: "neutral" },
            ],
            enterButtonId: "no",
            escapeButtonId: "no",
        });
        return result.buttonId === "yes";
    };

    const applySongCardPreviewStyles = (card) => {
        if (!(card instanceof HTMLElement)) {
            return;
        }

        const baseStyle = readAnimationBaseStyle();
        const songFontSelect = card.querySelector("[data-song-font-family]");
        const songFontFamily = String(songFontSelect?.value || "").trim() || baseStyle.fontFamily;
        const songColors = resolveSongEffectiveColors(card, baseStyle);
        const songTextColor = songColors.textColor;
        const songBgColor = songColors.bgColor;

        const songPreview = card.querySelector("[data-song-style-preview]");
        const songPreviewText = card.querySelector("[data-song-style-preview-text]");
        const songTextSwatch = card.querySelector("[data-song-text-swatch]");
        const songBgSwatch = card.querySelector("[data-song-bg-swatch]");
        if (songPreview instanceof HTMLElement) {
            songPreview.style.background = songBgColor;
        }
        if (songPreviewText instanceof HTMLElement) {
            songPreviewText.style.color = songTextColor;
            songPreviewText.style.fontFamily = `'${songFontFamily}', sans-serif`;
            songPreviewText.style.fontSize = `${previewFontSizePx}px`;
        }
        if (songTextSwatch instanceof HTMLElement) {
            songTextSwatch.style.background = songTextColor;
            songTextSwatch.setAttribute("title", `${label("textColorShortLabel")}: ${songTextColor}`);
        }
        if (songBgSwatch instanceof HTMLElement) {
            songBgSwatch.style.background = songBgColor;
            songBgSwatch.setAttribute("title", `${label("bgColorShortLabel")}: ${songBgColor}`);
        }
        card.querySelectorAll("[data-song-color-parent-trigger][data-color-target-level='song']").forEach((button) => {
            if (!(button instanceof HTMLElement)) {
                return;
            }
            const hasParentDiff = songTextColor !== baseStyle.textColor || songBgColor !== baseStyle.bgColor;
            button.hidden = !hasParentDiff;
        });

        card.querySelectorAll("[data-main-verse-row]").forEach((row) => {
            if (!(row instanceof HTMLElement)) {
                return;
            }
            const verseId = String(row.getAttribute("data-verse-id") || "");
            const verseCheckbox = card.querySelector(
                `[data-main-verse-checkbox][data-verse-id="${verseId}"]`
            );
            const verseFontSelect = row.querySelector("[data-verse-font-family]");
            const verseFontFamily = String(verseFontSelect?.value || "").trim() || songFontFamily;
            const verseColors = resolveVerseEffectiveColors(row, songColors);
            const verseTextColor = verseColors.textColor;
            const verseBgColor = verseColors.bgColor;

            const versePreview = row.querySelector("[data-verse-style-preview]");
            const versePreviewContent = row.querySelector("[data-verse-style-preview-content]");
            const verseTextSwatch = row.querySelector("[data-verse-text-swatch]");
            const verseBgSwatch = row.querySelector("[data-verse-bg-swatch]");
            if (versePreview instanceof HTMLElement) {
                versePreview.style.background = verseBgColor;
                const isVisible = verseCheckbox instanceof HTMLInputElement ? verseCheckbox.checked : true;
                versePreview.classList.toggle("is-not-visible", !isVisible);
            }
            if (versePreviewContent instanceof HTMLElement) {
                versePreviewContent.style.color = verseTextColor;
                versePreviewContent.style.fontFamily = `'${verseFontFamily}', sans-serif`;
                versePreviewContent.style.fontSize = `${previewFontSizePx}px`;
            }
            if (verseTextSwatch instanceof HTMLElement) {
                verseTextSwatch.style.background = verseTextColor;
                verseTextSwatch.setAttribute("title", `${label("textColorShortLabel")}: ${verseTextColor}`);
            }
            if (verseBgSwatch instanceof HTMLElement) {
                verseBgSwatch.style.background = verseBgColor;
                verseBgSwatch.setAttribute("title", `${label("bgColorShortLabel")}: ${verseBgColor}`);
            }
            row.querySelectorAll("[data-song-color-parent-trigger][data-color-target-level='verse']").forEach((button) => {
                if (!(button instanceof HTMLElement)) {
                    return;
                }
                const hasParentDiff = verseTextColor !== songTextColor || verseBgColor !== songBgColor;
                button.hidden = !hasParentDiff;
            });
        });
    };

    const refreshAllSongCardPreviews = () => {
        document.querySelectorAll("[data-main-song-card]").forEach((card) => {
            applySongCardPreviewStyles(card);
        });
    };

    const syncVerseCheckboxes = (card, verseId, checked, source) => {
        card.querySelectorAll(`[data-main-verse-checkbox][data-verse-id="${verseId}"]`).forEach((checkbox) => {
            if (!(checkbox instanceof HTMLInputElement) || checkbox === source) {
                return;
            }
            checkbox.checked = checked;
        });
    };

    const openSongColorPopup = async (card) => {
        if (!(card instanceof HTMLElement)) {
            return;
        }
        const initialTextColor = colorValueOrFallback(card.getAttribute("data-song-text-color"), fallbackValues.text_color);
        const initialBgColor = colorValueOrFallback(card.getAttribute("data-song-bg-color"), fallbackValues.bg_color);

        const result = await messageBox.show({
            title: label("songOptionsPopupTitle"),
            showCloseButton: true,
            buttons: [
                { id: "ok", label: label("okLabel"), tone: "success", validate: true },
                { id: "cancel", label: label("cancelLabel"), tone: "warning" },
                { id: "inherit", label: label("inheritParentColorsLabel"), tone: "neutral", validate: false },
                {
                    id: "reset",
                    label: label("resetLabel"),
                    tone: "neutral",
                    validate: false,
                    onClick: ({ setFieldValue, keepOpen }) => {
                        setFieldValue("text_color", initialTextColor);
                        setFieldValue("bg_color", initialBgColor);
                        keepOpen();
                        return false;
                    },
                },
            ],
            fields: [
                { id: "text_color", label: label("songTextColorLabel"), type: "color", value: initialTextColor, required: true },
                { id: "bg_color", label: label("songBgColorLabel"), type: "color", value: initialBgColor, required: true },
            ],
            enterButtonId: "ok",
            escapeButtonId: "cancel",
        });

        if (result.buttonId === "inherit") {
            clearSongColorOverrides(card);
            applySongCardPreviewStyles(card);
            updateSongsPayloadInput();
            refreshDirtyState();
            return;
        }

        if (result.buttonId !== "ok") {
            return;
        }

        card.setAttribute("data-song-text-color", colorValueOrFallback(result.values?.text_color, fallbackValues.text_color));
        card.setAttribute("data-song-bg-color", colorValueOrFallback(result.values?.bg_color, fallbackValues.bg_color));
        applySongCardPreviewStyles(card);
        updateSongsPayloadInput();
        refreshDirtyState();
    };

    const openVerseColorPopup = async (row) => {
        if (!(row instanceof HTMLElement)) {
            return;
        }
        const initialTextColor = colorValueOrFallback(row.getAttribute("data-verse-text-color"), fallbackValues.text_color);
        const initialBgColor = colorValueOrFallback(row.getAttribute("data-verse-bg-color"), fallbackValues.bg_color);

        const result = await messageBox.show({
            title: label("songOptionsPopupTitle"),
            showCloseButton: true,
            buttons: [
                { id: "ok", label: label("okLabel"), tone: "success", validate: true },
                { id: "cancel", label: label("cancelLabel"), tone: "warning" },
                { id: "inherit", label: label("inheritParentColorsLabel"), tone: "neutral", validate: false },
                {
                    id: "reset",
                    label: label("resetLabel"),
                    tone: "neutral",
                    validate: false,
                    onClick: ({ setFieldValue, keepOpen }) => {
                        setFieldValue("text_color", initialTextColor);
                        setFieldValue("bg_color", initialBgColor);
                        keepOpen();
                        return false;
                    },
                },
            ],
            fields: [
                { id: "text_color", label: label("songTextColorLabel"), type: "color", value: initialTextColor, required: true },
                { id: "bg_color", label: label("songBgColorLabel"), type: "color", value: initialBgColor, required: true },
            ],
            enterButtonId: "ok",
            escapeButtonId: "cancel",
        });

        if (result.buttonId === "inherit") {
            clearVerseColorOverrides(row);
            const cardFromRow = row.closest("[data-main-song-card]");
            applySongCardPreviewStyles(cardFromRow);
            updateSongsPayloadInput();
            refreshDirtyState();
            return;
        }

        if (result.buttonId !== "ok") {
            return;
        }

        row.setAttribute("data-verse-text-color", colorValueOrFallback(result.values?.text_color, fallbackValues.text_color));
        row.setAttribute("data-verse-bg-color", colorValueOrFallback(result.values?.bg_color, fallbackValues.bg_color));
        const card = row.closest("[data-main-song-card]");
        applySongCardPreviewStyles(card);
        updateSongsPayloadInput();
        refreshDirtyState();
    };

    const openSongTextPopup = async (url) => {
        try {
            const response = await fetch(String(url || ""), {
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });
            if (!response.ok) {
                throw new Error("Failed");
            }
            const payload = await response.json();
            await messageBox.alert({
                title: String(payload.title || label("songViewTextTitle")),
                messageMarkdown: String(payload.markdown || ""),
                showCloseButton: true,
                size: "wide",
            });
        } catch (_error) {
            await messageBox.alert({
                title: label("songViewTextTitle"),
                messageMarkdown: label("songViewTextError"),
                showCloseButton: true,
            });
        }
    };

    const bindMainSongCards = () => {
        document.querySelectorAll("[data-main-song-card]").forEach((card) => {
            if (!(card instanceof HTMLElement)) {
                return;
            }

            const toggle = card.querySelector("[data-song-options-toggle]");
            const expanded = card.querySelector("[data-song-expanded]");
            if (toggle instanceof HTMLButtonElement && expanded instanceof HTMLElement) {
                toggle.addEventListener("click", () => {
                    const shouldOpen = expanded.hidden;
                    expanded.hidden = !shouldOpen;
                    toggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
                    toggle.textContent = shouldOpen
                        ? String(toggle.getAttribute("data-close-label") || "")
                        : String(toggle.getAttribute("data-open-label") || "");
                });
            }

            card.querySelectorAll("[data-main-verse-checkbox]").forEach((checkbox) => {
                if (!(checkbox instanceof HTMLInputElement)) {
                    return;
                }
                checkbox.addEventListener("change", () => {
                    const verseId = String(checkbox.getAttribute("data-verse-id") || "");
                    syncVerseCheckboxes(card, verseId, checkbox.checked, checkbox);
                    applySongCardPreviewStyles(card);
                    updateSongsPayloadInput();
                    refreshDirtyState();
                });
            });

            card.querySelectorAll("[data-song-font-family], [data-song-font-size-delta], [data-verse-font-family], [data-verse-font-size-delta]").forEach((field) => {
                field.addEventListener("change", () => {
                    applySongCardPreviewStyles(card);
                    updateSongsPayloadInput();
                    refreshDirtyState();
                });
            });

            card.querySelectorAll("[data-song-color-popup-trigger]").forEach((button) => {
                button.addEventListener("click", async () => {
                    const level = String(button.getAttribute("data-color-target-level") || "song");
                    if (level === "verse") {
                        const verseId = String(button.getAttribute("data-verse-id") || "");
                        const row = card.querySelector(`[data-main-verse-row][data-verse-id="${verseId}"]`);
                        await openVerseColorPopup(row);
                        return;
                    }
                    await openSongColorPopup(card);
                });
            });

            card.querySelectorAll("[data-song-color-parent-trigger]").forEach((button) => {
                button.addEventListener("click", async () => {
                    const confirmed = await confirmParentReset();
                    if (!confirmed) {
                        return;
                    }
                    const level = String(button.getAttribute("data-color-target-level") || "song");
                    if (level === "verse") {
                        const verseId = String(button.getAttribute("data-verse-id") || "");
                        const row = card.querySelector(`[data-main-verse-row][data-verse-id="${verseId}"]`);
                        clearVerseColorOverrides(row);
                    } else {
                        clearSongColorOverrides(card);
                    }
                    applySongCardPreviewStyles(card);
                    updateSongsPayloadInput();
                    refreshDirtyState();
                });
            });

            card.querySelectorAll("[data-song-style-parent-reset-trigger]").forEach((button) => {
                button.addEventListener("click", async () => {
                    const confirmed = await confirmParentReset();
                    if (!confirmed) {
                        return;
                    }
                    const level = String(button.getAttribute("data-style-target-level") || "song");
                    if (level === "verse") {
                        const verseId = String(button.getAttribute("data-verse-id") || "");
                        const row = card.querySelector(`[data-main-verse-row][data-verse-id="${verseId}"]`);
                        resetVerseStyleToParent(row);
                    } else {
                        resetSongStyleToParent(card);
                    }
                    applySongCardPreviewStyles(card);
                    updateSongsPayloadInput();
                    refreshDirtyState();
                });
            });

            const viewLink = card.querySelector("[data-song-view-text]");
            if (viewLink instanceof HTMLAnchorElement) {
                viewLink.addEventListener("click", async (event) => {
                    event.preventDefault();
                    await openSongTextPopup(viewLink.getAttribute("data-popup-url"));
                });
            }

            const goToLink = card.querySelector("[data-song-go-to-link]");
            if (goToLink instanceof HTMLAnchorElement) {
                goToLink.addEventListener("click", async (event) => {
                    event.preventDefault();
                    const confirmed = await confirmUnsavedChanges();
                    if (!confirmed) {
                        return;
                    }
                    dirty = false;
                    window.location.assign(goToLink.href);
                });
            }

            applySongCardPreviewStyles(card);
        });
    };

    if (modeToggleButton instanceof HTMLButtonElement) {
        modeToggleButton.addEventListener("click", async () => {
            const confirmed = await confirmUnsavedChanges();
            if (!confirmed) {
                return;
            }
            const mainVisible = mainModePanel instanceof HTMLElement ? !mainModePanel.hidden : false;
            setMode(mainVisible ? "secondary" : "main");
        });
    }

    if (secondaryList instanceof HTMLElement) {
        secondaryList.addEventListener("click", async (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) {
                return;
            }
            const insertTrigger = target.closest("[data-animation-insert-trigger]");
            if (insertTrigger instanceof HTMLElement) {
                const confirmed = await confirmUnsavedChanges();
                if (!confirmed) {
                    return;
                }
                const insertIndex = Number.parseInt(String(insertTrigger.getAttribute("data-insert-index") || "0"), 10);
                await openSongPickerPopup(Number.isNaN(insertIndex) ? 0 : insertIndex);
                return;
            }
            const item = target.closest("[data-animation-song-item]");
            if (!(item instanceof HTMLElement)) {
                return;
            }
            if (target.closest("[data-animation-song-remove]")) {
                await removeItem(item);
            }
        });
    }

    const initReorderModule = async () => {
        if (!(secondaryList instanceof HTMLElement)) {
            return;
        }

        const moduleUrl = String(form.getAttribute("data-reorder-module-url") || "").trim();
        if (!moduleUrl) {
            return;
        }
        try {
            const reorderModule = await import(moduleUrl);
            if (!reorderModule || typeof reorderModule.init !== "function") {
                return;
            }
            reorderController = reorderModule.init({
                list: secondaryList,
                toggleButton: null,
                cancelButton: null,
                startPosition: 2,
                positionStep: 2,
                vibrateOnTargetChange: false,
                scrollToMovedItemAfterDrop: true,
                onChange: () => {
                    renderInsertSlots();
                    updateOrderedMix();
                    refreshDirtyState();
                },
                onCancel: () => {
                    renderInsertSlots();
                    updateOrderedMix();
                    refreshDirtyState();
                },
                onEnd: () => {
                    renderInsertSlots();
                    updateOrderedMix();
                    refreshDirtyState();
                },
            });
            if (reorderController && typeof reorderController.enable === "function") {
                reorderController.enable();
            }
        } catch (_error) {
            // Keep page usable when dynamic import fails.
        }
    };

    form.addEventListener("change", () => {
        refreshDirtyState();
    });

    form.addEventListener("submit", () => {
        isSubmitting = true;
        dirty = false;
    });

    hiddenFieldNames.forEach((name) => {
        const field = hiddenFields[name];
        if (!(field instanceof HTMLInputElement)) {
            return;
        }
        field.addEventListener("change", refreshDirtyState);
        field.addEventListener("input", refreshDirtyState);
    });

    getSecondaryItems().forEach((item) => normalizeSecondaryItemCompact(item));
    if (secondaryList instanceof HTMLElement) {
        secondaryList.classList.add("is-reorder-enabled");
    }

    window.addEventListener("beforeunload", (event) => {
        if (!dirty || isSubmitting) {
            return;
        }
        event.preventDefault();
        event.returnValue = "";
    });

    applySummaryPreview();
    bindMainSongCards();
    updateSongsPayloadInput();
    updateOrderedMix();
    renderInsertSlots();
    ensureModeOnLoad();
    initialSnapshot = getCurrentSnapshot();
    refreshDirtyState();
    void initReorderModule();
})();
