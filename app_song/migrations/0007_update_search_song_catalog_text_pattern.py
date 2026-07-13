from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app_song", "0006_create_search_song_catalog_function"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION lss.search_song_catalog(
                    p_is_authenticated boolean,
                    p_member_id uuid,
                    p_text text,
                    p_everywhere boolean,
                    p_match_all_selected_refs boolean,
                    p_genre_ids integer[],
                    p_band_ids integer[],
                    p_artist_ids integer[],
                    p_validation text,
                    p_favorites_only boolean
                )
                RETURNS TABLE(
                    song_id integer,
                    title text,
                    subtitle text,
                    description text,
                    status integer,
                    licensed boolean,
                    is_favorite boolean,
                    search_count bigint,
                    catalog_count bigint
                )
                LANGUAGE SQL
                STABLE
                AS $$
                    WITH raw_params AS (
                        SELECT
                            COALESCE(p_is_authenticated, FALSE) AS is_authenticated,
                            p_member_id AS member_id,
                            regexp_replace(
                                trim(lower(unaccent(COALESCE(p_text, '')))),
                                '[[:space:]]+',
                                ' ',
                                'g'
                            ) AS normalized_text,
                            COALESCE(p_everywhere, FALSE) AS everywhere,
                            COALESCE(p_match_all_selected_refs, FALSE) AS match_all_selected_refs,
                            COALESCE(p_genre_ids, ARRAY[]::integer[]) AS genre_ids,
                            COALESCE(p_band_ids, ARRAY[]::integer[]) AS band_ids,
                            COALESCE(p_artist_ids, ARRAY[]::integer[]) AS artist_ids,
                            CASE
                                WHEN p_validation IN ('all', 'validated_only', 'non_validated_only')
                                    THEN p_validation
                                ELSE 'all'
                            END AS validation,
                            (COALESCE(p_favorites_only, FALSE) AND p_member_id IS NOT NULL) AS favorites_only
                    ),
                    normalized_params AS (
                        SELECT
                            is_authenticated,
                            member_id,
                            normalized_text,
                            replace(normalized_text, ' ', '%') AS normalized_pattern,
                            everywhere,
                            match_all_selected_refs,
                            genre_ids,
                            band_ids,
                            artist_ids,
                            validation,
                            favorites_only
                        FROM raw_params
                    ),
                    accessible_songs AS (
                        SELECT
                            s.song_id,
                            s.title,
                            s.sub_title AS subtitle,
                            s.description,
                            s.status,
                            s.licensed
                        FROM "lss"."s_songs" AS s
                        CROSS JOIN normalized_params AS np
                        WHERE np.is_authenticated OR s.licensed = FALSE
                    ),
                    filtered_songs AS (
                        SELECT
                            s.song_id,
                            s.title,
                            s.subtitle,
                            s.description,
                            s.status,
                            s.licensed,
                            EXISTS (
                                SELECT 1
                                FROM "lss"."m_songs_users" AS favorites
                                CROSS JOIN normalized_params AS np
                                WHERE favorites.song_id = s.song_id
                                  AND favorites.user_id = np.member_id
                            ) AS is_favorite
                        FROM accessible_songs AS s
                        CROSS JOIN normalized_params AS np
                        WHERE (
                            np.normalized_text = ''
                            OR lower(unaccent(COALESCE(s.title, ''))) LIKE '%%' || np.normalized_pattern || '%%'
                            OR lower(unaccent(COALESCE(s.subtitle, ''))) LIKE '%%' || np.normalized_pattern || '%%'
                            OR (
                                np.everywhere
                                AND (
                                    lower(unaccent(COALESCE(s.description, ''))) LIKE '%%' || np.normalized_pattern || '%%'
                                    OR EXISTS (
                                        SELECT 1
                                        FROM "lss"."s_verses" AS verses
                                        WHERE verses.song_id = s.song_id
                                          AND lower(unaccent(COALESCE(verses.text, ''))) LIKE '%%' || np.normalized_pattern || '%%'
                                    )
                                )
                            )
                        )
                          AND (
                              np.validation = 'all'
                              OR (np.validation = 'validated_only' AND s.status IN (1, 2))
                              OR (np.validation = 'non_validated_only' AND s.status = 0)
                          )
                          AND (
                              COALESCE(array_length(np.genre_ids, 1), 0) = 0
                              OR (
                                  NOT np.match_all_selected_refs
                                  AND EXISTS (
                                      SELECT 1
                                      FROM "lss"."s_song_genres" AS song_genres
                                      WHERE song_genres.song_id = s.song_id
                                        AND song_genres.genre_id = ANY(np.genre_ids)
                                  )
                              )
                              OR (
                                  np.match_all_selected_refs
                                  AND NOT EXISTS (
                                      SELECT 1
                                      FROM unnest(np.genre_ids) AS required_genre_id
                                      WHERE NOT EXISTS (
                                          SELECT 1
                                          FROM "lss"."s_song_genres" AS song_genres
                                          WHERE song_genres.song_id = s.song_id
                                            AND song_genres.genre_id = required_genre_id
                                      )
                                  )
                              )
                          )
                          AND (
                              COALESCE(array_length(np.band_ids, 1), 0) = 0
                              OR (
                                  NOT np.match_all_selected_refs
                                  AND EXISTS (
                                      SELECT 1
                                      FROM "lss"."s_song_bands" AS song_bands
                                      WHERE song_bands.song_id = s.song_id
                                        AND song_bands.band_id = ANY(np.band_ids)
                                  )
                              )
                              OR (
                                  np.match_all_selected_refs
                                  AND NOT EXISTS (
                                      SELECT 1
                                      FROM unnest(np.band_ids) AS required_band_id
                                      WHERE NOT EXISTS (
                                          SELECT 1
                                          FROM "lss"."s_song_bands" AS song_bands
                                          WHERE song_bands.song_id = s.song_id
                                            AND song_bands.band_id = required_band_id
                                      )
                                  )
                              )
                          )
                          AND (
                              COALESCE(array_length(np.artist_ids, 1), 0) = 0
                              OR (
                                  NOT np.match_all_selected_refs
                                  AND EXISTS (
                                      SELECT 1
                                      FROM "lss"."s_song_artists" AS song_artists
                                      WHERE song_artists.song_id = s.song_id
                                        AND song_artists.artist_id = ANY(np.artist_ids)
                                  )
                              )
                              OR (
                                  np.match_all_selected_refs
                                  AND NOT EXISTS (
                                      SELECT 1
                                      FROM unnest(np.artist_ids) AS required_artist_id
                                      WHERE NOT EXISTS (
                                          SELECT 1
                                          FROM "lss"."s_song_artists" AS song_artists
                                          WHERE song_artists.song_id = s.song_id
                                            AND song_artists.artist_id = required_artist_id
                                      )
                                  )
                              )
                          )
                          AND (
                              NOT np.favorites_only
                              OR EXISTS (
                                  SELECT 1
                                  FROM "lss"."m_songs_users" AS favorites
                                  WHERE favorites.song_id = s.song_id
                                    AND favorites.user_id = np.member_id
                              )
                          )
                    ),
                    counts AS (
                        SELECT
                            (SELECT COUNT(*) FROM filtered_songs) AS search_count,
                            (SELECT COUNT(*) FROM accessible_songs) AS catalog_count
                    ),
                    ordered_songs AS (
                        SELECT
                            song_id,
                            title,
                            subtitle,
                            description,
                            status,
                            licensed,
                            is_favorite
                        FROM filtered_songs
                        ORDER BY title, subtitle
                    )
                    SELECT
                        ordered_songs.song_id,
                        ordered_songs.title,
                        ordered_songs.subtitle,
                        ordered_songs.description,
                        ordered_songs.status,
                        ordered_songs.licensed,
                        COALESCE(ordered_songs.is_favorite, FALSE) AS is_favorite,
                        counts.search_count,
                        counts.catalog_count
                    FROM counts
                    LEFT JOIN LATERAL (
                        SELECT
                            song_id,
                            title,
                            subtitle,
                            description,
                            status,
                            licensed,
                            is_favorite
                        FROM ordered_songs
                    ) AS ordered_songs ON TRUE
                    ORDER BY ordered_songs.title NULLS LAST, ordered_songs.subtitle NULLS LAST;
                $$;
            """,
            reverse_sql="""
                CREATE OR REPLACE FUNCTION lss.search_song_catalog(
                    p_is_authenticated boolean,
                    p_member_id uuid,
                    p_text text,
                    p_everywhere boolean,
                    p_match_all_selected_refs boolean,
                    p_genre_ids integer[],
                    p_band_ids integer[],
                    p_artist_ids integer[],
                    p_validation text,
                    p_favorites_only boolean
                )
                RETURNS TABLE(
                    song_id integer,
                    title text,
                    subtitle text,
                    description text,
                    status integer,
                    licensed boolean,
                    is_favorite boolean,
                    search_count bigint,
                    catalog_count bigint
                )
                LANGUAGE SQL
                STABLE
                AS $$
                    WITH normalized_params AS (
                        SELECT
                            COALESCE(p_is_authenticated, FALSE) AS is_authenticated,
                            p_member_id AS member_id,
                            lower(unaccent(COALESCE(p_text, ''))) AS normalized_text,
                            COALESCE(p_everywhere, FALSE) AS everywhere,
                            COALESCE(p_match_all_selected_refs, FALSE) AS match_all_selected_refs,
                            COALESCE(p_genre_ids, ARRAY[]::integer[]) AS genre_ids,
                            COALESCE(p_band_ids, ARRAY[]::integer[]) AS band_ids,
                            COALESCE(p_artist_ids, ARRAY[]::integer[]) AS artist_ids,
                            CASE
                                WHEN p_validation IN ('all', 'validated_only', 'non_validated_only')
                                    THEN p_validation
                                ELSE 'all'
                            END AS validation,
                            (COALESCE(p_favorites_only, FALSE) AND p_member_id IS NOT NULL) AS favorites_only
                    ),
                    accessible_songs AS (
                        SELECT
                            s.song_id,
                            s.title,
                            s.sub_title AS subtitle,
                            s.description,
                            s.status,
                            s.licensed
                        FROM "lss"."s_songs" AS s
                        CROSS JOIN normalized_params AS np
                        WHERE np.is_authenticated OR s.licensed = FALSE
                    ),
                    filtered_songs AS (
                        SELECT
                            s.song_id,
                            s.title,
                            s.subtitle,
                            s.description,
                            s.status,
                            s.licensed,
                            EXISTS (
                                SELECT 1
                                FROM "lss"."m_songs_users" AS favorites
                                CROSS JOIN normalized_params AS np
                                WHERE favorites.song_id = s.song_id
                                  AND favorites.user_id = np.member_id
                            ) AS is_favorite
                        FROM accessible_songs AS s
                        CROSS JOIN normalized_params AS np
                        WHERE (
                            np.normalized_text = ''
                            OR lower(unaccent(COALESCE(s.title, ''))) LIKE '%%' || np.normalized_text || '%%'
                            OR lower(unaccent(COALESCE(s.subtitle, ''))) LIKE '%%' || np.normalized_text || '%%'
                            OR (
                                np.everywhere
                                AND (
                                    lower(unaccent(COALESCE(s.description, ''))) LIKE '%%' || np.normalized_text || '%%'
                                    OR EXISTS (
                                        SELECT 1
                                        FROM "lss"."s_verses" AS verses
                                        WHERE verses.song_id = s.song_id
                                          AND lower(unaccent(COALESCE(verses.text, ''))) LIKE '%%' || np.normalized_text || '%%'
                                    )
                                )
                            )
                        )
                          AND (
                              np.validation = 'all'
                              OR (np.validation = 'validated_only' AND s.status IN (1, 2))
                              OR (np.validation = 'non_validated_only' AND s.status = 0)
                          )
                          AND (
                              COALESCE(array_length(np.genre_ids, 1), 0) = 0
                              OR (
                                  NOT np.match_all_selected_refs
                                  AND EXISTS (
                                      SELECT 1
                                      FROM "lss"."s_song_genres" AS song_genres
                                      WHERE song_genres.song_id = s.song_id
                                        AND song_genres.genre_id = ANY(np.genre_ids)
                                  )
                              )
                              OR (
                                  np.match_all_selected_refs
                                  AND NOT EXISTS (
                                      SELECT 1
                                      FROM unnest(np.genre_ids) AS required_genre_id
                                      WHERE NOT EXISTS (
                                          SELECT 1
                                          FROM "lss"."s_song_genres" AS song_genres
                                          WHERE song_genres.song_id = s.song_id
                                            AND song_genres.genre_id = required_genre_id
                                      )
                                  )
                              )
                          )
                          AND (
                              COALESCE(array_length(np.band_ids, 1), 0) = 0
                              OR (
                                  NOT np.match_all_selected_refs
                                  AND EXISTS (
                                      SELECT 1
                                      FROM "lss"."s_song_bands" AS song_bands
                                      WHERE song_bands.song_id = s.song_id
                                        AND song_bands.band_id = ANY(np.band_ids)
                                  )
                              )
                              OR (
                                  np.match_all_selected_refs
                                  AND NOT EXISTS (
                                      SELECT 1
                                      FROM unnest(np.band_ids) AS required_band_id
                                      WHERE NOT EXISTS (
                                          SELECT 1
                                          FROM "lss"."s_song_bands" AS song_bands
                                          WHERE song_bands.song_id = s.song_id
                                            AND song_bands.band_id = required_band_id
                                      )
                                  )
                              )
                          )
                          AND (
                              COALESCE(array_length(np.artist_ids, 1), 0) = 0
                              OR (
                                  NOT np.match_all_selected_refs
                                  AND EXISTS (
                                      SELECT 1
                                      FROM "lss"."s_song_artists" AS song_artists
                                      WHERE song_artists.song_id = s.song_id
                                        AND song_artists.artist_id = ANY(np.artist_ids)
                                  )
                              )
                              OR (
                                  np.match_all_selected_refs
                                  AND NOT EXISTS (
                                      SELECT 1
                                      FROM unnest(np.artist_ids) AS required_artist_id
                                      WHERE NOT EXISTS (
                                          SELECT 1
                                          FROM "lss"."s_song_artists" AS song_artists
                                          WHERE song_artists.song_id = s.song_id
                                            AND song_artists.artist_id = required_artist_id
                                      )
                                  )
                              )
                          )
                          AND (
                              NOT np.favorites_only
                              OR EXISTS (
                                  SELECT 1
                                  FROM "lss"."m_songs_users" AS favorites
                                  WHERE favorites.song_id = s.song_id
                                    AND favorites.user_id = np.member_id
                              )
                          )
                    ),
                    counts AS (
                        SELECT
                            (SELECT COUNT(*) FROM filtered_songs) AS search_count,
                            (SELECT COUNT(*) FROM accessible_songs) AS catalog_count
                    ),
                    ordered_songs AS (
                        SELECT
                            song_id,
                            title,
                            subtitle,
                            description,
                            status,
                            licensed,
                            is_favorite
                        FROM filtered_songs
                        ORDER BY title, subtitle
                    )
                    SELECT
                        ordered_songs.song_id,
                        ordered_songs.title,
                        ordered_songs.subtitle,
                        ordered_songs.description,
                        ordered_songs.status,
                        ordered_songs.licensed,
                        COALESCE(ordered_songs.is_favorite, FALSE) AS is_favorite,
                        counts.search_count,
                        counts.catalog_count
                    FROM counts
                    LEFT JOIN LATERAL (
                        SELECT
                            song_id,
                            title,
                            subtitle,
                            description,
                            status,
                            licensed,
                            is_favorite
                        FROM ordered_songs
                    ) AS ordered_songs ON TRUE
                    ORDER BY ordered_songs.title NULLS LAST, ordered_songs.subtitle NULLS LAST;
                $$;
            """,
        ),
    ]
