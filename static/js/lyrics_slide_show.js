// TRANSLATION
const pageLanguage = document.documentElement.lang || 'fr';
if (pageLanguage.toLowerCase() == 'fr-fr') {
    txt_fullscreen = 'APPUYEZ SUR F11 SUR CETTE ÉCRAN';
    txt_Description = "Description";
    txt_Add = "Ajouter";
    txt_Modify = "Modifier";
    txt_Delete = "Supprimer";
    err_qr_code = "Erreur lors de la génération du QR code";
} else {
    txt_fullscreen = 'PRESS F11 ON THIS SCREEN';
    txt_Description = "Description";
    txt_Add = "Add";
    txt_Modify = "Modify";
    txt_Delete = "Delete";
    err_qr_code = "Error generating QR code";
}

function toggleVisibility(id) {
    const element = document.getElementById(id);
    if (element.style.display === "none") {
        element.style.display = "block";
    } else {
        element.style.display = "none";
    }
}

function toggleDivDisplay(id_div, id_a, txt_show, txt_hide) {
    const div = document.getElementById(id_div);
    const a = document.getElementById(id_a);
    if (!div || !a) return;
    if (div.style.display === "none" || div.style.display === "") {
        div.style.display = "block";
        a.textContent = txt_hide;
    } else {
        div.style.display = "none";
        a.textContent = txt_show;
    }
}