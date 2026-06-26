# LSS — Règles métier de nommage des images de fond

## 1. Objectif

Implémenter une convention cohérente pour les images de fond téléversées par les utilisateurs dans Lyrics Slide Show.

Deux notions doivent être strictement séparées :

1. **Le nom technique du fichier**, utilisé pour le stockage.
2. **Le nom humain**, affiché dans l’interface utilisateur.

Ces deux noms ne répondent pas aux mêmes règles et ne doivent pas être confondus.

---

## 2. Périmètre

Cette spécification concerne :

- les images de fond téléversées par les utilisateurs ;
- les genres associés à ces images ;
- la génération du nom technique du fichier ;
- la génération du nom humain affiché dans l’interface ;
- les règles de recalcul du nom humain lorsque les genres changent.

Cette spécification ne définit pas :

- les règles de redimensionnement des images ;
- les formats d’image autorisés ;
- la compression ;
- la gestion des droits d’accès ;
- le stockage physique local ou objet ;
- la suppression des fichiers.

---

## 3. Modèle métier existant

Une image peut être associée à zéro, un ou plusieurs genres.

Un genre possède au minimum les champs suivants :

- `group`
- `name`

Exemple :

```text
group = "1 - scoutisme"
name = "veillée"
```

Le champ `group` commence normalement par un préfixe technique composé de :

```text
<numéro> + espaces éventuels + "-" + espaces éventuels
```

Exemples valides :

```text
1 - scoutisme
12 - liturgie
3-communauté
4  -  chants internationaux
```

Le préfixe numérique sert uniquement au classement des groupes. Il ne doit jamais apparaître dans le nom humain généré.

---

## 4. Nom technique du fichier

### 4.1 Format attendu

Le nom technique doit suivre la convention suivante :

```text
<slug_contexte>_<identifiant_aleatoire_10_caracteres>.<extension>
```

Exemples :

```text
scoutisme_k7m2p9x4qd.webp
taize_f8k2m4q7xp.jpg
background_h9x3q6f2ra.png
```

### 4.2 Identifiant aléatoire

L’identifiant aléatoire doit :

- contenir exactement 10 caractères ;
- utiliser uniquement des caractères sûrs pour un nom de fichier ;
- être suffisamment aléatoire pour éviter les collisions ;
- ne pas contenir d’espace ;
- ne pas dépendre du nom original du fichier ;
- ne pas dépendre de l’identifiant de base de données ;
- ne pas contenir de donnée personnelle.

Alphabet recommandé :

```text
abcdefghjkmnpqrstuvwxyz23456789
```

Cet alphabet évite les caractères visuellement ambigus comme :

```text
0, O, 1, l, I
```

### 4.3 Unicité

Le chemin ou le nom technique du fichier doit être unique.

L’implémentation doit prévoir :

1. la génération d’un identifiant aléatoire ;
2. la construction du nom technique ;
3. la vérification de son unicité ;
4. une nouvelle génération en cas de collision.

Une contrainte d’unicité en base de données doit rester la garantie finale.

### 4.4 Slug de contexte

Le préfixe du nom technique est uniquement descriptif.

Il doit être construit à partir du contexte disponible au moment de l’import :

- utiliser le groupe nettoyé lorsqu’un seul groupe cohérent peut être déterminé ;
- sinon utiliser le fallback `background`.

Le préfixe doit être transformé en slug :

- minuscules ;
- sans accents ;
- sans espace ;
- caractères non alphanumériques remplacés ou supprimés ;
- séparateur recommandé : tiret `-`.

Exemples :

```text
Scoutisme        -> scoutisme
Temps liturgique -> temps-liturgique
Prière & louange -> priere-louange
```

Le nom technique du fichier est stable après sa création.

Une modification ultérieure des genres ne doit pas provoquer automatiquement le renommage physique du fichier.

---

## 5. Nom original du fichier

Le nom envoyé par l’utilisateur ne doit pas être utilisé directement comme nom technique.

Exemple reçu :

```text
mon nom de fichier avec espace.jpg
```

Ce nom peut contenir :

