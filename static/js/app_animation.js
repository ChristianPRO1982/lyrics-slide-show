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
    const modeToggleButton = document.querySelector("[data-animation-mode-toggle]");
    const mainModePanel = document.querySelector("[data-animation-edit-mode='main']");
    const secondaryModePanel = document.querySelector("[data-animation-edit-mode='secondary']");
    const secondaryList = document.querySelector("[data-animation-secondary-list]");
    const siteMainContent = document.querySelector(".site-main-content");

    const initialValues = Object.fromEntries(
        hiddenFieldNames.map((name) => [name, String(hiddenFields[name]?.value || "")])
    );

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

    const hexPattern = /^#([0-9a-fA-F]{6})$/;
    const fallbackValues = {
        text_color: "#FFFFFF",
        bg_color: "#000000",
        font_family: "Source Sans Pro",
        font_size: 72,
        horizontal_padding: 80,
    };

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

    const applySummaryPreview = () => {
        const values = readCurrentValues();
        const textColor = validHex(values.text_color) || fallbackValues.text_color;
        const bgColor = validHex(values.bg_color) || fallbackValues.bg_color;
        const fontFamily = String(values.font_family || fallbackValues.font_family).trim() || fallbackValues.font_family;
        const fontSize = clampNumber(values.font_size, fallbackValues.font_size, 10, 300);
        const horizontalPadding = clampNumber(values.horizontal_padding, fallbackValues.horizontal_padding, 0, 600);

        if (summaryNodes.title) {
            summaryNodes.title.textContent = String(values.title || "-").trim() || "-";
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
            summaryNodes.live.textContent = String(values.title || "").trim() || label("previewText");
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
                { id: "cancel", label: label("cancelLabel"), tone: "neutral", validate: false },
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
    };

    const openVisualPopup = async () => {
        const values = readCurrentValues();
        const result = await messageBox.show({
            title: label("visualPopupTitle"),
            showCloseButton: true,
            buttons: [
                { id: "ok", label: label("okLabel"), tone: "success", validate: true },
                { id: "cancel", label: label("cancelLabel"), tone: "neutral", validate: false },
                makeResetButton([
                    "text_color",
                    "bg_color",
                    "font_family",
                    "font_size",
                    "horizontal_padding",
                ]),
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
    };

    const openFontListPopup = async () => {
        await messageBox.show({
            title: label("fontListPopupTitle"),
            fontSamples: fontPreviews,
            showCloseButton: true,
            size: "wide",
            buttons: [
                { id: "ok", label: label("okLabel"), tone: "neutral" },
            ],
        });
    };

    document.querySelectorAll("[data-animation-action]").forEach((button) => {
        button.addEventListener("click", async () => {
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
        return Array.from(secondaryList.querySelectorAll("[data-animation-song-item]"));
    };

    const updateOrderedMix = () => {
        if (!(orderedMixInput instanceof HTMLInputElement)) {
            return;
        }
        const tokens = getSecondaryItems()
            .map((item) => String(item.getAttribute("data-animation-song-id") || "").trim())
            .filter((id) => /^\d+$/.test(id))
            .map((id) => `asid:${id}`);
        orderedMixInput.value = tokens.join("|");
    };

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

    const moveItem = (item, direction) => {
        if (!(item instanceof HTMLElement) || !(secondaryList instanceof HTMLElement)) {
            return;
        }
        if (direction === "up") {
            const previous = item.previousElementSibling;
            if (previous) {
                secondaryList.insertBefore(item, previous);
            }
        } else if (direction === "down") {
            const next = item.nextElementSibling;
            if (next) {
                secondaryList.insertBefore(next, item);
            }
        }
        updateOrderedMix();
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
        updateOrderedMix();
        ensureModeOnLoad();
    };

    if (modeToggleButton instanceof HTMLButtonElement) {
        modeToggleButton.addEventListener("click", () => {
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
            const item = target.closest("[data-animation-song-item]");
            if (!(item instanceof HTMLElement)) {
                return;
            }
            if (target.closest("[data-animation-song-up]")) {
                moveItem(item, "up");
                return;
            }
            if (target.closest("[data-animation-song-down]")) {
                moveItem(item, "down");
                return;
            }
            if (target.closest("[data-animation-song-remove]")) {
                await removeItem(item);
            }
        });
    }

    applySummaryPreview();
    updateOrderedMix();
    ensureModeOnLoad();
})();
