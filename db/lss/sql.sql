-- lss.site_params definition

-- Drop table

-- DROP TABLE lss.site_params;

CREATE TABLE lss.site_params (
	"language" varchar(2) NOT NULL,
	title varchar(100) NOT NULL,
	title_h1 varchar(255) NOT NULL,
	home_text text NOT NULL,
	bloc1_text text NOT NULL,
	bloc2_text text NOT NULL,
	verse_max_lines int4 NOT NULL,
	verse_max_characters_for_a_line int4 NOT NULL,
	chorus_prefix varchar(10) NOT NULL,
	verse_prefix1 varchar(10) NOT NULL,
	verse_prefix2 varchar(3) NOT NULL,
	admin_message text NOT NULL,
	moderator_message text NOT NULL,
	bg_img_max_bytes int4 DEFAULT 2097152 NOT NULL,
	bg_img_min_w int4 DEFAULT 800 NOT NULL,
	bg_img_min_h int4 DEFAULT 600 NOT NULL,
	bg_img_max_w int4 DEFAULT 4096 NOT NULL,
	bg_img_max_h int4 DEFAULT 3072 NOT NULL,
	bg_img_ratio_min numeric DEFAULT 1.3 NOT NULL,
	bg_img_ratio_max numeric DEFAULT 2.0 NOT NULL,
	bg_img_allowed_ext varchar(100) DEFAULT '.jpg,.jpeg,.png'::character varying NOT NULL,
	bg_img_allowed_mime varchar(100) DEFAULT 'image/jpeg,image/png'::character varying NOT NULL,
	CONSTRAINT site_params_pk PRIMARY KEY (language)
);


-- lss.users definition

-- Drop table

-- DROP TABLE lss.users;

CREATE TABLE lss.users (
	id uuid NOT NULL,
	theme varchar(100) DEFAULT '"normal.css"'::character varying NOT NULL,
	search_txt varchar(255) NULL,
	search_everywhere bool DEFAULT false NOT NULL,
	search_logic bool DEFAULT false NOT NULL,
	search_genres bool DEFAULT false NOT NULL,
	search_bands bool DEFAULT false NOT NULL,
	search_artists bool DEFAULT false NOT NULL,
	search_song_approved bool DEFAULT false NOT NULL,
	search_favorites bool DEFAULT false NOT NULL,
	CONSTRAINT users_pk PRIMARY KEY (id),
	CONSTRAINT users_users_fk FOREIGN KEY (id) REFERENCES users.users(id) ON DELETE CASCADE
);


-- lss.image_submissions definition

-- Drop table

-- DROP TABLE lss.image_submissions;

CREATE TABLE lss.image_submissions (
	image_id serial4 NOT NULL,
	stored_path varchar(255) NOT NULL,
	mime varchar(50) NOT NULL,
	size_bytes int4 NOT NULL,
	width int4 NOT NULL,
	height int4 NOT NULL,
	description varchar(200) NOT NULL,
	created_at timestamptz NOT NULL,
	status varchar(10) DEFAULT 'ACTIVED'::character varying NOT NULL,
	CONSTRAINT image_submissions_pk PRIMARY KEY (image_id)
);


-- lss.verse_prefixes definition

-- Drop table

-- DROP TABLE lss.verse_prefixes;

CREATE TABLE lss.verse_prefixes (
	prefix_id serial4 NOT NULL,
	prefix varchar(15) NOT NULL,
	"comment" varchar(100) NULL,
	CONSTRAINT verse_prefixes_pk PRIMARY KEY (prefix_id),
	CONSTRAINT verse_prefixes_unique UNIQUE (prefix)
);


----------------------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------------------


-- lss.songs definition

-- Drop table

-- DROP TABLE lss.songs;

CREATE TABLE lss.songs (
	song_id serial4 NOT NULL,
	title varchar(255) NOT NULL,
	sub_title varchar(255) NOT NULL,
	description text NULL,
	status int4 DEFAULT 0 NOT NULL,
	CONSTRAINT songs_pk PRIMARY KEY (song_id),
	CONSTRAINT songs_unique UNIQUE (title, sub_title)
);


-- lss.song_genre definition

-- Drop table

-- DROP TABLE lss.song_genre;

