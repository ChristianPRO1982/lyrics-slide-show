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
})();
