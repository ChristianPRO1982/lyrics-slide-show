(() => {
    const root = document.querySelector("[data-lyrics-master-root]");
    const panel = document.querySelector("[data-remote-management-panel]");
    const toggleButton = document.querySelector("[data-remote-management-toggle]");
    const activateButton = document.querySelector("[data-remote-management-activate]");
    const deactivateButton = document.querySelector("[data-remote-management-deactivate]");
    const statusNode = document.querySelector("[data-remote-management-status]");
    const countNode = document.querySelector("[data-remote-management-count]");
    const qrNode = document.querySelector("[data-remote-management-qr]");
    const linkNode = document.querySelector("[data-remote-management-link]");
    const csrfNode = document.querySelector("input[name=csrfmiddlewaretoken]");
    if (!(root instanceof HTMLElement) || !(panel instanceof HTMLElement)) {
        return;
    }

    const i18n = window.LSS_LYRICS_I18N || {};
    const label = (key, fallback) => String(i18n[key] || fallback);
    const createUrl = String(root.dataset.remoteCreateUrl || "").trim();
    const csrfToken = csrfNode instanceof HTMLInputElement ? csrfNode.value : "";
    let state = "INACTIVE";
    let remoteCount = 0;
    let connection = null;
    let sessionId = "";
    let masterToken = "";

    const statusLabels = {
        INACTIVE: label("remoteInactiveLabel", "Inactive"),
        ACTIVATING: label("remoteActivatingLabel", "Activation…"),
        MASTER_CONNECTING: label("remoteConnectingLabel", "Connexion de la master…"),
        MASTER_CONNECTED: label("remoteConnectedLabel", "Master connectée"),
        ERROR: label("remoteErrorLabel", "Télécommande indisponible"),
        DISABLED: label("remoteDisabledLabel", "Désactivée"),
    };

    const render = () => {
        statusNode.textContent = statusLabels[state] || statusLabels.ERROR;
        const active = state !== "INACTIVE" && state !== "DISABLED";
        activateButton.hidden = active;
        deactivateButton.hidden = !active;
        countNode.hidden = !active;
        countNode.textContent = label("remoteCountLabel", "{count} télécommande(s) connectée(s)")
            .replace("{count}", String(remoteCount));
    };

    const setState = (nextState) => {
        state = nextState;
        render();
    };

    const showError = async (message) => {
        if (window.LSSMessageBox?.alert) {
            await window.LSSMessageBox.alert({
                title: label("remoteErrorLabel", "Télécommande indisponible"),
                messageMarkdown: message,
                buttons: [{ id: "ok", label: label("okLabel", "OK"), tone: "neutral" }],
            });
        }
    };

    const updateConnectionStatus = (transportStatus) => {
        if (transportStatus === "CONNECTED") {
            setState("MASTER_CONNECTED");
        } else if (transportStatus === "AUTHENTICATING" || transportStatus === "RECONNECTING") {
            setState("MASTER_CONNECTING");
        } else if (transportStatus === "DISABLED") {
            setState("DISABLED");
        } else if (transportStatus === "ERROR" || transportStatus === "REPLACED") {
            setState("ERROR");
        }
    };

    const deactivate = async ({ keepalive = false } = {}) => {
        if (!sessionId || !masterToken || !createUrl) {
            return;
        }
        const controller = connection;
        connection = null;
        if (controller) {
            controller.disconnect();
        }
        const body = new URLSearchParams({ master_token: masterToken });
        try {
            const response = await fetch(`${createUrl}${encodeURIComponent(sessionId)}/deactivate/`, {
                method: "POST",
                credentials: "same-origin",
                keepalive,
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "X-CSRFToken": csrfToken,
                },
                body: body.toString(),
            });
            if (!response.ok) {
                throw new Error("Remote deactivation failed.");
            }
            sessionId = "";
            masterToken = "";
            remoteCount = 0;
            qrNode.hidden = true;
            qrNode.removeAttribute("src");
            linkNode.hidden = true;
            linkNode.removeAttribute("href");
            setState("DISABLED");
        } catch (_error) {
            setState("ERROR");
            if (!keepalive) {
                await showError(label("remoteDeactivationFailedMessage", "La désactivation de la télécommande distante a échoué."));
            }
        }
    };

    const activate = async () => {
        if (!createUrl || !csrfToken || !window.LSSRemoteTransport) {
            setState("ERROR");
            await showError(label("remoteActivationFailedMessage", "L'activation de la télécommande distante a échoué."));
            return;
        }
        setState("ACTIVATING");
        try {
            const response = await fetch(createUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: { "X-CSRFToken": csrfToken },
            });
            if (!response.ok) {
                throw new Error("Remote activation failed.");
            }
            const payload = await response.json();
            sessionId = String(payload.session_id || "");
            masterToken = String(payload.master_token || "");
            const accessUrl = String(payload.access_url || "");
            if (!sessionId || !masterToken || !accessUrl) {
                throw new Error("Incomplete remote session.");
            }
            remoteCount = Number.isInteger(payload.remote_count) ? payload.remote_count : 0;
            linkNode.href = accessUrl;
            linkNode.textContent = label("remoteLinkLabel", "Ouvrir la télécommande distante");
            linkNode.hidden = false;
            const qrCode = String(payload.access_qr_code_png_base64 || "");
            if (qrCode) {
                qrNode.src = `data:image/png;base64,${qrCode}`;
                qrNode.hidden = false;
            }
            setState("MASTER_CONNECTING");
            connection = window.LSSRemoteTransport.connectMaster({
                sessionId,
                masterToken,
                onStatus: updateConnectionStatus,
                onRemoteCount: (count) => {
                    remoteCount = count;
                    render();
                },
            });
            if (!connection) {
                throw new Error("Unable to start the master connection.");
            }
        } catch (_error) {
            if (sessionId && masterToken) {
                await deactivate();
            }
            setState("ERROR");
            await showError(label("remoteActivationFailedMessage", "L'activation de la télécommande distante a échoué."));
        }
    };

    toggleButton?.addEventListener("click", () => {
        panel.hidden = !panel.hidden;
        toggleButton.setAttribute("aria-expanded", String(!panel.hidden));
    });
    activateButton?.addEventListener("click", () => void activate());
    deactivateButton?.addEventListener("click", () => void deactivate());
    window.addEventListener("pagehide", () => {
        void deactivate({ keepalive: true });
    });
    render();
})();
