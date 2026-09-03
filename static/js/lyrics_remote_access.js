(() => {
    const root = document.querySelector("[data-remote-access-root]");
    const statusNode = document.querySelector("[data-remote-access-status]");
    if (!(root instanceof HTMLElement) || !(statusNode instanceof HTMLElement)) {
        return;
    }
    const i18n = window.LSS_REMOTE_ACCESS_I18N || {};
    const token = new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
    const sessionId = String(root.dataset.sessionId || "");
    if (!sessionId || !token || !window.LSSRemoteTransport) {
        statusNode.textContent = String(i18n.unavailable || "Session indisponible");
        return;
    }
    window.history.replaceState(null, "", window.location.pathname);
    window.LSSRemoteTransport.connectRemote({
        sessionId,
        accessToken: token,
        onStatus: (status) => {
            const labels = {
                AUTHENTICATING: i18n.connecting,
                CONNECTED: i18n.connected,
                RECONNECTING: i18n.reconnecting,
                DISABLED: i18n.disabled,
                ERROR: i18n.unavailable,
            };
            statusNode.textContent = String(labels[status] || i18n.unavailable || "Session indisponible");
        },
    });
})();
