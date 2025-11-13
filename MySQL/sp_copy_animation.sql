CREATE DEFINER=`root`@`localhost` PROCEDURE `carthographie`.`sp_copy_animation`(
    IN  p_original_animation_id MEDIUMINT,
    IN  p_new_date DATE,
    OUT p_new_animation_id MEDIUMINT)

BEGIN
	
	-- ------- --
	-- DECLARE --
	-- ------- --
	
	DECLARE v_new_animation_song_id MEDIUMINT;
	
	DECLARE v_done INT DEFAULT 0;
    DECLARE v_animation_song_id MEDIUMINT;
    DECLARE v_song_id MEDIUMINT;
    DECLARE v_num SMALLINT;
    DECLARE v_color_rgba VARCHAR(100);
    DECLARE v_bg_rgba VARCHAR(100);
    DECLARE v_font VARCHAR(50);
    DECLARE v_font_size TINYINT;
    DECLARE cur CURSOR FOR
        SELECT animation_song_id, song_id, num, color_rgba, bg_rgba, font, font_size
          FROM l_animation_song
        WHERE animation_id = p_original_animation_id;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;
	
    
    -- ---- --
    -- BODY --
    -- ---- --
    
    -- l_animations
	INSERT INTO l_animations (group_id, name, description, date, color_rgba, bg_rgba, font, font_size, padding)
	     SELECT group_id, CONCAT('[COPY] ',name), description, p_new_date, color_rgba, bg_rgba, font, font_size, padding
           FROM l_animations
          WHERE animation_id = p_original_animation_id;

	SET p_new_animation_id = LAST_INSERT_ID();
	
	
	-- l_animation_song
	OPEN cur;
    read_loop: LOOP
	    
        FETCH cur INTO v_animation_song_id, v_song_id, v_num, v_color_rgba, v_bg_rgba, v_font, v_font_size;
		IF v_done = 1 THEN
            LEAVE read_loop;
        END IF;

        INSERT INTO l_animation_song (animation_id, song_id, num, color_rgba, bg_rgba, font, font_size)
             VALUES (p_new_animation_id, v_song_id, v_num, v_color_rgba, v_bg_rgba, v_font, v_font_size);
         
        SET v_new_animation_song_id = LAST_INSERT_ID();
        
        INSERT INTO l_animation_song_verse
             SELECT v_new_animation_song_id, verse_id, selected, color_rgba, bg_rgba, font, font_size
               FROM l_animation_song_verse
              WHERE animation_song_id = v_animation_song_id;
        
    END LOOP;
    CLOSE cur;
	
	
    COMMIT;
    
END