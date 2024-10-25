class Verse:
    def __init__(self, num_verse: int, followed: bool, text: str):
        self.num_verse = num_verse
        self.followed = followed
        self.text = text

class Chorus(Verse):
    _chorus_counter = 0

    def __init__(self, followed: bool, text: str, start: bool):
        Chorus._chorus_counter += 1
        super().__init__(Chorus._chorus_counter, followed, text)
        self.start = start
        self.num_chorus = self.num_verse
        del self.num_verse