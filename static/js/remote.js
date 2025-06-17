document.getElementById('openDisplayWindow').addEventListener('click', () => {
    if (blockScrollKeys == false) {
        scrollable();
    }
    displayWindow = window.open('', 'SlideDisplay', 'width=800,height=600');
    displayWindow.document.write(`
        <!DOCTYPE html>
        <html lang="fr">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://fonts.googleapis.com/css2?family=Amatic+SC&family=Anton&family=Baloo+2&family=Bangers&family=Bree+Serif&family=Caveat&family=Chewy&family=Concert+One&family=Fredoka&family=Fugaz+One&family=Gloria+Hallelujah&family=Indie+Flower&family=Lobster&family=Patrick+Hand&family=Poppins&family=Quicksand&family=Righteous&family=Roboto+Slab&family=SACRAMENTO&family=Source+Sans+Pro&family=Special+Elite&family=Staatliches&family=Ubuntu&family=Work+Sans&display=swap" rel="stylesheet">
        <title>` + txt_fullscreen + `</title>
        <style>
            body {
                margin: 0;
                padding: 0;
                color: grey;
                background-color: black;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }

            .full-screen {
                font-size: ` + font_size + `px;
                text-align: center;
            }

            #slideContent {
                width: 100vw;
                height: 100vh;
                display: flex;
                justify-content: center; /* horizontal */
                align-items: center;     /* vertical */
                flex-direction: column;  /* au cas où tu as plusieurs lignes */
            }
        </style>
        </head>
        <body>
        <div
            id="slideContent"
            class="full-screen"
            style="text-align: center;
                color: ` + color_rgba + `;
                background-color: ` + bg_rgba + `;">
            ` + txt_fullscreen + `
        </div>
        </body>
        </html>
    `);
    });

let last_text = '';

function showSlide(index, updateCurrentSlide = true) {
    text = decodeHTMLEntities(getText(index));
    color_rgba = getColorRgba(index);
    bg_rgba = getBgRgba(index);
    font = getFont(index);
    fontSize = getFontSize(index);
    
    if (displayWindow) {
        displayWindow.document.getElementById('slideContent').innerHTML = text;
        displayWindow.document.getElementById('slideContent').style.fontSize = fontSize + 'px';
        displayWindow.document.getElementById('slideContent').style.fontFamily = font;
        displayWindow.document.getElementById('slideContent').style.color = color_rgba;
        displayWindow.document.getElementById('slideContent').style.backgroundColor = bg_rgba;
        last_text = text;
    }
    
    cleanSelectedSlides();
    
    if (updateCurrentSlide) {
        const divs = document.querySelectorAll(`[id="${index}"][name="${current_slide}"]`);
        divs.forEach(div => div.classList.add('active'));
    }
    const chorus_divs = document.querySelectorAll(`[id="${index}"]`);
    chorus_divs.forEach(div => div.classList.add('chorus_active'));

    if (updateCurrentSlide) {nextChorusSlideSelect(index);}
    disChoruses();
}

function decodeHTMLEntities(str) {
    const txt = document.createElement("textarea");
    txt.innerHTML = str;
    return txt.value;
}

function nextChorusSlideSelect(index) {
    current_chorus_slide = 0;
    for (i = 0; i < chorus.length; i++) {if (chorus[i] == index) {current_chorus_slide = i + 1;}}
    if (current_chorus_slide + 1 > chorus.length) {current_chorus_slide = 0;}
}

function getText(index) {
    let [animation_song_id, verse_id] = index.split('_');
    for (i = 0; i < verses_choruses.length; i++) {
        if (verses_choruses[i].animation_song_id == animation_song_id && verses_choruses[i].verse_id == verse_id) {
            text = verses_choruses[i].text;
            return text;
        }
    }
}

function getColorRgba(index) {
    let [animation_song_id, verse_id] = index.split('_');
    for (i = 0; i < verses_choruses.length; i++) {
        if (verses_choruses[i].animation_song_id == animation_song_id && verses_choruses[i].verse_id == verse_id) {
            color_rgba = verses_choruses[i].color_rgba;
            return color_rgba;
        }
    }
}