CREATE TABLE lss.song_genre (
	song_id int4 NOT NULL,
	genre_id int4 NOT NULL,
	CONSTRAINT song_genre_pk PRIMARY KEY (song_id, genre_id),
	CONSTRAINT song_genre_genres_fk FOREIGN KEY (genre_id) REFERENCES lss.genres(genre_id) ON DELETE CASCADE,
	CONSTRAINT song_genre_songs_fk FOREIGN KEY (song_id) REFERENCES lss.songs(song_id) ON DELETE CASCADE
);


-- lss.genres definition

-- Drop table

-- DROP TABLE lss.genres;

CREATE TABLE lss.genres (
	genre_id serial4 NOT NULL,
	"group" varchar(255) NOT NULL,
	"name" varchar(255) NOT NULL,
	CONSTRAINT genres_pk PRIMARY KEY (genre_id),
	CONSTRAINT genres_unique UNIQUE ("group", name)
);


-- lss.songs_mod_message definition

-- Drop table

-- DROP TABLE lss.songs_mod_message;

CREATE TABLE lss.songs_mod_message (
	message_id serial4 NOT NULL,
	song_id int4 NOT NULL,
	message text NULL,
	status int4 DEFAULT 0 NOT NULL,
	"date" timestamptz NOT NULL,
	CONSTRAINT songs_mod_message_pk PRIMARY KEY (message_id),
	CONSTRAINT songs_mod_message_songs_fk FOREIGN KEY (song_id) REFERENCES lss.songs(song_id) ON DELETE CASCADE
);
CREATE INDEX songs_mod_message_date_idx ON lss.songs_mod_message USING btree (date);
CREATE INDEX songs_mod_message_song_id_idx ON lss.songs_mod_message USING btree (song_id);
CREATE INDEX songs_mod_message_status_idx ON lss.songs_mod_message USING btree (status);


-- lss.song_artists definition

-- Drop table

-- DROP TABLE lss.song_artists;

CREATE TABLE lss.song_artists (
	song_id int4 NOT NULL,
	artist_id int4 NOT NULL,
	CONSTRAINT song_artists_pk PRIMARY KEY (song_id, artist_id),
	CONSTRAINT song_artists_artists_fk FOREIGN KEY (artist_id) REFERENCES common.artists(artist_id) ON DELETE CASCADE,
	CONSTRAINT song_artists_songs_fk FOREIGN KEY (song_id) REFERENCES lss.songs(song_id) ON DELETE CASCADE
);


-- lss.song_bands definition

-- Drop table

-- DROP TABLE lss.song_bands;

CREATE TABLE lss.song_bands (
	song_id int4 NOT NULL,
	band_id int4 NOT NULL,
	CONSTRAINT song_bands_pk PRIMARY KEY (song_id, band_id),
	CONSTRAINT song_bands_bands_fk FOREIGN KEY (band_id) REFERENCES common.bands(band_id) ON DELETE CASCADE,
	CONSTRAINT song_bands_songs_fk FOREIGN KEY (song_id) REFERENCES lss.songs(song_id) ON DELETE CASCADE
);


-- lss.song_link definition

-- Drop table

-- DROP TABLE lss.song_link;

CREATE TABLE lss.song_link (
	song_id int4 NOT NULL,
	link varchar(255) NOT NULL,
	CONSTRAINT song_link_pk PRIMARY KEY (song_id, link),
	CONSTRAINT song_link_songs_fk FOREIGN KEY (song_id) REFERENCES lss.songs(song_id) ON DELETE CASCADE
);
CREATE INDEX song_link_song_id_idx ON lss.song_link USING btree (song_id);


-- lss.song_favorite definition

-- Drop table

-- DROP TABLE lss.song_favorite;

CREATE TABLE lss.song_favorite (
	song_id int4 NOT NULL,
	user_id uuid NOT NULL,
	CONSTRAINT song_favorite_pk PRIMARY KEY (song_id, user_id),
	CONSTRAINT song_favorite_songs_fk FOREIGN KEY (song_id) REFERENCES lss.songs(song_id) ON DELETE CASCADE,
	CONSTRAINT song_favorite_users_fk FOREIGN KEY (user_id) REFERENCES users.users(id) ON DELETE CASCADE
);


-- lss.verses definition

-- Drop table

-- DROP TABLE lss.verses;

