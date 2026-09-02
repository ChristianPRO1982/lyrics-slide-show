(() => {
    const root = document.querySelector("[data-lyrics-display-root]");
    if (!(root instanceof HTMLElement)) {
        return;
    }

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
    const transitionRegistry = {
        direct: true,
        fade: true,
        wipe: true,
    };
    const processedNonces = new Set();
    const processedNonceOrder = [];

    const createDisplayLayer = (active = false) => {
        const layer = document.createElement("article");
        layer.className = `lyrics-display-layer${active ? " is-active" : ""}`;
        const slide = document.createElement("section");
        slide.className = "lyrics-display-slide";
        layer.appendChild(slide);
        root.appendChild(layer);
        return { layer, slide };
    };

    root.replaceChildren();
    const layers = [createDisplayLayer(true), createDisplayLayer(false)];
    let activeLayerIndex = 0;
    let currentTransitionController = null;

    let channel = null;
    if (typeof window.BroadcastChannel === "function") {
        try {
            channel = new window.BroadcastChannel(bridgeStorageKey);
        } catch (_error) {
            channel = null;
        }
    }

    const rememberNonce = (value) => {
        const nonce = String(value || "").trim();
        if (!nonce) {
            return true;
        }
        if (processedNonces.has(nonce)) {
            return false;
        }
        processedNonces.add(nonce);
        processedNonceOrder.push(nonce);
        while (processedNonceOrder.length > 100) {
            const oldNonce = processedNonceOrder.shift();
            processedNonces.delete(oldNonce);
        }
        return true;
    };

    const setDisplayBaseStyle = (targetSlide) => {
        targetSlide.style.display = "flex";
        targetSlide.style.alignItems = "center";
        targetSlide.style.justifyContent = "center";
        targetSlide.style.textAlign = "center";
        targetSlide.style.width = "100%";
        targetSlide.style.height = "100vh";
        targetSlide.style.boxSizing = "border-box";
        targetSlide.style.whiteSpace = "pre-wrap";
        targetSlide.style.overflowWrap = "anywhere";
        targetSlide.style.backgroundSize = "100% 100%";
        targetSlide.style.backgroundRepeat = "no-repeat";
        targetSlide.style.backgroundPosition = "center center";
    };

    const readIntegerWithFallback = (value, fallback) => {
        const parsed = Number.parseInt(String(value ?? ""), 10);
        return Number.isNaN(parsed) ? fallback : parsed;
    };

    const setBackgroundFromStyle = (targetSlide, style) => {
        const bgUrl = String(style.backgroundUrl || "").trim();
        targetSlide.style.backgroundImage = bgUrl ? `url('${bgUrl.replace(/'/g, "\\'")}')` : "";
        targetSlide.style.backgroundColor = String(style.bgColor || "#000000");
    };

    const setBaseTextStyleFromStyle = (targetSlide, style) => {
        targetSlide.style.color = String(style.textColor || "#FFFFFF");
        targetSlide.style.fontFamily = `'${String(style.fontFamily || "Source Sans Pro")}', sans-serif`;
        targetSlide.style.fontWeight = String(style.fontWeight || "normal");
        targetSlide.style.fontSize = `${readIntegerWithFallback(style.fontSize, 72)}px`;
    };

    const renderIdle = (targetSlide) => {
        setDisplayBaseStyle(targetSlide);
        targetSlide.style.backgroundImage = "";
        targetSlide.style.backgroundColor = "#000000";
        targetSlide.style.color = "#FFFFFF";
        targetSlide.style.fontFamily = "'Source Sans Pro', sans-serif";
        targetSlide.style.fontWeight = "normal";
        targetSlide.style.fontSize = "64px";
        targetSlide.style.paddingLeft = "80px";
        targetSlide.style.paddingRight = "80px";
        targetSlide.textContent = waitingLabel;
    };

    const renderSimpleSlide = (targetSlide, slide) => {
        if (!slide || typeof slide !== "object") {
            renderIdle(targetSlide);
            return;
        }

        const style = slide.style && typeof slide.style === "object" ? slide.style : {};
        const text = String(slide.text || "");

        setDisplayBaseStyle(targetSlide);
        setBaseTextStyleFromStyle(targetSlide, style);
        targetSlide.style.paddingLeft = `${readIntegerWithFallback(style.horizontalPadding, 80)}px`;
        targetSlide.style.paddingRight = `${readIntegerWithFallback(style.horizontalPadding, 80)}px`;
        setBackgroundFromStyle(targetSlide, style);
        targetSlide.textContent = text;
    };

    const buildDoubleColumn = (slide, side, leftStyle) => {
        const style = slide && typeof slide.style === "object" ? slide.style : {};
        const basePadding = readIntegerWithFallback(leftStyle.horizontalPadding, 80);
        const column = document.createElement("div");
        column.className = `lyrics-display-column lyrics-display-column--${side}`;
        column.style.color = String(leftStyle.textColor || "#FFFFFF");
        column.style.fontFamily = `'${String(style.fontFamily || "Source Sans Pro")}', sans-serif`;
        column.style.fontWeight = String(style.fontWeight || "normal");
        column.style.fontSize = `${readIntegerWithFallback(style.fontSize, 72)}px`;
        column.style.paddingLeft = `${side === "left" ? basePadding / 2 : basePadding / 4}px`;
        column.style.paddingRight = `${side === "left" ? basePadding / 4 : basePadding / 2}px`;
        column.textContent = String(slide?.text || "");
        return column;
    };

    const renderDoubleProjectionStep = (targetSlide, projectionStep) => {
        const leftSlide = projectionStep.left;
        const rightSlide = projectionStep.right;
        if (!leftSlide || typeof leftSlide !== "object" || !rightSlide || typeof rightSlide !== "object") {
            renderIdle(targetSlide);
            return;
        }

        const leftStyle = leftSlide.style && typeof leftSlide.style === "object" ? leftSlide.style : {};

        setDisplayBaseStyle(targetSlide);
        setBaseTextStyleFromStyle(targetSlide, leftStyle);
        targetSlide.style.paddingLeft = "0";
        targetSlide.style.paddingRight = "0";
        setBackgroundFromStyle(targetSlide, leftStyle);
        targetSlide.replaceChildren();

        const wrapper = document.createElement("div");
        wrapper.className = "lyrics-display-double";
        wrapper.appendChild(buildDoubleColumn(leftSlide, "left", leftStyle));
        wrapper.appendChild(buildDoubleColumn(rightSlide, "right", leftStyle));
        targetSlide.appendChild(wrapper);
    };

    const renderBlack = (targetSlide) => {
        setDisplayBaseStyle(targetSlide);
        targetSlide.style.backgroundImage = "";
        targetSlide.style.backgroundColor = "#000000";
        targetSlide.style.color = "#000000";
        targetSlide.style.fontWeight = "normal";
        targetSlide.textContent = "";
    };

    const renderF11Reminder = (targetSlide) => {
        setDisplayBaseStyle(targetSlide);
        targetSlide.style.backgroundImage = "";
        targetSlide.style.backgroundColor = "#000000";
        targetSlide.style.color = "rgb(200, 200, 200)";
        targetSlide.style.fontFamily = "'Source Sans Pro', sans-serif";
        targetSlide.style.fontWeight = "normal";
        targetSlide.style.fontSize = "64px";
        targetSlide.style.paddingLeft = "80px";
        targetSlide.style.paddingRight = "80px";
        targetSlide.textContent = f11ReminderLabel;
    };

    const renderQr = (targetSlide, frame) => {
        setDisplayBaseStyle(targetSlide);
        targetSlide.style.backgroundImage = "";
        targetSlide.style.backgroundColor = "#000000";
        targetSlide.style.color = "#FFFFFF";
        targetSlide.style.fontFamily = "'Source Sans Pro', sans-serif";
        targetSlide.style.fontWeight = "normal";
        targetSlide.style.fontSize = "42px";
        targetSlide.style.paddingLeft = "60px";
        targetSlide.style.paddingRight = "60px";

        targetSlide.replaceChildren();

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

        targetSlide.appendChild(wrapper);
    };

    const renderSlide = (targetSlide, frame) => {
        const projectionStep = frame.projectionStep;
        if (projectionStep && typeof projectionStep === "object") {
            if (String(projectionStep.mode || "simple") === "double") {
                renderDoubleProjectionStep(targetSlide, projectionStep);
                return;
            }
            renderSimpleSlide(targetSlide, projectionStep.left);
            return;
        }

        renderSimpleSlide(targetSlide, frame.slide);
    };

    const renderFrameIntoLayer = (targetLayer, frame) => {
        const targetSlide = targetLayer.slide;
        if (!frame || typeof frame !== "object") {
            renderIdle(targetSlide);
            return;
        }

        const mode = String(frame.mode || "idle");
        if (mode === "black") {
            renderBlack(targetSlide);
            return;
        }
        if (mode === "f11-reminder") {
            renderF11Reminder(targetSlide);
            return;
        }
        if (mode === "qr") {
            renderQr(targetSlide, frame);
            return;
        }
        if (mode === "slide") {
            renderSlide(targetSlide, frame);
            return;
        }
        renderIdle(targetSlide);
    };

    const persistFrame = (frame) => {
        try {
            window.localStorage.setItem(frameStorageKey, JSON.stringify(frame));
        } catch (_error) {
            // Ignore storage failures.
        }
    };

    const resetLayerTransitionStyles = (displayLayer) => {
        displayLayer.style.opacity = "";
        displayLayer.style.clipPath = "";
        displayLayer.style.transition = "";
        displayLayer.style.zIndex = "";
    };

    const cancelCurrentTransition = () => {
        if (currentTransitionController && typeof currentTransitionController.cancel === "function") {
            currentTransitionController.cancel();
        }
        currentTransitionController = null;
    };

    const activateLayer = (layerIndex) => {
        layers.forEach((displayLayer, index) => {
            resetLayerTransitionStyles(displayLayer.layer);
            displayLayer.layer.classList.toggle("is-active", index === layerIndex);
        });
        activeLayerIndex = layerIndex;
    };

    const normalizeDurationMs = (value) => {
        const parsed = Number.parseInt(String(value ?? ""), 10);
        return Number.isInteger(parsed) && parsed >= 0 ? parsed : 0;
    };

    const resolveTransition = (rawTransition) => {
        const transition = rawTransition && typeof rawTransition === "object" ? rawTransition : {};
        const params = transition.params && typeof transition.params === "object" ? transition.params : {};
        const transitionId = String(transition.id || "direct");
        if (!transitionRegistry[transitionId]) {
            return { id: "direct", durationMs: 0 };
        }
        if (transitionId === "fade") {
            return { id: "fade", durationMs: normalizeDurationMs(params.duration_ms) };
        }
        if (transitionId === "wipe" && String(params.direction || "") === "left_to_right") {
            return { id: "wipe", durationMs: normalizeDurationMs(params.duration_ms), direction: "left_to_right" };
        }
        return { id: "direct", durationMs: 0 };
    };

    const runDirectTransition = (incomingIndex) => {
        activateLayer(incomingIndex);
    };

    const runAnimatedTransition = (incomingIndex, transition) => {
        cancelCurrentTransition();
        const outgoingIndex = activeLayerIndex;
        if (incomingIndex === outgoingIndex || transition.durationMs <= 0) {
            runDirectTransition(incomingIndex);
            return;
        }

        const outgoingLayer = layers[outgoingIndex].layer;
        const incomingLayer = layers[incomingIndex].layer;
        let finished = false;
        const timerIds = [];
        const rafIds = [];

        const finish = () => {
            if (finished) {
                return;
            }
            finished = true;
            timerIds.forEach((timerId) => window.clearTimeout(timerId));
            rafIds.forEach((rafId) => window.cancelAnimationFrame(rafId));
            activateLayer(incomingIndex);
            currentTransitionController = null;
        };

        currentTransitionController = {
            cancel: () => {
                if (finished) {
                    return;
                }
                finished = true;
                timerIds.forEach((timerId) => window.clearTimeout(timerId));
                rafIds.forEach((rafId) => window.cancelAnimationFrame(rafId));
                layers.forEach((displayLayer) => resetLayerTransitionStyles(displayLayer.layer));
            },
        };

        [outgoingLayer, incomingLayer].forEach((layer) => {
            resetLayerTransitionStyles(layer);
            layer.classList.add("is-active");
        });
        outgoingLayer.style.zIndex = "1";
        incomingLayer.style.zIndex = "2";

        if (transition.id === "fade") {
            incomingLayer.style.opacity = "0";
            rafIds.push(window.requestAnimationFrame(() => {
                incomingLayer.style.transition = `opacity ${transition.durationMs}ms ease`;
                incomingLayer.style.opacity = "1";
            }));
        } else if (transition.id === "wipe") {
            incomingLayer.style.clipPath = "inset(0 100% 0 0)";
            rafIds.push(window.requestAnimationFrame(() => {
                incomingLayer.style.transition = `clip-path ${transition.durationMs}ms ease`;
                incomingLayer.style.clipPath = "inset(0 0 0 0)";
            }));
        } else {
            runDirectTransition(incomingIndex);
            return;
        }

        timerIds.push(window.setTimeout(finish, transition.durationMs + 80));
    };

    const displayFrame = (frame, transition, options = {}) => {
        const animate = options.animate !== false;
        if (!animate) {
            cancelCurrentTransition();
            renderFrameIntoLayer(layers[activeLayerIndex], frame);
            activateLayer(activeLayerIndex);
            return;
        }

        const incomingIndex = activeLayerIndex === 0 ? 1 : 0;
        try {
            renderFrameIntoLayer(layers[incomingIndex], frame);
            const resolvedTransition = resolveTransition(transition);
            if (resolvedTransition.id === "direct" || resolvedTransition.durationMs <= 0) {
                cancelCurrentTransition();
                runDirectTransition(incomingIndex);
                return;
            }
            runAnimatedTransition(incomingIndex, resolvedTransition);
        } catch (_error) {
            cancelCurrentTransition();
            renderFrameIntoLayer(layers[incomingIndex], frame);
            runDirectTransition(incomingIndex);
        }
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
        if (type === "heartbeat") {
            return;
        }
        if (!["init", "frame"].includes(type)) {
            return;
        }
        if (!rememberNonce(message.nonce)) {
            return;
        }

        const frame = message.frame;
        displayFrame(frame, message.transition, { animate: true });
        persistFrame(frame);
    };

    const restoreFrame = () => {
        try {
            const raw = window.localStorage.getItem(frameStorageKey);
            if (!raw) {
                displayFrame({ mode: "idle" }, null, { animate: false });
                return;
            }
            const frame = JSON.parse(raw);
            displayFrame(frame, null, { animate: false });
        } catch (_error) {
            displayFrame({ mode: "idle" }, null, { animate: false });
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
        displayFrame(reminderFrame, null, { animate: false });
        persistFrame(reminderFrame);
    } else {
        restoreFrame();
    }
})();
