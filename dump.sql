-- carthographie.l_animation_song definition

CREATE TABLE `l_animation_song` (
  `animation_song_id` mediumint NOT NULL AUTO_INCREMENT,
  `animation_id` mediumint NOT NULL,
  `song_id` mediumint NOT NULL,
  `num` smallint NOT NULL DEFAULT '1000',
  `verses` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`animation_song_id`),
  KEY `l_animation_song_l_animations_FK` (`animation_id`),
  KEY `l_animation_song_num_IDX` (`num`) USING BTREE,
  KEY `l_animation_song_l_songs_FK` (`song_id`),
  CONSTRAINT `l_animation_song_l_animations_FK` FOREIGN KEY (`animation_id`) REFERENCES `l_animations` (`animation_id`) ON DELETE CASCADE,
  CONSTRAINT `l_animation_song_l_songs_FK` FOREIGN KEY (`song_id`) REFERENCES `l_songs` (`song_id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- carthographie.l_animations definition

CREATE TABLE `l_animations` (
  `animation_id` mediumint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `date` date NOT NULL,
  PRIMARY KEY (`animation_id`),
  KEY `l_animations_date_IDX` (`date`,`name`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- carthographie.l_songs definition

CREATE TABLE `l_songs` (
  `song_id` mediumint NOT NULL AUTO_INCREMENT,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sub_title` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `artist` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`song_id`),
  KEY `l_songs_title_IDX` (`title`,`sub_title`,`artist`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- carthographie.l_verses definition

CREATE TABLE `l_verses` (
  `verse_id` mediumint NOT NULL AUTO_INCREMENT,
  `song_id` mediumint NOT NULL,
  `num` smallint NOT NULL DEFAULT '1000',
  `num_verse` smallint NOT NULL DEFAULT '1000',
  `chorus` tinyint(1) NOT NULL DEFAULT '0',
  `followed` tinyint(1) NOT NULL DEFAULT '0',
  `text` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`verse_id`),
  KEY `l_verses_song_id_IDX` (`song_id`) USING BTREE,
  KEY `l_verses_num_IDX` (`num`) USING BTREE,
  KEY `l_verses_chorus_IDX` (`chorus`) USING BTREE,
  CONSTRAINT `l_verses_l_songs_FK` FOREIGN KEY (`song_id`) REFERENCES `l_songs` (`song_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE DEFINER=`root`@`localhost` TRIGGER `before_update_l_verses` BEFORE UPDATE ON `l_verses` FOR EACH ROW BEGIN
    IF NEW.chorus = TRUE THEN
        SET NEW.followed = FALSE;
    END IF;
END