// Protect pages with forms marked data-protect-leave="true" from accidental leave
document.addEventListener("DOMContentLoaded", () => {
    let isDirty = false;
    const protectedForms = document.querySelectorAll('form[data-protect-leave="true"]');

    if (!protectedForms.length) {
        return;
    }

    function isProtectedForm(form) {
        return Array.prototype.includes.call(protectedForms, form);
    }

    function setDirty() {
        isDirty = true;
    }

    protectedForms.forEach((form) => {
        form.addEventListener("input", () => {
            setDirty();
        });

        form.addEventListener("change", () => {
            setDirty();
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

    window.markFormDirty = (form) => {
        if (!form) {
            return;
        }
        if (!isProtectedForm(form)) {
            return;
        }
        setDirty();
    };
});
