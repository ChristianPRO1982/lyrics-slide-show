-- Ajout manuel des cles etrangeres liees aux groupes communs.
--
-- Important:
-- - lancer ces requetes une par une ;
-- - si la session SQL affiche "current transaction is aborted", lancer d'abord:
--   ROLLBACK;
-- - ne pas lancer ce fichier comme une transaction unique ;
-- - les controles de 02_migration_common_groups_checks.sql doivent etre OK avant.

-- 0. Reinitialiser la session si une precedente erreur a laisse une transaction
-- ouverte et avortee.
-- ROLLBACK;

-- 1. Verifier les contraintes deja presentes.
SELECT
  conrelid::regclass AS table_name,
  conname AS constraint_name,
  confrelid::regclass AS referenced_table,
  convalidated AS validated
FROM pg_constraint
WHERE contype = 'f'
  AND conrelid IN (
    'common.g_group_user'::regclass,
    'common.g_group_user_ask_to_join'::regclass,
    'lss.a_animations'::regclass
  )
ORDER BY conrelid::regclass::text, conname;

-- 2. Ajouter les FKs common.g_group_user.
-- Si la contrainte existe deja, PostgreSQL renverra une erreur "already exists";
-- dans ce cas, passer simplement a la requete VALIDATE correspondante.
ALTER TABLE common.g_group_user
  ADD CONSTRAINT g_group_user_group_fk
  FOREIGN KEY (group_id)
  REFERENCES common.g_groups (group_id)
  ON DELETE CASCADE
  NOT VALID;

ALTER TABLE common.g_group_user
  VALIDATE CONSTRAINT g_group_user_group_fk;

ALTER TABLE common.g_group_user
  ADD CONSTRAINT g_group_user_member_fk
  FOREIGN KEY (member_id)
  REFERENCES users.users (id)
  ON DELETE CASCADE
  NOT VALID;

ALTER TABLE common.g_group_user
  VALIDATE CONSTRAINT g_group_user_member_fk;

-- 3. Ajouter les FKs common.g_group_user_ask_to_join.
-- Meme regle: si la contrainte existe deja, passer a la requete VALIDATE.
ALTER TABLE common.g_group_user_ask_to_join
  ADD CONSTRAINT g_group_user_ask_to_join_group_fk
  FOREIGN KEY (group_id)
  REFERENCES common.g_groups (group_id)
  ON DELETE CASCADE
  NOT VALID;

ALTER TABLE common.g_group_user_ask_to_join
  VALIDATE CONSTRAINT g_group_user_ask_to_join_group_fk;

ALTER TABLE common.g_group_user_ask_to_join
  ADD CONSTRAINT g_group_user_ask_to_join_member_fk
  FOREIGN KEY (member_id)
  REFERENCES users.users (id)
  ON DELETE CASCADE
  NOT VALID;

ALTER TABLE common.g_group_user_ask_to_join
  VALIDATE CONSTRAINT g_group_user_ask_to_join_member_fk;

-- 4. Identifier l'ancienne FK de lss.a_animations(group_id).
-- Copier le constraint_name retourne par cette requete dans la requete DROP
-- juste en dessous. Si aucune ligne n'est retournee, passer directement a
-- l'ajout de a_animations_group_common_fk.
SELECT
  tc.constraint_name,
  ccu.table_schema AS referenced_schema,
  ccu.table_name AS referenced_table,
  ccu.column_name AS referenced_column
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON kcu.constraint_schema = tc.constraint_schema
 AND kcu.constraint_name = tc.constraint_name
 AND kcu.table_schema = tc.table_schema
 AND kcu.table_name = tc.table_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_schema = tc.constraint_schema
 AND ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'lss'
  AND tc.table_name = 'a_animations'
  AND kcu.column_name = 'group_id';

-- 5. Supprimer l'ancienne FK de lss.a_animations(group_id), si elle existe.
-- Remplacer <constraint_name> par le nom retourne a l'etape 4.
-- Ne pas lancer cette requete telle quelle.
-- ALTER TABLE lss.a_animations DROP CONSTRAINT <constraint_name>;
--
-- Nom observe pendant la migration LSS actuelle :
-- ALTER TABLE lss.a_animations
--   DROP CONSTRAINT a_animations_group_id_2fbc45cf_fk_g_groups_group_id;

-- 6. Ajouter la nouvelle FK de lss.a_animations vers common.g_groups.
-- Si elle existe deja, passer a la requete VALIDATE.
ALTER TABLE lss.a_animations
  ADD CONSTRAINT a_animations_group_common_fk
  FOREIGN KEY (group_id)
  REFERENCES common.g_groups (group_id)
  ON DELETE CASCADE
  NOT VALID;

ALTER TABLE lss.a_animations
  VALIDATE CONSTRAINT a_animations_group_common_fk;

-- 7. Verification finale des FKs attendues.
-- Attendu:
-- - 2 FKs sur common.g_group_user ;
-- - 2 FKs sur common.g_group_user_ask_to_join ;
-- - 1 FK lss.a_animations.group_id vers common.g_groups.
SELECT
  tc.table_schema,
  tc.table_name,
  tc.constraint_name,
  kcu.column_name,
  ccu.table_schema AS referenced_schema,
  ccu.table_name AS referenced_table,
  ccu.column_name AS referenced_column
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON kcu.constraint_schema = tc.constraint_schema
 AND kcu.constraint_name = tc.constraint_name
 AND kcu.table_schema = tc.table_schema
 AND kcu.table_name = tc.table_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_schema = tc.constraint_schema
 AND ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND (
    (tc.table_schema = 'common'
     AND tc.table_name IN ('g_group_user', 'g_group_user_ask_to_join'))
    OR (tc.table_schema = 'lss'
        AND tc.table_name = 'a_animations'
        AND kcu.column_name = 'group_id')
  )
ORDER BY tc.table_schema, tc.table_name, tc.constraint_name, kcu.column_name;