function getBgRgba(index) {
    let [animation_song_id, verse_id] = index.split('_');
    for (i = 0; i < verses_choruses.length; i++) {
        if (verses_choruses[i].animation_song_id == animation_song_id && verses_choruses[i].verse_id == verse_id) {
            bg_rgba = verses_choruses[i].bg_rgba;
            return bg_rgba;
        }
    }
}

function getFontSize(index) {
    let [animation_song_id, verse_id] = index.split('_');
    for (i = 0; i < verses_choruses.length; i++) {
        if (verses_choruses[i].animation_song_id == animation_song_id && verses_choruses[i].verse_id == verse_id) {
            font_size = verses_choruses[i].font_size;
            return font_size;
        }
    }
}

function getFont(index) {
    let [animation_song_id, verse_id] = index.split('_');
    for (i = 0; i < verses_choruses.length; i++) {
        if (verses_choruses[i].animation_song_id == animation_song_id && verses_choruses[i].verse_id == verse_id) {
            font = verses_choruses[i].font;
            return font;
        }
    }
}

function getSongSlides() {
    slides = [];
    chorusSet = new Set();

    for (i = 0; i < all_slides.length; i++) {
        let [animation_song_id, verse_id] = all_slides[i].split('_');
        if (animation_song_id == current_song_id) {
            slides.push(all_slides[i]);

            if (isChorus(animation_song_id, verse_id)) {
                chorusSet.add(all_slides[i]);
            }
        }
    }
    
    chorus = Array.from(chorusSet);

    return slides;
}

function isChorus(id1, id2) {
    for (i2 = 0; i2 < verses_choruses.length; i2++) {
        if (verses_choruses[i2].animation_song_id == id1 && verses_choruses[i2].verse_id == id2 && verses_choruses[i2].chorus == 1) {
            return true;
        }
    }
    return false;
}

function blackMode() {
    const div = document.getElementById('blackMode');
    if (!div.classList.contains('active')) {
        if (displayWindow) {
            displayWindow.document.getElementById('slideContent').innerHTML = '';
        }
        div.classList.add('active');
    } else {
        if (displayWindow) {
            displayWindow.document.getElementById('slideContent').innerHTML = last_text;
        }
        div.classList.remove('active');
    }
}

function nextActiveSlide() {
    // select next slide
    next_slide = current_slide + 1;
    if (next_slide >= slides.length) {next_slide = 0;}
    next_index = slides[next_slide];
    const next_divs = document.querySelectorAll(`[id="${next_index}"][name="${next_slide}"]`);
    if (slides.length > 1) {next_divs.forEach(div => div.classList.add('next_active'));}

    // display next slide text on preview div
    next_text = decodeHTMLEntities(getText(slides[next_slide]));
    document.getElementById('draggableDivText').innerHTML = next_text;
}

function navNextSlide() {
    current_slide += 1;
    if (current_slide >= slides.length) {current_slide = 0;}
    showSlide(slides[current_slide]);

    const navNextSlideDiv = document.getElementById('nav_next_slide');
    if (navNextSlideDiv) {
        navNextSlideDiv.innerHTML = '';
    }

    if (navNextSlideDiv) {
        navNextSlideDiv.innerHTML = '<a href="#song_' + current_song_id +
        '" style="text-decoration: none!important;" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">🎶📜</div></a>';
    }

    nextActiveSlide();
}

function navNextSlideInit() {
    const navNextSlideDiv = document.getElementById('nav_next_slide');
    if (navNextSlideDiv) {
        navNextSlideDiv.innerHTML = '';
    }

    if (navNextSlideDiv) {
        navNextSlideDiv.innerHTML = '<a href="#song_' + current_song_id +
        '" style="text-decoration: none!important;" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">🎶📜</div></a>';
    }
}