- des espaces ;
- des accents ;
- des apostrophes ;
- des caractères spéciaux ;
- des parenthèses ;
- un nom très long ;
- une extension trompeuse ;
- un nom déjà utilisé par un autre fichier.

Le nom original peut être conservé séparément en base de données pour :

- la traçabilité ;
- l’affichage éventuel ;
- le support utilisateur ;
- un fallback d’interface.

Champ recommandé :

```text
original_filename
```

---

## 6. Génération du nom humain

### 6.1 Principe général

Le nom humain est une étiquette calculée à partir des genres associés à l’image.

Il doit rester simple, pertinent et lisible.

Il ne faut pas essayer de concaténer tous les genres lorsque l’image couvre plusieurs groupes différents.

### 6.2 Nettoyage du groupe

Avant toute génération, le préfixe numérique du champ `group` doit être supprimé.

Exemples :

```text
"1 - scoutisme"              -> "scoutisme"
"12 - temps liturgiques"     -> "temps liturgiques"
"3-communauté"               -> "communauté"
"4  -  chants internationaux" -> "chants internationaux"
```

La suppression doit être basée sur la structure du préfixe, et non sur un nombre fixe de caractères.

La logique attendue est équivalente à :

```text
début de chaîne
+ un ou plusieurs chiffres
+ espaces éventuels
+ tiret
+ espaces éventuels
```

Après nettoyage :

- supprimer les espaces en début et fin ;
- conserver les accents ;
- conserver les espaces internes ;
- conserver la casse prévue pour l’affichage, ou appliquer une capitalisation homogène côté présentation.

---

## 7. Règles métier du nom humain

### Cas 1 — Aucun genre associé

Lorsque l’image n’a aucun genre associé :

```text
nom humain généré = NULL
```

L’interface peut afficher un fallback, mais ce fallback ne fait pas partie du nom métier calculé.

Fallbacks possibles côté interface :

```text
Image personnalisée
```

ou :

```text
nom original du fichier
```

---

### Cas 2 — Un seul genre associé

Lorsque l’image possède exactement un genre :

```text
nom humain = <groupe nettoyé> — <nom du genre>
```

Exemple :

```text
group = "1 - scoutisme"
name = "veillée"
```

Résultat :

```text
Scoutisme — Veillée
```

Le séparateur recommandé est un tiret cadratin :

```text
—
```

Le nom du groupe et le nom du genre doivent être nettoyés des espaces inutiles.

---

### Cas 3 — Plusieurs genres appartenant au même groupe

Lorsque l’image possède plusieurs genres et qu’ils appartiennent tous au même groupe :

```text
nom humain = <groupe nettoyé>
```

Exemple :

```text
1 - scoutisme / veillée
1 - scoutisme / camp
1 - scoutisme / prière
```

Résultat :

```text
Scoutisme
```

Les noms individuels des genres ne doivent pas être concaténés.

---

### Cas 4 — Plusieurs genres appartenant à des groupes différents

Lorsque l’image possède plusieurs genres répartis dans plusieurs groupes :

```text
nom humain généré = NULL
```

Exemple :

```text
1 - scoutisme / veillée
2 - liturgie / louange
```

Résultat :

```text
NULL
```

Il ne faut pas produire un nom du type :

```text
Scoutisme / Liturgie
```

La présence de plusieurs groupes signifie que le système ne peut pas générer un libellé unique suffisamment pertinent.

---

## 8. Résumé décisionnel

| Nombre de genres | Nombre de groupes distincts | Nom humain généré |
|---:|---:|---|
| 0 | 0 | `NULL` |
| 1 | 1 | `<groupe nettoyé> — <nom du genre>` |
| supérieur à 1 | 1 | `<groupe nettoyé>` |
| supérieur à 1 | supérieur à 1 | `NULL` |

---

## 9. Détermination des groupes distincts

La comparaison des groupes doit être réalisée de manière robuste.

Avant comparaison :

- supprimer le préfixe numérique ;
- supprimer les espaces en début et fin ;
- normaliser les espaces multiples ;
- comparer sans tenir compte des différences superficielles de casse.

