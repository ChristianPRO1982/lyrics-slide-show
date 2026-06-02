SELECT setval(
    pg_get_serial_sequence('common.artists', 'artist_id'),
    (SELECT MAX(artist_id) FROM common.artists)
);

SELECT CONCAT("INSERT INTO common.artists (artist_id, name) OVERRIDING SYSTEM VALUE VALUES (", artist_id, ", '", REPLACE(name, '''', ''''''), "');") FROM c_artists c;

SELECT CONCAT("INSERT INTO common.bands (band_id, name) OVERRIDING SYSTEM VALUE VALUES (", band_id, ", '", REPLACE(name, '''', ''''''), "');") FROM c_bands

SELECT CONCAT("INSERT INTO common.genres OVERRIDING SYSTEM VALUE VALUES (", genre_id, ", '", REPLACE(l.group, '''', ''''''), "', '", REPLACE(l.name, '''', ''''''), "');") FROM  l_genres l

SELECT CONCAT(
	"INSERT INTO lss.s_songs VALUES (",
	l.song_id,
	", '",
	REPLACE(l.title, '''', ''''''),
	"', '",
	REPLACE(l.sub_title, '''', ''''''),
	"', '",
	REPLACE(l.description, '''', ''''''),
	"', ",
	l.status,
	", ",
	CASE WHEN l.licensed = 0 THEN "FALSE" ELSE "TRUE" END,
	");"
)
FROM  l_songs l

SELECT CONCAT(
	"INSERT INTO lss.s_verses (verse_id, song_id, num, num_verse, chorus, chorus_like, followed, notcontinuenumbering, text, prefix) VALUES (",
	l.verse_id,
	", ",
	l.song_id,
	", ",
	l.num,
	", ",
	l.num_verse,
	", ",
	CASE
		WHEN l.chorus = 0 THEN "FALSE"
		WHEN l.chorus = 1 THEN "TRUE"
		WHEN l.chorus = 2 THEN "FALSE"
	END,
	", ",
	CASE
		WHEN l.chorus = 0 THEN "FALSE"
		WHEN l.chorus = 1 THEN "FALSE"
		WHEN l.chorus = 2 THEN "TRUE"
	END,
	", ",
	CASE WHEN l.followed = 0 THEN "FALSE" ELSE "TRUE" END,
	", ",
	CASE WHEN l.notcontinuenumbering = 0 THEN "FALSE" ELSE "TRUE" END,
	", '",
	REPLACE(l.text, '''', ''''''),
	"', '",
	REPLACE(l.prefix, '''', ''''''),
	"');"
)
FROM l_verses l

SELECT CONCAT("INSERT INTO lss.s_verse_prefixes (prefix_id, prefix, comment) VALUES (", l.prefix_id, ", '", l.prefix, "', '", l.comment, "');") FROM l_verse_prefixes l

SELECT CONCAT(
	"INSERT INTO lss.s_song_links (song_id, type, link) VALUES (",
	l.song_id,
	", '",
	CASE
        WHEN l.link LIKE '%emmanuelmusic%'
             AND l.link NOT LIKE '%emmanuelmusic%mp3%' THEN 'partition'
        WHEN l.link LIKE '%emmanuelmusic%mp3%' THEN 'audio'
        WHEN l.link LIKE '%choralepolefontainebleau%' THEN 'audio'
        WHEN l.link LIKE '%youtu%' THEN 'YouTube'
        WHEN l.link LIKE '%carthographie%' THEN 'lien interne'
        WHEN l.link LIKE '%topchretien%' THEN 'partition'
        WHEN l.link LIKE '%bayardmusique%' THEN 'partition'
        ELSE 'lien'
    END,
    "', '",
	REPLACE(l.link, '''', ''''''),
	"');"
)
FROM l_song_link l

SELECT CONCAT("INSERT INTO lss.s_song_bands (song_id, band_id) VALUES (", l.song_id, ", ", l.band_id, ");") FROM l_song_bands l

SELECT CONCAT("INSERT INTO lss.s_song_artists (song_id, artist_id) VALUES (", l.song_id, ", ", l.artist_id, ");") FROM l_song_artists l

SELECT CONCAT("INSERT INTO lss.s_song_genres (song_id, genre_id) VALUES (", lsg.song_id, ", ", lsg.genre_id, ");") FROM l_song_genre lsg




"""
BEGIN;

UPDATE lss.s_song_links
SET "type" = CASE
    -- anciens labels FR
    WHEN "type" = 'lien' THEN 'web'
    WHEN "type" = 'partition' THEN 'score'
    WHEN "type" = 'lien interne' THEN 'internal'
    WHEN "type" = 'YouTube' THEN 'youtube'
    WHEN "type" = 'audio' THEN 'audio'

    -- ancien type fusionné
    WHEN "type" = 'audio-video'
         AND (LOWER(link) LIKE '%youtube.com%' OR LOWER(link) LIKE '%youtu.be%')
      THEN 'youtube'
    WHEN "type" = 'audio-video'
      THEN 'audio'

    ELSE "type"
END
WHERE "type" IN ('lien', 'partition', 'YouTube', 'audio', 'lien interne', 'audio-video');

COMMIT;
"""
