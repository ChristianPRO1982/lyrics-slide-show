(() => {
    const messageBox = window.LSSMessageBox;
    const i18n = window.LSS_SONG_I18N || {};
    const label = (key) => String(i18n[key] || "");
    const floatingSearch = document.querySelector("[data-song-search-floating]");
    const floatingHelpConfig = window.LSS_FLOATING_HELP_CONFIG || {};
    const compactOptionsCollapseDelayMs = Number(floatingHelpConfig.collapseDelayMs) || 3000;
    if (floatingSearch && document.body && floatingSearch.parentElement !== document.body) {
        document.body.appendChild(floatingSearch);
    }
    const floatingSmartphone = document.querySelector("[data-song-smartphone-floating]");
    if (
        floatingSmartphone
        && document.body
        && floatingSmartphone.parentElement !== document.body
    ) {
        document.body.appendChild(floatingSmartphone);
    }

    const normalizeSearch = (value) => {
        return String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .replace(/\s+/g, " ")
            .trim();
    };

    const matchesSearchQuery = (haystack, query) => {
        if (!query) {
            return true;
        }
        const segments = query.split(" ").filter(Boolean);
        if (!segments.length) {
            return true;
        }
        let position = 0;
        for (const segment of segments) {
            const foundAt = haystack.indexOf(segment, position);
            if (foundAt === -1) {
                return false;
            }
            position = foundAt + segment.length;
        }
        return true;
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

    const readJsonScriptValue = (id, fallback = null) => {
        const node = document.getElementById(String(id || ""));
        if (!node) {
            return fallback;
        }
        try {
            return JSON.parse(node.textContent || "null");
        } catch (_error) {
            return fallback;
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

    const searchCard = document.querySelector(".song-search-card");
    const searchInput = document.querySelector("[data-song-local-search]");
    const floatingSearchAnchor = document.querySelector(".song-search-anchor");
    if (
        floatingSearchAnchor
        && searchCard instanceof HTMLElement
        && searchInput instanceof HTMLElement
    ) {
        const focusSearchInput = () => {
            searchCard.scrollIntoView({ block: "start", behavior: "smooth" });
            window.requestAnimationFrame(() => {
                searchInput.focus({ preventScroll: true });
                if (
                    searchInput instanceof HTMLInputElement
                    || searchInput instanceof HTMLTextAreaElement
                ) {
                    searchInput.select();
                }
            });
        };
        floatingSearchAnchor.addEventListener("click", focusSearchInput);
    }
    const createSongCard = document.querySelector("[data-song-create-card]");
    const floatingCreateAnchor = document.querySelector(".song-create-anchor");
    if (floatingCreateAnchor && createSongCard instanceof HTMLElement) {
        // Keep the floating button from taking focus back after its click.
        floatingCreateAnchor.addEventListener("pointerdown", (event) => {
            event.preventDefault();
        });
        floatingCreateAnchor.addEventListener("click", (event) => {
            event.preventDefault();
            const firstInput = document.getElementById("song-create-title");
            if (
                !(
                    firstInput instanceof HTMLInputElement
                    || firstInput instanceof HTMLTextAreaElement
                    || firstInput instanceof HTMLSelectElement
                )
            ) {
                createSongCard.scrollIntoView({ block: "start", behavior: "smooth" });
                return;
            }

            const focusCreateTitle = () => {
                firstInput.focus({ preventScroll: true });
            };

            // Run within the user click so browsers retain the field focus.
            focusCreateTitle();
            createSongCard.scrollIntoView({ block: "start", behavior: "smooth" });
            window.requestAnimationFrame(() => {
                // Some browsers drop focus while completing smooth scrolling.
                if (document.activeElement !== firstInput) {
                    focusCreateTitle();
                }
            });
        });
    }
    const songCardNodes = Array.from(document.querySelectorAll("[data-song-card-id]"));
    const visibleCountTargets = Array.from(document.querySelectorAll("[data-song-visible-count]"));
    const localEmptyState = document.querySelector("[data-song-local-empty]");
    const desktopSongList = document.querySelector("[data-song-list-desktop]");
    const compactSongList = document.querySelector("[data-song-list-compact]");
    if (searchInput && songCardNodes.length) {
        const savedSearchText = normalizeSearch(
            searchInput.getAttribute("data-song-saved-search-text"),
        );
        const songCardGroups = Array.from(
            songCardNodes.reduce((groups, card) => {
                const songId = String(card.getAttribute("data-song-card-id") || "").trim();
                if (!songId) {
                    return groups;
                }

                const existingGroup = groups.get(songId) || {
                    haystack: normalizeSearch(card.getAttribute("data-song-search-text")),
                    nodes: [],
                };
                existingGroup.nodes.push(card);
                groups.set(songId, existingGroup);
                return groups;
            }, new Map()).values(),
        );

        const updateVisibleCount = (count) => {
            visibleCountTargets.forEach((target) => {
                target.textContent = String(count);
            });
        };

        const applyLocalSearch = () => {
            const query = normalizeSearch(searchInput.value);
            const sameAsSavedSearchText = query === savedSearchText;
            const shouldFilter = query.length >= 3 && !sameAsSavedSearchText;
            let visibleCount = 0;

            songCardGroups.forEach((group) => {
                const isVisible = !shouldFilter || matchesSearchQuery(group.haystack, query);
                group.nodes.forEach((card) => {
                    card.style.display = isVisible ? "" : "none";
                });
                if (isVisible) {
                    visibleCount += 1;
                }
            });

            updateVisibleCount(visibleCount);
            if (desktopSongList instanceof HTMLElement) {
                desktopSongList.hidden = visibleCount === 0;
            }
            if (compactSongList instanceof HTMLElement) {
                compactSongList.hidden = visibleCount === 0;
            }
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

    const summaryHelpToggle = document.querySelector("[data-song-summary-toggle]");
    const summaryHelpContent = document.querySelector("[data-song-summary-content]");
    if (summaryHelpToggle && summaryHelpContent) {
        const summaryHelpMobileQuery = window.matchMedia("(max-width: 760px)");

        const setSummaryHelpState = (expanded) => {
            summaryHelpContent.hidden = !expanded;
            summaryHelpToggle.setAttribute("aria-expanded", String(expanded));
        };

        const applySummaryHelpMode = () => {
            if (summaryHelpMobileQuery.matches) {
                setSummaryHelpState(false);
                return;
            }
            setSummaryHelpState(true);
        };

        summaryHelpToggle.addEventListener("click", () => {
            if (!summaryHelpMobileQuery.matches) {
                setSummaryHelpState(true);
                return;
            }
            setSummaryHelpState(summaryHelpContent.hidden);
        });

        if (typeof summaryHelpMobileQuery.addEventListener === "function") {
            summaryHelpMobileQuery.addEventListener("change", applySummaryHelpMode);
        } else if (typeof summaryHelpMobileQuery.addListener === "function") {
            summaryHelpMobileQuery.addListener(applySummaryHelpMode);
        }
        applySummaryHelpMode();
    }

    const compactOptionsGroups = Array.from(document.querySelectorAll("[data-song-compact-options]"));
    let openCompactOptionsGroup = null;
    let openCompactOptionsTimeoutId = null;

    const clearCompactOptionsTimeout = () => {
        if (openCompactOptionsTimeoutId) {
            window.clearTimeout(openCompactOptionsTimeoutId);
            openCompactOptionsTimeoutId = null;
        }
    };

    const closeCompactOptionsGroup = (group) => {
        if (!(group instanceof HTMLElement)) {
            return;
        }
        const toggle = group.querySelector("[data-song-compact-options-toggle]");
        const panel = group.querySelector("[data-song-compact-options-panel]");
        if (!(toggle instanceof HTMLElement) || !(panel instanceof HTMLElement)) {
            return;
        }
        clearCompactOptionsTimeout();
        panel.hidden = true;
        toggle.hidden = false;
        toggle.setAttribute("aria-expanded", "false");
        if (openCompactOptionsGroup === group) {
            openCompactOptionsGroup = null;
        }
    };

    const scheduleCompactOptionsClose = (group) => {
        clearCompactOptionsTimeout();
        openCompactOptionsTimeoutId = window.setTimeout(() => {
            closeCompactOptionsGroup(group);
        }, compactOptionsCollapseDelayMs);
    };

    const openCompactOptionsForGroup = (group) => {
        if (!(group instanceof HTMLElement)) {
            return;
        }
        if (openCompactOptionsGroup && openCompactOptionsGroup !== group) {
            closeCompactOptionsGroup(openCompactOptionsGroup);
        }
        const toggle = group.querySelector("[data-song-compact-options-toggle]");
        const panel = group.querySelector("[data-song-compact-options-panel]");
        if (!(toggle instanceof HTMLElement) || !(panel instanceof HTMLElement)) {
            return;
        }
        openCompactOptionsGroup = group;
        panel.hidden = false;
        toggle.hidden = true;
        toggle.setAttribute("aria-expanded", "true");
        scheduleCompactOptionsClose(group);
    };

    compactOptionsGroups.forEach((group) => {
        const toggle = group.querySelector("[data-song-compact-options-toggle]");
        const panel = group.querySelector("[data-song-compact-options-panel]");
        if (!(toggle instanceof HTMLElement) || !(panel instanceof HTMLElement)) {
            return;
        }

        toggle.addEventListener("click", () => {
            if (!panel.hidden) {
                closeCompactOptionsGroup(group);
                return;
            }
            openCompactOptionsForGroup(group);
        });

        panel.addEventListener("mouseenter", () => {
            clearCompactOptionsTimeout();
        });
        panel.addEventListener("mouseleave", () => {
            scheduleCompactOptionsClose(group);
        });
    });

    document.addEventListener("click", (event) => {
        if (!openCompactOptionsGroup) {
            return;
        }
        if (!(event.target instanceof Node)) {
            return;
        }
        if (openCompactOptionsGroup.contains(event.target)) {
            return;
        }
        closeCompactOptionsGroup(openCompactOptionsGroup);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && openCompactOptionsGroup) {
            closeCompactOptionsGroup(openCompactOptionsGroup);
        }
    });

    document.querySelectorAll("[data-song-compact-options-panel] a, [data-song-compact-options-panel] button").forEach((action) => {
        action.addEventListener("click", () => {
            const group = action.closest("[data-song-compact-options]");
            if (group instanceof HTMLElement) {
                closeCompactOptionsGroup(group);
            }
        });
    });

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

    const unsavedChanges = window.LSSUnsavedChanges;
    const modifySongForm = document.querySelector("[data-song-edit-form]");
    const metadataForm = document.querySelector("[data-song-metadata-form]");
    const modifySongUnsavedController = (
        unsavedChanges
        && modifySongForm instanceof HTMLFormElement
    ) ? unsavedChanges.attach(modifySongForm) : null;
    const metadataUnsavedController = (
        unsavedChanges
        && metadataForm instanceof HTMLFormElement
    ) ? unsavedChanges.attach(metadataForm) : null;

    if (metadataUnsavedController) {
        window.LSSSongMetadataUnsaved = metadataUnsavedController;
    }

    const addBlockButton = document.querySelector("[data-song-add-block-action]");
    const reorderList = document.querySelector("[data-reorder-list]");
    if (addBlockButton && reorderList) {
        let newBlockCounter = 0;
        const blockTemplate = document.querySelector("[data-song-block-template]");
        const slideDisplayModeSelect = document.querySelector("[data-song-slide-display-mode-edit]");
        const rawOfficialPrefixes = readJsonScriptValue("modify-song-official-prefixes", []);
        const officialPrefixes = (Array.isArray(rawOfficialPrefixes) ? rawOfficialPrefixes : [])
            .map((item) => ({
                id: String(item?.id || ""),
                prefix: String(item?.prefix || "").trim(),
                comment: String(item?.comment || "").trim(),
            }))
            .filter((item) => item.id && item.prefix);
        const refreshUnsavedChanges = () => {
            if (modifySongUnsavedController) {
                modifySongUnsavedController.refresh();
            }
        };

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

        const chooseOfficialPrefix = async (card) => {
            if (!messageBox || !officialPrefixes.length || !card) {
                return;
            }
            const result = await messageBox.show({
                title: label("officialPrefixPopupTitle"),
                size: "wide",
                showCloseButton: true,
                actionList: {
                    items: officialPrefixes.map((item) => ({
                        id: item.id,
                        label: item.prefix,
                        description: item.comment,
                        payload: {
                            prefixId: item.id,
                        },
                    })),
                },
                buttons: [
                    {
                        id: "close",
                        label: label("officialPrefixPopupCloseLabel"),
                        tone: "neutral",
                    },
                ],
            });

            const selectedPrefixId = String(result?.payload?.prefixId || "").trim();
            if (!selectedPrefixId) {
                return;
            }

            const selectedPrefix = officialPrefixes.find(
                (item) => item.id === selectedPrefixId,
            );
            if (!selectedPrefix) {
                return;
            }

            openEditor(card.getAttribute("data-song-block-row") || "", "prefix");
            const prefixInput = card.querySelector("[data-song-block-prefix-input]");
            if (!(prefixInput instanceof HTMLInputElement)) {
                return;
            }
            prefixInput.value = selectedPrefix.prefix;
            syncCardFromEditor(card);
            prefixInput.focus();
            prefixInput.select();
        };

        const getCards = () => Array.from(reorderList.querySelectorAll("[data-song-block-card]"));
        const hasActiveChorusBlocks = () => {
            return getCards().some((card) => {
                if (card.hidden) {
                    return false;
                }
                const hiddenDelete = getHidden(card, "[data-song-hidden-delete]");
                const hiddenType = getHidden(card, "[data-song-hidden-type]");
                return (
                    (!hiddenDelete || hiddenDelete.value !== "1")
                    && hiddenType
                    && hiddenType.value === "chorus"
                );
            });
        };

        const normalizeSlideDisplayMode = (value, hasChorus) => {
            const raw = String(value || "single");
            if (raw === "single") {
                return "single";
            }
            if (hasChorus) {
                if (raw === "verses_by_pairs") {
                    return "chorus_then_parallel";
                }
                if (
                    raw === "chorus_then_parallel"
                    || raw === "chorus_always_parallel"
                ) {
                    return raw;
                }
                return "single";
            }
            if (
                raw === "chorus_then_parallel"
                || raw === "chorus_always_parallel"
            ) {
                return "verses_by_pairs";
            }
            if (raw === "verses_by_pairs") {
                return raw;
            }
            return "single";
        };

        const rebuildSlideDisplayModeOptions = () => {
            if (!(slideDisplayModeSelect instanceof HTMLSelectElement)) {
                return;
            }
            const hasChorus = hasActiveChorusBlocks();
            const previousValue = slideDisplayModeSelect.value;
            const normalizedValue = normalizeSlideDisplayMode(previousValue, hasChorus);
            const nextOptions = hasChorus
                ? [
                    ["single", label("slideModeSingleLabel")],
                    [
                        "chorus_then_parallel",
                        label("slideModeChorusThenParallelLabel"),
                    ],
                    [
                        "chorus_always_parallel",
                        label("slideModeChorusAlwaysParallelLabel"),
                    ],
                ]
                : [
                    ["single", label("slideModeSingleLabel")],
                    ["verses_by_pairs", label("slideModeVersesByPairsLabel")],
                ];

            slideDisplayModeSelect.innerHTML = "";
            nextOptions.forEach(([value, text]) => {
                const option = document.createElement("option");
                option.value = value;
                option.textContent = text;
                option.selected = value === normalizedValue;
                slideDisplayModeSelect.appendChild(option);
            });
            slideDisplayModeSelect.value = normalizedValue;
            slideDisplayModeSelect.dispatchEvent(new Event("change", { bubbles: true }));
        };

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
            rebuildSlideDisplayModeOptions();
            refreshUnsavedChanges();
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
            if (!(blockTemplate instanceof HTMLTemplateElement) || !blockTemplate.content.firstElementChild) {
                return;
            }

            const article = blockTemplate.content.firstElementChild.cloneNode(true);
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
                ? (label("newChorusLabel") || label("chorusPrefix") || label("chorusLabel"))
                : (label("newVerseLabel") || label("verseLabel"));
            const rowSlug = rowKey.replace(/[^a-zA-Z0-9_-]+/g, "-");

            article.dataset.id = rowKey;
            article.setAttribute("data-song-block-card", "");
            article.setAttribute("data-song-block-row", rowKey);
            article.setAttribute("data-song-block-default-label", initialLabel);
            article.classList.toggle("song-edit-block--emphasis", initialType === "chorus");

            const textLabel = article.querySelector("[data-song-block-text-label]");
            const textInput = article.querySelector("[data-song-block-lyrics-input]");
            const prefixLabel = article.querySelector("[data-song-block-prefix-label]");
            const prefixInput = article.querySelector("[data-song-block-prefix-input]");

            if (textLabel instanceof HTMLLabelElement && textInput instanceof HTMLTextAreaElement) {
                textInput.id = `song-block-text-${rowSlug}`;
                textLabel.htmlFor = textInput.id;
            }

            if (prefixLabel instanceof HTMLLabelElement && prefixInput instanceof HTMLInputElement) {
                prefixInput.id = `song-block-prefix-${rowSlug}`;
                prefixLabel.htmlFor = prefixInput.id;
            }

            const setHiddenFieldName = (selector, fieldName, value) => {
                const input = article.querySelector(selector);
                if (!(input instanceof HTMLInputElement)) {
                    return;
                }
                input.name = `blocks[${rowKey}][${fieldName}]`;
                input.value = value;
            };

            setHiddenFieldName("[data-song-hidden-position]", "position", String(position));
            setHiddenFieldName("[data-song-hidden-id]", "id", "");
            setHiddenFieldName("[data-song-hidden-type]", "type", initialState.type);
            setHiddenFieldName("[data-song-hidden-text]", "text", initialState.text);
            setHiddenFieldName("[data-song-hidden-prefix]", "prefix", "");
            setHiddenFieldName("[data-song-hidden-followed]", "followed", "0");
            setHiddenFieldName("[data-song-hidden-not-c-num]", "not_c_num", "0");
            setHiddenFieldName("[data-song-hidden-delete]", "delete", "0");

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
            renderCardFromState(article, initialState);
            closeAllEditors();
            refreshUnsavedChanges();

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
            if (target.closest("[data-song-block-prefix-picker]")) {
                event.preventDefault();
                await chooseOfficialPrefix(card);
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
                    rebuildSlideDisplayModeOptions();
                    closeAllEditors();
                    refreshUnsavedChanges();
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
        window.LSSModifySong.unsavedController = modifySongUnsavedController;
        window.LSSModifySong.refreshUnsavedChanges = refreshUnsavedChanges;
        initializeCardDefaults();
        rebuildSlideDisplayModeOptions();
    }
})();
