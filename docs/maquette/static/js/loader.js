document.addEventListener("DOMContentLoaded", () => {
    const cfg = (window.LOADER_CONFIG || {});
    const LOADER_DEBUG = !!cfg.loaderDebug;
    const LOADER_DEBUG_DELAY_MS = Number.isFinite(cfg.loaderDebugDelayMs) ? Number(cfg.loaderDebugDelayMs) : 0;
    
    if (LOADER_DEBUG && LOADER_DEBUG_DELAY_MS > 0) {
        setTimeout(endLoader, LOADER_DEBUG_DELAY_MS);
    } else {
        endLoader();
    }
});

function endLoader() {
    const loader = document.getElementById("loader");
    const content = document.getElementById("general");

    if (loader) loader.style.display = "none";
    if (content) content.style.display = "block";
}