CREATE TABLE lss.verses (
	verse_id serial4 NOT NULL,
	song_id int4 NOT NULL,
	num int4 DEFAULT 1000 NOT NULL,
	num_verse int4 DEFAULT 1000 NOT NULL,
	chorus bool DEFAULT false NOT NULL,
	followed bool DEFAULT false NOT NULL,
	notcontinuenumbering bool DEFAULT false NOT NULL,
	"text" text NULL,
	prefix varchar(50) NULL,
	CONSTRAINT verses_pk PRIMARY KEY (verse_id),
	CONSTRAINT verses_songs_fk FOREIGN KEY (song_id) REFERENCES lss.songs(song_id) ON DELETE CASCADE
);
CREATE INDEX verses_chorus_idx ON lss.verses USING btree (chorus);
CREATE INDEX verses_num_idx ON lss.verses USING btree (num);
CREATE INDEX verses_song_id_idx ON lss.verses USING btree (song_id);


-- lss.animations definition

-- Drop table

-- DROP TABLE lss.animations;

CREATE TABLE lss.animations (
	animation_id serial4 NOT NULL,
	group_id int4 NOT NULL,
	"name" varchar(255) NOT NULL,
	description text NULL,
	"date" timestamptz NOT NULL,
	color_rgba varchar(100) DEFAULT 'rgba(127, 127, 127, 1)'::character varying NOT NULL,
	bg_rgba varchar(100) DEFAULT 'rgba(0, 0, 0, 1)'::character varying NOT NULL,
	font varchar(50) NULL,
	font_size int4 DEFAULT 50 NULL,
	padding int4 DEFAULT 50 NULL,
	CONSTRAINT animations_pk PRIMARY KEY (animation_id),
	CONSTRAINT animations_groups_fk FOREIGN KEY (group_id) REFERENCES common."groups"(group_id) ON DELETE CASCADE
);


-- lss.animation_song definition

-- Drop table

-- DROP TABLE lss.animation_song;

CREATE TABLE lss.animation_song (
	animation_song_id serial4 NOT NULL,
	animation_id int4 NOT NULL,
	song_id int4 NOT NULL,
	num int4 DEFAULT 1000 NOT NULL,
	color_rgba varchar(100) NULL,
	bg_rgba varchar(100) NULL,
	font varchar(50) NULL,
	font_size int4 DEFAULT 0 NOT NULL,
	CONSTRAINT animation_song_pk PRIMARY KEY (animation_song_id),
	CONSTRAINT animation_song_animations_fk FOREIGN KEY (animation_id) REFERENCES lss.animations(animation_id) ON DELETE CASCADE,
	CONSTRAINT animation_song_songs_fk FOREIGN KEY (song_id) REFERENCES lss.songs(song_id) ON DELETE CASCADE
);
CREATE INDEX animation_song_animation_id_idx ON lss.animation_song USING btree (animation_id);
CREATE INDEX animation_song_num_idx ON lss.animation_song USING btree (num);
CREATE INDEX animation_song_song_id_idx ON lss.animation_song USING btree (song_id);


-- lss.animation_song_verse definition

-- Drop table

-- DROP TABLE lss.animation_song_verse;

CREATE TABLE lss.animation_song_verse (
	animation_song_id int4 NOT NULL,
	verse_id int4 NOT NULL,
	selected bool DEFAULT true NOT NULL,
	color_rgba varchar(100) NULL,
	bg_rgba varchar(100) NULL,
	font varchar(50) NULL,
	font_size varchar DEFAULT false NOT NULL,
	CONSTRAINT l_animation_song_verse_unique UNIQUE (animation_song_id, verse_id),
	CONSTRAINT l_animation_song_verse_animation_song_fk FOREIGN KEY (animation_song_id) REFERENCES lss.animation_song(animation_song_id) ON DELETE CASCADE,
	CONSTRAINT l_animation_song_verse_verses_fk FOREIGN KEY (verse_id) REFERENCES lss.verses(verse_id) ON DELETE CASCADE
);
CREATE INDEX l_animation_song_verse_animation_song_id_idx ON lss.animation_song_verse USING btree (animation_song_id);
CREATE INDEX l_animation_song_verse_verse_id_idx ON lss.animation_song_verse USING btree (verse_id);