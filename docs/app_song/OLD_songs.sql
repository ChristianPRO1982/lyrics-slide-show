    @staticmethod
    def get_all_songs(is_authenticated: bool,
        search_txt: str = '',
        search_everywhere: bool = False,
        search_logic: int = 0,
        search_genres: str = '',
        search_bands: str = '',
        search_artists: str = '',
        search_song_approved: int = 0,
        search_favorites: int = 0) -> list[dict[str, Any]]:

        search_txt = build_like_pattern(search_txt, accent_insensitive=True)

        search_genres_is_null = '0'
        if not search_genres:
            search_genres = '0'
            search_genres_is_null = '1'

        search_bands_is_null = '0'
        if not search_bands:
            search_bands = '0'
            search_bands_is_null = '1'

        search_artists_is_null = '0'
        if not search_artists:
            search_artists = '0'
            search_artists_is_null = '1'

        search_logic_SQL = ''
        if search_logic:
            for genre in search_genres.split(','):
                if genre != '0':
                    search_logic_SQL += f"""
      AND EXISTS (SELECT 1 FROM l_song_genre lsg WHERE lsg.song_id = ls1.song_id AND lsg.genre_id = {genre})"""
            for band in search_bands.split(','):
                if band != '0':
                    search_logic_SQL += f"""
      AND EXISTS (SELECT 1 FROM l_song_bands lsb WHERE lsb.song_id = ls1.song_id AND lsb.band_id = {band})"""
            for artist in search_artists.split(','):
                if artist != '0':
                    search_logic_SQL += f"""
      AND EXISTS (SELECT 1 FROM l_song_artists lsa WHERE lsa.song_id = ls1.song_id AND lsa.artist_id = {artist})"""


        request = f"""
   SELECT ls1.*,
          CONCAT(ls1.title,
                 CASE
                     WHEN ls1.sub_title != '' THEN CONCAT(' - ', ls1.sub_title)
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.status = 1 THEN ' ✔️'
                     WHEN ls1.status = 2 THEN ' ✔️⁉️'
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.licensed IS TRUE THEN ' 📄'
                     ELSE ''
                 END) AS full_title,
          CONCAT('[', GROUP_CONCAT(CONCAT(lg.`group`, '|', lg.name)), ']') AS genres,
          CONCAT('[', GROUP_CONCAT(CONCAT(cb.name)), ']') AS bands,
          CONCAT('[', GROUP_CONCAT(CONCAT(ca.name)), ']') AS artists,
          COUNT(lsf.song_id) AS favorite
     FROM l_songs ls1
LEFT JOIN l_song_genre lsg ON lsg.song_id = ls1.song_id
LEFT JOIN l_genres lg ON lg.genre_id = lsg.genre_id
LEFT JOIN l_song_bands lsb ON lsb.song_id = ls1.song_id
LEFT JOIN c_bands cb ON cb.band_id = lsb.band_id
LEFT JOIN l_song_artists lsa ON lsa.song_id = ls1.song_id
LEFT JOIN c_artists ca ON ca.artist_id = lsa.artist_id
LEFT JOIN l_song_favorite lsf ON lsf.song_id = ls1.song_id
    WHERE (ls1.licensed IS FALSE OR {is_authenticated} IS TRUE)
      AND ({search_everywhere} IS FALSE
           AND (ls1.title LIKE '%{search_txt}%'
                OR ls1.sub_title LIKE '%{search_txt}%')
            OR {search_everywhere} IS TRUE
           AND (ls1.title LIKE '%{search_txt}%'
                OR ls1.sub_title LIKE '%{search_txt}%'
                OR ls1.description LIKE '%{search_txt}%'
                OR EXISTS (SELECT 1
                             FROM l_songs ls2
                             JOIN l_verses lv ON lv.song_id = ls2.song_id
                            WHERE ls2.song_id = ls1.song_id
                              AND lv.text LIKE '%{search_txt}%'
                          )
               )
          )
      AND (lg.genre_id IN ({search_genres})
           OR {search_genres_is_null} = 1)
      AND (cb.band_id IN ({search_bands})
           OR {search_bands_is_null} = 1)
      AND (ca.artist_id IN ({search_artists})
           OR {search_artists_is_null} = 1){search_logic_SQL}
      AND ({search_song_approved} = 0
           OR {search_song_approved} = 1 AND ls1.status > 0
           OR {search_song_approved} = 2 AND ls1.status = 0)
      AND ({search_favorites} = 0
           OR {search_favorites} = 1 AND lsf.song_id IS NOT NULL)
 GROUP BY ls1.song_id, ls1.title, ls1.sub_title, ls1.description, ls1.status,
          CONCAT(ls1.title,
                 CASE
                     WHEN ls1.sub_title != '' THEN CONCAT(' - ', ls1.sub_title)
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.status = 1 THEN ' ✔️'
                     WHEN ls1.status = 2 THEN ' ✔️⁉️'
                     ELSE ''
                 END,
                 CASE
                     WHEN ls1.licensed IS TRUE THEN ' 📄'
                     ELSE ''
                 END)
 ORDER BY ls1.title, ls1.sub_title
"""
        params = []

        create_SQL_log(code_file, "Song.get_all_songs", "SELECT_1", request, params)
        with connection.cursor() as cursor:
            cursor.execute(request)
            rows = cursor.fetchall()
        return [{'song_id': row[0],
                 'title': row[1],
                 'sub_title': row[2],
                 'description': row[3],
                 'status': row[4],
                 'licensed': row[5],
                 'full_title': row[6],
                 'genres': row[7],
                 'bands': row[8],
                 'artists': row[9],
                 'favorite': row[10]
                 } for row in rows]
    