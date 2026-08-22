# Objectif

Finaliser la partie **Remote** de la nouvelle fonctionnalité de double affichage des chants dans Lyrics Slide Show.

La gestion des nouveaux modes est **déjà implémentée** :

* dans la configuration du chant ;
* dans la création/configuration d'une animation.

Il ne faut donc **pas modifier cette partie fonctionnelle**.

Cette étape concerne uniquement le **pré-affichage des slides dans la Remote pendant une animation**.

L'affichage plein écran destiné au vidéoprojecteur sera traité séparément dans une étape suivante.

---

# Contexte fonctionnel

Lors d'une animation, Django fournit une interface **Remote** utilisée sur le PC de contrôle.

Cette Remote :

* contient les boutons permettant de piloter la projection ;
* affiche un pré-affichage des différentes slides/blocs du chant ;
* ouvre/pilote une seconde page HTML utilisée pour la projection ;
* la seconde page est mise en plein écran, généralement avec `F11`, et joue le rôle de l'écran PowerPoint destiné au vidéoprojecteur.

Dans cette tâche :

> **Ne modifier que le pré-affichage présent dans la Remote.**

Ne pas modifier :

* les boutons ;
* les commandes clavier ;
* la navigation ;
* la communication avec la fenêtre de projection ;
* la logique d'ouverture de la seconde fenêtre ;
* l'affichage plein écran ;
* les modèles de données ;
* les formulaires de création/modification des chants ;
* les formulaires de création/modification des animations.

---

# Avant toute modification

Commencer par analyser le code existant et identifier :

1. le template Django utilisé pour la Remote ;
2. la vue Django et/ou le contexte alimentant ce template ;
3. le JavaScript éventuellement utilisé pour construire le pré-affichage ;
4. la manière dont les blocs `couplet`, `refrain`, `pont`, `pré-refrain`, `refrain final`, etc. sont actuellement représentés ;
5. la manière dont les nouvelles options de double affichage sont déjà exposées au moment d'une animation.

Réutiliser impérativement les champs, enums, propriétés et conventions existants.

**Ne pas inventer un deuxième système de détection des modes si cette information existe déjà dans le modèle ou dans l'animation.**

Chercher la modification minimale permettant d'adapter la Remote.

---

# Important : blocs physiques et blocs logiques

Un couplet ou un refrain peut être trop long pour tenir sur une seule slide.

Il peut alors être enregistré sous la forme de plusieurs blocs physiques.

Exemple :

```text
Couplet 2 :
C2a
C2b
C2c
```

Ces trois blocs représentent cependant **un seul couplet logique**.

Les options existantes permettent notamment :

* de ne pas incrémenter le numéro de couplet pour les blocs de continuation ;
* de ne pas insérer un refrain entre deux morceaux appartenant au même couplet.

Il faut donc respecter cette mécanique existante.

En particulier :

> Ne jamais déterminer qu'un couplet est pair ou impair simplement à partir de la position de sa ligne dans une liste ou de son ID en base.

Il faut utiliser la logique de numérotation existante des couplets.

---

# Les trois modes à prendre en compte

## CAS 1 — Refrain seul puis double affichage

Fonctionnement futur de la projection :

```text
R
R | C1

R
R | C2

R
R | C3
```

Exemple avec plusieurs blocs :

```text
Ra
Rb

Ra | C1a
Rb | C1b

Ra
Rb

Ra | C2a
Rb | C2b
```

### Comportement demandé dans la Remote

**Aucune modification du pré-affichage actuel pour ce mode.**

La Remote doit continuer à présenter les blocs comme elle le fait actuellement.

Ne pas essayer dès maintenant de représenter visuellement les deux colonnes dans la miniature/prévisualisation.

Le fonctionnement existant doit rester intact.

---

# CAS 2 — Refrain + couplet sans refrain seul entre les couplets

Fonctionnement futur de la projection :

```text
R | C1
R | C2
R | C3
```

Exemple avec plusieurs blocs :

