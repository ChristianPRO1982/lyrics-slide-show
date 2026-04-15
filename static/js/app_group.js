(() => {
    const messageBox = window.LSSMessageBox;
    const floatingSearch = document.querySelector("[data-group-search-floating]");

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

    const searchInput = document.querySelector("[data-group-search-input]");
    const groupCards = Array.from(document.querySelectorAll("[data-group-card]"));
    if (searchInput && groupCards.length) {
        const applySearch = () => {
            const query = normalizeSearch(searchInput.value);
            const shouldFilter = query.length >= 3;

            groupCards.forEach((card) => {
                const haystack = normalizeSearch(card.getAttribute("data-group-search-text"));
                card.hidden = shouldFilter && !haystack.includes(query);
            });
        };

        searchInput.addEventListener("input", applySearch);
    }

    document.querySelectorAll("[data-group-info-toggle]").forEach((button) => {
        button.addEventListener("click", () => {
            const container = button.closest(".group-info-block");
            if (!container) {
                return;
            }

            const preview = container.querySelector("[data-group-info-preview]");
            const full = container.querySelector("[data-group-info-full]");
            const expanded = !full.hidden;
            full.hidden = expanded;
            preview.hidden = !expanded;
            button.textContent = expanded ? button.dataset.moreLabel : button.dataset.lessLabel;
        });
    });

    document.querySelectorAll("[data-copy-text]").forEach((button) => {
        button.addEventListener("click", async () => {
            const text = button.getAttribute("data-copy-text") || "";
            try {
                await navigator.clipboard.writeText(text);
                if (messageBox) {
                    messageBox.alert({ title: "Copie", messageMarkdown: "Le lien a été copié." });
                }
            } catch (_error) {
                if (messageBox) {
                    messageBox.alert({ title: "Copie", messageMarkdown: "La copie automatique a échoué." });
                }
            }
        });
    });

    document.querySelectorAll("[data-copy-qr]").forEach((button) => {
        button.addEventListener("click", async () => {
            const container = button.closest(".group-qr-panel");
            const image = container?.querySelector("[data-group-qr-image]");
            if (!(image instanceof HTMLImageElement) || !image.src) {
                return;
            }

            try {
                const response = await fetch(image.src, { mode: "cors" });
                const blob = await response.blob();

                if (navigator.clipboard && window.ClipboardItem) {
                    await navigator.clipboard.write([
                        new ClipboardItem({
                            [blob.type || "image/png"]: blob,
                        }),
                    ]);
                    if (messageBox) {
                        messageBox.alert({ title: "Copie", messageMarkdown: "Le QR code a été copié." });
                    }
                    return;
                }

                throw new Error("Clipboard image write not supported.");
            } catch (_error) {
                if (messageBox) {
                    messageBox.alert({ title: "Copie", messageMarkdown: "La copie du QR code a échoué." });
                }
            }
        });
    });

    document.querySelectorAll("[data-group-secret-prompt]").forEach((button) => {
        button.addEventListener("click", async () => {
            const form = button.closest("[data-group-secret-form]");
            if (!form || !messageBox) {
                return;
            }

            const groupName = button.getAttribute("data-group-name") || "";
            const result = await messageBox.prompt({
                title: "Secret du groupe",
                messageMarkdown: `Saisissez le secret pour **${groupName}**.`,
                fields: [
                    {
                        id: "secret",
                        label: "Secret",
                        type: "text",
                        required: true,
                    },
                ],
            });

            if (result.buttonId !== "confirm") {
                return;
            }

            const secretInput = form.querySelector("input[name='secret']");
            if (secretInput) {
                secretInput.value = result.values?.secret || "";
            }
            form.submit();
        });
    });

    document.querySelectorAll("[data-group-confirm-form]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            if (!messageBox) {
                return;
            }
            event.preventDefault();
            const message = form.getAttribute("data-confirm-message") || "Confirmer cette action ?";
            const result = await messageBox.confirm({
                title: "Confirmation",
                messageMarkdown: message,
            });
            if (result.buttonId === "yes") {
                form.submit();
            }
        });
    });

    document.querySelectorAll("[data-group-delete-form]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            if (!messageBox) {
                return;
            }
            event.preventDefault();

            const result = await messageBox.prompt({
                title: form.getAttribute("data-confirm-title") || "Confirmation",
                messageMarkdown: form.getAttribute("data-confirm-message") || "",
                fields: [
                    {
                        id: "confirmation_word",
                        label: form.getAttribute("data-confirm-word") || "DELETE",
                        type: "text",
                        required: true,
                    },
                ],
            });

            if (result.buttonId !== "confirm") {
                return;
            }

            const hiddenInput = form.querySelector("input[name='confirmation_word']");
            if (hiddenInput) {
                hiddenInput.value = result.values?.confirmation_word || "";
            }
            form.submit();
        });
    });

    document.querySelectorAll("[data-group-join-review]").forEach((button) => {
        button.addEventListener("click", async () => {
            const form = button.closest("[data-group-join-review-form]");
            if (!form || !messageBox) {
                return;
            }

            const result = await messageBox.show({
                title: "Confirmation",
                messageMarkdown: "Accepter cette demande d’adhésion ?",
                showCloseButton: true,
                buttons: [
                    {
                        id: "accept",
                        label: "Accepter",
                        tone: "success",
                    },
                    {
                        id: "cancel",
                        label: "Abandonner",
                        tone: "neutral",
                    },
                    {
                        id: "reject",
                        label: "Refuser",
                        tone: "danger",
                    },
                ],
            });

            if (!["accept", "reject"].includes(result.buttonId || "")) {
                return;
            }

            const actionInput = form.querySelector("input[name='action']");
            if (!actionInput) {
                return;
            }

            actionInput.value = result.buttonId === "accept" ? "accept_join_request" : "reject_join_request";
            form.submit();
        });
    });
})();
