(() => {
    const root = document.documentElement;
    const drawer = document.querySelector("[data-nav-drawer]");
    const backdrop = document.querySelector("[data-nav-backdrop]");
    const openButton = document.querySelector("[data-nav-open]");
    const closeButton = document.querySelector("[data-nav-close]");

    if (!drawer || !backdrop || !openButton || !closeButton) {
        return;
    }

    const openMenu = () => {
        root.classList.add("site-nav-open");
        drawer.setAttribute("aria-hidden", "false");
        backdrop.hidden = false;
        openButton.setAttribute("aria-expanded", "true");
    };

    const closeMenu = () => {
        root.classList.remove("site-nav-open");
        drawer.setAttribute("aria-hidden", "true");
        backdrop.hidden = true;
        openButton.setAttribute("aria-expanded", "false");
    };

    openButton.addEventListener("click", openMenu);
    closeButton.addEventListener("click", closeMenu);
    backdrop.addEventListener("click", closeMenu);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeMenu();
        }
    });

    closeMenu();
})();
