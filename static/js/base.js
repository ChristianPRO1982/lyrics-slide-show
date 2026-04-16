(() => {
    const root = document.documentElement;
    const themeConfig = window.LSS_THEME_CONFIG || null;
    const messageBoxI18n = window.LSS_MESSAGE_BOX_CONFIG?.i18n || {};
    const floatingHelpConfig = window.LSS_FLOATING_HELP_CONFIG || {};
    const sitePopupConfigElement = document.getElementById("lss-site-popup-config");
    const themeStylesheet = document.querySelector("#site-theme-stylesheet");
    const faviconLink = document.querySelector("#site-favicon");
    const themeButtons = document.querySelectorAll("[data-theme-select]");
    const colorSchemeQuery = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    let sitePopupConfig = {};

    if (sitePopupConfigElement) {
        try {
            sitePopupConfig = JSON.parse(sitePopupConfigElement.textContent || "{}");
        } catch (error) {
            sitePopupConfig = {};
        }
    }

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

    const buildFaviconPath = (theme, mode) => {
        return buildThemeIconPath(theme, "64", mode, "lss");
    };

    const updateFavicon = (theme) => {
        if (!themeConfig || !faviconLink) {
            return;
        }

        const mode = colorSchemeQuery && colorSchemeQuery.matches ? "dark" : "light";
        const candidatePath = buildFaviconPath(theme, mode);
        const fallbackPath = themeConfig.faviconFallbackPath;
        const probe = new window.Image();

        probe.onload = () => {
            faviconLink.href = candidatePath;
        };

        probe.onerror = () => {
            faviconLink.href = fallbackPath;
        };

        probe.src = candidatePath;
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
        updateFavicon(theme);
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

        if (colorSchemeQuery) {
            colorSchemeQuery.addEventListener("change", () => {
                updateFavicon(root.dataset.theme || getStoredTheme());
            });
        }
    }

    const drawer = document.querySelector("[data-nav-drawer]");
    const backdrop = document.querySelector("[data-nav-backdrop]");
    const openButton = document.querySelector("[data-nav-open]");
    const closeButton = document.querySelector("[data-nav-close]");

    if (drawer && backdrop && openButton && closeButton) {
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
        drawer.dataset.navReady = "true";
    }

    document.querySelectorAll("[data-lss-logout-confirm='true']").forEach((link) => {
        link.addEventListener("click", async (event) => {
            if (!window.LSSMessageBox || typeof window.LSSMessageBox.show !== "function") {
                return;
            }

            event.preventDefault();

            const result = await window.LSSMessageBox.show({
                title: messageBoxI18n.logoutTitle || "Déconnexion",
                messageMarkdown:
                    messageBoxI18n.logoutMessage || "Voulez-vous vraiment vous déconnecter du site ?",
                buttons: [
                    {
                        id: "yes",
                        label: messageBoxI18n.yesLabel || "Oui",
                        tone: "success",
                    },
                    {
                        id: "no",
                        label: messageBoxI18n.noLabel || "Non",
                        tone: "danger",
                    },
                ],
            });

            if (result.buttonId === "yes") {
                window.location.assign(link.href);
            }
        });
    });

    const getDeferredPopupSections = () => {
        const sections = Array.isArray(sitePopupConfig.sections) ? sitePopupConfig.sections : [];
        const now = Date.now();

        return sections.filter((section) => {
            const messageMarkdown = String(section.messageMarkdown || "").trim();
            if (!messageMarkdown) {
                return false;
            }

            const storageKey = `lss-site-popup:${section.id}:${section.version}`;
            const cooldownMs = Math.max(Number(section.cooldownMinutes) || 0, 0) * 60 * 1000;

            try {
                const storedAt = Number(window.localStorage.getItem(storageKey));
                if (Number.isFinite(storedAt) && cooldownMs > 0 && now - storedAt < cooldownMs) {
                    return false;
                }
            } catch (error) {
                // Ignore localStorage errors and display the popup immediately.
            }

            return true;
        });
    };

    const rememberPopupSections = (sections) => {
        const storedAt = Date.now().toString();

        sections.forEach((section) => {
            try {
                window.localStorage.setItem(`lss-site-popup:${section.id}:${section.version}`, storedAt);
            } catch (error) {
                // Ignore localStorage errors to preserve the popup interaction.
            }
        });
    };

    const buildSitePopupMarkdown = (sections) => {
        if (sections.length === 1) {
            return sections[0].messageMarkdown;
        }

        return sections
            .map((section) => `## ${section.title}\n\n${section.messageMarkdown}`)
            .join("\n\n");
    };

    const runWhenPageReady = (callback) => {
        const isPageLoaderActive = root.classList.contains("lss-page-loading")
            && !root.classList.contains("lss-page-ready");

        if (!isPageLoaderActive) {
            callback();
            return;
        }

        document.addEventListener("lss:page-ready", callback, { once: true });
    };

    document.addEventListener("DOMContentLoaded", () => {
        runWhenPageReady(async () => {
            if (!window.LSSMessageBox || typeof window.LSSMessageBox.alert !== "function") {
                return;
            }

            const eligibleSections = getDeferredPopupSections();
            if (!eligibleSections.length) {
                return;
            }

            const result = await window.LSSMessageBox.alert({
                title: sitePopupConfig.title || "Informations du site",
                messageMarkdown: buildSitePopupMarkdown(eligibleSections),
                size: eligibleSections.length > 1 ? "wide" : "default",
                buttons: [
                    {
                        id: "ok",
                        label: messageBoxI18n.okLabel || "OK",
                        tone: "neutral",
                    },
                ],
            });

            if (result.buttonId === "ok") {
                rememberPopupSections(eligibleSections);
            }
        });
    });

    const floatingHelp = document.querySelector("[data-floating-help]");
    const floatingHelpToggle = document.querySelector("[data-floating-help-toggle]");
    const floatingHelpPanel = document.querySelector("[data-floating-help-panel]");
    const floatingHelpCollapseDelayMs = Number(floatingHelpConfig.collapseDelayMs) || 3000;
    let floatingHelpTimeoutId = null;

    if (floatingHelp && floatingHelpToggle && floatingHelpPanel) {
        const closeFloatingHelp = () => {
            if (floatingHelpTimeoutId) {
                window.clearTimeout(floatingHelpTimeoutId);
                floatingHelpTimeoutId = null;
            }

            floatingHelp.dataset.state = "collapsed";
            floatingHelpToggle.hidden = false;
            floatingHelpToggle.setAttribute("aria-expanded", "false");
            floatingHelpPanel.hidden = true;
        };

        const openFloatingHelp = () => {
            if (floatingHelpTimeoutId) {
                window.clearTimeout(floatingHelpTimeoutId);
            }

            floatingHelp.dataset.state = "expanded";
            floatingHelpToggle.hidden = true;
            floatingHelpToggle.setAttribute("aria-expanded", "true");
            floatingHelpPanel.hidden = false;
            floatingHelpTimeoutId = window.setTimeout(closeFloatingHelp, floatingHelpCollapseDelayMs);
        };

        floatingHelpToggle.addEventListener("click", openFloatingHelp);
        floatingHelpPanel.addEventListener("mouseenter", () => {
            if (floatingHelpTimeoutId) {
                window.clearTimeout(floatingHelpTimeoutId);
                floatingHelpTimeoutId = null;
            }
        });
        floatingHelpPanel.addEventListener("mouseleave", () => {
            floatingHelpTimeoutId = window.setTimeout(closeFloatingHelp, floatingHelpCollapseDelayMs);
        });

        closeFloatingHelp();
    }
})();