```text
Ra | C1a
Rb | C1b

Ra | C2a
Rb | C2b
```

Le bouton **Refrain** de la Remote continuera par ailleurs à permettre l'affichage du refrain seul.

Cette mécanique sera conservée ; il ne faut pas modifier le bouton dans cette tâche.

## Comportement demandé dans le pré-affichage de la Remote

Dans ce mode :

> **Ne plus afficher les blocs de refrain dans la liste de pré-affichage.**

La Remote doit afficher uniquement les blocs correspondant aux couplets.

Exemple conceptuel.

Données du chant :

```text
R
C1
R
C2
R
C3
```

Le pré-affichage Remote doit devenir :

```text
C1
C2
C3
```

et non :

```text
R
C1
R
C2
R
C3
```

Cela concerne uniquement la représentation dans le pré-affichage.

Les refrains doivent toujours :

* exister dans les données ;
* rester accessibles à la logique de projection ;
* rester accessibles via le bouton `Refrain` ;
* pouvoir être utilisés plus tard pour construire les slides doubles.

Il ne faut donc surtout **pas supprimer les refrains du chant ou de la séquence interne**.

Il faut uniquement les exclure de la liste de prévisualisation de la Remote pour ce mode.

---

# CAS 3 — Double affichage de deux couplets sans refrain

Fonctionnement futur de la projection :

```text
C1 | C2
C3 | C4
C5
```

Autrement dit :

* C1 est affiché à gauche avec C2 à droite ;
* C3 est affiché à gauche avec C4 à droite ;
* si le nombre de couplets est impair, le dernier couplet est affiché seul.

## Comportement demandé dans le pré-affichage de la Remote

La Remote ne doit afficher que les couplets servant de **colonne gauche**.

Donc :

```text
C1
C3
C5
```

Les couplets pairs ne doivent pas apparaître comme des éléments indépendants dans le pré-affichage, puisqu'ils seront projetés avec le couplet précédent.

Exemple :

```text
Chant :
C1
C2
C3
C4
C5
```

Remote :

```text
C1
C3
C5
```

Projection future :

```text
C1 | C2
C3 | C4
C5
```

---

# Attention aux couplets découpés en plusieurs blocs

Cette règle doit fonctionner avec la mécanique actuelle de découpage des textes longs.

Exemple :

```text
Couplet logique 1 :
C1a
C1b

Couplet logique 2 :
C2a
C2b

Couplet logique 3 :
C3a
C3b
```

Dans le CAS 3, la Remote doit conserver tous les morceaux appartenant aux couplets logiques impairs :

```text
C1a
C1b

C3a
C3b
```

et masquer :

```text
C2a
C2b
```

Il ne faut donc pas faire quelque chose du type :

```text
bloc 1 visible
bloc 2 caché
bloc 3 visible
bloc 4 caché
```

Ce serait incorrect dès qu'un couplet est découpé en plusieurs morceaux.

La décision doit être basée sur le **numéro du couplet logique**, en respectant les options existantes de continuité de numérotation.

---

# Autres types de blocs

Le système existant sait également gérer d'autres types de blocs :

* pont ;
* pré-refrain ;
* refrain final ;
* autres éventuels types déjà présents dans le projet.

Ne pas introduire de comportement arbitraire pour ces blocs.

Pour cette première implémentation :

* appliquer les nouvelles règles uniquement aux blocs directement concernés par les trois modes ;
* conserver le comportement existant pour les autres types ;
* ne pas supprimer silencieusement un pont ou un pré-refrain simplement parce qu'un chant utilise un mode double affichage.

Si le code existant possède déjà une règle déterminant comment ces blocs entrent dans la séquence de projection, la conserver.

---

# Principe d'implémentation souhaité

Chercher à conserver une séparation claire entre :

```text
séquence complète du chant
```

et :

```text
éléments affichés dans le pré-affichage de la Remote
```

Le filtrage demandé ici est essentiellement un **filtrage de représentation de la Remote**.

Il ne doit pas modifier la séquence musicale source.

