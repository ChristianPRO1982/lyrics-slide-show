// TRANSLATION
const pageLanguage = document.documentElement.lang || 'fr';
if (pageLanguage.toLowerCase() == 'fr-fr') {
    txt_fullscreen = 'APPUYEZ SUR F11 SUR CETTE ÉCRAN';
    txt_Add = "Ajouter";
} else {
    txt_fullscreen = 'PRESS F11 ON THIS SCREEN';
    txt_Add = "Add";
}

function toggleVisibility(id) {
    const element = document.getElementById(id);
    if (element.style.display === "none") {
        element.style.display = "block";
    } else {
        element.style.display = "none";
    }
}