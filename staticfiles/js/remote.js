let slides = ['Slide 1', 'Slide 2', 'Slide 3', 'Slide 4', 'Slide 5']; // Exemple de slides
let slideList = document.getElementById('slideList');
let displayWindow;

// Générer la liste des slides dynamiquement
slides.forEach((slide, index) => {
    let slideElement = document.createElement('div');
    slideElement.classList.add('slide');
    slideElement.innerText = slide;
    slideElement.addEventListener('click', () => {
    selectSlide(index, slideElement);
    });
    slideList.appendChild(slideElement);
});


// Ouvrir la fenêtre pour l'écran secondaire en plein écran
document.getElementById('openDisplayWindow').addEventListener('click', () => {
    displayWindow = window.open('', 'SlideDisplay', 'width=800,height=600');
    displayWindow.document.write(`
        <!DOCTYPE html>
        <html lang="fr">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>APPUYEZ SUR F11 SUR CETTE ÉCRAN</title>
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
        <div class="full-screen" id="slideContent">APPUYEZ SUR F11 SUR CETTE ÉCRAN</div>
        </body>
        </html>
    `);
    });

// Fonction pour sélectionner une slide et l'afficher dans la fenêtre secondaire
function selectSlide(index, element) {
    // Mettre à jour l'interface pour montrer la slide sélectionnée
    document.querySelectorAll('.slide').forEach(slide => {
    slide.classList.remove('active');
    });
    element.classList.add('active');

    // Envoyer la slide à la fenêtre secondaire
    if (displayWindow) {
    displayWindow.document.getElementById('slideContent').innerText = slides[index];
    }
}