function navChorus() {
    const navChorusDiv = document.getElementById('nav_chorus');
    if (navChorusDiv) {
        navChorusDiv.innerHTML = '';
    }
    
    if (navChorusDiv) {
        navChorusDiv.innerHTML = '<a href="#song_' + current_song_id +
        '" style="text-decoration: none!important;" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">🎼🌟</div></a>';
    }
    
    showSlide(chorus[current_chorus_slide], false);
    
    current_chorus_slide += 1;
    if (current_chorus_slide + 1 > chorus.length) {current_chorus_slide = 0;}
}

function navChorusInit() {
    const navChorusDiv = document.getElementById('nav_chorus');
    if (navChorusDiv) {
        navChorusDiv.innerHTML = '';
    }

    if (navChorusDiv) {
        navChorusDiv.innerHTML = '<a href="#song_' + current_song_id +
        '" style="text-decoration: none!important;" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">🎼🌟</div></a>';
    }
}

function navSongs(index) {
    const navPreviousSongDiv = document.getElementById('nav_previous_song');
    if (navPreviousSongDiv) {
        navPreviousSongDiv.innerHTML = '';
    }
    const navPreviousSongFullTitleDiv = document.getElementById('nav_previous_song_full_title');
    if (navPreviousSongFullTitleDiv) {
        navPreviousSongFullTitleDiv.innerHTML = '';
    }
    
    const navNextSongDiv = document.getElementById('nav_next_song');
    if (navNextSongDiv) {
        navNextSongDiv.innerHTML = '';
    }
    const navNextSongFullTitleDiv = document.getElementById('nav_next_full_title');
    if (navNextSongFullTitleDiv) {
        navNextSongFullTitleDiv.innerHTML = '';
    }

    
    if (navPreviousSongDiv) {
        navPreviousSongDiv.innerHTML = '<a href="#song_' + songs[index].previous_song_id +
        '" style="text-decoration: none!important;" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">⏮️</div></a>';
        navPreviousSongFullTitleDiv.innerHTML = '<span class="text-xs">' + songs[index].previous_song_full_title + '</span>';
    }
    if (navNextSongDiv) {
        navNextSongDiv.innerHTML = '<a href="#song_' + songs[index].next_song_id +
        '" style="text-decoration: none!important;" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">⏭️</div></a>';
        navNextSongFullTitleDiv.innerHTML = '<span class="text-xs">' + songs[index].next_song_full_title + '</span>';
    }

    let currentSongTitleDiv = document.getElementById('current_song_title');
    let draggableSpanSongTitle = document.getElementById('draggableSpanSongTitle');
    let currentSongTitle = songs[index].song_full_title.replace('&#x27;', "'").replace('&quot;', '"').replace('&amp;', '&');
    currentSongTitleDiv.textContent = currentSongTitle;
    draggableSpanSongTitle.textContent = currentSongTitle;

    current_song_id = songs[index].song_id;
    slides = getSongSlides();
    current_slide = -1;
    previous_song_id = 0;
    next_song_id = 0;
    current_chorus_slide = 0;
    navNextSlideInit();
    navChorusInit();
    cleanSelectedSlides();
    nextActiveSlide();
}

function cleanSelectedSlides() {
    document.querySelectorAll('.slide').forEach(slide => {
        slide.classList.remove('active');
        slide.classList.remove('chorus_active');
        slide.classList.remove('next_active');
    });
}

function updateCurrentSlide(currentSlide) {
    current_slide = currentSlide;
}

function navPreviousSong() {
    if (songs[songIdToIndex(current_song_id)].previous_song_id != '') {
        navSongs(songIdToIndex(songs[songIdToIndex(current_song_id)].previous_song_id));
    }
    targetElement = document.getElementById("song_" + current_song_id);
    targetElement.scrollIntoView();
}

function navNextSong() {
    if (songs[songIdToIndex(current_song_id)].next_song_id != '') {
        navSongs(songIdToIndex(songs[songIdToIndex(current_song_id)].next_song_id));
    }
    targetElement = document.getElementById("song_" + current_song_id);
    targetElement.scrollIntoView();
}

function songIdToIndex(song_id) {
    for (i = 0; i < songs.length; i++) {
        let song = songs[i];
        if (song.song_id == song_id) {
            return i;
        }
    }
    return 0;
}

