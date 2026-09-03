(() => {
    const reconnectDelayMs = 1000;

    const websocketUrl = (sessionId, role) => {
        const scheme = window.location.protocol === "https:" ? "wss" : "ws";
        return `${scheme}://${window.location.host}/ws/animations/remote/${encodeURIComponent(sessionId)}/${role}/`;
    };

    const createConnection = ({ role, sessionId, token, onState, onStatus }) => {
        let socket = null;
        let reconnectTimer = null;
        let closedByCaller = false;
        let replaced = false;
        let ready = false;
        let unsubscribeState = null;

        const notifyStatus = (status) => {
            if (typeof onStatus === "function") {
                onStatus(status);
            }
        };

        const send = (message) => {
            if (!ready || !socket || socket.readyState !== window.WebSocket.OPEN) {
                return false;
            }
            socket.send(JSON.stringify(message));
            return true;
        };

        const sendMasterState = (state) => {
            if (role !== "master") {
                return;
            }
            send({
                type: "STATE",
                state: {
                    ...state,
                    master_status: "MASTER_CONNECTED",
                },
            });
        };

        const connect = () => {
            if (closedByCaller || replaced) {
                return;
            }
            ready = false;
            socket = new window.WebSocket(websocketUrl(sessionId, role));
            socket.addEventListener("open", () => {
                socket.send(JSON.stringify({ type: "AUTH", token }));
                notifyStatus("AUTHENTICATING");
            });
            socket.addEventListener("message", (event) => {
                let message = null;
                try {
                    message = JSON.parse(event.data);
                } catch (_error) {
                    return;
                }
                if (!message || typeof message !== "object") {
                    return;
                }
                if (message.type === "READY") {
                    ready = true;
                    notifyStatus("CONNECTED");
                    if (role === "master") {
                        const adapter = window.LSSLyricsMasterAdapter;
                        if (!adapter) {
                            return;
                        }
                        unsubscribeState = adapter.subscribeRemoteState(sendMasterState);
                    }
                    return;
                }
                if (message.type === "STATE" && typeof onState === "function") {
                    onState(message.state);
                    return;
                }
                if (message.type === "COMMAND" && role === "master") {
                    const result = window.LSSLyricsMasterAdapter?.handleExternalCommand(message);
                    if (result && !result.accepted) {
                        send({
                            type: "MASTER_COMMAND_REJECTED",
                            command_id: message.command_id,
                            reason: result.reason,
                        });
                    }
                    return;
                }
                if (message.type === "MASTER_REPLACED" && role === "master") {
                    replaced = true;
                    notifyStatus("REPLACED");
                }
            });
            socket.addEventListener("close", () => {
                ready = false;
                if (typeof unsubscribeState === "function") {
                    unsubscribeState();
                    unsubscribeState = null;
                }
                if (closedByCaller || replaced) {
                    return;
                }
                notifyStatus("RECONNECTING");
                reconnectTimer = window.setTimeout(connect, reconnectDelayMs);
            });
            socket.addEventListener("error", () => {
                notifyStatus("ERROR");
            });
        };

        connect();

        return {
            disconnect: () => {
                closedByCaller = true;
                if (reconnectTimer !== null) {
                    window.clearTimeout(reconnectTimer);
                    reconnectTimer = null;
                }
                if (typeof unsubscribeState === "function") {
                    unsubscribeState();
                    unsubscribeState = null;
                }
                if (socket) {
                    socket.close();
                }
            },
            sendCommand: (command, target) => {
                const message = { type: "COMMAND", command };
                if (target !== undefined) {
                    message.target = target;
                }
                return send(message);
            },
        };
    };

    window.LSSRemoteTransport = Object.freeze({
        connectMaster: ({ sessionId, masterToken, onStatus } = {}) => {
            if (!window.LSSLyricsMasterAdapter || !sessionId || !masterToken) {
                return null;
            }
            return createConnection({
                role: "master",
                sessionId,
                token: masterToken,
                onStatus,
            });
        },
        connectRemote: ({ sessionId, accessToken, onState, onStatus } = {}) => {
            if (!sessionId || !accessToken) {
                return null;
            }
            return createConnection({
                role: "remote",
                sessionId,
                token: accessToken,
                onState,
                onStatus,
            });
        },
    });
})();
