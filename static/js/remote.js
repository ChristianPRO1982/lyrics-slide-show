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

let last_text = '';

function showSlide(index, updateCurrentSlide = true) {
    text = decodeHTMLEntities(getText(index));
    
    if (displayWindow) {
        displayWindow.document.getElementById('slideContent').innerHTML = text;
        last_text = text;
    }
    
    document.querySelectorAll('.slide').forEach(slide => {
        slide.classList.remove('active');
    });
    
    const divs = document.querySelectorAll(`[id="${index}"]`);
    divs.forEach(div => div.classList.add('active'));

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

function navNextSlide() {
    current_slide += 1;
    if (current_slide >= slides.length) {
        current_slide = 0;
    }
    showSlide(slides[current_slide]);

    const navNextSlideDiv = document.getElementById('nav_next_slide');
    if (navNextSlideDiv) {
        navNextSlideDiv.innerHTML = '';
    }

    if (navNextSlideDiv) {
        navNextSlideDiv.innerHTML = '<a href="#song_' + current_song_id +
        '" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">🎶📜</div></a>';
    }
}

function navNextSlideInit() {
    const navNextSlideDiv = document.getElementById('nav_next_slide');
    if (navNextSlideDiv) {
        navNextSlideDiv.innerHTML = '';
    }

    if (navNextSlideDiv) {
        navNextSlideDiv.innerHTML = '<a href="#song_' + current_song_id +
        '" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">🎶📜</div></a>';
    }
}

function navChorus() {
    const navChorusDiv = document.getElementById('nav_chorus');
    if (navChorusDiv) {
        navChorusDiv.innerHTML = '';
    }
    
    if (navChorusDiv) {
        navChorusDiv.innerHTML = '<a href="#song_' + current_song_id +
        '" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">🎼🌟</div></a>';
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
        '" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">🎼🌟</div></a>';
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
        '" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">⏮️</div></a>';
        navPreviousSongFullTitleDiv.innerHTML = '<span class="text-xs">' + songs[index].previous_song_full_title + '</span>';
    }
    if (navNextSongDiv) {
        navNextSongDiv.innerHTML = '<a href="#song_' + songs[index].next_song_id +
        '" class="w-full"><div class="slide flex w-full h-28 p-2 items-center justify-center border rounded-lg text-4xl">⏭️</div></a>';
        navNextSongFullTitleDiv.innerHTML = '<span class="text-xs">' + songs[index].next_song_full_title + '</span>';
    }

    current_song_id = songs[index].song_id;
    slides = getSongSlides();
    current_slide = -1;
    previous_song_id = 0;
    next_song_id = 0;
    current_chorus_slide = 0;
    navNextSlideInit();
    navChorusInit();
}

function navPreviousSong() {
    if (songs[songIdToIndex(current_song_id)].previous_song_id != '') {
        navSongs(songIdToIndex(songs[songIdToIndex(current_song_id)].previous_song_id));
    }
}

function navNextSong() {
    if (songs[songIdToIndex(current_song_id)].next_song_id != '') {
        navSongs(songIdToIndex(songs[songIdToIndex(current_song_id)].next_song_id));
    }
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
    // display choruses
    if (event.key.toLowerCase() === 'a') {
        disChoruses(true);
    }
    if (event.key.toLowerCase() === 'd') {
        disChoruses(true);
    }
    // undisplay choruses
    if (event.key.toLowerCase() === 'm') {
        disChoruses(false);
    }
    if (event.key.toLowerCase() === 'u') {
        disChoruses(false);
    }
});