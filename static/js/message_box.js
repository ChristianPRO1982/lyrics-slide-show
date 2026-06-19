(() => {
    const root = document.getElementById("lss-messagebox-root");

    if (!root) {
        return;
    }

    const i18n = {
        closeLabel: "",
        okLabel: "",
        yesLabel: "",
        noLabel: "",
        cancelLabel: "",
        confirmLabel: "",
        fieldRequiredLabel: "",
        invalidEmailLabel: "",
        dialogLabel: "",
        ...(window.LSS_MESSAGE_BOX_CONFIG || {}).i18n,
    };

    const allowedButtonTones = new Set(["neutral", "success", "warning", "danger"]);
    const allowedFieldTypes = new Set(["text", "email", "password", "textarea", "color", "number", "select", "datetime-local"]);
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

    const findFieldInput = (container, fieldId) => {
        const escapedFieldId = escapeSelectorValue(fieldId);
        return container.querySelector(
            `input[data-field-id="${escapedFieldId}"], textarea[data-field-id="${escapedFieldId}"], select[data-field-id="${escapedFieldId}"]`
        );
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

    const normalizeSelectOptions = (options) => {
        return (Array.isArray(options) ? options : []).map((option, optionIndex) => {
            if (option == null || typeof option !== "object") {
                return {
                    value: `option-${optionIndex}`,
                    label: `option-${optionIndex}`,
                };
            }
            const value = String(option.value ?? `option-${optionIndex}`);
            return {
                value,
                label: String(option.label ?? value),
            };
        });
    };

    const normalizeFields = (fields) => {
        const normalized = Array.isArray(fields) ? fields : [];

        if (normalized.length > 12) {
            throw new Error("Popup supports at most twelve fields.");
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
                readonly: Boolean(field.readonly),
                placeholder: String(field.placeholder ?? ""),
                required: Boolean(field.required),
                autocomplete: String(field.autocomplete ?? ""),
                maxLength: Number.isInteger(field.maxLength) && field.maxLength > 0 ? field.maxLength : null,
                rows: type === "textarea" && Number.isInteger(field.rows) && field.rows > 0 ? field.rows : 4,
                min: Number.isFinite(field.min) ? Number(field.min) : null,
                max: Number.isFinite(field.max) ? Number(field.max) : null,
                step: Number.isFinite(field.step) && Number(field.step) > 0 ? Number(field.step) : null,
                size: type === "select" && Number.isInteger(field.size) && field.size > 1 ? field.size : null,
                options: type === "select" ? normalizeSelectOptions(field.options) : [],
            };
        });
    };

    const normalizeTabbedSelect = (tabbedSelect, fields, buttons) => {
        if (!tabbedSelect || typeof tabbedSelect !== "object") {
            return null;
        }

        const fieldId = typeof tabbedSelect.fieldId === "string" ? tabbedSelect.fieldId.trim() : "";
        if (!fieldId) {
            throw new Error("tabbedSelect.fieldId must be a non-empty string.");
        }

        const selectField = fields.find((field) => field.id === fieldId);
        if (!selectField || selectField.type !== "select") {
            throw new Error("tabbedSelect.fieldId must target an existing select field.");
        }

        const tabs = (Array.isArray(tabbedSelect.tabs) ? tabbedSelect.tabs : []).map((tab, index) => {
            if (!tab || typeof tab.id !== "string" || !tab.id.trim()) {
                throw new Error(`tabbedSelect tab at index ${index} must define a non-empty id.`);
            }
            return {
                id: tab.id,
                label: String(tab.label ?? tab.id),
                options: normalizeSelectOptions(tab.options),
                emptyMessage: String(tab.emptyMessage ?? ""),
            };
        });

        if (!tabs.length) {
            throw new Error("tabbedSelect requires at least one tab.");
        }

        const initialTabId = typeof tabbedSelect.initialTabId === "string"
            && tabs.some((tab) => tab.id === tabbedSelect.initialTabId)
            ? tabbedSelect.initialTabId
            : tabs[0].id;
        const submitButtonId = typeof tabbedSelect.submitButtonId === "string"
            && buttons.some((button) => button.id === tabbedSelect.submitButtonId)
            ? tabbedSelect.submitButtonId
            : null;

        return {
            fieldId,
            fieldLabel: String(tabbedSelect.fieldLabel ?? selectField.label),
            size: Number.isInteger(tabbedSelect.size) && tabbedSelect.size > 1
                ? tabbedSelect.size
                : selectField.size,
            initialTabId,
            submitButtonId,
            tabs,
        };
    };

    const normalizeConfig = (config) => {
        const normalized = config && typeof config === "object" ? config : {};
        const buttons = normalizeButtons(normalized.buttons);
        const fields = normalizeFields(normalized.fields);
        const tabbedSelect = normalizeTabbedSelect(normalized.tabbedSelect, fields, buttons);

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
            onFieldChange: typeof normalized.onFieldChange === "function" ? normalized.onFieldChange : null,
            preview: normalized.preview && typeof normalized.preview === "object"
                ? {
                    label: String(normalized.preview.label ?? ""),
                    text: String(normalized.preview.text ?? ""),
                    className: String(normalized.preview.className ?? "").trim(),
                }
                : null,
            fontSamples: Array.isArray(normalized.fontSamples)
                ? normalized.fontSamples.map((sample) => ({
                    fontFamily: String((sample && sample.fontFamily) ?? "").trim(),
                    sample: String((sample && sample.sample) ?? ""),
                    label: String((sample && sample.label) ?? ""),
                })).filter((sample) => sample.fontFamily)
                : [],
            tabbedSelect,
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

        const isTextArea = field.type === "textarea";
        const isSelect = field.type === "select";
        const input = document.createElement(isTextArea ? "textarea" : (isSelect ? "select" : "input"));
        input.id = `lss-messagebox-field-${field.id}`;
        input.name = field.id;
        input.className = isTextArea
            ? "lss-messagebox-textarea"
            : (isSelect ? "lss-messagebox-select" : "lss-messagebox-input");
        input.value = field.value;
        input.dataset.fieldId = field.id;

        if (!isTextArea && !isSelect) {
            input.type = field.type;
        } else if (isTextArea) {
            input.rows = field.rows;
        }

        if (field.readonly && (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement)) {
            input.readOnly = true;
            input.setAttribute("aria-readonly", "true");
        }

        if (!isSelect) {
            input.placeholder = field.placeholder;
        }

        if (isSelect) {
            field.options.forEach((option) => {
                const optionElement = document.createElement("option");
                optionElement.value = option.value;
                optionElement.textContent = option.label;
                input.appendChild(optionElement);
            });
            if (field.size !== null) {
                input.size = field.size;
            }
            if (field.options.some((option) => option.value === field.value)) {
                input.value = field.value;
            } else if (field.options.length > 0) {
                input.value = field.options[0].value;
            }
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

        if (field.min !== null && "min" in input) {
            input.min = String(field.min);
        }

        if (field.max !== null && "max" in input) {
            input.max = String(field.max);
        }

        if (field.step !== null && "step" in input) {
            input.step = String(field.step);
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

        if (normalizedConfig.fontSamples.length) {
            const sampleList = document.createElement("div");
            sampleList.className = "lss-messagebox-font-samples";
            normalizedConfig.fontSamples.forEach((sample) => {
                const item = document.createElement("div");
                item.className = "lss-messagebox-font-sample";
                item.style.fontFamily = `'${sample.fontFamily}', sans-serif`;

                const textNode = document.createTextNode(`${sample.sample} `);
                const labelNode = document.createElement("strong");
                labelNode.textContent = `[${sample.label || sample.fontFamily}]`;
                item.append(textNode, labelNode);
                sampleList.appendChild(item);
            });
            content.appendChild(sampleList);
        }

        let previewElement = null;
        if (normalizedConfig.preview) {
            const previewWrapper = document.createElement("div");
            previewWrapper.className = "lss-messagebox-live-preview-wrapper";

            if (normalizedConfig.preview.label) {
                const previewLabel = document.createElement("p");
                previewLabel.className = "lss-messagebox-live-preview-label";
                previewLabel.textContent = normalizedConfig.preview.label;
                previewWrapper.appendChild(previewLabel);
            }

            previewElement = document.createElement("div");
            previewElement.className = "lss-messagebox-live-preview";
            if (normalizedConfig.preview.className) {
                previewElement.classList.add(normalizedConfig.preview.className);
            }
            previewElement.textContent = normalizedConfig.preview.text;
            previewWrapper.appendChild(previewElement);
            content.appendChild(previewWrapper);
        }

        let form = null;
        let tabbedSelectController = null;

        if (normalizedConfig.fields.length) {
            form = document.createElement("form");
            form.className = "lss-messagebox-form";
            form.noValidate = true;

            normalizedConfig.fields.forEach((field) => {
                form.appendChild(createFieldElement(field));
            });

            content.appendChild(form);
        }

        if (normalizedConfig.tabbedSelect && form) {
            const tabbedSelect = normalizedConfig.tabbedSelect;
            const selectInput = findFieldInput(form, tabbedSelect.fieldId);
            const escapedFieldId = escapeSelectorValue(tabbedSelect.fieldId);
            const fieldWrapper = form.querySelector(`.lss-messagebox-field[data-field-id="${escapedFieldId}"]`);
            const fieldLabel = fieldWrapper instanceof HTMLElement
                ? fieldWrapper.querySelector(".lss-messagebox-label")
                : null;
            const errorNode = fieldWrapper instanceof HTMLElement
                ? fieldWrapper.querySelector(".lss-messagebox-error")
                : null;

            if (selectInput instanceof HTMLSelectElement && fieldWrapper instanceof HTMLElement) {
                const tabsNode = document.createElement("div");
                tabsNode.className = "lss-messagebox-tabbed-select-tabs";
                tabsNode.setAttribute("role", "tablist");

                const emptyNode = document.createElement("p");
                emptyNode.className = "lss-messagebox-tabbed-select-empty";
                emptyNode.hidden = true;

                let updateSubmitButtonState = () => {};
                let activeTabId = tabbedSelect.initialTabId;
                const tabButtons = new Map();

                const applyTab = (requestedTabId) => {
                    const activeTab = tabbedSelect.tabs.find((tab) => tab.id === requestedTabId) || tabbedSelect.tabs[0];
                    activeTabId = activeTab.id;
                    const currentValue = selectInput.value;

                    selectInput.innerHTML = "";
                    activeTab.options.forEach((option) => {
                        const optionElement = document.createElement("option");
                        optionElement.value = option.value;
                        optionElement.textContent = option.label;
                        selectInput.appendChild(optionElement);
                    });

                    if (tabbedSelect.size !== null) {
                        selectInput.size = tabbedSelect.size;
                    }

                    tabButtons.forEach((button, tabId) => {
                        button.setAttribute("aria-selected", tabId === activeTab.id ? "true" : "false");
                        button.classList.toggle("is-active", tabId === activeTab.id);
                    });

                    const hasOptions = activeTab.options.length > 0;
                    selectInput.disabled = !hasOptions;

                    if (hasOptions) {
                        if (activeTab.options.some((option) => option.value === currentValue)) {
                            selectInput.value = currentValue;
                        } else {
                            selectInput.value = activeTab.options[0].value;
                        }
                        emptyNode.hidden = true;
                        emptyNode.textContent = "";
                    } else {
                        selectInput.value = "";
                        emptyNode.textContent = activeTab.emptyMessage;
                        emptyNode.hidden = !activeTab.emptyMessage;
                    }

                    if (tabbedSelect.submitButtonId) {
                        updateSubmitButtonState(tabbedSelect.submitButtonId, !hasOptions);
                    }
                };

                tabbedSelect.tabs.forEach((tab) => {
                    const tabButton = document.createElement("button");
                    tabButton.type = "button";
                    tabButton.className = "lss-messagebox-tabbed-select-tab";
                    tabButton.setAttribute("role", "tab");
                    tabButton.dataset.tabId = tab.id;
                    tabButton.textContent = tab.label;
                    tabButton.addEventListener("click", () => {
                        applyTab(tab.id);
                    });
                    tabButtons.set(tab.id, tabButton);
                    tabsNode.appendChild(tabButton);
                });

                if (fieldLabel instanceof HTMLElement) {
                    if (fieldLabel.nextSibling) {
                        fieldWrapper.insertBefore(tabsNode, fieldLabel.nextSibling);
                    } else {
                        fieldWrapper.appendChild(tabsNode);
                    }
                } else {
                    fieldWrapper.insertBefore(tabsNode, fieldWrapper.firstChild);
                }

                if (errorNode instanceof HTMLElement) {
                    fieldWrapper.insertBefore(emptyNode, errorNode);
                } else {
                    fieldWrapper.appendChild(emptyNode);
                }

                applyTab(activeTabId);

                tabbedSelectController = {
                    bindRuntime: (setButtonDisabled) => {
                        updateSubmitButtonState = typeof setButtonDisabled === "function" ? setButtonDisabled : () => {};
                        applyTab(activeTabId);
                    },
                };
            }
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
            previewElement,
            tabbedSelectController,
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
        const input = findFieldInput(state.form, fieldId);

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

    const setFieldValue = (state, fieldId, value) => {
        if (!state.form) {
            return false;
        }

        const input = findFieldInput(state.form, fieldId);
        if (!(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement || input instanceof HTMLSelectElement)) {
            return false;
        }

        const nextValue = String(value ?? "");
        if (input.value === nextValue) {
            return false;
        }

        input.value = nextValue;
        return true;
    };

    const triggerFieldChangeHook = (state, fieldId) => {
        if (!state.config.onFieldChange) {
            return;
        }

        try {
            state.config.onFieldChange({
                fieldId,
                value: fieldId ? (getFieldValues(state)[fieldId] ?? "") : "",
                values: getFieldValues(state),
                previewElement: state.previewElement,
                setFieldValue: (targetFieldId, targetValue) => {
                    const changed = setFieldValue(state, targetFieldId, targetValue);
                    if (changed) {
                        triggerFieldChangeHook(state, targetFieldId);
                    }
                    return changed;
                },
                setFieldError: (targetFieldId, message) => {
                    setFieldError(state, targetFieldId, String(message || ""));
                },
            });
        } catch (error) {
            window.console.error("LSSMessageBox onFieldChange callback failed.", error);
        }
    };

    const validateFields = (state, button) => {
        if (!state.form || !shouldValidateButton(state.config, button)) {
            return true;
        }

        clearFieldErrors(state);
        let firstInvalidInput = null;

        state.config.fields.forEach((field) => {
            const input = findFieldInput(state.form, field.id);

            if (!(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement || input instanceof HTMLSelectElement)) {
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
                button.disabled = isBusy
                    || state.disabledButtonIds.has(button.dataset.buttonId)
                    || state.runtimeDisabledButtonIds.has(button.dataset.buttonId);
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
            setFieldValue: (fieldId, value) => {
                const changed = setFieldValue(state, fieldId, value);
                if (changed) {
                    triggerFieldChangeHook(state, fieldId);
                }
                return changed;
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
            target = state.form.querySelector("input[data-field-id], textarea[data-field-id], select[data-field-id]");
        } else if (initialFocus && initialFocus.startsWith("button:")) {
            target = state.panel.querySelector(`[data-button-id="${escapeSelectorValue(initialFocus.slice(7))}"]`);
        } else if (initialFocus && initialFocus.startsWith("field:")) {
            target = findFieldInput(state.panel, initialFocus.slice(6));
        }

        if (!(target instanceof HTMLElement)) {
            if (state.form) {
                target = state.form.querySelector("input[data-field-id], textarea[data-field-id], select[data-field-id]");
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

            if (state.closeButton) {
                resolveAndClose(state, {
                    reason: "escape",
                    buttonId: null,
                    values: getFieldValues(state),
                });
                return;
            }

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
            runtimeDisabledButtonIds: new Set(),
        };

        state.onKeyDown = (event) => handleKeyDown(state, event);
        state.onFocusIn = (event) => {
            if (!state.panel.contains(event.target)) {
                moveFocusToInitialTarget(state);
            }
        };

        activeState = state;

        if (state.tabbedSelectController && typeof state.tabbedSelectController.bindRuntime === "function") {
            state.tabbedSelectController.bindRuntime((buttonId, isDisabled) => {
                if (!buttonId) {
                    return;
                }
                if (isDisabled) {
                    state.runtimeDisabledButtonIds.add(buttonId);
                } else {
                    state.runtimeDisabledButtonIds.delete(buttonId);
                }
                setBusyState(state, state.isBusy);
            });
        }

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

        if (state.form) {
            state.form.querySelectorAll("input[data-field-id], textarea[data-field-id], select[data-field-id]").forEach((fieldElement) => {
                fieldElement.addEventListener("input", () => {
                    triggerFieldChangeHook(state, fieldElement.dataset.fieldId || "");
                });
                fieldElement.addEventListener("change", () => {
                    triggerFieldChangeHook(state, fieldElement.dataset.fieldId || "");
                });
            });
        }

        document.addEventListener("keydown", state.onKeyDown, true);
        document.addEventListener("focusin", state.onFocusIn, true);

        setBusyState(state, false);
        window.requestAnimationFrame(() => {
            triggerFieldChangeHook(state, "");
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
