(() => {
    const root = document.documentElement;
    const config = window.LSS_PAGE_LOADER_CONFIG || {};
    const state = window.LSS_PAGE_LOADER_STATE || {};

    const now = () =>
        window.performance && typeof window.performance.now === "function" ? window.performance.now() : Date.now();

    const toDelay = (value, fallback) => {
        const parsed = Number(value);
        return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
    };

    const clearLoaderTimers = () => {
        if (state.revealTimerId) {
            window.clearTimeout(state.revealTimerId);
            state.revealTimerId = null;
        }

        if (state.failsafeTimerId) {
            window.clearTimeout(state.failsafeTimerId);
            state.failsafeTimerId = null;
        }
    };

    const dispatchPageReady = () => {
        document.dispatchEvent(new CustomEvent("lss:page-ready"));
    };

    const markReady = () => {
        if (root.classList.contains("lss-page-ready")) {
            return;
        }

        clearLoaderTimers();

        if (typeof state.markReady === "function") {
            state.markReady();
            return;
        }

        root.classList.add("lss-page-ready");
        root.classList.remove("lss-page-loading", "lss-page-loader-visible");
        dispatchPageReady();
    };

    const finishAfterMinimumVisibleDelay = () => {
        const minimumVisibleMs = toDelay(config.minimumVisibleMs, 250);
        const shownAt = Number(state.loaderShownAt);

        if (root.classList.contains("lss-page-loader-visible") && Number.isFinite(shownAt)) {
            const remainingMs = minimumVisibleMs - (now() - shownAt);

            if (remainingMs > 0) {
                window.setTimeout(markReady, remainingMs);
                return;
            }
        }

        markReady();
    };

    const showLoaderImmediately = () => {
        if (!root.classList.contains("lss-page-loader-visible")) {
            state.loaderShownAt = now();
            root.classList.add("lss-page-loader-visible");
        } else if (!Number.isFinite(Number(state.loaderShownAt))) {
            state.loaderShownAt = now();
        }
    };

    const finishAfterPaint = () => {
        const readyDelayMs = toDelay(config.readyDelayMs, 0);

        if (readyDelayMs > 0) {
            showLoaderImmediately();
            window.setTimeout(finishAfterMinimumVisibleDelay, readyDelayMs);
            return;
        }

        if (typeof window.requestAnimationFrame === "function") {
            window.requestAnimationFrame(finishAfterMinimumVisibleDelay);
            return;
        }

        window.setTimeout(finishAfterMinimumVisibleDelay, 0);
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", finishAfterPaint, { once: true });
    } else {
        finishAfterPaint();
    }
})();
