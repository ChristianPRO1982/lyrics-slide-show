(function () {
    "use strict";

    const form = document.querySelector("[data-animation-copy-form]");
    const config = document.querySelector("[data-animation-copy-i18n]");

    if (!(form instanceof HTMLFormElement) || !(config instanceof HTMLElement)) {
        return;
    }

    const scheduledInput = form.querySelector("[data-animation-copy-scheduled-at]");
    const titleInput = form.querySelector("[data-animation-copy-title]");
    const descriptionInput = form.querySelector("[data-animation-copy-description]");

    if (
        !(scheduledInput instanceof HTMLInputElement)
        || !(titleInput instanceof HTMLInputElement)
        || !(descriptionInput instanceof HTMLInputElement)
    ) {
        return;
    }

    const label = (name, fallback) => String(config.dataset[name] || fallback);
    const paragraphValue = (value, fallback) => {
        const normalized = String(value || "").trim();
        return normalized || fallback;
    };

    const openCopyPopup = async (trigger) => {
        const messageBox = window.LSSMessageBox;
        if (!messageBox || typeof messageBox.show !== "function") {
            return;
        }

        const sourceTitle = paragraphValue(
            trigger.dataset.sourceTitle,
            label("emptyDescriptionLabel", "Aucune description"),
        );
        const sourceDescription = paragraphValue(
            trigger.dataset.sourceDescription,
            label("emptyDescriptionLabel", "Aucune description"),
        );

        const result = await messageBox.show({
            title: label("popupTitle", "Copier l'animation"),
            messageMarkdown: [
                `**${label("sourceTitleLabel", "Titre actuel")}**`,
                sourceTitle,
                "",
                `**${label("sourceDescriptionLabel", "Description actuelle")}**`,
                sourceDescription,
            ].join("\n\n"),
            showCloseButton: true,
            fields: [
                {
                    id: "scheduled_at",
                    label: label("scheduledLabel", "Date et heure"),
                    type: "datetime-local",
                    value: "",
                    required: true,
                },
                {
                    id: "title",
                    label: label("titleLabel", "Titre"),
                    type: "text",
                    value: "",
                    required: true,
                    maxLength: 255,
                },
                {
                    id: "description",
                    label: label("descriptionLabel", "Description"),
                    type: "textarea",
                    value: "",
                    required: true,
                    rows: 4,
                },
            ],
            buttons: [
                {
                    id: "create",
                    label: label("createLabel", "Créer la copie"),
                    tone: "success",
                    validate: true,
                },
                {
                    id: "cancel",
                    label: label("cancelLabel", "Annuler"),
                    tone: "neutral",
                    validate: false,
                },
            ],
            enterButtonId: "create",
            escapeButtonId: "cancel",
            initialFocus: "first-field",
        });

        if (result.buttonId !== "create") {
            return;
        }

        scheduledInput.value = String(result.values?.scheduled_at || "").trim();
        titleInput.value = String(result.values?.title || "").trim();
        descriptionInput.value = String(result.values?.description || "").trim();
        form.action = trigger.dataset.copyUrl || "";

        if (!form.action) {
            return;
        }

        if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
            return;
        }
        form.submit();
    };

    document.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const trigger = target.closest("[data-animation-copy-trigger]");
        if (!(trigger instanceof HTMLElement)) {
            return;
        }
        event.preventDefault();
        openCopyPopup(trigger);
    });
})();
