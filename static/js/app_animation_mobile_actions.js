(function () {
    "use strict";

    const mobileActionsToggle = document.querySelector("[data-animation-mobile-actions-toggle]");
    const mobileActionsContainer = document.querySelector("[data-animation-mobile-actions]");
    if (!mobileActionsToggle || !mobileActionsContainer) {
        return;
    }

    mobileActionsToggle.addEventListener("click", () => {
        const isHidden = mobileActionsContainer.hidden;
        mobileActionsContainer.hidden = !isHidden;
        mobileActionsToggle.setAttribute("aria-expanded", String(isHidden));
        mobileActionsToggle.textContent = isHidden
            ? String(mobileActionsToggle.getAttribute("data-close-label") || "")
            : String(mobileActionsToggle.getAttribute("data-open-label") || "");
    });
})();