Exemples considérés comme appartenant au même groupe :

```text
1 - scoutisme
1 - Scoutisme
1  -  scoutisme
```

Le libellé affiché doit néanmoins provenir d’une valeur propre et cohérente.

Lorsque plusieurs variantes existent, privilégier :

1. la valeur du premier genre selon un ordre métier stable ;
2. sinon une capitalisation normalisée.

Ne pas dépendre d’un ordre arbitraire de base de données.

---

## 10. Ordre des genres

La notion de « premier genre » ne doit pas dépendre d’un résultat SQL sans ordre explicite.

Lorsque l’ordre des genres est utilisé, il doit reposer sur au moins un des éléments suivants :

- un champ d’ordre explicite ;
- l’ordre de sélection par l’utilisateur ;
- un genre principal explicite ;
- un ordre stable défini par le modèle métier.

Dans cette spécification, l’ordre n’a pas d’incidence sur le nom humain, sauf pour choisir la forme d’affichage lorsque plusieurs lignes présentent le même groupe avec des variations de casse ou d’espacement.

---

## 11. Stockage ou calcul du nom humain

Le nom humain généré dépend entièrement des genres associés.

La stratégie privilégiée est :

```text
nom humain calculé dynamiquement
```

Ainsi, lorsque les associations de genres changent, le nom affiché est automatiquement recalculé.

Exemple :

```text
Avant :
1 genre
-> Scoutisme — Veillée

Après ajout d’un second genre du même groupe :
-> Scoutisme

Après ajout d’un genre d’un autre groupe :
-> NULL
```

Si un champ de nom personnalisé est prévu, séparer clairement :

```text
generated_display_name
custom_display_name
```

La priorité d’affichage recommandée est :

```text
custom_display_name
sinon generated_display_name
sinon original_filename
sinon "Image personnalisée"
```

Un nom personnalisé ne doit pas être écrasé par un recalcul automatique.

---

## 12. Stabilité des URLs

Le nom humain et le nom technique sont indépendants.

Une modification des genres peut modifier :

```text
generated_display_name
```

mais ne doit pas modifier automatiquement :

```text
storage_filename
storage_path
```

Objectifs :

- éviter de casser les URLs existantes ;
- éviter d’invalider inutilement les caches ;
- éviter les déplacements physiques de fichiers ;
- éviter les références orphelines ;
- conserver un stockage simple.

---

## 13. Cas limites

### Groupe vide

Si le champ `group` est vide ou contient uniquement son préfixe :

```text
"1 - "
```

alors le groupe nettoyé est considéré comme vide.

Conséquences :

- pour un seul genre, ne pas produire `— Veillée` ;
- pour plusieurs genres, ne pas produire un nom vide ;
- retourner `NULL` si aucun libellé cohérent ne peut être construit.

### Nom de genre vide

Pour un seul genre avec un groupe valide mais un nom vide :

```text
nom humain = <groupe nettoyé>
```

Exemple :

```text
group = "1 - scoutisme"
name = ""
```

Résultat :

```text
Scoutisme
```

### Groupe et nom vides

Résultat :

```text
NULL
```

### Genres dupliqués

Les doublons exacts ne doivent pas changer le résultat métier.

Exemple :

```text
Scoutisme / Veillée
Scoutisme / Veillée
```

Résultat attendu :

```text
Scoutisme — Veillée
```

si le doublon représente en réalité une seule association métier.

Si les doublons sont possibles, ils doivent être dédupliqués avant le calcul.

### Groupes incohérents seulement par le préfixe

Exemple :

```text
1 - scoutisme
9 - scoutisme
```

Après nettoyage, ces valeurs représentent le même groupe métier :

```text
scoutisme
```

Le résultat doit donc être traité comme un seul groupe distinct.

---

## 14. Exemples complets

### Exemple A

Genres :

```text
aucun
```

Nom humain :

```text
NULL
```

Nom technique possible :

```text
background_k7m2p9x4qd.webp
```

---

### Exemple B

Genres :

```text
group = "1 - scoutisme"
name = "veillée"
```

Nom humain :

