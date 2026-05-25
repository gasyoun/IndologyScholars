(() => {
    if (!("serviceWorker" in navigator)) {
        return;
    }

    window.addEventListener("load", () => {
        navigator.serviceWorker
            .register("/IndologyScholars/service-worker.js", { scope: "/IndologyScholars/" })
            .catch(() => {});
    });
})();
