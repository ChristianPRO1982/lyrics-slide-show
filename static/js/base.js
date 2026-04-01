(() => {
    const root = document.documentElement;
    const themeConfig = window.LSS_THEME_CONFIG || null;
    const themeStylesheet = document.querySelector("#site-theme-stylesheet");
    const themeButtons = document.querySelectorAll("[data-theme-select]");

    const getStoredTheme = () => {
        if (!themeConfig) {
            return "normal";
        }

        try {
            const savedTheme = window.localStorage.getItem(themeConfig.storageKey);
            return themeConfig.themeStylesheets[savedTheme] ? savedTheme : themeConfig.defaultTheme;
        } catch (error) {
            return themeConfig.defaultTheme;
        }
    };

    const buildThemeIconPath = (theme, size, mode, iconName) => {
        return `${themeConfig.iconBasePath}/${theme}/${size}/${mode}/${iconName}.png`;
    };

    const applyThemeIcons = (theme) => {
        if (!themeConfig) {
            return;
        }

        document.querySelectorAll("[data-theme-icon]").forEach((picture) => {
            const iconName = picture.dataset.themeIcon;
            const iconAlt = picture.dataset.themeAlt || "";
            const image = picture.querySelector("img");
            const sources = picture.querySelectorAll("source[data-theme-size][data-theme-mode]");

            sources.forEach((source) => {
                const size = source.dataset.themeSize;
                const mode = source.dataset.themeMode;
                source.srcset = buildThemeIconPath(theme, size, mode, iconName);
            });

            if (image) {
                const imageSize = image.dataset.themeSize || "64";
                const imageMode = image.dataset.themeMode || "light";
                image.src = buildThemeIconPath(theme, imageSize, imageMode, iconName);
                image.alt = iconAlt;
            }
        });
    };

    const applyThemeSelectionState = (theme) => {
        document.querySelectorAll("[data-theme-option]").forEach((card) => {
            const isActive = card.dataset.themeOption === theme;
            card.classList.toggle("is-active", isActive);
        });

        themeButtons.forEach((button) => {
            const isActive = button.dataset.themeSelect === theme;
            button.disabled = isActive;
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
    };

    const applyTheme = (theme, persist = false) => {
        if (!themeConfig || !themeConfig.themeStylesheets[theme]) {
            return;
        }

        root.dataset.theme = theme;

        if (themeStylesheet) {
            themeStylesheet.href = themeConfig.themeStylesheets[theme];
        }

        applyThemeIcons(theme);
        applyThemeSelectionState(theme);

        if (persist) {
            try {
                window.localStorage.setItem(themeConfig.storageKey, theme);
            } catch (error) {
                // Ignore storage failures and keep the theme only for the current page.
            }
        }
    };

    if (themeConfig) {
        applyTheme(getStoredTheme());

        themeButtons.forEach((button) => {
            button.addEventListener("click", () => {
                applyTheme(button.dataset.themeSelect, true);
            });
        });
    }

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
