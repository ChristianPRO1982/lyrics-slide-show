/*
  Loader overlay with cancellable pre-navigation delay and bypass links.

  - Allows clicking links inside #loader to bypass any pending pre-nav delay.
  - Adds support for links marked with data-bypass-loader="true" or .loader-bypass.
  - Exposes AppLoader.cancelPendingNav().
*/

(function () {
  const loader = document.getElementById("loader");
  const content = document.getElementById("general");
  if (!loader || !content) return;

  const cfg = (window.LOADER_CONFIG || {});
  const DEBUG_MODE = !!cfg.debug;
  const POST_DELAY_MS = Number.isFinite(cfg.delayMs) ? Number(cfg.delayMs) : 0;
  const PRENAV_DELAY_MS = Number.isFinite(cfg.preNavDelayMs) ? Number(cfg.preNavDelayMs) : 0;

  let manualLock = false;
  let navInProgress = false;
  let pendingNavTimeout = null;

  function showLoader() {
    if (manualLock) return;
    loader.style.display = "flex";
    content.style.display = "none";
  }

  function hideLoader() {
    const doHide = () => {
      loader.style.display = "none";
      content.style.display = "block";
      manualLock = false;
    };
    if (DEBUG_MODE && POST_DELAY_MS > 0) {
      setTimeout(doHide, POST_DELAY_MS);
    } else {
      doHide();
    }
  }

  document.addEventListener("DOMContentLoaded", hideLoader);
  window.addEventListener("beforeunload", showLoader);

  function cancelPendingNav() {
    if (pendingNavTimeout) {
      clearTimeout(pendingNavTimeout);
      pendingNavTimeout = null;
    }
    navInProgress = false;
  }

  function navigateWithOptionalDelay(fn) {
    if (navInProgress) return;
    navInProgress = true;
    showLoader();
    const go = () => {
      pendingNavTimeout = null;
      fn();
    };
    if (DEBUG_MODE && PRENAV_DELAY_MS > 0) {
      pendingNavTimeout = setTimeout(go, PRENAV_DELAY_MS);
    } else {
      go();
    }
  }

  document.addEventListener("click", function (e) {
    const a = e.target.closest("a");
    if (!a) return;

    // 1) Bypass inside the loader overlay: always allow immediate navigation
    const insideLoader = !!e.target.closest("#loader");
    if (insideLoader) {
      const href = a.getAttribute("href");
      if (!href) return;
      e.preventDefault();
      cancelPendingNav();
      showLoader();
      window.location.assign(href);
      return;
    }

    // 2) Normal guardrails (same-tab navigations only)
    if (e.defaultPrevented) return;
    if (e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (a.target && a.target !== "_self") return;

    const href = a.getAttribute("href");
    if (!href || href.startsWith("#")) return;
    if (/^(mailto:|tel:|sms:|blob:|data:|javascript:)/i.test(href)) return;
    if (a.hasAttribute("download")) return;

    // 3) Explicit bypass markers
    const bypass = a.dataset.bypassLoader === "true" || a.classList.contains("loader-bypass");
    if (bypass) {
      // No pre-nav delay, navigate immediately
      e.preventDefault();
      cancelPendingNav();
      showLoader();
      window.location.assign(href);
      return;
    }

    // 4) Default behavior with optional pre-nav delay
    e.preventDefault();
    navigateWithOptionalDelay(() => {
      window.location.assign(href);
    });
  }, { capture: true });

  document.addEventListener("submit", function (e) {
    if (e.defaultPrevented) return;
    const form = e.target;
    if (form.target && form.target !== "_self") return;

    if (!form.noValidate && !form.checkValidity()) {
      if (typeof form.reportValidity === "function") form.reportValidity();
      return;
    }

    // If the submit control requests bypass (e.g., <button data-bypass-loader="true">)
    const submitter = e.submitter || document.activeElement;
    const bypass = submitter && (submitter.dataset.bypassLoader === "true" || submitter.classList?.contains("loader-bypass"));

    e.preventDefault();
    if (bypass) {
      cancelPendingNav();
      showLoader();
      HTMLFormElement.prototype.submit.call(form);
    } else {
      navigateWithOptionalDelay(() => {
        HTMLFormElement.prototype.submit.call(form);
      });
    }
  }, { capture: true });

  window.addEventListener("pageshow", function (e) {
    cancelPendingNav();
    if (e.persisted) hideLoader();
  });

  window.AppLoader = {
    show() { manualLock = false; showLoader(); },
    hide() { hideLoader(); },
    lock() { manualLock = true; },
    unlock() { manualLock = false; },
    cancelPendingNav
  };
})();
