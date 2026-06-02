(() => {
    const HEX_RE = /^#([0-9a-fA-F]{6})$/;

    const normalizeHex = (value) => {
        const raw = String(value || "").trim();
        if (!raw) {
            return null;
        }

        const shortMatch = /^#([0-9a-fA-F]{3})$/.exec(raw);
        if (shortMatch) {
            const shortHex = shortMatch[1].toUpperCase();
            return `#${shortHex[0]}${shortHex[0]}${shortHex[1]}${shortHex[1]}${shortHex[2]}${shortHex[2]}`;
        }

        const match = HEX_RE.exec(raw);
        if (!match) {
            return null;
        }
        return `#${match[1].toUpperCase()}`;
    };

    const setupHexPicker = (textInput) => {
        if (!(textInput instanceof HTMLInputElement) || !textInput.id) {
            return;
        }

        const trigger = document.querySelector(`[data-hex-trigger-for="${textInput.id}"]`);
        if (!(trigger instanceof HTMLButtonElement)) {
            return;
        }

        const picker = document.createElement("input");
        picker.type = "color";
        picker.tabIndex = -1;
        picker.setAttribute("aria-hidden", "true");
        picker.style.position = "absolute";
        picker.style.width = "1px";
        picker.style.height = "1px";
        picker.style.opacity = "0";
        picker.style.pointerEvents = "auto";
        picker.style.left = "-10000px";

        const initialHex = normalizeHex(textInput.value);
        picker.value = initialHex || "#FFFFFF";
        document.body.appendChild(picker);

        const syncPickerFromInput = () => {
            const normalized = normalizeHex(textInput.value);
            if (normalized) {
                picker.value = normalized;
                textInput.value = normalized;
            }
        };

        const openPickerFallback = () => {
            // Some browsers block click on fully hidden color inputs.
            // Temporarily place it in viewport, still visually discreet.
            const previousLeft = picker.style.left;
            const previousTop = picker.style.top;
            const previousOpacity = picker.style.opacity;
            const previousWidth = picker.style.width;
            const previousHeight = picker.style.height;
            const previousPosition = picker.style.position;

            picker.style.position = "fixed";
            picker.style.left = "12px";
            picker.style.top = "12px";
            picker.style.opacity = "0.01";
            picker.style.width = "28px";
            picker.style.height = "28px";

            try {
                picker.focus();
                picker.click();
            } finally {
                window.setTimeout(() => {
                    picker.style.left = previousLeft;
                    picker.style.top = previousTop;
                    picker.style.opacity = previousOpacity;
                    picker.style.width = previousWidth;
                    picker.style.height = previousHeight;
                    picker.style.position = previousPosition;
                }, 200);
            }
        };

        trigger.addEventListener("click", () => {
            syncPickerFromInput();
            if (typeof picker.showPicker === "function") {
                try {
                    picker.showPicker();
                    return;
                } catch (_error) {
                    // fall back below
                }
            }
            openPickerFallback();
        });

        picker.addEventListener("input", () => {
            textInput.value = picker.value.toUpperCase();
        });

        picker.addEventListener("change", () => {
            textInput.value = picker.value.toUpperCase();
        });

        textInput.addEventListener("blur", syncPickerFromInput);
    };

    document.querySelectorAll("input[data-hex-input]").forEach((input) => {
        setupHexPicker(input);
    });
})();
