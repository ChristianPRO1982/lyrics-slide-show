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
    if (addBlockButton && reorderList && messageBox) {
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

        const readNextPosition = () => {
            const positions = Array.from(reorderList.querySelectorAll("[data-reorder-position]"))
                .map((input) => Number.parseInt(input.value, 10))
                .filter((value) => Number.isFinite(value));
            if (!positions.length) {
                return 2;
            }
            return Math.max(...positions) + 2;
        };

        const createBlockCard = ({ rowKey, blockType, blockText, displayLabel }) => {
            const article = document.createElement("article");
            const dragText = firstLine(blockText) || label("emptyBlockLabel");
            const position = readNextPosition();
            const escapedLabel = escapeHtml(displayLabel);
            const escapedDragText = escapeHtml(dragText);
            const escapedTextHtml = escapeHtml(blockText).replace(/\n/g, "<br>");
            const escapedTextValue = escapeHtml(blockText).replace(/\n/g, "&#10;");

            article.className = `site-theme-card song-card song-edit-block${blockType === "chorus" ? " song-edit-block--emphasis" : ""}`;
            article.setAttribute("data-reorder-item", "");
            article.setAttribute("data-id", rowKey);
            article.innerHTML = `
                <div class="song-edit-block-drag-view" data-reorder-drag-view hidden>
                    <button type="button" class="song-tool-button song-reorder-handle-inline" data-reorder-handle aria-label="${escapeHtml(label("moveLabel"))}">⋮↕⋮</button>
                    <strong class="song-edit-block-drag-label">${escapedLabel}</strong>
                    <span class="song-edit-block-drag-text">${escapedDragText}</span>
                </div>

                <div data-reorder-normal-view>
                    <table style="text-align: left; width: 100%;" border="0" cellpadding="0" cellspacing="5">
                        <tbody>
                            <tr>
                                <td style="vertical-align: top; width: 3em;">
                                    <button type="button" class="song-tool-button song-reorder-handle-symbol" data-reorder-handle>⋮↕⋮</button>
                                </td>
                                <td style="vertical-align: top; text-align: right; width: 5em;">
                                    <strong>${escapedLabel}</strong>
                                </td>
                                <td style="vertical-align: top;">
                                    <div class="song-block-readonly">
                                        <p>${escapedTextHtml}</p>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <input type="hidden" data-reorder-position name="blocks[${escapeHtml(rowKey)}][position]" value="${position}">
                <input type="hidden" name="blocks[${escapeHtml(rowKey)}][id]" value="">
                <input type="hidden" name="blocks[${escapeHtml(rowKey)}][type]" value="${escapeHtml(blockType)}">
                <input type="hidden" name="blocks[${escapeHtml(rowKey)}][text]" value="${escapedTextValue}">
                <input type="hidden" name="blocks[${escapeHtml(rowKey)}][prefix]" value="">
                <input type="hidden" name="blocks[${escapeHtml(rowKey)}][followed]" value="0">
                <input type="hidden" name="blocks[${escapeHtml(rowKey)}][not_c_num]" value="0">
                <input type="hidden" name="blocks[${escapeHtml(rowKey)}][delete]" value="0">
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

            article.scrollIntoView({ behavior: "smooth", block: "center" });
        };

        addBlockButton.addEventListener("click", async () => {
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
                displayLabel: typeChoice.buttonId === "chorus" ? label("chorusLabel") : label("verseLabel"),
            });
        });
    }
})();
