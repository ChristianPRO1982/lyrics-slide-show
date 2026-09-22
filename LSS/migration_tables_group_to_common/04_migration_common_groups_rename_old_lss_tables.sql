-- Renommage des anciennes tables groupes du schema lss.
--
-- Objectif:
-- - rendre tout appel residuel vers lss.g_groups, lss.g_group_user ou
--   lss.g_group_user_ask_to_join explicitement visible par une erreur ;
-- - conserver les anciennes donnees temporairement ;
-- - ne supprimer aucune table.
--
-- Preconditions:
-- - les tables common sont hydratees ;
-- - les controles de 02_migration_common_groups_checks.sql sont OK ;
-- - les FKs de 03_migration_common_groups_foreign_keys.sql sont OK ;
-- - lss.a_animations.group_id ne pointe plus vers lss.g_groups.

-- 1. Controle avant renommage.
SELECT
  table_schema,
  table_name
FROM information_schema.tables
WHERE table_schema = 'lss'
  AND table_name IN (
    'g_groups',
    'g_group_user',
    'g_group_user_ask_to_join',
    'g_groups_old_before_common_migration',
    'g_group_user_old_before_common_migration',
    'g_group_user_ask_to_join_old_before_common_migration'
  )
ORDER BY table_name;

-- 2. Renommage des anciennes tables.
ALTER TABLE lss.g_group_user_ask_to_join
  RENAME TO g_group_user_ask_to_join_old_before_common_migration;

ALTER TABLE lss.g_group_user
  RENAME TO g_group_user_old_before_common_migration;

ALTER TABLE lss.g_groups
  RENAME TO g_groups_old_before_common_migration;

-- 3. Controle apres renommage.
-- Attendu:
-- - seules les tables *_old_before_common_migration doivent etre presentes ;
-- - les noms lss.g_groups, lss.g_group_user et
--   lss.g_group_user_ask_to_join ne doivent plus apparaitre.
SELECT
  table_schema,
  table_name
FROM information_schema.tables
WHERE table_schema = 'lss'
  AND table_name IN (
    'g_groups',
    'g_group_user',
    'g_group_user_ask_to_join',
    'g_groups_old_before_common_migration',
    'g_group_user_old_before_common_migration',
    'g_group_user_ask_to_join_old_before_common_migration'
  )
ORDER BY table_name;
