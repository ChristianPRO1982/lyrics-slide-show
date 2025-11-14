// Warn user before leaving the page when marked forms have unsaved changes
document.addEventListener("DOMContentLoaded", () => {
    let isDirty = false;
    const protectedForms = document.querySelectorAll('form[data-protect-leave="true"]');

    if (!protectedForms.length) {
        return;
    }

    protectedForms.forEach((form) => {
        form.addEventListener("input", () => {
            isDirty = true;
        });

        form.addEventListener("change", () => {
            isDirty = true;
        });

        form.addEventListener("submit", () => {
            isDirty = false;
        });
    });

    window.addEventListener("beforeunload", (event) => {
        if (!isDirty) {
            return;
        }
        event.preventDefault();
        event.returnValue = "";
    });
});