Conceptuellement :

```text
séquence de l'animation
        ↓
détermination du mode d'affichage
        ↓
construction de la liste Remote
        ↓
template Remote
```

Éviter autant que possible de faire porter au HTML une logique musicale complexe.

Si une préparation propre de la liste peut être faite dans la logique Django existante avant rendu du template, privilégier cette approche.

Cependant, respecter l'architecture actuelle du projet : ne pas déplacer massivement de logique simplement pour cette tâche.

---

# Récapitulatif attendu

| Mode                            | Pré-affichage Remote                                   |
| ------------------------------- | ------------------------------------------------------ |
| Cas 1 — `R` puis `R + C`        | comportement actuel, aucune modification               |
| Cas 2 — toujours `R + C`        | afficher uniquement les couplets, masquer les refrains |
| Cas 3 — `C1 + C2`, `C3 + C4`... | afficher uniquement les couplets logiques impairs      |

---

# Contraintes

La modification doit être la plus locale possible.

Ne pas :

* modifier la base de données ;
* créer de nouvelle migration ;
* modifier les options déjà enregistrées ;
* modifier les formulaires ;
* modifier les boutons de la Remote ;
* modifier le bouton `Refrain` ;
* modifier la navigation précédente/suivante ;
* modifier les raccourcis clavier ;
* modifier l'ouverture de la fenêtre de projection ;
* implémenter maintenant le nouvel affichage deux colonnes sur l'écran projeté ;
* refactorer des parties sans rapport direct avec cette fonctionnalité.

---

# Vérifications à effectuer

Vérifier au minimum les scénarios suivants.

## Test 1 — chant classique

Un chant ne possédant aucune option de double affichage doit avoir exactement le même pré-affichage qu'avant la modification.

---

## Test 2 — CAS 1

Pour :

```text
R
C1
R
C2
```

le pré-affichage doit conserver le comportement actuellement utilisé.

Aucune régression.

---

## Test 3 — CAS 2

Pour :

```text
R
C1
R
C2
```

le pré-affichage doit présenter uniquement :

```text
C1
C2
```

Le refrain reste cependant disponible pour la logique interne et pour le bouton `Refrain`.

---

## Test 4 — CAS 3 pair

Pour :

```text
C1
C2
C3
C4
```

le pré-affichage doit présenter :

```text
C1
C3
```

---

## Test 5 — CAS 3 impair

Pour :

```text
C1
C2
C3
C4
C5
```

le pré-affichage doit présenter :

```text
C1
C3
C5
```

---

## Test 6 — CAS 3 avec couplets découpés

Pour :

```text
C1a
C1b
C2a
C2b
C3a
C3b
```

avec les marqueurs existants indiquant que `C1b`, `C2b` et `C3b` sont des continuations des couplets précédents, le pré-affichage doit présenter :

```text
C1a
C1b
C3a
C3b
```

et ne pas présenter :

```text
C2a
C2b
```

---

# Travail attendu de Codex

1. Inspecter l'implémentation actuelle.
2. Identifier précisément où est construite la liste utilisée par le pré-affichage Remote.
3. Identifier les champs existants correspondant aux trois nouveaux modes.
4. Proposer puis réaliser la modification minimale.
5. Réutiliser la logique existante permettant de connaître le numéro logique d'un couplet.
6. Préserver intégralement les fonctionnalités actuelles de pilotage.
7. Ajouter ou adapter des tests si le projet possède déjà des tests autour de cette partie.
8. Vérifier l'absence de régression sur les chants classiques.
9. Ne pas implémenter l'affichage plein écran deux colonnes dans cette tâche.

À la fin, fournir un résumé court indiquant :

* les fichiers modifiés ;
* où le filtrage du pré-affichage a été réalisé ;
* comment sont distingués les trois modes ;
* comment les couplets découpés en plusieurs blocs sont pris en compte ;
* les tests effectués ;
* les éventuels points qui devront être repris lors de l'étape suivante concernant l'écran de projection.
