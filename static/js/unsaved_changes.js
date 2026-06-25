(() => {
    const controllers = new Set();
    let beforeUnloadBound = false;

    const serializeValue = (value) => {
        if (value instanceof File) {
            return {
                name: value.name,
                size: value.size,
                type: value.type,
                lastModified: value.lastModified,
            };
        }
        return String(value ?? "");
    };

    const defaultSnapshot = (form) => {
        const entries = [];
        const formData = new FormData(form);
        formData.forEach((value, key) => {
            entries.push([key, serializeValue(value)]);
        });
        return JSON.stringify(entries);
    };

    const bindBeforeUnload = () => {
        if (beforeUnloadBound) {
            return;
        }
        window.addEventListener("beforeunload", (event) => {
            for (const controller of controllers) {
                if (!controller.shouldWarn()) {
                    continue;
                }
                event.preventDefault();
                event.returnValue = "";
                return;
            }
        });
        beforeUnloadBound = true;
    };

    const attach = (form, options = {}) => {
        if (!(form instanceof HTMLFormElement)) {
            return null;
        }
        if (form.__lssUnsavedChangesController) {
            return form.__lssUnsavedChangesController;
        }

        const getSnapshot = typeof options.getSnapshot === "function"
            ? () => String(options.getSnapshot(form))
            : () => defaultSnapshot(form);

        let baseline = getSnapshot();
        let dirty = false;
        let isSubmitting = false;

        const refresh = () => {
            if (isSubmitting) {
                return false;
            }
            dirty = getSnapshot() !== baseline;
            return dirty;
        };

        const reset = () => {
            baseline = getSnapshot();
            dirty = false;
            isSubmitting = false;
        };

        const controller = {
            form,
            refresh,
            markDirty: refresh,
            reset,
            shouldWarn: () => dirty && !isSubmitting,
            isDirty: () => dirty,
        };

        form.addEventListener("input", refresh);
        form.addEventListener("change", refresh);
        form.addEventListener("submit", () => {
            isSubmitting = true;
            dirty = false;
        });

        bindBeforeUnload();
        controllers.add(controller);
        form.__lssUnsavedChangesController = controller;
        return controller;
    };

    window.LSSUnsavedChanges = {
        attach,
    };
})();
