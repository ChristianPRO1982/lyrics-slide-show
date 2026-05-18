(() => {
    const messageBox = window.LSSMessageBox;
    const i18n = window.LSS_SONG_I18N || {};
    const label = (key) => String(i18n[key] || "");
    const floatingSearch = document.querySelector("[data-song-search-floating]");
    if (floatingSearch && document.body && floatingSearch.parentElement !== document.body) {
        document.body.appendChild(floatingSearch);
    }

    const normalizeSearch = (value) => {
        return String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .trim();
    };

    const searchInput = document.querySelector("[data-song-local-search]");
    const songCards = Array.from(document.querySelectorAll("[data-song-card]"));
    const visibleCountTargets = Array.from(document.querySelectorAll("[data-song-visible-count]"));
    const localEmptyState = document.querySelector("[data-song-local-empty]");
    if (searchInput && songCards.length) {
        const updateVisibleCount = (count) => {
            visibleCountTargets.forEach((target) => {
                target.textContent = String(count);
            });
        };

        const applyLocalSearch = () => {
            const query = normalizeSearch(searchInput.value);
            const shouldFilter = query.length >= 3;
            let visibleCount = 0;

            songCards.forEach((card) => {
                const haystack = normalizeSearch(card.getAttribute("data-song-search-text"));
                const isVisible = !shouldFilter || haystack.includes(query);
                card.style.display = isVisible ? "" : "none";
                if (isVisible) {
                    visibleCount += 1;
                }
            });

            updateVisibleCount(visibleCount);
            if (localEmptyState) {
                localEmptyState.hidden = visibleCount !== 0;
            }
        };

        searchInput.addEventListener("input", applyLocalSearch);
        applyLocalSearch();
    }

    const referenceFilterInput = document.querySelector("[data-song-reference-filter]");
    const referenceOptions = Array.from(document.querySelectorAll("[data-song-reference-option]"));
    if (referenceFilterInput && referenceOptions.length) {
        const applyReferenceFilter = () => {
            const query = normalizeSearch(referenceFilterInput.value);
            const shouldFilter = query.length >= 1;

            referenceOptions.forEach((option) => {
                const haystack = normalizeSearch(option.textContent || "");
                const isHidden = shouldFilter && !haystack.includes(query);
                option.style.display = isHidden ? "none" : "";
            });
        };

        referenceFilterInput.addEventListener("input", applyReferenceFilter);
        applyReferenceFilter();
    }

    document.querySelectorAll("[data-song-description-toggle]").forEach((button) => {
        button.addEventListener("click", () => {
            const container = button.closest("[data-song-description]");
            if (!container) {
                return;
            }

            const rest = container.querySelector("[data-song-description-rest]");
            const openButton = container.querySelector("p [data-song-description-toggle]");
            if (!rest) {
                return;
            }

            const expanded = rest.hidden;
            rest.hidden = !expanded;

            if (openButton) {
                openButton.hidden = expanded;
                openButton.setAttribute("aria-expanded", String(expanded));
            }
        });
    });

    document.querySelectorAll("[data-song-summary-popup]").forEach((link) => {
        link.addEventListener("click", async (event) => {
            if (!messageBox) {
                return;
            }
            event.preventDefault();
            const fullSummary = String(link.getAttribute("data-full-summary") || "").trim();
            if (!fullSummary) {
                return;
            }
            await messageBox.alert({
                title: label("summaryTitle"),
                messageMarkdown: fullSummary,
                showCloseButton: true,
            });
        });
    });

    const mobileActionsToggle = document.querySelector("[data-song-mobile-actions-toggle]");
    const mobileActionsContainer = document.querySelector("[data-song-mobile-actions]");
    if (mobileActionsToggle && mobileActionsContainer) {
        mobileActionsToggle.addEventListener("click", () => {
            const isHidden = mobileActionsContainer.hidden;
            mobileActionsContainer.hidden = !isHidden;
            mobileActionsToggle.setAttribute("aria-expanded", String(isHidden));
            mobileActionsToggle.textContent = isHidden
                ? String(mobileActionsToggle.getAttribute("data-close-label") || "")
                : String(mobileActionsToggle.getAttribute("data-open-label") || "");
        });
    }

    document.querySelectorAll("[data-song-delete-form]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            if (!messageBox) {
                return;
            }

            event.preventDefault();
            const result = await messageBox.confirm({
                title: label("deleteTitle"),
                messageMarkdown: label("deleteMessage"),
                showCloseButton: false,
                buttons: [
                    {
                        id: "yes",
                        label: label("yesLabel"),
                        tone: "danger",
                    },
                    {
                        id: "no",
                        label: label("noLabel"),
                        tone: "neutral",
                    },
                ],
            });

            if (result.buttonId === "yes") {
                form.submit();
            }
        });
    });

    const copyTextFromUrl = async (url) => {
        const response = await fetch(url, {
            credentials: "same-origin",
            headers: {
                "Accept": "text/plain",
            },
        });
        if (!response.ok) {
            throw new Error("Unable to fetch song text.");
        }
        await navigator.clipboard.writeText(await response.text());
    };

    document.querySelectorAll("[data-song-print-menu]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (!messageBox) {
                return;
            }

            const singleUrl = button.getAttribute("data-single-url") || "";
            const fullUrl = button.getAttribute("data-full-url") || "";
            const singlePlainUrl = button.getAttribute("data-single-plain-url") || "";
            const fullPlainUrl = button.getAttribute("data-full-plain-url") || "";

            const result = await messageBox.show({
                title: label("printTitle"),
                messageMarkdown: label("printMessage"),
                showCloseButton: true,
                buttons: [
                    {
                        id: "copy-single",
                        label: label("copySingleLabel"),
                        tone: "warning",
                    },
                    {
                        id: "copy-full",
                        label: label("copyFullLabel"),
                        tone: "warning",
                    },
                    {
                        id: "show-single",
                        label: label("showSingleLabel"),
                        tone: "neutral",
                    },
                    {
                        id: "show-full",
                        label: label("showFullLabel"),
                        tone: "neutral",
                    },
                ],
            });

            try {
                if (result.buttonId === "copy-single") {
                    await copyTextFromUrl(singlePlainUrl);
                    await messageBox.alert({ title: label("copyTitle"), messageMarkdown: label("copySuccess") });
                } else if (result.buttonId === "copy-full") {
                    await copyTextFromUrl(fullPlainUrl);
                    await messageBox.alert({ title: label("copyTitle"), messageMarkdown: label("copySuccess") });
                } else if (result.buttonId === "show-single") {
                    window.location.href = singleUrl;
                } else if (result.buttonId === "show-full") {
                    window.location.href = fullUrl;
                }
            } catch (_error) {
                await messageBox.alert({ title: label("copyTitle"), messageMarkdown: label("copyFailed") });
            }
        });
    });

    const createForm = document.querySelector("[data-song-create-form]");
    const createTitleInput = document.querySelector("[data-song-create-title]");
    const createSubtitleInput = document.querySelector("[data-song-create-subtitle]");
    const createSubmit = document.querySelector("[data-song-create-submit]");
    const existingIdentityNode = document.getElementById("song-existing-identities");
    if (createForm && createTitleInput && createSubtitleInput && createSubmit && existingIdentityNode) {
        const existingIdentityPairs = JSON.parse(existingIdentityNode.textContent || "[]");
        const existingIdentitySet = new Set(
            existingIdentityPairs.map((entry) => {
                const pair = Array.isArray(entry) ? entry : ["", ""];
                return `${normalizeSearch(pair[0])}::${normalizeSearch(pair[1])}`;
            }),
        );

        const updateCreateSongState = () => {
            const title = normalizeSearch(createTitleInput.value);
            const subtitle = normalizeSearch(createSubtitleInput.value);
            const hasTitle = title.length > 0;
            const duplicate = existingIdentitySet.has(`${title}::${subtitle}`);
            createSubmit.disabled = !hasTitle || duplicate;
        };

        createTitleInput.addEventListener("input", updateCreateSongState);
        createSubtitleInput.addEventListener("input", updateCreateSongState);
        updateCreateSongState();
    }

    const addBlockButton = document.querySelector("[data-song-add-block-action]");
    const reorderList = document.querySelector("[data-reorder-list]");
    if (addBlockButton && reorderList) {
        let newBlockCounter = 0;

        const escapeHtml = (value) => {
            return String(value || "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#39;");
        };

        const firstLine = (value) => {
            const lines = String(value || "").split("\n");
            for (const line of lines) {
                const cleaned = line.trim();
                if (cleaned.length > 0) {
                    return cleaned;
                }
            }
            return "";
        };

        const encodeForInputValue = (value) => {
            return escapeHtml(String(value || "")).replace(/\n/g, "&#10;");
        };

        const getCards = () => Array.from(reorderList.querySelectorAll("[data-song-block-card]"));

        const getCardByRowKey = (rowKey) => {
            const needle = String(rowKey || "");
            return getCards().find((item) => item.getAttribute("data-song-block-row") === needle) || null;
        };

        const getHidden = (card, selector) => card ? card.querySelector(selector) : null;
        const asBool = (value) => String(value || "") === "1";

        const normalizeBlockState = (state) => {
            const next = {
                type: state.type === "chorus" || state.type === "special" ? state.type : "verse",
                text: String(state.text || ""),
                prefix: String(state.prefix || ""),
                followed: Boolean(state.followed),
                notCNum: Boolean(state.notCNum),
            };
            if (next.type === "chorus") {
                next.followed = false;
                next.notCNum = false;
                next.prefix = "";
            }
            return next;
        };

        const labelForState = (state, card) => {
            if (state.type === "chorus") {
                return label("chorusLabel");
            }
            if (state.type === "special") {
                return state.prefix.trim() || label("specialSectionFallbackLabel");
            }
            if (state.notCNum) {
                return label("verseNoNumberingLabel");
            }
            const original = card?.getAttribute("data-song-block-default-label") || "";
            return original || label("verseLabel");
        };

        const renderCardFromState = (card, state) => {
            if (!card) return;
            const normalized = normalizeBlockState(state);
            const finalLabel = labelForState(normalized, card);
            const finalText = normalized.text.trim();
            const finalDragText = firstLine(finalText) || label("emptyBlockLabel");
            const finalDisplayText = finalText || label("emptyBlockLabel");

            const displayLabelNode = card.querySelector("[data-song-block-display-label]");
            const dragLabelNode = card.querySelector("[data-song-block-drag-label]");
            const displayTextNode = card.querySelector("[data-song-block-display-text]");
            const dragTextNode = card.querySelector("[data-song-block-drag-text]");
            if (displayLabelNode) displayLabelNode.textContent = finalLabel;
            if (dragLabelNode) dragLabelNode.textContent = finalLabel;
            if (displayTextNode) displayTextNode.innerHTML = escapeHtml(finalDisplayText).replace(/\n/g, "<br>");
            if (dragTextNode) dragTextNode.textContent = finalDragText;

            card.classList.toggle("song-edit-block--emphasis", normalized.type === "chorus" || normalized.type === "special");
        };

        const readStateFromHidden = (card) => {
            const hiddenType = getHidden(card, "[data-song-hidden-type]");
            const hiddenText = getHidden(card, "[data-song-hidden-text]");
            const hiddenPrefix = getHidden(card, "[data-song-hidden-prefix]");
            const hiddenFollowed = getHidden(card, "[data-song-hidden-followed]");
            const hiddenNotCNum = getHidden(card, "[data-song-hidden-not-c-num]");
            return normalizeBlockState({
                type: hiddenType?.value || "verse",
                text: hiddenText?.value || "",
                prefix: hiddenPrefix?.value || "",
                followed: asBool(hiddenFollowed?.value || "0"),
                notCNum: asBool(hiddenNotCNum?.value || "0"),
            });
        };

        const writeStateToHidden = (card, state) => {
            const normalized = normalizeBlockState(state);
            const hiddenType = getHidden(card, "[data-song-hidden-type]");
            const hiddenText = getHidden(card, "[data-song-hidden-text]");
            const hiddenPrefix = getHidden(card, "[data-song-hidden-prefix]");
            const hiddenFollowed = getHidden(card, "[data-song-hidden-followed]");
            const hiddenNotCNum = getHidden(card, "[data-song-hidden-not-c-num]");
            if (hiddenType) hiddenType.value = normalized.type;
            if (hiddenText) hiddenText.value = normalized.text;
            if (hiddenPrefix) hiddenPrefix.value = normalized.prefix;
            if (hiddenFollowed) hiddenFollowed.value = normalized.followed ? "1" : "0";
            if (hiddenNotCNum) hiddenNotCNum.value = normalized.notCNum ? "1" : "0";
            renderCardFromState(card, normalized);
            return normalized;
        };

        const readStateFromEditor = (card) => {
            const textInput = card.querySelector("[data-song-block-text-input]");
            const prefixInput = card.querySelector("[data-song-block-prefix-input]");
            const chorusCheckbox = card.querySelector("[data-song-block-chorus-checkbox]");
            const followedCheckbox = card.querySelector("[data-song-block-followed-checkbox]");
            const notCNumCheckbox = card.querySelector("[data-song-block-not-c-num-checkbox]");
            const specialCheckbox = card.querySelector("[data-song-block-special-checkbox]");
            let type = "verse";
            if (chorusCheckbox?.checked) {
                type = "chorus";
            } else if (specialCheckbox?.checked) {
                type = "special";
            }
            return normalizeBlockState({
                type,
                text: String(textInput?.value || ""),
                prefix: String(prefixInput?.value || ""),
                followed: Boolean(followedCheckbox?.checked),
                notCNum: Boolean(notCNumCheckbox?.checked),
            });
        };

        const writeStateToEditor = (card, state) => {
            const normalized = normalizeBlockState(state);
            const textInput = card.querySelector("[data-song-block-text-input]");
            const prefixInput = card.querySelector("[data-song-block-prefix-input]");
            const chorusCheckbox = card.querySelector("[data-song-block-chorus-checkbox]");
            const followedCheckbox = card.querySelector("[data-song-block-followed-checkbox]");
            const notCNumCheckbox = card.querySelector("[data-song-block-not-c-num-checkbox]");
            const specialCheckbox = card.querySelector("[data-song-block-special-checkbox]");
            if (textInput) textInput.value = normalized.text;
            if (prefixInput) prefixInput.value = normalized.prefix;
            if (chorusCheckbox) chorusCheckbox.checked = normalized.type === "chorus";
            if (specialCheckbox) specialCheckbox.checked = normalized.type === "special";
            if (followedCheckbox) followedCheckbox.checked = normalized.followed;
            if (notCNumCheckbox) notCNumCheckbox.checked = normalized.notCNum;

            const isChorus = normalized.type === "chorus";
            if (prefixInput) prefixInput.disabled = isChorus;
            if (followedCheckbox) followedCheckbox.disabled = isChorus;
            if (notCNumCheckbox) notCNumCheckbox.disabled = isChorus;
            if (specialCheckbox) specialCheckbox.disabled = isChorus;
        };

        const closeAllEditors = () => {
            getCards().forEach((card) => {
                const editor = card.querySelector("[data-song-block-editor]");
                if (editor) {
                    editor.hidden = true;
                }
            });
        };

        const openEditor = (rowKey, focusTarget) => {
            closeAllEditors();
            const card = getCardByRowKey(rowKey);
            if (!card) return;
            const hiddenDelete = getHidden(card, "[data-song-hidden-delete]");
            if (hiddenDelete && hiddenDelete.value === "1") return;

            const editor = card.querySelector("[data-song-block-editor]");
            if (!editor) return;
            const state = readStateFromHidden(card);
            writeStateToEditor(card, state);
            editor.hidden = false;

            const focusSelector = focusTarget === "prefix"
                ? "[data-song-block-prefix-input]"
                : "[data-song-block-text-input]";
            const focusNode = card.querySelector(focusSelector);
            if (focusNode && typeof focusNode.focus === "function") {
                focusNode.focus();
            }
        };

        const ensureExclusiveType = (card, changedKey) => {
            const chorusCheckbox = card.querySelector("[data-song-block-chorus-checkbox]");
            const specialCheckbox = card.querySelector("[data-song-block-special-checkbox]");
            if (!chorusCheckbox || !specialCheckbox) return;
            if (changedKey === "chorus" && chorusCheckbox.checked) {
                specialCheckbox.checked = false;
            }
            if (changedKey === "special" && specialCheckbox.checked) {
                chorusCheckbox.checked = false;
            }
        };

        const syncCardFromEditor = (card) => {
            const state = readStateFromEditor(card);
            const normalized = writeStateToHidden(card, state);
            writeStateToEditor(card, normalized);
        };

        const readNextPosition = () => {
            const positions = Array.from(reorderList.querySelectorAll("[data-reorder-position]"))
                .map((input) => Number.parseInt(input.value, 10))
                .filter((value) => Number.isFinite(value));
            if (!positions.length) {
                return 2;
            }
            return Math.max(...positions) + 2;
        };

        const createBlockCard = ({ rowKey, blockType, blockText }) => {
            const article = document.createElement("article");
            const position = readNextPosition();
            const initialType = blockType === "chorus" ? "chorus" : "verse";
            const initialState = normalizeBlockState({
                type: initialType,
                text: blockText,
                prefix: "",
                followed: false,
                notCNum: false,
            });
            const initialLabel = initialType === "chorus" ? label("chorusLabel") : label("verseLabel");

            article.className = `site-theme-card song-card song-edit-block${blockType === "chorus" ? " song-edit-block--emphasis" : ""}`;
            article.setAttribute("data-reorder-item", "");
            article.setAttribute("data-id", rowKey);
            article.setAttribute("data-song-block-card", "");
            article.setAttribute("data-song-block-row", rowKey);
            article.setAttribute("data-song-block-default-label", initialLabel);
            article.innerHTML = `
                <div class="song-edit-block-drag-view" data-reorder-drag-view hidden>
                    <button type="button" class="song-tool-button song-reorder-handle-inline" data-reorder-handle aria-label="${escapeHtml(label("moveLabel"))}">⋮↕⋮</button>
                    <strong class="song-edit-block-drag-label" data-song-block-drag-label>${escapeHtml(initialLabel)}</strong>
                    <span class="song-edit-block-drag-text" data-song-block-drag-text>${escapeHtml(firstLine(initialState.text) || label("emptyBlockLabel"))}</span>
                </div>

                <div data-reorder-normal-view>
                    <table style="text-align: left; width: 100%;" border="0" cellpadding="0" cellspacing="5">
                        <tbody>
                            <tr>
                                <td style="vertical-align: top; width: 3em;">
                                    <button type="button" class="song-tool-button song-reorder-handle-symbol" data-reorder-handle>⋮↕⋮</button>
                                </td>
                                <td style="vertical-align: top; text-align: right; width: 5em;">
                                    <button type="button" class="song-tool-button" data-song-block-open-prefix>
                                        <strong data-song-block-display-label>${escapeHtml(initialLabel)}</strong>
                                    </button>
                                </td>
                                <td style="vertical-align: top;">
                                    <div class="song-block-readonly">
                                        <button type="button" class="song-tool-button" data-song-block-open-text style="text-align: left; width: 100%;">
                                            <span data-song-block-display-text>${escapeHtml(initialState.text || label("emptyBlockLabel")).replace(/\n/g, "<br>")}</span>
                                        </button>
                                    </div>
                                </td>
                                <td style="vertical-align: top; text-align: right; width: 8em;">
                                    <button type="button" class="song-secondary-action site-action site-action--secondary" data-song-block-delete-action>
                                        ${escapeHtml(label("deleteBlockLabel"))}
                                    </button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    <div data-song-block-editor hidden>
                        <p>
                            <label>${escapeHtml(label("prefixFieldLabel"))}</label>
                            <input type="text" value="" data-song-block-prefix-input>
                        </p>
                        <p>
                            <label><input type="checkbox" ${initialType === "chorus" ? "checked" : ""} data-song-block-chorus-checkbox> ${escapeHtml(label("chorusLabel"))}</label>
                        </p>
                        <p>
                            <label><input type="checkbox" data-song-block-followed-checkbox> ${escapeHtml(label("followedLabel"))}</label>
                        </p>
                        <p>
                            <label><input type="checkbox" data-song-block-not-c-num-checkbox> ${escapeHtml(label("notCNumLabel"))}</label>
                        </p>
                        <p>
                            <label><input type="checkbox" data-song-block-special-checkbox> ${escapeHtml(label("specialLikeChorusLabel"))}</label>
                        </p>
                        <p>
                            <label>${escapeHtml(label("textFieldLabel"))}</label>
                            <textarea rows="5" data-song-block-text-input>${escapeHtml(initialState.text)}</textarea>
                        </p>
                        <p>
                            <button type="button" class="song-tool-button site-action site-action--primary" data-song-block-editor-ok>${escapeHtml(label("okLabel"))}</button>
                        </p>
                    </div>
                </div>

                <input type="hidden" data-reorder-position data-song-hidden-position name="blocks[${escapeHtml(rowKey)}][position]" value="${position}">
                <input type="hidden" data-song-hidden-id name="blocks[${escapeHtml(rowKey)}][id]" value="">
                <input type="hidden" data-song-hidden-type name="blocks[${escapeHtml(rowKey)}][type]" value="${escapeHtml(initialState.type)}">
                <input type="hidden" data-song-hidden-text name="blocks[${escapeHtml(rowKey)}][text]" value="${encodeForInputValue(initialState.text)}">
                <input type="hidden" data-song-hidden-prefix name="blocks[${escapeHtml(rowKey)}][prefix]" value="">
                <input type="hidden" data-song-hidden-followed name="blocks[${escapeHtml(rowKey)}][followed]" value="0">
                <input type="hidden" data-song-hidden-not-c-num name="blocks[${escapeHtml(rowKey)}][not_c_num]" value="0">
                <input type="hidden" data-song-hidden-delete name="blocks[${escapeHtml(rowKey)}][delete]" value="0">
            `;

            const addCardContainer = addBlockButton.closest(".song-card");
            if (addCardContainer && addCardContainer.parentElement === reorderList) {
                reorderList.insertBefore(article, addCardContainer);
            } else {
                reorderList.appendChild(article);
            }

            const reorderIsEnabled = reorderList.classList.contains("is-reorder-enabled");
            const dragView = article.querySelector("[data-reorder-drag-view]");
            const normalView = article.querySelector("[data-reorder-normal-view]");
            if (dragView && normalView) {
                dragView.hidden = !reorderIsEnabled;
                normalView.hidden = reorderIsEnabled;
            }
            article.classList.toggle("is-reorder-compact", reorderIsEnabled);
            writeStateToHidden(article, initialState);
            closeAllEditors();

            article.scrollIntoView({ behavior: "smooth", block: "center" });
        };

        const initializeCardDefaults = () => {
            getCards().forEach((card) => {
                const labelNode = card.querySelector("[data-song-block-display-label]");
                if (labelNode && !card.getAttribute("data-song-block-default-label")) {
                    card.setAttribute("data-song-block-default-label", labelNode.textContent || "");
                }
                renderCardFromState(card, readStateFromHidden(card));
            });
        };

        reorderList.addEventListener("click", async (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const card = target.closest("[data-song-block-card]");
            if (!card) return;

            const rowKey = card.getAttribute("data-song-block-row") || "";

            if (target.closest("[data-song-block-open-prefix]")) {
                event.preventDefault();
                openEditor(rowKey, "prefix");
                return;
            }
            if (target.closest("[data-song-block-open-text]")) {
                event.preventDefault();
                openEditor(rowKey, "text");
                return;
            }
            if (target.closest("[data-song-block-editor-ok]")) {
                event.preventDefault();
                syncCardFromEditor(card);
                closeAllEditors();
                return;
            }
            if (target.closest("[data-song-block-delete-action]")) {
                if (!messageBox) return;
                event.preventDefault();
                const result = await messageBox.confirm({
                    title: label("deleteBlockTitle"),
                    messageMarkdown: label("deleteBlockMessage"),
                    showCloseButton: false,
                    buttons: [
                        { id: "yes", label: label("yesLabel"), tone: "danger" },
                        { id: "no", label: label("noLabel"), tone: "neutral" },
                    ],
                });
                if (result.buttonId === "yes") {
                    const hiddenDelete = getHidden(card, "[data-song-hidden-delete]");
                    if (hiddenDelete) hiddenDelete.value = "1";
                    card.hidden = true;
                    closeAllEditors();
                }
                return;
            }
        });

        reorderList.addEventListener("input", (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const card = target.closest("[data-song-block-card]");
            if (!card) return;

            if (
                target.matches("[data-song-block-text-input]") ||
                target.matches("[data-song-block-prefix-input]") ||
                target.matches("[data-song-block-followed-checkbox]") ||
                target.matches("[data-song-block-not-c-num-checkbox]")
            ) {
                syncCardFromEditor(card);
            }
        });

        reorderList.addEventListener("change", (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const card = target.closest("[data-song-block-card]");
            if (!card) return;

            if (target.matches("[data-song-block-chorus-checkbox]")) {
                ensureExclusiveType(card, "chorus");
                syncCardFromEditor(card);
                return;
            }
            if (target.matches("[data-song-block-special-checkbox]")) {
                ensureExclusiveType(card, "special");
                syncCardFromEditor(card);
                return;
            }
            if (
                target.matches("[data-song-block-followed-checkbox]") ||
                target.matches("[data-song-block-not-c-num-checkbox]")
            ) {
                syncCardFromEditor(card);
            }
        });

        addBlockButton.addEventListener("click", async () => {
            if (!messageBox) return;
            closeAllEditors();
            const typeChoice = await messageBox.show({
                title: label("addBlockChoiceTitle"),
                messageMarkdown: label("addBlockChoiceMessage"),
                showCloseButton: true,
                buttons: [
                    { id: "verse", label: label("addVerseButtonLabel"), tone: "neutral" },
                    { id: "chorus", label: label("addChorusButtonLabel"), tone: "neutral" },
                    { id: "cancel", label: label("cancelLabel"), tone: "warning" },
                ],
            });

            if (typeChoice.buttonId !== "verse" && typeChoice.buttonId !== "chorus") {
                return;
            }

            const textPrompt = await messageBox.prompt({
                title: label("addBlockTextTitle"),
                messageMarkdown: label("addBlockTextMessage"),
                showCloseButton: true,
                fields: [
                    {
                        id: "text",
                        label: label("addBlockTextFieldLabel"),
                        type: "textarea",
                        required: true,
                        rows: 5,
                    },
                ],
            });

            if (textPrompt.buttonId !== "confirm") {
                return;
            }

            const rawText = String(textPrompt.values?.text || "");
            const normalizedText = rawText.replace(/\r\n/g, "\n").trim();
            if (!normalizedText) {
                return;
            }

            newBlockCounter += 1;
            const rowKey = `new-${Date.now()}-${newBlockCounter}`;
            createBlockCard({
                rowKey,
                blockType: typeChoice.buttonId === "chorus" ? "chorus" : "verse",
                blockText: normalizedText,
            });
        });

        window.LSSModifySong = window.LSSModifySong || {};
        window.LSSModifySong.closeAllBlockEditors = closeAllEditors;
        initializeCardDefaults();
    }
})();
