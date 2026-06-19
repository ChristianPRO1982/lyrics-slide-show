import { init as initReorder } from "./reorder-list.module.js";

(() => {
    const form = document.querySelector("[data-song-edit-form]");
    if (!(form instanceof HTMLFormElement)) {
        return;
    }

    const messageBox = window.LSSMessageBox;
    const i18n = window.LSS_MODIFY_SONG_I18N || {};
    const label = (key) => String(i18n[key] || "");

    const list = form.querySelector("[data-reorder-list]");
    if (!(list instanceof HTMLElement)) {
        return;
    }

    const template = form.querySelector("template[data-song-block-template]");
    const addFirstButton = form.querySelector("[data-add-block-before='first']");
    const dirtyStatus = form.querySelector("[data-dirty-status]");
    const nextUrlInput = form.querySelector("[data-next-url-input]");
    const deletedContainer = document.createElement("div");
    deletedContainer.hidden = true;
    deletedContainer.setAttribute("data-deleted-blocks", "true");
    form.appendChild(deletedContainer);

    let dirty = false;
    let blockCounter = 0;
    let isSubmitting = false;
    let pendingNavigationUrl = "";

    const escapeHtml = (value) => {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    };

    const escapeSelectorValue = (value) => {
        if (window.CSS && typeof window.CSS.escape === "function") {
            return window.CSS.escape(value);
        }
        return String(value).replace(/[\"\\\\]/g, "\\\\$&");
    };

    const setDirty = (value) => {
        dirty = Boolean(value);
        if (dirtyStatus instanceof HTMLElement) {
            dirtyStatus.hidden = !dirty;
        }
    };

    const markDirty = () => {
        setDirty(true);
    };

    const closeAllEditors = () => {
        form.querySelectorAll("[data-block-editor]").forEach((editor) => {
            if (editor instanceof HTMLElement) {
                editor.hidden = true;
            }
        });
        form.querySelectorAll("[data-block-open]").forEach((button) => {
            if (button instanceof HTMLElement) {
                button.setAttribute("aria-expanded", "false");
            }
        });
    };

    const updateBlockTypeVisibility = (item) => {
        const typeSelect = item.querySelector("[data-block-type]");
        const prefixField = item.querySelector("[data-prefix-field]");
        const followedOption = item.querySelector("[data-block-followed]")?.closest("p");
        const notCNumOption = item.querySelector("[data-block-not-c-num]")?.closest("p");

        if (!(typeSelect instanceof HTMLSelectElement)) {
            return;
        }

        const type = typeSelect.value;
        if (prefixField instanceof HTMLElement) {
            prefixField.hidden = type !== "special";
        }

        const isChorus = type === "chorus";
        if (followedOption instanceof HTMLElement) {
            followedOption.hidden = isChorus;
        }
        if (notCNumOption instanceof HTMLElement) {
            notCNumOption.hidden = isChorus;
        }
    };

    const syncReadonlyView = (item) => {
        const readonlyContainer = item.querySelector("[data-block-readonly]");
        const textInput = item.querySelector("[data-block-text]");
        const openButton = item.querySelector("[data-block-open]");
        const typeSelect = item.querySelector("[data-block-type]");
        const prefixInput = item.querySelector("[data-block-prefix]");
        if (!(readonlyContainer instanceof HTMLElement) || !(textInput instanceof HTMLTextAreaElement)) {
            return;
        }

        const text = String(textInput.value || "").trim();
        if (!text) {
            readonlyContainer.innerHTML = `<p><em>${escapeHtml(label("emptyBlockLabel"))}</em></p>`;
        } else {
            readonlyContainer.innerHTML = `<p>${escapeHtml(text).replace(/\n/g, "<br>")}</p>`;
        }

        if (openButton instanceof HTMLElement && typeSelect instanceof HTMLSelectElement) {
            const typeLabel = typeSelect.options[typeSelect.selectedIndex]?.text || "";
            const prefix = prefixInput instanceof HTMLInputElement ? String(prefixInput.value || "").trim() : "";
            const heading = typeSelect.value === "special" && prefix ? prefix : typeLabel;
            openButton.textContent = heading || typeLabel;
        }
    };

    const refreshPositions = () => {
        const items = Array.from(list.querySelectorAll("[data-reorder-item]"));
        let position = 2;
        items.forEach((item) => {
            if (!(item instanceof HTMLElement)) {
                return;
            }
            const input = item.querySelector("[data-reorder-position]");
            if (input instanceof HTMLInputElement) {
                input.value = String(position);
                position += 2;
            }
        });
    };

    const ensureVisibleEmptyCallout = () => {
        const emptyCallout = form.querySelector("[data-song-empty-callout]");
        if (!(emptyCallout instanceof HTMLElement)) {
            return;
        }
        const hasItems = list.querySelector("[data-reorder-item]");
        emptyCallout.hidden = Boolean(hasItems);
    };

    const bindBlockItem = (item) => {
        if (!(item instanceof HTMLElement)) {
            return;
        }

        const openButton = item.querySelector("[data-block-open]");
        if (openButton instanceof HTMLButtonElement) {
            openButton.addEventListener("click", () => {
                const editor = item.querySelector("[data-block-editor]");
                if (!(editor instanceof HTMLElement)) {
                    return;
                }
                const shouldOpen = editor.hidden;
                closeAllEditors();
                editor.hidden = !shouldOpen;
                openButton.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
            });
        }

        const typeSelect = item.querySelector("[data-block-type]");
        if (typeSelect instanceof HTMLSelectElement) {
            typeSelect.addEventListener("change", () => {
                updateBlockTypeVisibility(item);
                syncReadonlyView(item);
                markDirty();
            });
        }

        item.querySelectorAll("input, textarea, select").forEach((field) => {
            field.addEventListener("change", () => {
                syncReadonlyView(item);
                markDirty();
            });
            field.addEventListener("input", () => {
                syncReadonlyView(item);
                markDirty();
            });
        });

        const deleteButton = item.querySelector("[data-delete-block]");
        if (deleteButton instanceof HTMLButtonElement) {
            deleteButton.addEventListener("click", async () => {
                if (!messageBox) {
                    return;
                }
                const result = await messageBox.confirm({
                    title: label("deleteTitle"),
                    messageMarkdown: label("deleteBlockMessage"),
                    showCloseButton: false,
                    buttons: [
                        { id: "yes", label: label("yesLabel"), tone: "danger" },
                        { id: "no", label: label("noLabel"), tone: "neutral" },
                    ],
                });

                if (result.buttonId !== "yes") {
                    return;
                }

                const deleteInput = item.querySelector("[data-block-delete-input]");
                if (deleteInput instanceof HTMLInputElement) {
                    deleteInput.value = "1";
                }

                item.removeAttribute("data-reorder-item");
                item.hidden = true;
                deletedContainer.appendChild(item);
                refreshPositions();
                ensureVisibleEmptyCallout();
                markDirty();
            });
        }

        const addAfterButton = item.querySelector("[data-add-block-after]");
        if (addAfterButton instanceof HTMLButtonElement) {
            addAfterButton.addEventListener("click", () => {
                const rowKey = addAfterButton.getAttribute("data-add-block-after") || "";
                insertNewBlock({ afterRowKey: rowKey });
            });
        }

        const handle = item.querySelector("[data-reorder-handle]");
        if (handle instanceof HTMLElement) {
            handle.addEventListener("pointerdown", () => {
                closeAllEditors();
            });
        }

        updateBlockTypeVisibility(item);
        syncReadonlyView(item);
    };

    const buildNewBlockElement = () => {
        if (!(template instanceof HTMLTemplateElement)) {
            return null;
        }
        const rowKey = `new-${Date.now()}-${blockCounter}`;
        blockCounter += 1;

        let html = template.innerHTML.replace(/__ROW_KEY__/g, rowKey);
        html = html.replace(/__POSITION__/g, "999999");

        const wrapper = document.createElement("div");
        wrapper.innerHTML = html.trim();
        const item = wrapper.firstElementChild;
        return item instanceof HTMLElement ? item : null;
    };

    const insertNewBlock = ({ afterRowKey = "" } = {}) => {
        const newItem = buildNewBlockElement();
        if (!newItem) {
            return;
        }

        if (afterRowKey) {
            const anchor = list.querySelector(`[data-id="${escapeSelectorValue(afterRowKey)}"]`);
            if (anchor && anchor.parentElement === list) {
                list.insertBefore(newItem, anchor.nextSibling);
            } else {
                list.appendChild(newItem);
            }
        } else {
            if (list.firstElementChild) {
                list.insertBefore(newItem, list.firstElementChild);
            } else {
                list.appendChild(newItem);
            }
        }

        bindBlockItem(newItem);
        ensureVisibleEmptyCallout();
        refreshPositions();
        closeAllEditors();

        const editor = newItem.querySelector("[data-block-editor]");
        const opener = newItem.querySelector("[data-block-open]");
        if (editor instanceof HTMLElement) {
            editor.hidden = false;
        }
        if (opener instanceof HTMLElement) {
            opener.setAttribute("aria-expanded", "true");
        }

        const textInput = newItem.querySelector("[data-block-text]");
        if (textInput instanceof HTMLTextAreaElement) {
            textInput.focus();
        }

        markDirty();
    };

    if (addFirstButton instanceof HTMLButtonElement) {
        addFirstButton.addEventListener("click", () => {
            insertNewBlock({ afterRowKey: "" });
        });
    }

    form.querySelectorAll("[data-reorder-item]").forEach((item) => bindBlockItem(item));

    const reorderController = initReorder({
        list,
        toggleButton: form.querySelector("[data-reorder-toggle]"),
        cancelButton: form.querySelector("[data-reorder-cancel]"),
        startPosition: 2,
        positionStep: 2,
        vibrateOnTargetChange: false,
        scrollToMovedItemAfterDrop: true,
        onStart: () => {
            closeAllEditors();
        },
        onChange: () => {
            markDirty();
        },
    });

    const submitWithIntent = (intent) => {
        if (isSubmitting) {
            return;
        }
        const intentInput = document.createElement("input");
        intentInput.type = "hidden";
        intentInput.name = "submit_intent";
        intentInput.value = intent;
        form.appendChild(intentInput);
        isSubmitting = true;
        setDirty(false);
        form.requestSubmit();
    };

    document.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        if (target.closest("[data-reorder-item]")) {
            return;
        }
        if (target.closest("[data-reorder-toggle]") || target.closest("[data-reorder-cancel]")) {
            return;
        }
        closeAllEditors();
    });

    document.addEventListener("click", async (event) => {
        if (!dirty || isSubmitting || !messageBox) {
            return;
        }

        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }

        const link = target.closest("a[href]");
        if (!(link instanceof HTMLAnchorElement)) {
            return;
        }

        const href = (link.getAttribute("href") || "").trim();
        if (!href || href.startsWith("#") || link.target === "_blank" || href.startsWith("javascript:")) {
            return;
        }

        event.preventDefault();
        pendingNavigationUrl = link.href;

        const result = await messageBox.show({
            title: label("leaveTitle"),
            messageMarkdown: label("leaveMessage"),
            showCloseButton: false,
            buttons: [
                { id: "abandon", label: label("abandonLabel"), tone: "danger" },
                { id: "save", label: label("saveAndLeaveLabel"), tone: "success" },
                { id: "stay", label: label("stayLabel"), tone: "neutral" },
            ],
        });

        if (result.buttonId === "abandon") {
            setDirty(false);
            window.location.assign(pendingNavigationUrl);
            return;
        }

        if (result.buttonId === "save") {
            if (nextUrlInput instanceof HTMLInputElement) {
                nextUrlInput.value = pendingNavigationUrl;
            }
            submitWithIntent("save_and_exit");
        }
    }, true);

    window.addEventListener("beforeunload", (event) => {
        if (!dirty || isSubmitting) {
            return;
        }
        event.preventDefault();
        event.returnValue = "";
    });

    form.addEventListener("submit", () => {
        isSubmitting = true;
        setDirty(false);
    });

    ensureVisibleEmptyCallout();
    refreshPositions();

    window.modifySongController = {
        closeAllEditors,
        insertNewBlock,
        markDirty,
        reorderController,
    };
})();
