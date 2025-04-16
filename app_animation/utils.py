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
                slide['new_animation_song'] = 0
                choruses.append(slide)
        
        # get all slides : choruses + verses
        start_by_chorus = True
        for slide in slides:
            if slide['chorus'] != 1:
                if slide['text']:
                    slide['new_animation_song'] = 0
                    lyrics.append(slide)
                if slide['followed'] == 0 and len(choruses) > 0:
                    lyrics.extend([chorus.copy() for chorus in choruses])
            elif start_by_chorus:
                lyrics.extend([chorus.copy() for chorus in choruses])
            start_by_chorus = False
        
        lyrics[0]['new_animation_song'] = 1
        return lyrics

    except Exception as e:
        return []