function disChoruses(change = false) {
    const disChorusesDiv = document.getElementById('dis_choruses');
    if (disChorusesDiv) {
        disChorusesDiv.innerHTML = '';
    }

    if (change == true) {
        if (display_choruses == 1) {
            display_choruses = 0;
        } else {
            display_choruses = 1;
        }
    }

    if (display_choruses == 1) {
        if (disChorusesDiv) {
            disChorusesDiv.innerHTML = '<div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">🎼🔽</div>';
            document.querySelectorAll('.chorus').forEach(chorus => {
                chorus.classList.add('hidden');
            });
        }
    } else {
        if (disChorusesDiv) {
            disChorusesDiv.innerHTML = '<div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">🎼🔼</div>';
            document.querySelectorAll('.chorus').forEach(chorus => {
                chorus.classList.remove('hidden');
            });
        }
    }
}

document.addEventListener('keydown', (event) => {
    // alert(event.key);

    // BLACK MODE \\
    if (event.key.toLowerCase() === 'escape') {
        blackMode();
    }
    if (event.key.toLowerCase() === 'b') {
        blackMode();
    }
    if (event.key.toLowerCase() === 'arrowup') {
        blackMode();
    }

    // NEXT SLIDE \\
    if (event.key.toLowerCase() === 'arrowdown') {
        navNextSlide();
    }
    if (event.key.toLowerCase() === 's') {
        navNextSlide();
    }
    if (event.key.toLowerCase() === 'v') {
        navNextSlide();
    }
    if (event.key.toLowerCase() === ' ') {
        navNextSlide();
    }

    // CHORUS \\
    if (event.key.toLowerCase() === 'c') {
        navChorus();
    }
    if (event.key.toLowerCase() === 'r') {
        navChorus();
    }

    // PREVIOUS SONG \\
    if (event.key.toLowerCase() === 'arrowleft') {
        navPreviousSong();
    }
    if (event.key.toLowerCase() === 'p') {
        navPreviousSong();
    }

    // NEXT SONG \\
    if (event.key.toLowerCase() === 'arrowright') {
        navNextSong();
    }
    if (event.key.toLowerCase() === 'enter') {
        navNextSong();
    }
    if (event.key.toLowerCase() === 'n') {
        navNextSong();
    }

    // OPTIONS \\
    // display-undisplay choruses
    if (event.key.toLowerCase() === 'a') {
        disChoruses(true);
    }
    if (event.key.toLowerCase() === 'd') {
        disChoruses(true);
    }
    // scrollable
    if (event.key.toLowerCase() === 'l') {
        scrollable();
    }
    // display preview window
    if (event.key.toLowerCase() === 'w') {
        if (document.getElementById('draggableDiv').style.display=='block') {
            document.getElementById('draggableDiv').style.display='none';
            document.getElementById('showDraggableDivLink').style.display='inline-block';
        } else {
            document.getElementById('draggableDiv').style.display='block';
            document.getElementById('showDraggableDivLink').style.display='none';
        }
    }
});

let blockScrollKeys = true;

function handleKeydown(event) {
    const keysToBlock = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '];

    if (blockScrollKeys && keysToBlock.includes(event.key)) {
        event.preventDefault();
    }
}

function enableScrollKeyBlocking() {
    blockScrollKeys = true;
}

function disableScrollKeyBlocking() {
    blockScrollKeys = false;
}

function scrollable() {
    if (blockScrollKeys) {
        blockScrollKeys = false;
    } else {
        blockScrollKeys = true;
    }

    const scrollableDiv = document.getElementById('scrollable');
    if (scrollableDiv) {
        scrollableDiv.innerHTML = '';
    }

    if (blockScrollKeys == 1) {
        if (scrollableDiv) {
            scrollableDiv.innerHTML = '<div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">🧱</div>';
        }
    } else {
        if (scrollableDiv) {
            scrollableDiv.innerHTML = '<div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">↕️</div>';
        }
    }
}

window.addEventListener('keydown', handleKeydown, { passive: false });
