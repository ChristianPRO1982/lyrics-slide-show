// global helper (no module): window.preloadImages(urls[, onProgress]) -> Promise<{ok:number, failed:string[]}>
(function (global) {
  function preloadImages(urls, onProgress) {
    const list = Array.from(new Set(urls)).filter(Boolean);
    let loaded = 0;
    const total = list.length;
    const failed = [];
    const tasks = list.map((url) => new Promise((resolve, reject) => {
      const img = new Image();
      img.decoding = "async";
      img.loading = "eager";
      img.onload = () => {
        loaded += 1;
        if (typeof onProgress === "function") onProgress({ loaded, total, url });
        resolve(url);
      };
      img.onerror = () => {
        loaded += 1;
        failed.push(url);
        if (typeof onProgress === "function") onProgress({ loaded, total, url });
        reject(url);
      };
      img.src = url;
    }));
    return Promise.allSettled(tasks).then(() => ({ ok: total - failed.length, failed }));
  }
  global.preloadImages = preloadImages;
})(window);
