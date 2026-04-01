(() => {
    const root = document.getElementById("lss-messagebox-root");

    if (!root) {
        return;
    }

    const i18n = {
        closeLabel: "Fermer la fenetre",
        okLabel: "OK",
        yesLabel: "Oui",
        noLabel: "Non",
        cancelLabel: "Annuler",
        confirmLabel: "Confirmer",
        fieldRequiredLabel: "Ce champ est obligatoire.",
        invalidEmailLabel: "Veuillez saisir une adresse e-mail valide.",
        dialogLabel: "Fenetre de dialogue",
        ...(window.LSS_MESSAGE_BOX_CONFIG || {}).i18n,
    };

    const allowedButtonTones = new Set(["neutral", "success", "warning", "danger"]);
    const allowedFieldTypes = new Set(["text", "email", "password", "textarea"]);
    const allowedSizes = new Set(["compact", "default", "wide"]);
    const themeConfig = window.LSS_THEME_CONFIG || null;
    const colorSchemeQuery = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    const focusableSelector = [
        "button:not([disabled])",
        "[href]",
        "input:not([disabled]):not([type='hidden'])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        "[tabindex]:not([tabindex='-1'])",
    ].join(", ");

    const queue = [];
    let activeState = null;
    let dialogIndex = 0;

    const escapeSelectorValue = (value) => {
        if (window.CSS && typeof window.CSS.escape === "function") {
            return window.CSS.escape(value);
        }

        return String(value).replace(/["\\]/g, "\\$&");
    };

    const escapeHtml = (value) => {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    };

    const sanitizeUrl = (rawUrl) => {
        const value = String(rawUrl || "").trim();

        if (!value) {
            return null;
        }

        if (value.startsWith("#") || value.startsWith("/") || value.startsWith("./") || value.startsWith("../")) {
            return value;
        }

        try {
            const parsed = new URL(value, window.location.href);

            if (["http:", "https:", "mailto:", "tel:"].includes(parsed.protocol)) {
                return parsed.href;
            }
        } catch (error) {
            return null;
        }

        return null;
    };

    const buildThemeIconPath = (iconName) => {
        if (!themeConfig) {
            return null;
        }

        const theme = document.documentElement.dataset.theme || themeConfig.defaultTheme || "normal";
        const mode = colorSchemeQuery && colorSchemeQuery.matches ? "dark" : "light";
        return `${themeConfig.iconBasePath}/${theme}/128/${mode}/${iconName}.png`;
    };

    const buildInlineMarkdown = (text) => {
        const codeTokens = [];
        const linkTokens = [];
        let output = escapeHtml(text);

        output = output.replace(/`([^`]+)`/g, (_match, code) => {
            const token = `@@LSSCODE${codeTokens.length}@@`;
            codeTokens.push(`<code>${escapeHtml(code)}</code>`);
            return token;
        });

        output = output.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_match, label, url) => {
            const safeUrl = sanitizeUrl(url);

            if (!safeUrl) {
                return escapeHtml(label);
            }

            const token = `@@LSSLINK${linkTokens.length}@@`;
            linkTokens.push(`<a href="${escapeHtml(safeUrl)}">${escapeHtml(label)}</a>`);
            return token;
        });

        output = output.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        output = output.replace(/\*([^*]+)\*/g, "<em>$1</em>");
        output = output.replace(/_([^_]+)_/g, "<em>$1</em>");

        linkTokens.forEach((html, index) => {
            output = output.replace(`@@LSSLINK${index}@@`, html);
        });

        codeTokens.forEach((html, index) => {
            output = output.replace(`@@LSSCODE${index}@@`, html);
        });

        return output;
    };

    const buildParagraphHtml = (lines) => {
        return `<p>${lines.map((line) => buildInlineMarkdown(line)).join("<br>")}</p>`;
    };

    const renderMarkdown = (markdown) => {
        const normalized = String(markdown || "").replace(/\r\n/g, "\n").trim();

        if (!normalized) {
            return "";
        }

        const lines = normalized.split("\n");
        const blocks = [];
        let index = 0;

        while (index < lines.length) {
            const currentLine = lines[index];
            const trimmed = currentLine.trim();

            if (!trimmed) {
                index += 1;
                continue;
            }

            if (trimmed.startsWith("```")) {
                const codeLines = [];
                index += 1;

                while (index < lines.length && !lines[index].trim().startsWith("```")) {
                    codeLines.push(lines[index]);
                    index += 1;
                }

                if (index < lines.length) {
                    index += 1;
                }

                blocks.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
                continue;
            }

            const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);

            if (headingMatch) {
                const level = headingMatch[1].length;
                blocks.push(`<h${level}>${buildInlineMarkdown(headingMatch[2])}</h${level}>`);
                index += 1;
                continue;
            }

            if (/^>\s?/.test(trimmed)) {
                const quoteLines = [];

                while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
                    quoteLines.push(lines[index].trim().replace(/^>\s?/, ""));
                    index += 1;
                }

                blocks.push(`<blockquote>${buildParagraphHtml(quoteLines)}</blockquote>`);
                continue;
            }

            if (/^[-*]\s+/.test(trimmed)) {
                const items = [];

                while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
                    items.push(lines[index].trim().replace(/^[-*]\s+/, ""));
                    index += 1;
                }

                blocks.push(`<ul>${items.map((item) => `<li>${buildInlineMarkdown(item)}</li>`).join("")}</ul>`);
                continue;
            }

            if (/^\d+\.\s+/.test(trimmed)) {
                const items = [];

                while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
                    items.push(lines[index].trim().replace(/^\d+\.\s+/, ""));
                    index += 1;
                }

                blocks.push(`<ol>${items.map((item) => `<li>${buildInlineMarkdown(item)}</li>`).join("")}</ol>`);
                continue;
            }

            const paragraphLines = [currentLine];
            index += 1;

            while (
                index < lines.length
                && lines[index].trim()
                && !lines[index].trim().startsWith("```")
                && !/^#{1,6}\s+/.test(lines[index].trim())
                && !/^>\s?/.test(lines[index].trim())
                && !/^[-*]\s+/.test(lines[index].trim())
                && !/^\d+\.\s+/.test(lines[index].trim())
            ) {
                paragraphLines.push(lines[index]);
                index += 1;
            }

            blocks.push(buildParagraphHtml(paragraphLines));
        }

        return blocks.join("");
    };

    const getFocusableElements = (container) => {
        return Array.from(container.querySelectorAll(focusableSelector)).filter((element) => {
            if (!(element instanceof HTMLElement)) {
                return false;
            }

            if (element.hidden || element.getAttribute("aria-hidden") === "true") {
                return false;
            }

            return element.offsetParent !== null || element === document.activeElement;
        });
    };

    const normalizeButtons = (buttons) => {
        return (Array.isArray(buttons) ? buttons : []).map((button, index) => {
            if (!button || typeof button.id !== "string" || !button.id.trim()) {
                throw new Error(`Popup button at index ${index} must define a non-empty id.`);
            }

            return {
                id: button.id,
                label: String(button.label ?? button.id),
                tone: allowedButtonTones.has(button.tone) ? button.tone : "neutral",
                disabled: Boolean(button.disabled),
                onClick: typeof button.onClick === "function" ? button.onClick : null,
                validate: typeof button.validate === "boolean" ? button.validate : null,
            };
        });
    };

    const normalizeFields = (fields) => {
        const normalized = Array.isArray(fields) ? fields : [];

        if (normalized.length > 5) {
            throw new Error("Popup supports at most five fields.");
        }

        return normalized.map((field, index) => {
            if (!field || typeof field.id !== "string" || !field.id.trim()) {
                throw new Error(`Popup field at index ${index} must define a non-empty id.`);
            }

            const type = allowedFieldTypes.has(field.type) ? field.type : "text";

            return {
                id: field.id,
                label: String(field.label ?? field.id),
                type,
                value: String(field.value ?? ""),
                placeholder: String(field.placeholder ?? ""),
                required: Boolean(field.required),
                autocomplete: String(field.autocomplete ?? ""),
                maxLength: Number.isInteger(field.maxLength) && field.maxLength > 0 ? field.maxLength : null,
                rows: type === "textarea" && Number.isInteger(field.rows) && field.rows > 0 ? field.rows : 4,
            };
        });
    };

    const normalizeConfig = (config) => {
        const normalized = config && typeof config === "object" ? config : {};
        const buttons = normalizeButtons(normalized.buttons);
        const fields = normalizeFields(normalized.fields);

        if (fields.length && !buttons.length) {
            throw new Error("Popup fields require at least one action button.");
        }

        const size = allowedSizes.has(normalized.size) ? normalized.size : "default";
        const showCloseButton = buttons.length === 0 ? true : normalized.showCloseButton !== false;
        const enterButtonId = typeof normalized.enterButtonId === "string" ? normalized.enterButtonId : null;
        const escapeButtonId = typeof normalized.escapeButtonId === "string" ? normalized.escapeButtonId : null;

        return {
            title: String(normalized.title ?? ""),
            messageMarkdown: String(normalized.messageMarkdown ?? ""),
            buttons,
            fields,
            size,
            initialFocus: typeof normalized.initialFocus === "string" ? normalized.initialFocus : null,
            showCloseButton,
            enterButtonId,
            escapeButtonId,
        };
    };

    const getDefaultEnterButtonId = (config) => {
        if (!config.buttons.length) {
            return null;
        }

        if (config.enterButtonId && config.buttons.some((button) => button.id === config.enterButtonId)) {
            return config.enterButtonId;
        }

        return config.buttons[0].id;
    };

    const getDefaultEscapeButtonId = (config) => {
        if (!config.buttons.length) {
            return null;
        }

        if (config.escapeButtonId && config.buttons.some((button) => button.id === config.escapeButtonId)) {
            return config.escapeButtonId;
        }

        if (config.buttons.length === 1) {
            return config.buttons[0].id;
        }

        return config.buttons[1].id;
    };

    const shouldValidateButton = (config, button) => {
        if (!config.fields.length) {
            return false;
        }

        if (typeof button.validate === "boolean") {
            return button.validate;
        }

        const enterButtonId = getDefaultEnterButtonId(config);
        return button.id === enterButtonId;
    };

    const createFieldElement = (field) => {
        const wrapper = document.createElement("div");
        wrapper.className = "lss-messagebox-field";
        wrapper.dataset.fieldId = field.id;

        const label = document.createElement("label");
        label.className = "lss-messagebox-label";
        label.htmlFor = `lss-messagebox-field-${field.id}`;
        label.textContent = field.label;

        if (field.required) {
            const required = document.createElement("span");
            required.className = "lss-messagebox-required";
            required.textContent = " *";
            label.appendChild(required);
        }

        const input = document.createElement(field.type === "textarea" ? "textarea" : "input");
        input.id = `lss-messagebox-field-${field.id}`;
        input.name = field.id;
        input.className = field.type === "textarea" ? "lss-messagebox-textarea" : "lss-messagebox-input";
        input.placeholder = field.placeholder;
        input.value = field.value;
        input.dataset.fieldId = field.id;

        if (field.type !== "textarea") {
            input.type = field.type;
        } else {
            input.rows = field.rows;
        }

        if (field.required) {
            input.required = true;
        }

        if (field.autocomplete) {
            input.autocomplete = field.autocomplete;
        }

        if (field.maxLength) {
            input.maxLength = field.maxLength;
        }

        const error = document.createElement("p");
        error.className = "lss-messagebox-error";
        error.id = `lss-messagebox-error-${field.id}`;
        error.setAttribute("aria-live", "polite");

        wrapper.append(label, input, error);

        return wrapper;
    };

    const buildDialog = (normalizedConfig) => {
        dialogIndex += 1;

        const titleId = `lss-messagebox-title-${dialogIndex}`;
        const overlay = document.createElement("div");
        overlay.className = "lss-messagebox-overlay";

        const panel = document.createElement("section");
        panel.className = "lss-messagebox-panel";
        panel.dataset.size = normalizedConfig.size;
        panel.setAttribute("role", "dialog");
        panel.setAttribute("aria-modal", "true");
        panel.tabIndex = -1;

        const header = document.createElement("header");
        header.className = "lss-messagebox-header";

        const title = document.createElement("h2");
        title.className = "lss-messagebox-title";
        title.id = titleId;
        title.textContent = normalizedConfig.title;

        if (normalizedConfig.title) {
            panel.setAttribute("aria-labelledby", titleId);
        } else {
            panel.setAttribute("aria-label", i18n.dialogLabel);
        }

        header.appendChild(title);

        let closeButton = null;

        if (normalizedConfig.showCloseButton) {
            closeButton = document.createElement("button");
            closeButton.type = "button";
            closeButton.className = "lss-messagebox-close";
            closeButton.dataset.action = "close";
            closeButton.setAttribute("aria-label", i18n.closeLabel);

            const closeIcon = document.createElement("img");
            closeIcon.className = "lss-messagebox-close-icon";
            closeIcon.alt = "";
            closeIcon.setAttribute("aria-hidden", "true");
            closeIcon.src = buildThemeIconPath("close") || "";
            closeButton.appendChild(closeIcon);
            header.appendChild(closeButton);
        }

        const body = document.createElement("div");
        body.className = "lss-messagebox-body";

        const content = document.createElement("div");
        content.className = "lss-messagebox-content";
        body.appendChild(content);

        if (normalizedConfig.messageMarkdown) {
            const markdown = document.createElement("div");
            markdown.className = "lss-messagebox-markdown";
            markdown.innerHTML = renderMarkdown(normalizedConfig.messageMarkdown);
            content.appendChild(markdown);
        }

        let form = null;

        if (normalizedConfig.fields.length) {
            form = document.createElement("form");
            form.className = "lss-messagebox-form";
            form.noValidate = true;

            normalizedConfig.fields.forEach((field) => {
                form.appendChild(createFieldElement(field));
            });

            content.appendChild(form);
        }

        const footer = document.createElement("footer");
        footer.className = "lss-messagebox-footer";

        normalizedConfig.buttons.forEach((button) => {
            const element = document.createElement("button");
            element.type = "button";
            element.className = "lss-messagebox-button";
            element.dataset.buttonId = button.id;
            element.dataset.tone = button.tone;
            element.textContent = button.label;
            element.disabled = button.disabled;
            footer.appendChild(element);
        });

        panel.append(header, body, footer);
        overlay.appendChild(panel);

        return {
            overlay,
            panel,
            closeButton,
            form,
            footer,
        };
    };

    const getFieldValues = (state) => {
        if (!state.form) {
            return {};
        }

        const values = {};
        const elements = state.form.querySelectorAll("[data-field-id]");

        elements.forEach((element) => {
            if (
                element instanceof HTMLInputElement
                || element instanceof HTMLTextAreaElement
                || element instanceof HTMLSelectElement
            ) {
                values[element.dataset.fieldId] = element.value;
            }
        });

        return values;
    };

    const clearFieldErrors = (state) => {
        if (!state.form) {
            return;
        }

        state.form.querySelectorAll(".lss-messagebox-field").forEach((wrapper) => {
            wrapper.classList.remove("is-invalid");
        });

        state.form.querySelectorAll(".lss-messagebox-error").forEach((error) => {
            error.textContent = "";
        });

        state.form.querySelectorAll("[aria-invalid='true']").forEach((input) => {
            input.removeAttribute("aria-invalid");
            input.removeAttribute("aria-describedby");
        });
    };

    const setFieldError = (state, fieldId, message) => {
        if (!state.form) {
            return;
        }

        const wrapper = state.form.querySelector(`.lss-messagebox-field[data-field-id="${escapeSelectorValue(fieldId)}"]`);
        const input = state.form.querySelector(`[data-field-id="${escapeSelectorValue(fieldId)}"]`);

        if (!(wrapper instanceof HTMLElement) || !(input instanceof HTMLElement)) {
            return;
        }

        const error = wrapper.querySelector(".lss-messagebox-error");

        if (!(error instanceof HTMLElement)) {
            return;
        }

        wrapper.classList.add("is-invalid");
        input.setAttribute("aria-invalid", "true");
        input.setAttribute("aria-describedby", error.id);
        error.textContent = message;
    };

    const validateFields = (state, button) => {
        if (!state.form || !shouldValidateButton(state.config, button)) {
            return true;
        }

        clearFieldErrors(state);
        let firstInvalidInput = null;

        state.config.fields.forEach((field) => {
            const selector = `[data-field-id="${escapeSelectorValue(field.id)}"]`;
            const input = state.form.querySelector(selector);

            if (!(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement)) {
                return;
            }

            const value = input.value.trim();

            if (field.required && !value) {
                setFieldError(state, field.id, i18n.fieldRequiredLabel);
                firstInvalidInput = firstInvalidInput || input;
                return;
            }

            if (field.type === "email" && value && !input.checkValidity()) {
                setFieldError(state, field.id, i18n.invalidEmailLabel);
                firstInvalidInput = firstInvalidInput || input;
            }
        });

        if (firstInvalidInput) {
            firstInvalidInput.focus();
            return false;
        }

        return true;
    };

    const setBusyState = (state, isBusy) => {
        state.isBusy = isBusy;

        state.panel.querySelectorAll(".lss-messagebox-button").forEach((button) => {
            if (button instanceof HTMLButtonElement) {
                button.disabled = isBusy || state.disabledButtonIds.has(button.dataset.buttonId);
            }
        });

        if (state.closeButton) {
            state.closeButton.disabled = isBusy;
        }

        state.panel.setAttribute("aria-busy", isBusy ? "true" : "false");
    };

    const resolveAndClose = (state, result) => {
        if (!activeState || activeState !== state || state.isClosed) {
            return;
        }

        state.isClosed = true;
        document.body.classList.remove("lss-messagebox-open");
        document.removeEventListener("keydown", state.onKeyDown, true);
        document.removeEventListener("focusin", state.onFocusIn, true);

        root.hidden = true;
        root.innerHTML = "";
        activeState = null;

        if (state.restoreFocus && typeof state.restoreFocus.focus === "function") {
            window.requestAnimationFrame(() => {
                state.restoreFocus.focus();
            });
        }

        state.resolve(result);

        window.requestAnimationFrame(() => {
            showNextInQueue();
        });
    };

    const buildActionContext = (state, buttonId, reason) => {
        return {
            buttonId,
            values: getFieldValues(state),
            close: (payload) => {
                resolveAndClose(state, {
                    reason,
                    buttonId,
                    values: getFieldValues(state),
                    payload,
                });
            },
            keepOpen: () => {
                state.keepOpenRequested = true;
            },
            setFieldError: (fieldId, message) => {
                setFieldError(state, fieldId, String(message || ""));
            },
        };
    };

    const triggerButton = async (state, buttonId, reason = "button") => {
        if (!activeState || activeState !== state || state.isBusy) {
            return;
        }

        const button = state.config.buttons.find((candidate) => candidate.id === buttonId);

        if (!button || button.disabled) {
            return;
        }

        if (!validateFields(state, button)) {
            return;
        }

        clearFieldErrors(state);
        state.keepOpenRequested = false;
        setBusyState(state, true);

        const context = buildActionContext(state, button.id, reason);

        try {
            let callbackResult = true;

            if (button.onClick) {
                callbackResult = await button.onClick(context);
            }

            if (!activeState || activeState !== state || state.isClosed) {
                return;
            }

            if (state.keepOpenRequested || callbackResult === false) {
                setBusyState(state, false);
                return;
            }

            resolveAndClose(state, {
                reason,
                buttonId: button.id,
                values: getFieldValues(state),
            });
        } catch (error) {
            setBusyState(state, false);
            window.console.error("LSSMessageBox button callback failed.", error);
        }
    };

    const closeActivePopup = (result = {}) => {
        if (!activeState) {
            return false;
        }

        resolveAndClose(activeState, {
            reason: "programmatic",
            buttonId: null,
            values: getFieldValues(activeState),
            ...result,
        });

        return true;
    };

    const moveFocusToInitialTarget = (state) => {
        const { initialFocus } = state.config;
        let target = null;

        if (initialFocus === "close" && state.closeButton) {
            target = state.closeButton;
        } else if (initialFocus === "first-field" && state.form) {
            target = state.form.querySelector("[data-field-id]");
        } else if (initialFocus && initialFocus.startsWith("button:")) {
            target = state.panel.querySelector(`[data-button-id="${escapeSelectorValue(initialFocus.slice(7))}"]`);
        } else if (initialFocus && initialFocus.startsWith("field:")) {
            target = state.panel.querySelector(`[data-field-id="${escapeSelectorValue(initialFocus.slice(6))}"]`);
        }

        if (!(target instanceof HTMLElement)) {
            if (state.form) {
                target = state.form.querySelector("[data-field-id]");
            }
        }

        if (!(target instanceof HTMLElement)) {
            const enterButtonId = getDefaultEnterButtonId(state.config);

            if (enterButtonId) {
                target = state.panel.querySelector(`[data-button-id="${escapeSelectorValue(enterButtonId)}"]`);
            }
        }

        if (!(target instanceof HTMLElement) && state.closeButton) {
            target = state.closeButton;
        }

        if (!(target instanceof HTMLElement)) {
            target = getFocusableElements(state.panel)[0] || state.panel;
        }

        target.focus();
    };

    const trapFocus = (state, event) => {
        if (event.key !== "Tab") {
            return;
        }

        const focusableElements = getFocusableElements(state.panel);

        if (!focusableElements.length) {
            event.preventDefault();
            state.panel.focus();
            return;
        }

        const first = focusableElements[0];
        const last = focusableElements[focusableElements.length - 1];

        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
            return;
        }

        if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    };

    const handleKeyDown = (state, event) => {
        if (!activeState || activeState !== state) {
            return;
        }

        trapFocus(state, event);

        if (state.isBusy && event.key !== "Tab") {
            return;
        }

        if (event.key === "Escape") {
            event.preventDefault();

            const escapeButtonId = getDefaultEscapeButtonId(state.config);

            if (escapeButtonId) {
                triggerButton(state, escapeButtonId, "escape");
                return;
            }

            resolveAndClose(state, {
                reason: "escape",
                buttonId: null,
                values: getFieldValues(state),
            });
            return;
        }

        if (event.key !== "Enter") {
            return;
        }

        const target = event.target;

        if (target instanceof HTMLTextAreaElement) {
            return;
        }

        if (
            target instanceof HTMLButtonElement
            || target instanceof HTMLAnchorElement
            || (target instanceof HTMLInputElement && ["button", "submit", "reset"].includes(target.type))
        ) {
            return;
        }

        const enterButtonId = getDefaultEnterButtonId(state.config);

        if (!enterButtonId) {
            return;
        }

        event.preventDefault();
        triggerButton(state, enterButtonId, "button");
    };

    const showNextInQueue = () => {
        if (activeState || !queue.length) {
            return;
        }

        const next = queue.shift();
        const dialog = buildDialog(next.config);

        root.innerHTML = "";
        root.hidden = false;
        root.appendChild(dialog.overlay);
        document.body.classList.add("lss-messagebox-open");

        const state = {
            ...dialog,
            config: next.config,
            resolve: next.resolve,
            restoreFocus: document.activeElement instanceof HTMLElement ? document.activeElement : null,
            keepOpenRequested: false,
            isBusy: false,
            isClosed: false,
            disabledButtonIds: new Set(next.config.buttons.filter((button) => button.disabled).map((button) => button.id)),
        };

        state.onKeyDown = (event) => handleKeyDown(state, event);
        state.onFocusIn = (event) => {
            if (!state.panel.contains(event.target)) {
                moveFocusToInitialTarget(state);
            }
        };

        activeState = state;

        if (state.closeButton) {
            state.closeButton.addEventListener("click", () => {
                resolveAndClose(state, {
                    reason: "close",
                    buttonId: null,
                    values: getFieldValues(state),
                });
            });
        }

        state.overlay.addEventListener("click", (event) => {
            if (event.target === state.overlay) {
                moveFocusToInitialTarget(state);
            }
        });

        state.panel.querySelectorAll("[data-button-id]").forEach((buttonElement) => {
            buttonElement.addEventListener("click", () => {
                triggerButton(state, buttonElement.dataset.buttonId, "button");
            });
        });

        document.addEventListener("keydown", state.onKeyDown, true);
        document.addEventListener("focusin", state.onFocusIn, true);

        setBusyState(state, false);
        window.requestAnimationFrame(() => {
            moveFocusToInitialTarget(state);
        });
    };

    const enqueuePopup = (config) => {
        const normalizedConfig = normalizeConfig(config);

        return new Promise((resolve) => {
            queue.push({ config: normalizedConfig, resolve });
            showNextInQueue();
        });
    };

    const show = (config) => {
        try {
            return enqueuePopup(config);
        } catch (error) {
            return Promise.reject(error);
        }
    };

    const alert = (config = {}) => {
        const hasButtons = Array.isArray(config.buttons) && config.buttons.length > 0;

        return show({
            ...config,
            buttons: hasButtons ? config.buttons : [
                {
                    id: "ok",
                    label: i18n.okLabel,
                    tone: "neutral",
                },
            ],
            showCloseButton: typeof config.showCloseButton === "boolean" ? config.showCloseButton : false,
        });
    };

    const confirm = (config = {}) => {
        const hasButtons = Array.isArray(config.buttons) && config.buttons.length > 0;

        return show({
            ...config,
            buttons: hasButtons ? config.buttons : [
                {
                    id: "yes",
                    label: i18n.yesLabel,
                    tone: "success",
                },
                {
                    id: "no",
                    label: i18n.noLabel,
                    tone: "neutral",
                },
            ],
            showCloseButton: typeof config.showCloseButton === "boolean" ? config.showCloseButton : false,
        });
    };

    const prompt = (config = {}) => {
        const hasButtons = Array.isArray(config.buttons) && config.buttons.length > 0;

        return show({
            ...config,
            buttons: hasButtons ? config.buttons : [
                {
                    id: "confirm",
                    label: i18n.confirmLabel,
                    tone: "success",
                    validate: true,
                },
                {
                    id: "cancel",
                    label: i18n.cancelLabel,
                    tone: "neutral",
                    validate: false,
                },
            ],
            showCloseButton: typeof config.showCloseButton === "boolean" ? config.showCloseButton : false,
        });
    };

    window.LSSMessageBox = {
        show,
        alert,
        confirm,
        prompt,
        close: closeActivePopup,
        isOpen: () => Boolean(activeState),
    };
})();
