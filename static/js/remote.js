// TRANSLATION
const pageLanguage = document.documentElement.lang || 'fr';
// Convertir la langue de la page en minuscule
if (pageLanguage.toLowerCase() == 'fr-fr') {
    txt_fullscreen = 'APPUYEZ SUR F11 SUR CETTE ÉCRAN';
} else {
    txt_fullscreen = 'PRESS F11 ON THIS SCREEN';
}

// Ouvrir la fenêtre pour l'écran secondaire en plein écran
document.getElementById('openDisplayWindow').addEventListener('click', () => {
    displayWindow = window.open('', 'SlideDisplay', 'width=800,height=600');
    displayWindow.document.write(`
        <!DOCTYPE html>
        <html lang="fr">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>` + txt_fullscreen + `</title>
        <style>
            body {
            margin: 0;
            padding: 0;
            color: white;
            background-color: black;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            }
            .full-screen {
            font-size: 50px;
            text-align: center;
            }
        </style>
        </head>
        <body>
        <div class="full-screen" id="slideContent">` + txt_fullscreen + `</div>
        </body>
        </html>
    `);
    });

function showSlide(index, text) {
    // Vérifier si la fenêtre secondaire est ouverte
    if (displayWindow) {
        displayWindow.document.getElementById('slideContent').innerHTML = text;
    }

    // Mettre à jour l'interface pour montrer la slide sélectionnée
    document.querySelectorAll('.slide').forEach(slide => {
        slide.classList.remove('active');
    });
    
    const div = document.getElementById(index);
    div.classList.add('active');
}