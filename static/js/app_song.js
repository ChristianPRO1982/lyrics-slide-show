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

    const readJsonScriptString = (id) => {
        const node = document.getElementById(String(id || ""));
        if (!node) {
            return "";
        }
        try {
            return String(JSON.parse(node.textContent || "\"\"") || "");
        } catch (_error) {
            return "";
        }
    };

    const getCsrfToken = () => {
        const field = document.querySelector("input[name=csrfmiddlewaretoken]");
        if (field && typeof field.value === "string" && field.value) {
            return field.value;
        }
        return "";
    };

    const buildMessageReadStateUrl = (messageId) => {
        const template = String(label("messageReadStateUrlTemplate") || "").trim();
        if (!template) {
            return "";
        }
        return template.replace(/0\/read-state\/?$/, `${messageId}/read-state/`);
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

    document.querySelectorAll("[data-song-inline-popup]").forEach((link) => {
        link.addEventListener("click", async (event) => {
            if (!messageBox) {
                return;
            }

            event.preventDefault();
            const popupTitle = String(
                link.getAttribute("data-popup-title") || label("infoPopupTitle"),
            ).trim();
            const popupMessage = String(link.getAttribute("data-popup-message") || "").trim();
            if (!popupMessage) {
                return;
            }

            await messageBox.alert({
                title: popupTitle || label("infoPopupTitle"),
                messageMarkdown: popupMessage,
                showCloseButton: true,
            });
        });
    });

    document.querySelectorAll("[data-song-markdown-popup]").forEach((link) => {
        link.addEventListener("click", async (event) => {
            if (!messageBox) {
                return;
            }

            event.preventDefault();
            const popupTitle = String(
                link.getAttribute("data-popup-title") || label("messagePopupTitle"),
            ).trim();
            const popupJsonId = String(link.getAttribute("data-popup-json-id") || "").trim();
            const popupMarkdown = readJsonScriptString(popupJsonId);
            if (!popupMarkdown) {
                return;
            }

            await messageBox.alert({
                title: popupTitle,
                messageMarkdown: popupMarkdown,
                showCloseButton: true,
                size: "wide",
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

    const correctionForm = document.getElementById("song-correction-form");
    const correctionMessageField = correctionForm
        ? correctionForm.querySelector('input[name="message"]')
        : null;
    const openCorrectionPopup = async (initialValue = "") => {
        if (!messageBox || !correctionForm || !correctionMessageField) {
            return;
        }

        const result = await messageBox.show({
            title: label("reportPopupTitle"),
            messageMarkdown: label("reportPopupMessage"),
            showCloseButton: true,
            buttons: [
                {
                    id: "submit",
                    label: label("reportSubmitLabel"),
                    tone: "success",
                    validate: true,
                },
                {
                    id: "cancel",
                    label: label("reportCancelLabel"),
                    tone: "neutral",
                    validate: false,
                },
            ],
            fields: [
                {
                    id: "message",
                    label: label("reportFieldLabel"),
                    type: "textarea",
                    value: initialValue,
                    placeholder: label("reportFieldPlaceholder"),
                    required: true,
                    rows: 6,
                },
            ],
            initialFocus: "first-field",
            enterButtonId: "submit",
            escapeButtonId: "cancel",
        });

        if (result.buttonId !== "submit") {
            return;
        }

        correctionMessageField.value = String(result.values.message || "");
        correctionForm.submit();
    };

    document.querySelectorAll("[data-song-report-trigger]").forEach((button) => {
        button.addEventListener("click", async () => {
            await openCorrectionPopup("");
        });
    });

    if (
        messageBox &&
        correctionForm &&
        correctionMessageField &&
        correctionForm.dataset.messageError === "true"
    ) {
        window.setTimeout(() => {
            void (async () => {
                await messageBox.alert({
                    title: label("reportPopupTitle"),
                    messageMarkdown: label("reportEmptyError"),
                    showCloseButton: true,
                });
                await openCorrectionPopup(correctionMessageField.value || "");
            })();
        }, 0);
    }

    document.addEventListener("click", async (event) => {
        const toggleLink = event.target instanceof Element
            ? event.target.closest('a[href^="#song-message-toggle-"]')
            : null;
        if (!toggleLink) {
            return;
        }

        event.preventDefault();

        const href = String(toggleLink.getAttribute("href") || "");
        const match = href.match(/^#song-message-toggle-(\d+)-(0|1)$/);
        if (!match) {
            return;
        }

        const messageId = match[1];
        const isRead = match[2];
        const endpoint = buildMessageReadStateUrl(messageId);
        const csrfToken = getCsrfToken();
        if (!endpoint || !csrfToken) {
            return;
        }

        const body = new URLSearchParams();
        body.set("is_read", isRead);

        try {
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
                throw new Error("Unable to update message read state.");
            }
            window.location.reload();
        } catch (_error) {
            if (messageBox) {
                await messageBox.alert({
                    title: label("messagePopupTitle"),
                    messageMarkdown: label("messageToggleFailed"),
                    showCloseButton: true,
                });
            }
        }
    });

    const fetchTextFromUrl = async (url) => {
        const response = await fetch(url, {
            credentials: "same-origin",
            headers: {
                "Accept": "text/plain",
            },
        });
        if (!response.ok) {
            throw new Error("Unable to fetch song text.");
        }
        return await response.text();
    };

    const copyTextFromUrl = async (url) => {
        await navigator.clipboard.writeText(await fetchTextFromUrl(url));
    };

    document.querySelectorAll("[data-song-plain-copy-trigger]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (!messageBox) {
                return;
            }

            const plainUrl = String(button.getAttribute("data-plain-url") || "").trim();
            const popupLabel = String(
                button.getAttribute("data-popup-label") || label("plainCopyFieldLabel"),
            ).trim();

            if (!plainUrl) {
                return;
            }

            try {
                const text = await fetchTextFromUrl(plainUrl);
                await messageBox.show({
                    title: label("plainCopyPopupTitle"),
                    showCloseButton: true,
                    size: "wide",
                    buttons: [
                        {
                            id: "copy",
                            label: label("plainCopyButtonLabel"),
                            tone: "warning",
                            validate: true,
                            onClick: async ({ values, keepOpen, setFieldError }) => {
                                try {
                                    await navigator.clipboard.writeText(String(values.text || ""));
                                    keepOpen();
                                } catch (_error) {
                                    keepOpen();
                                    setFieldError("text", label("copyFailed"));
                                    return false;
                                }
                                return false;
                            },
                        },
                        {
                            id: "close",
                            label: label("plainCloseButtonLabel"),
                            tone: "neutral",
                            validate: false,
                        },
                    ],
                    fields: [
                        {
                            id: "text",
                            label: popupLabel || label("plainCopyFieldLabel"),
                            type: "textarea",
                            value: text,
                            rows: 12,
                            readonly: true,
                        },
                    ],
                    initialFocus: "field:text",
                    enterButtonId: "copy",
                    escapeButtonId: "close",
                });
            } catch (_error) {
                await messageBox.alert({
                    title: label("plainCopyPopupTitle"),
                    messageMarkdown: label("copyFailed"),
                    showCloseButton: true,
                });
            }
        });
    });

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
                        onClick: () => {
                            const newTab = window.open(singleUrl, "_blank", "noopener");
                            if (newTab) {
                                newTab.opener = null;
                            }
                        },
                    },
                    {
                        id: "show-full",
                        label: label("showFullLabel"),
                        tone: "neutral",
                        onClick: () => {
                            const newTab = window.open(fullUrl, "_blank", "noopener");
                            if (newTab) {
                                newTab.opener = null;
                            }
                        },
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
        const getReadView = (card) => card ? card.querySelector("[data-song-block-read-view]") : null;
        const getEditView = (card) => card ? card.querySelector("[data-song-block-edit-view]") : null;
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
            } else if (next.type === "special") {
                next.notCNum = true;
            } else {
                next.prefix = "";
            }
            return next;
        };

        const labelForState = (state, card) => {
            if (state.type === "chorus") {
                return label("chorusPrefix") || label("chorusLabel");
            }
            if (state.type === "special") {
                return state.prefix.trim();
            }
            if (state.notCNum) {
                return "";
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
            const textInput = card.querySelector("[data-song-block-lyrics-input]");
            const prefixInput = card.querySelector("[data-song-block-prefix-input]");
            const chorusCheckbox = card.querySelector("[data-song-block-chorus-checkbox]");
            const followedCheckbox = card.querySelector("[data-song-block-followed-checkbox]");
            const notCNumCheckbox = card.querySelector("[data-song-block-no-continue-numbering-checkbox]");
            const chorusLikeCheckbox = card.querySelector("[data-song-block-chorus-like-checkbox]");
            let type = "verse";
            if (chorusCheckbox?.checked) {
                type = "chorus";
            } else if (chorusLikeCheckbox?.checked) {
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
            const textInput = card.querySelector("[data-song-block-lyrics-input]");
            const prefixInput = card.querySelector("[data-song-block-prefix-input]");
            const chorusCheckbox = card.querySelector("[data-song-block-chorus-checkbox]");
            const followedCheckbox = card.querySelector("[data-song-block-followed-checkbox]");
            const notCNumCheckbox = card.querySelector("[data-song-block-no-continue-numbering-checkbox]");
            const chorusLikeCheckbox = card.querySelector("[data-song-block-chorus-like-checkbox]");
            const prefixField = card.querySelector("[data-song-block-prefix-field]");
            const followedOption = card.querySelector("[data-song-block-followed-option]");
            const noContinueOption = card.querySelector("[data-song-block-no-continue-numbering-option]");
            const chorusLikeOption = card.querySelector("[data-song-block-chorus-like-option]");
            if (textInput) textInput.value = normalized.text;
            if (prefixInput) prefixInput.value = normalized.prefix;
            if (chorusCheckbox) chorusCheckbox.checked = normalized.type === "chorus";
            if (chorusLikeCheckbox) chorusLikeCheckbox.checked = normalized.type === "special";
            if (followedCheckbox) followedCheckbox.checked = normalized.followed;
            if (notCNumCheckbox) notCNumCheckbox.checked = normalized.notCNum;

            const isChorus = normalized.type === "chorus";
            const isChorusLike = normalized.type === "special";
            if (prefixInput) prefixInput.disabled = isChorus;
            if (followedCheckbox) followedCheckbox.disabled = isChorus;
            if (notCNumCheckbox) notCNumCheckbox.disabled = isChorus || isChorusLike;
            if (chorusLikeCheckbox) chorusLikeCheckbox.disabled = isChorus;
            if (prefixField) prefixField.hidden = !isChorusLike;
            if (followedOption) followedOption.hidden = isChorus;
            if (noContinueOption) noContinueOption.hidden = isChorus;
            if (chorusLikeOption) chorusLikeOption.hidden = isChorus;
        };

        const closeAllEditors = () => {
            getCards().forEach((card) => {
                const readView = getReadView(card);
                const editView = getEditView(card);
                if (readView) readView.hidden = false;
                if (editView) editView.hidden = true;
            });
        };

        const openEditor = (rowKey, focusTarget) => {
            closeAllEditors();
            const card = getCardByRowKey(rowKey);
            if (!card) return;
            const hiddenDelete = getHidden(card, "[data-song-hidden-delete]");
            if (hiddenDelete && hiddenDelete.value === "1") return;

            const readView = getReadView(card);
            const editView = getEditView(card);
            if (!editView) return;
            const state = readStateFromHidden(card);
            writeStateToEditor(card, state);
            if (readView) readView.hidden = true;
            editView.hidden = false;

            const focusSelector = focusTarget === "prefix"
                ? "[data-song-block-prefix-input]"
                : "[data-song-block-lyrics-input]";
            const focusNode = card.querySelector(focusSelector);
            if (focusNode && typeof focusNode.focus === "function") {
                focusNode.focus();
            }
        };

        const ensureExclusiveType = (card, changedKey) => {
            const chorusCheckbox = card.querySelector("[data-song-block-chorus-checkbox]");
            const chorusLikeCheckbox = card.querySelector("[data-song-block-chorus-like-checkbox]");
            if (!chorusCheckbox || !chorusLikeCheckbox) return;
            if (changedKey === "chorus" && chorusCheckbox.checked) {
                chorusLikeCheckbox.checked = false;
            }
            if (changedKey === "chorus-like" && chorusLikeCheckbox.checked) {
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
            const initialLabel = initialType === "chorus"
                ? (label("chorusPrefix") || label("chorusLabel"))
                : label("verseLabel");

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
                                <td style="vertical-align: top;">
                                    <div data-song-block-read-view>
                                        <table style="text-align: left; width: 100%;" border="0" cellpadding="2" cellspacing="0">
                                            <tbody>
                                                <tr>
                                                    <td class="song-block-prefix-col" style="vertical-align: top; white-space: nowrap;">
                                                        <button type="button" class="song-inline-trigger" data-song-block-open-prefix>
                                                            <strong data-song-block-display-label>${escapeHtml(initialLabel)}</strong>
                                                        </button>
                                                    </td>
                                                    <td style="vertical-align: top;">
                                                        <div class="song-block-readonly">
                                                            <button type="button" class="song-inline-trigger song-inline-trigger--text" data-song-block-open-text>
                                                                <span data-song-block-display-text>${escapeHtml(initialState.text || label("emptyBlockLabel")).replace(/\n/g, "<br>")}</span>
                                                            </button>
                                                        </div>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                    <div data-song-block-edit-view data-song-block-editor hidden>
                        <div class="song-block-edit-layout" data-song-block-edit-layout>
                            <div class="song-block-edit-text-col" data-song-block-edit-text-col>
                                <label>${escapeHtml(label("textFieldLabel"))}</label>
                                <textarea rows="5" data-song-block-lyrics-input>${escapeHtml(initialState.text)}</textarea>
                            </div>
                            <div class="song-block-edit-options-col" data-song-block-edit-options-col>
                                <p data-song-block-prefix-field hidden>
                                    <label>${escapeHtml(label("prefixFieldLabel"))}</label>
                                    <input type="text" value="" data-song-block-prefix-input>
                                </p>
                                <p>
                                    <label><input type="checkbox" ${initialType === "chorus" ? "checked" : ""} data-song-block-chorus-checkbox> ${escapeHtml(label("chorusLabel"))}</label>
                                </p>
                                <p data-song-block-followed-option ${initialType === "chorus" ? "hidden" : ""}>
                                    <label><input type="checkbox" data-song-block-followed-checkbox> ${escapeHtml(label("followedLabel"))}</label>
                                </p>
                                <p data-song-block-no-continue-numbering-option ${initialType === "chorus" ? "hidden" : ""}>
                                    <label><input type="checkbox" data-song-block-no-continue-numbering-checkbox> ${escapeHtml(label("notCNumLabel"))}</label>
                                </p>
                                <p data-song-block-chorus-like-option ${initialType === "chorus" ? "hidden" : ""}>
                                    <label><input type="checkbox" data-song-block-chorus-like-checkbox> ${escapeHtml(label("specialLikeChorusLabel"))}</label>
                                </p>
                                <p>
                                    <button type="button" class="song-tool-button site-action site-action--primary" data-song-block-editor-ok>${escapeHtml(label("okLabel"))}</button>
                                </p>
                            </div>
                        </div>
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
                target.matches("[data-song-block-lyrics-input]") ||
                target.matches("[data-song-block-prefix-input]") ||
                target.matches("[data-song-block-followed-checkbox]") ||
                target.matches("[data-song-block-no-continue-numbering-checkbox]")
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
            if (target.matches("[data-song-block-chorus-like-checkbox]")) {
                ensureExclusiveType(card, "chorus-like");
                syncCardFromEditor(card);
                return;
            }
            if (
                target.matches("[data-song-block-followed-checkbox]") ||
                target.matches("[data-song-block-no-continue-numbering-checkbox]")
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
