SELECT CONCAT("INSERT INTO common.artists VALUES (", artist_id, ", '", REPLACE(name, '''', ''''''), "');") FROM c_artists c;

SELECT CONCAT("INSERT INTO common.bands VALUES (", band_id, ", '", REPLACE(name, '''', ''''''), "');") FROM c_bands

SELECT CONCAT("INSERT INTO common.genres VALUES (", genre_id, ", '", REPLACE(l.group, '''', ''''''), "', '", REPLACE(l.group, '''', ''''''), "');") FROM  l_genres l

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