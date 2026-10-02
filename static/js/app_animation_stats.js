(function () {
    "use strict";

    document.querySelectorAll("[data-animation-stats-popup]").forEach((trigger) => {
        trigger.addEventListener("click", async (event) => {
            const messageBox = window.LSSMessageBox;
            if (!messageBox || typeof messageBox.alert !== "function") {
                return;
            }

            event.preventDefault();
            const title = String(trigger.getAttribute("data-popup-title") || "").trim();
            const messageMarkdown = String(
                trigger.getAttribute("data-popup-message") || "",
            ).trim();
            if (!messageMarkdown) {
                return;
            }

            await messageBox.alert({
                title,
                messageMarkdown,
                showCloseButton: true,
            });
        });
    });
})();
