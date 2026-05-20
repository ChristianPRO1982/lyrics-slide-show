(() => {
    const root = document.querySelector("[data-lyrics-display-root]");
    if (!(root instanceof HTMLElement)) {
        return;
    }

    const slideNode = root.querySelector("[data-lyrics-display-slide]");
    if (!(slideNode instanceof HTMLElement)) {
        return;
    }

    const waitingNode = root.querySelector("[data-lyrics-display-waiting]");
    const i18n = window.LSS_LYRICS_DISPLAY_I18N || {};
    const waitingLabel = String(i18n.waitingLabel || "");
    const f11ReminderLabel = String(i18n.f11ReminderLabel || "");
    const forceReminderOnLoad = new URLSearchParams(window.location.search).get("remind") === "1";
    const sessionId = String(root.getAttribute("data-display-session-id") || "").trim();
    if (!sessionId) {
        return;
    }

    const bridgeStorageKey = `lss-lyrics-bridge:${sessionId}`;
    const frameStorageKey = `lss-lyrics-display-lastframe:${sessionId}`;

    let channel = null;
    if (typeof window.BroadcastChannel === "function") {
        try {
            channel = new window.BroadcastChannel(bridgeStorageKey);
        } catch (_error) {
            channel = null;
        }
    }

    const clearWaiting = () => {
        if (waitingNode instanceof HTMLElement) {
            waitingNode.hidden = true;
        }
    };

    const setWaiting = () => {
        if (waitingNode instanceof HTMLElement) {
            waitingNode.hidden = false;
            waitingNode.textContent = waitingLabel;
        }
    };

    const setDisplayBaseStyle = () => {
        slideNode.style.display = "flex";
        slideNode.style.alignItems = "center";
        slideNode.style.justifyContent = "center";
        slideNode.style.textAlign = "center";
        slideNode.style.width = "100%";
        slideNode.style.height = "100vh";
        slideNode.style.boxSizing = "border-box";
        slideNode.style.whiteSpace = "pre-wrap";
        slideNode.style.overflowWrap = "anywhere";
        slideNode.style.backgroundSize = "100% 100%";
        slideNode.style.backgroundRepeat = "no-repeat";
        slideNode.style.backgroundPosition = "center center";
    };

    const persistFrame = (frame) => {
        try {
            window.localStorage.setItem(frameStorageKey, JSON.stringify(frame));
        } catch (_error) {
            // Ignore storage failures.
        }
    };

    const renderIdle = () => {
        setDisplayBaseStyle();
        slideNode.style.backgroundImage = "";
        slideNode.style.backgroundColor = "#000000";
        slideNode.style.color = "#FFFFFF";
        slideNode.style.fontFamily = "'Source Sans Pro', sans-serif";
        slideNode.style.fontSize = "64px";
        slideNode.style.paddingLeft = "80px";
        slideNode.style.paddingRight = "80px";
        slideNode.textContent = waitingLabel;
        setWaiting();
    };

    const renderBlack = () => {
        clearWaiting();
        setDisplayBaseStyle();
        slideNode.style.backgroundImage = "";
        slideNode.style.backgroundColor = "#000000";
        slideNode.style.color = "#000000";
        slideNode.textContent = "";
    };

    const renderF11Reminder = () => {
        clearWaiting();
        setDisplayBaseStyle();
        slideNode.style.backgroundImage = "";
        slideNode.style.backgroundColor = "#000000";
        slideNode.style.color = "rgb(200, 200, 200)";
        slideNode.style.fontFamily = "'Source Sans Pro', sans-serif";
        slideNode.style.fontSize = "64px";
        slideNode.style.paddingLeft = "80px";
        slideNode.style.paddingRight = "80px";
        slideNode.textContent = f11ReminderLabel;
    };

    const renderQr = (frame) => {
        clearWaiting();
        setDisplayBaseStyle();
        slideNode.style.backgroundImage = "";
        slideNode.style.backgroundColor = "#000000";
        slideNode.style.color = "#FFFFFF";
        slideNode.style.fontFamily = "'Source Sans Pro', sans-serif";
        slideNode.style.fontSize = "42px";
        slideNode.style.paddingLeft = "60px";
        slideNode.style.paddingRight = "60px";

        slideNode.replaceChildren();

        const wrapper = document.createElement("div");
        wrapper.className = "lyrics-display-qr-wrapper";

        if (frame.publicUrl) {
            const line = document.createElement("p");
            line.textContent = String(frame.publicUrl);
            wrapper.appendChild(line);
        }

        if (frame.qrCodePngBase64) {
            const image = document.createElement("img");
            image.src = `data:image/png;base64,${String(frame.qrCodePngBase64)}`;
            image.alt = "";
            image.className = "lyrics-display-qr-image";
            wrapper.appendChild(image);
        }

        slideNode.appendChild(wrapper);
    };

    const renderSlide = (frame) => {
        const slide = frame.slide;
        if (!slide || typeof slide !== "object") {
            renderIdle();
            return;
        }

        const style = slide.style && typeof slide.style === "object" ? slide.style : {};
        const text = String(slide.text || "");
        const bgUrl = String(style.backgroundUrl || "").trim();

        clearWaiting();
        setDisplayBaseStyle();

        slideNode.style.color = String(style.textColor || "#FFFFFF");
        slideNode.style.backgroundColor = String(style.bgColor || "#000000");
        slideNode.style.fontFamily = `'${String(style.fontFamily || "Source Sans Pro")}', sans-serif`;
        slideNode.style.fontSize = `${Number.parseInt(String(style.fontSize || "72"), 10) || 72}px`;
        slideNode.style.paddingLeft = `${Number.parseInt(String(style.horizontalPadding || "80"), 10) || 80}px`;
        slideNode.style.paddingRight = `${Number.parseInt(String(style.horizontalPadding || "80"), 10) || 80}px`;
        slideNode.style.backgroundImage = bgUrl ? `url('${bgUrl.replace(/'/g, "\\'")}')` : "";
        slideNode.textContent = text;
    };

    const renderFrame = (frame) => {
        if (!frame || typeof frame !== "object") {
            renderIdle();
            return;
        }

        const mode = String(frame.mode || "idle");
        if (mode === "black") {
            renderBlack();
            return;
        }
        if (mode === "f11-reminder") {
            renderF11Reminder();
            return;
        }
        if (mode === "qr") {
            renderQr(frame);
            return;
        }
        if (mode === "slide") {
            renderSlide(frame);
            return;
        }
        renderIdle();
    };

    const handleMessage = (raw) => {
        const message = raw && typeof raw === "object" ? raw : null;
        if (!message) {
            return;
        }
        if (String(message.sessionId || "") !== sessionId) {
            return;
        }

        const type = String(message.type || "");
        if (!["init", "frame", "heartbeat"].includes(type)) {
            return;
        }

        const frame = message.frame;
        renderFrame(frame);
        persistFrame(frame);
    };

    const restoreFrame = () => {
        try {
            const raw = window.localStorage.getItem(frameStorageKey);
            if (!raw) {
                renderIdle();
                return;
            }
            const frame = JSON.parse(raw);
            renderFrame(frame);
        } catch (_error) {
            renderIdle();
        }
    };

    if (channel) {
        channel.addEventListener("message", (event) => {
            handleMessage(event.data);
        });
    }

    window.addEventListener("storage", (event) => {
        if (event.key !== bridgeStorageKey) {
            return;
        }
        if (!event.newValue) {
            return;
        }
        try {
            handleMessage(JSON.parse(event.newValue));
        } catch (_error) {
            // Ignore invalid storage payloads.
        }
    });

    if (forceReminderOnLoad) {
        const reminderFrame = { mode: "f11-reminder" };
        renderFrame(reminderFrame);
        persistFrame(reminderFrame);
    } else {
        restoreFrame();
    }
})();
