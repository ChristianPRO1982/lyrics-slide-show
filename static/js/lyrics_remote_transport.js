(() => {
    const reconnectDelayMs = 1000;

    const websocketUrl = (sessionId, role) => {
        const scheme = window.location.protocol === "https:" ? "wss" : "ws";
        return `${scheme}://${window.location.host}/ws/animations/remote/${encodeURIComponent(sessionId)}/${role}/`;
    };

    const createConnection = ({ role, sessionId, token, onState, onStatus, onRemoteCount }) => {
        let socket = null;
        let reconnectTimer = null;
        let closedByCaller = false;
        let replaced = false;
        let disabled = false;
        let ready = false;
        let unsubscribeState = null;

        const notifyStatus = (status) => {
            if (typeof onStatus === "function") {
                onStatus(status);
            }
        };

        const notifyRemoteCount = (count) => {
            if (typeof onRemoteCount === "function" && Number.isInteger(count) && count >= 0) {
                onRemoteCount(count);
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
                    notifyRemoteCount(message.remote_count);
                    if (role === "master") {
                        const adapter = window.LSSLyricsMasterAdapter;
                        if (!adapter) {
                            return;
                        }
                        unsubscribeState = adapter.subscribeRemoteState(sendMasterState);
                        sendMasterState(adapter.getRemoteState());
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
                    return;
                }
                if (message.type === "REMOTE_COUNT" && role === "master") {
                    notifyRemoteCount(message.count);
                    return;
                }
                if (message.type === "SESSION_DISABLED") {
                    disabled = true;
                    notifyStatus("DISABLED");
                }
            });
            socket.addEventListener("close", () => {
                ready = false;
                if (typeof unsubscribeState === "function") {
                    unsubscribeState();
                    unsubscribeState = null;
                }
                if (closedByCaller || replaced || disabled) {
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
        connectMaster: ({ sessionId, masterToken, onStatus, onRemoteCount } = {}) => {
            if (!window.LSSLyricsMasterAdapter || !sessionId || !masterToken) {
                return null;
            }
            return createConnection({
                role: "master",
                sessionId,
                token: masterToken,
                onStatus,
                onRemoteCount,
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