```text
Scoutisme — Veillée
```

Nom technique possible :

```text
scoutisme_k7m2p9x4qd.webp
```

---

### Exemple C

Genres :

```text
group = "1 - scoutisme"
name = "veillée"

group = "1 - scoutisme"
name = "camp"
```

Nom humain :

```text
Scoutisme
```

Nom technique possible :

```text
scoutisme_b3n6r9w2cz.webp
```

---

### Exemple D

Genres :

```text
group = "1 - scoutisme"
name = "veillée"

group = "2 - liturgie"
name = "louange"
```

Nom humain :

```text
NULL
```

Nom technique possible :

```text
background_t7v4p2k8md.webp
```

---

### Exemple E

Genres :

```text
group = "12 - temps liturgiques"
name = "avent"
```

Nom humain :

```text
Temps liturgiques — Avent
```

Nom technique possible :

```text
temps-liturgiques_f8k2m4q7xp.webp
```

---

## 15. Critères d’acceptation

L’implémentation est considérée comme conforme lorsque :

1. un fichier téléversé ne conserve pas son nom original comme nom physique ;
2. le nom technique contient un suffixe aléatoire de 10 caractères ;
3. le nom technique est unique ;
4. le nom technique ne contient pas d’espace ni de caractère dangereux ;
5. le préfixe numérique du groupe n’apparaît jamais dans le nom humain ;
6. un seul genre produit `Groupe — Nom` ;
7. plusieurs genres du même groupe produisent uniquement `Groupe` ;
8. plusieurs genres de groupes différents produisent `NULL` ;
9. aucun genre produit `NULL` ;
10. les variations d’espacement du préfixe numérique sont correctement gérées ;
11. une modification des genres recalcule le nom humain ;
12. une modification des genres ne renomme pas automatiquement le fichier physique ;
13. un éventuel nom personnalisé n’est jamais écrasé ;
14. les doublons d’associations n’altèrent pas le résultat ;
15. l’ordre arbitraire des requêtes ne modifie pas le résultat.

---

## 16. Tests métier attendus

Prévoir au minimum les tests suivants :

### Nettoyage des groupes

```text
"1 - scoutisme" -> "scoutisme"
"12 - liturgie" -> "liturgie"
"3-communauté" -> "communauté"
"4  -  prière" -> "prière"
"scoutisme" -> "scoutisme"
"" -> ""
NULL -> ""
```

### Génération du nom humain

```text
0 genre -> NULL
1 genre valide -> "Scoutisme — Veillée"
2 genres du même groupe -> "Scoutisme"
3 genres du même groupe -> "Scoutisme"
2 genres de groupes différents -> NULL
1 genre avec nom vide -> "Scoutisme"
1 genre avec groupe vide -> NULL ou nom du genre uniquement si cette règle est explicitement décidée
1 genre avec groupe et nom vides -> NULL
doublon exact d’un genre -> même résultat qu’un genre unique
```

### Génération du nom technique

```text
suffixe de 10 caractères
nom unique
slug sans espace
fallback "background"
extension conservée ou normalisée selon la politique globale du projet
absence de donnée personnelle
```

---

## 17. Décisions à ne pas prendre implicitement

Codex ne doit pas modifier seul les choix suivants sans validation explicite :

- ajouter la date dans le nom ;
- utiliser un UUID complet ;
- utiliser le nom original comme nom physique ;
- renommer les fichiers lors d’un changement de genre ;
- concaténer plusieurs groupes dans le nom humain ;
- stocker définitivement le nom humain sans mécanisme de recalcul ;
- considérer le premier genre renvoyé par la base comme un ordre métier ;
- utiliser uniquement l’identifiant de base de données pour garantir l’unicité.

---

## 18. Résultat attendu

À la fin de l’implémentation :

- les fichiers ont des noms techniques courts, sûrs et uniques ;
- les utilisateurs voient des noms humains cohérents ;
- la logique reste prévisible avec zéro, un ou plusieurs genres ;
- le classement numérique des groupes reste invisible ;
- les URLs des images restent stables ;
- les règles sont couvertes par des tests automatisés.
