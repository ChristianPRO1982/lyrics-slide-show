


def all_lyrics(slides):
    try:
        new_slides = []
        verses_choruses = []
        for slide in slides:
            if slide['new_animation_song'] and verses_choruses != []:
                new_slides.extend(lyrics(verses_choruses))
                verses_choruses = []
            
            verses_choruses.append(slide)
        new_slides.extend(lyrics(verses_choruses))

        return new_slides

    except Exception as e:
        return None
    

def lyrics(slides):
    try:
        choruses = []
        lyrics = []

        # Get all choruses
        for slide in slides:
            if slide['chorus'] == 1:
                choruses.append(slide)
        
        # get all slides : choruses + verses
        start_by_chorus = True
        for slide in slides:
            if slide['chorus'] != 1:
                if slide['text']:
                    lyrics.append(slide)
                if slide['followed'] == 0 and len(choruses) > 0:
                    lyrics.extend(choruses)
            elif start_by_chorus:
                lyrics.extend(choruses)
            start_by_chorus = False

            # Set "new_animation_song" to 0 for all dictionaries except the first
            for i, lyric in enumerate(lyrics):
                if i == 0:
                    lyric['new_animation_song'] = 1
                else:
                    lyric['new_animation_song'] = 0
        
        return lyrics

    except Exception as e:
        return []
    

def get_lyrics(self):
    choruses = []
    lyrics = ""

    # Get all choruses
    for verse in self.verses:
        if verse.chorus == 1:
            choruses.append("<b>" + verse.text.replace("\n", "<br>") + "</b>")

    start_by_chorus = True
    for verse in self.verses:
        if verse.chorus != 1:
            if verse.text and not verse.like_chorus:
                lyrics += str(verse.num_verse) + ". " + verse.text.replace("\n", "<br>") + "<br><br>"
            if verse.text and verse.like_chorus:
                lyrics += "<b>" + verse.text.replace("\n", "<br>") + "</b><br><br>"
            if not verse.followed and choruses:
                lyrics += "<br><br>".join(choruses) + "<br><br>"
        elif start_by_chorus:
            lyrics += "<br><br>".join(choruses) + "<br><br>"
        start_by_chorus = False
    
    if not lyrics:
        lyrics = "<br><br>".join(choruses)

    
    return lyrics