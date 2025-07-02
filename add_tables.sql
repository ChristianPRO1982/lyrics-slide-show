-------------------
-- CARTHOGRAPHIE --
-------------------

CREATE TABLE `c_groups` (
  `group_id` mediumint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `info` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `token` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `private` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`group_id`),
  UNIQUE KEY `c_groups_unique` (`name`),
  KEY `c_groups_private_key_IDX` (`token`) USING BTREE,
  KEY `c_groups_private_IDX` (`private`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=36 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `c_users` (
  `id` mediumint NOT NULL AUTO_INCREMENT,
  `username` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `theme` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'normal.css',
  `search_txt` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `search_everywhere` tinyint(1) NOT NULL DEFAULT '0',
  `search_logic` tinyint(1) NOT NULL DEFAULT '0',
  `search_genres` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `search_song_approved` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `c_users_auth_user_FK` (`username`),
  CONSTRAINT `c_users_auth_user_FK` FOREIGN KEY (`username`) REFERENCES `auth_user` (`username`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `c_group_user` (
  `group_id` mediumint NOT NULL,
  `username` varchar(150) COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `admin` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`group_id`,`username`),
  KEY `c_group_user_admin_IDX` (`admin`) USING BTREE,
  KEY `c_group_user_auth_user_FK` (`username`),
  CONSTRAINT `c_group_user_auth_user_FK` FOREIGN KEY (`username`) REFERENCES `auth_user` (`username`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `c_group_user_c_groups_FK` FOREIGN KEY (`group_id`) REFERENCES `c_groups` (`group_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-----------------------
-- LYRICS SLIDE SHOW --
-----------------------

CREATE TABLE `l_genres` (
  `genre_id` mediumint NOT NULL AUTO_INCREMENT,
  `group` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`genre_id`),
  UNIQUE KEY `l_genres_unique` (`group`,`name`)
) ENGINE=InnoDB AUTO_INCREMENT=68 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_songs` (
  `song_id` mediumint NOT NULL AUTO_INCREMENT,
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `sub_title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `artist` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` smallint NOT NULL DEFAULT '0',
  PRIMARY KEY (`song_id`),
  UNIQUE KEY `l_songs_unique` (`title`,`sub_title`),
  KEY `l_songs_title_IDX` (`title`,`sub_title`,`artist`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=10091 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_song_genre` (
  `song_id` mediumint NOT NULL,
  `genre_id` mediumint NOT NULL,
  PRIMARY KEY (`song_id`,`genre_id`),
  KEY `l_song_genre_l_genre_FK` (`genre_id`),
  CONSTRAINT `l_song_genre_l_genre_FK` FOREIGN KEY (`genre_id`) REFERENCES `l_genres` (`genre_id`) ON DELETE CASCADE,
  CONSTRAINT `l_song_genre_l_songs_FK` FOREIGN KEY (`song_id`) REFERENCES `l_songs` (`song_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_song_link` (
  `song_id` mediumint NOT NULL,
  `link` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`song_id`,`link`),
  KEY `l_song_link_song_id_IDX` (`song_id`) USING BTREE,
  CONSTRAINT `l_song_link_l_songs_FK` FOREIGN KEY (`song_id`) REFERENCES `l_songs` (`song_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_songs_mod_message` (
  `message_id` mediumint NOT NULL AUTO_INCREMENT,
  `song_id` mediumint NOT NULL,
  `message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` smallint NOT NULL DEFAULT '0',
  `date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`message_id`),
  KEY `l_songs_mod_message_l_songs_FK` (`song_id`),
  KEY `l_songs_mod_message_status_IDX` (`status`) USING BTREE,
  KEY `l_songs_mod_message_date_IDX` (`date`) USING BTREE,
  CONSTRAINT `l_songs_mod_message_l_songs_FK` FOREIGN KEY (`song_id`) REFERENCES `l_songs` (`song_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_verses` (
  `verse_id` mediumint NOT NULL AUTO_INCREMENT,
  `song_id` mediumint NOT NULL,
  `num` smallint NOT NULL DEFAULT '1000',
  `num_verse` smallint NOT NULL DEFAULT '1000',
  `chorus` tinyint(1) NOT NULL DEFAULT '0',
  `followed` tinyint(1) NOT NULL DEFAULT '0',
  `notcontinuenumbering` tinyint(1) NOT NULL DEFAULT '0',
  `text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `prefix` varchar(15) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`verse_id`),
  KEY `l_verses_song_id_IDX` (`song_id`) USING BTREE,
  KEY `l_verses_num_IDX` (`num`) USING BTREE,
  KEY `l_verses_chorus_IDX` (`chorus`) USING BTREE,
  CONSTRAINT `l_verses_l_songs_FK` FOREIGN KEY (`song_id`) REFERENCES `l_songs` (`song_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=40616 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_animations` (
  `animation_id` mediumint NOT NULL AUTO_INCREMENT,
  `group_id` mediumint DEFAULT NULL,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `date` date NOT NULL,
  `color_rgba` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'rgba(127, 127, 127, 1)',
  `bg_rgba` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'rgba(0, 0, 0, 1)',
  `font` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `font_size` tinyint NOT NULL DEFAULT '50',
  `padding` tinyint NOT NULL DEFAULT '50',
  PRIMARY KEY (`animation_id`),
  KEY `l_animations_date_IDX` (`date`,`name`) USING BTREE,
  KEY `l_animations_c_groups_FK` (`group_id`),
  CONSTRAINT `l_animations_c_groups_FK` FOREIGN KEY (`group_id`) REFERENCES `c_groups` (`group_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_animation_song` (
  `animation_song_id` mediumint NOT NULL AUTO_INCREMENT,
  `animation_id` mediumint NOT NULL,
  `song_id` mediumint NOT NULL,
  `num` smallint NOT NULL DEFAULT '1000',
  `color_rgba` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `bg_rgba` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `font` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `font_size` tinyint NOT NULL DEFAULT '0',
  PRIMARY KEY (`animation_song_id`),
  KEY `l_animation_song_l_animations_FK` (`animation_id`),
  KEY `l_animation_song_num_IDX` (`num`) USING BTREE,
  KEY `l_animation_song_l_songs_FK` (`song_id`),
  CONSTRAINT `l_animation_song_l_animations_FK` FOREIGN KEY (`animation_id`) REFERENCES `l_animations` (`animation_id`) ON DELETE CASCADE,
  CONSTRAINT `l_animation_song_l_songs_FK` FOREIGN KEY (`song_id`) REFERENCES `l_songs` (`song_id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=63 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_animation_song_verse` (
  `animation_song_id` mediumint NOT NULL,
  `verse_id` mediumint NOT NULL,
  `selected` tinyint(1) NOT NULL DEFAULT '1',
  `color_rgba` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `bg_rgba` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `font` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `font_size` tinyint NOT NULL DEFAULT '0',
  PRIMARY KEY (`animation_song_id`,`verse_id`),
  KEY `l_animation_song_verse_l_verses_FK` (`verse_id`),
  KEY `l_animation_song_verse_animation_song_id_IDX` (`animation_song_id`) USING BTREE,
  CONSTRAINT `l_animation_song_verse_l_animation_song_FK` FOREIGN KEY (`animation_song_id`) REFERENCES `l_animation_song` (`animation_song_id`) ON DELETE CASCADE,
  CONSTRAINT `l_animation_song_verse_l_verses_FK` FOREIGN KEY (`verse_id`) REFERENCES `l_verses` (`verse_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `c_group_user_ask_to_join` (
  `group_id` mediumint NOT NULL,
  `username` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`group_id`,`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_site` (
  `language` varchar(2) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `title_h1` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `home_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `bloc1_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `bloc2_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`language`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_site_params` (
  `verse_max_lines` tinyint NOT NULL,
  `verse_max_characters_for_a_line` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_verse_prefixes` (
  `prefix_id` mediumint NOT NULL AUTO_INCREMENT,
  `prefix` varchar(15) COLLATE utf8mb4_unicode_ci NOT NULL,
  `comment` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`prefix_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `c_bands` (
  `band_id` mediumint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`band_id`),
  UNIQUE KEY `c_bands_unique` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `c_band_links` (
  `band_id` mediumint NOT NULL,
  `link` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`band_id`,`link`),
  CONSTRAINT `c_band_links_c_bands_FK` FOREIGN KEY (`band_id`) REFERENCES `c_bands` (`band_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `c_artists` (
  `artist_id` mediumint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`artist_id`),
  UNIQUE KEY `c_artist_unique` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `c_artist_links` (
  `artist_id` mediumint NOT NULL,
  `link` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`artist_id`,`link`),
  CONSTRAINT `c_artist_links_c_artists_FK` FOREIGN KEY (`artist_id`) REFERENCES `c_artists` (`artist_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_song_bands` (
  `song_id` mediumint NOT NULL,
  `band_id` mediumint NOT NULL,
  PRIMARY KEY (`song_id`,`band_id`),
  KEY `l_song_bands_c_bands_FK` (`band_id`),
  CONSTRAINT `l_song_bands_c_bands_FK` FOREIGN KEY (`band_id`) REFERENCES `c_bands` (`band_id`) ON DELETE CASCADE,
  CONSTRAINT `l_song_bands_l_songs_FK` FOREIGN KEY (`song_id`) REFERENCES `l_songs` (`song_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `l_song_artist` (
  `song_id` mediumint NOT NULL,
  `artist_id` mediumint NOT NULL,
  PRIMARY KEY (`song_id`,`artist_id`),
  KEY `l_song_artist_c_artists_FK` (`artist_id`),
  CONSTRAINT `l_song_artist_c_artists_FK` FOREIGN KEY (`artist_id`) REFERENCES `c_artists` (`artist_id`) ON DELETE CASCADE,
  CONSTRAINT `l_song_artist_l_songs_FK` FOREIGN KEY (`song_id`) REFERENCES `l_songs` (`song_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;