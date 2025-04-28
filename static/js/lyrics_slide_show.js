// TRANSLATION
const pageLanguage = document.documentElement.lang || 'fr';
if (pageLanguage.toLowerCase() == 'fr-fr') {
    txt_fullscreen = 'APPUYEZ SUR F11 SUR CETTE ÉCRAN';
    txt_Description = "Description";
    txt_Add = "Ajouter";
    txt_Modify = "Modifier";
    txt_Delete = "Supprimer";
} else {
    txt_fullscreen = 'PRESS F11 ON THIS SCREEN';
    txt_Description = "Description";
    txt_Add = "Add";
    txt_Modify = "Modify";
    txt_Delete = "Delete";
}

function toggleVisibility(id) {
    const element = document.getElementById(id);
    if (element.style.display === "none") {
        element.style.display = "block";
    } else {
        element.style.display = "none";
    }
}