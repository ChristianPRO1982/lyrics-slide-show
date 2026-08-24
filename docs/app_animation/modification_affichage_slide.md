# Objectif

Finaliser la partie **affichage projeté** de la fonctionnalité de double affichage des chants dans Lyrics Slide Show.

La gestion de la fonctionnalité est déjà en place :

* configuration du chant ;
* configuration dans la création d'une animation ;
* adaptation du pré-affichage dans la Remote.

Cette tâche concerne uniquement la **page HTML de projection**, c'est-à-dire la fenêtre ouverte par la Remote et affichée en plein écran sur le vidéoprojecteur.

Ne pas modifier la Remote dans cette étape.

---

# Principe actuel de l'affichage

L'affichage projeté est volontairement extrêmement minimaliste.

Une slide contient uniquement :

* le texte ;
* sa police ;
* sa taille de police ;
* sa couleur ;
* sa mise en forme, notamment le gras déjà pris en charge par le mode simple ;
* la couleur de fond ou l'image de fond ;
* un padding horizontal gauche/droite.

Le texte est actuellement :

* centré horizontalement ;
* centré verticalement ;
* sans padding spécifique en haut ou en bas.

Si le contenu est trop grand pour l'écran, le texte peut sortir de l'écran.

Il ne faut pas introduire de mécanisme complexe de redimensionnement automatique dans cette tâche.

---

# Philosophie visuelle à conserver

Le mode double doit rester dans exactement le même esprit que le mode simple.

Ne jamais ajouter d'élément graphique de séparation.

En particulier, ne pas ajouter :

* de `<hr>` ;
* de trait vertical ;
* de bordure ;
* de tableau visible ;
* de cadre ;
* de fond distinct entre les deux parties ;
* de séparateur graphique quelconque.

La séparation entre les deux textes doit être obtenue uniquement par leur positionnement et leurs paddings.

L'écran doit toujours donner l'impression d'une slide minimaliste contenant du texte.

---

# Avant toute modification

Commencer par inspecter l'implémentation actuelle de la page de projection.

Identifier précisément :

1. le template Django de la fenêtre projetée ;
2. l'élément HTML qui contient actuellement le texte d'une slide ;
3. la manière dont sont appliqués :

   * la police ;
   * la taille ;
   * la couleur ;
   * le gras et les autres mises en forme éventuellement existantes ;
   * le fond ;
   * l'image de fond ;
   * le padding ;
   * l'alignement vertical ;
   * l'alignement horizontal ;
4. le JavaScript éventuel qui remplace dynamiquement le contenu lors du changement de slide ;
5. la manière dont les informations de la slide courante arrivent depuis la Remote ;
6. les nouveaux modes de double affichage déjà disponibles dans les données de l'animation.

Réutiliser au maximum l'architecture actuelle.

Ne pas créer une seconde mécanique complète d'affichage si le renderer existant peut être étendu proprement.

---

# Affichage simple

Le fonctionnement actuel doit rester strictement inchangé pour toutes les slides normales.

Conceptuellement :

```text
┌───────────────────────────────────────────────┐
│                                               │
│                                               │
│                  TEXTE                        │
│                                               │
│                                               │
└───────────────────────────────────────────────┘
```

Le texte utilise tous les paramètres actuels de la slide :

* police ;
* taille ;
* couleur ;
* mise en gras ;
* autres mises en forme déjà supportées ;
* couleur de fond ;
* image de fond ;
* padding horizontal ;
* autres paramètres existants.

Aucune régression ne doit être introduite sur ce mode.

---

# Affichage double

Lorsqu'une slide doit afficher deux blocs simultanément, le texte central actuel doit être remplacé par **deux zones de texte disposées horizontalement l'une à côté de l'autre**.

Conceptuellement :

```text
┌───────────────────────────────────────────────┐
│                                               │
│                                               │
│       TEXTE GAUCHE        TEXTE DROITE        │
│                                               │
│                                               │
└───────────────────────────────────────────────┘
```

Aucun séparateur ne doit apparaître entre les deux.

Les deux zones doivent obligatoirement rester :

```text
GAUCHE | DROITE
```

et jamais se placer l'une sous l'autre.

Même avec beaucoup de texte, le layout doit rester horizontal.

---

# Structure HTML attendue

Ne pas imposer une technologie particulière sans avoir inspecté le code existant.

Cependant, conceptuellement, le mode double doit correspondre à :

```text
conteneur de la slide
    ├── zone gauche
    └── zone droite
```

Les deux zones doivent occuper chacune environ la moitié de la largeur disponible.

Si le renderer actuel utilise un `<div>` pour le texte principal, privilégier une évolution cohérente du même mécanisme.

Éviter les `<table>` simplement pour obtenir les deux colonnes.

Un layout de type `flex` ou équivalent est préférable si cela correspond à l'architecture actuelle.

---

# Répartition de la largeur

En mode double :

```text
zone gauche = 50 %
zone droite = 50 %
```

Les deux zones doivent rester côte à côte.

Chaque zone conserve le centrage vertical du texte.

Le texte doit également conserver le comportement d'alignement horizontal actuel du mode simple.

Ne pas inventer d'alignement spécifique différent entre les deux côtés.

---

# Gestion du padding

Le padding horizontal actuel du mode simple doit servir de référence.

Appelons :

```text
P = padding horizontal actuel
```

En mode simple :

```text
|---- P ---- TEXTE ---- P ----|
```

En mode double, le padding doit être redistribué.

## Bords extérieurs

Pour le bord gauche de la zone gauche :

```text
P / 2
```

Pour le bord droit de la zone droite :

```text
P / 2
```

## Espace central

Pour le bord droit de la zone gauche :

```text
P / 4
```

Pour le bord gauche de la zone droite :

```text
P / 4
```

Conceptuellement :

```text
|-- P/2 -- [ TEXTE GAUCHE ] -- P/4 --|-- P/4 -- [ TEXTE DROITE ] -- P/2 --|
```

Ainsi, l'espace central total vaut :

```text
P/4 + P/4 = P/2
```

Il n'y a toujours aucun trait séparateur.

---

# Aucun padding vertical supplémentaire

Conserver la philosophie actuelle :

* pas de padding spécifique en haut ;
* pas de padding spécifique en bas ;
* texte centré verticalement dans l'écran.

En mode double, chaque zone doit conserver ce même centrage vertical.

Il ne faut pas aligner artificiellement les deux textes en haut.

Chaque texte doit être centré verticalement dans sa propre moitié de slide.

---

# Règles de style en mode double

Il faut distinguer :

1. les paramètres globaux de la slide ;
2. les paramètres propres au texte de gauche ;
3. les paramètres propres au texte de droite.

---

# Paramètres globaux : priorité absolue au bloc gauche

Le **fond** appartient à l'ensemble de la slide et non à une colonne.

En mode double, utiliser exclusivement les paramètres de fond du bloc gauche.

Cela concerne :

* la couleur de fond ;
* l'image de fond ;
* son positionnement ;
* son dimensionnement ;
* son comportement actuel (`cover`, centrage ou autre logique déjà existante).

## Image de fond

L'image de fond du bloc gauche doit continuer à être affichée sur **100 % de la surface de la slide**.

Il ne faut surtout pas :

* limiter l'image à la moitié gauche ;
* créer une image différente pour chaque colonne ;
* compresser l'image dans 50 % de l'écran ;
* utiliser l'image de fond du bloc droit.

Conceptuellement :

```text
┌───────────────────────────────────────────────┐
│                                               │
│         IMAGE DE FOND DU BLOC GAUCHE          │
│              SUR TOUT L'ÉCRAN                 │
│                                               │
│     TEXTE GAUCHE          TEXTE DROITE        │
│                                               │
└───────────────────────────────────────────────┘
```

La slide droite conserve ses propres paramètres de fond dans les données, mais ils sont ignorés lorsqu'elle est utilisée comme partie droite d'un affichage double.

---

# Couleur du texte

En mode double, utiliser la **couleur du texte du bloc gauche pour les deux textes**.

Donc :

```text
couleur texte gauche = couleur du bloc gauche
couleur texte droite = couleur du bloc gauche
```

Cette règle permet de garantir la lisibilité par rapport au fond choisi par le bloc gauche.

Exemple :

```text
bloc gauche :
fond sombre
texte blanc

bloc droit :
fond clair
texte noir
```

En double affichage, le fond sombre du bloc gauche est utilisé sur toute la slide.

Le texte droit doit donc également utiliser le blanc du bloc gauche.

Il ne faut pas utiliser sa couleur noire initiale.

Les couleurs enregistrées du bloc droit ne doivent cependant pas être modifiées en base.

---

# Police de caractères

Contrairement au fond et à la couleur, **chaque texte conserve sa propre police**.

Donc :

```text
zone gauche  → police du bloc gauche
zone droite  → police du bloc droit
```

Exemple :

```text
bloc gauche : Montserrat
bloc droit  : Arial
```

Le double affichage doit conserver :

```text
Montserrat | Arial
```

Il ne faut pas imposer automatiquement la police du bloc gauche à la partie droite.

---

# Taille de police

Chaque texte conserve également **sa propre taille de police**.

Donc :

```text
zone gauche  → taille du bloc gauche
zone droite  → taille du bloc droit
```

Exemple :

```text
bloc gauche : 60 px
bloc droit  : 48 px
```

Le double affichage doit conserver :

```text
60 px | 48 px
```

Ne pas :

* utiliser la taille du bloc gauche pour les deux ;
* utiliser la taille du bloc droit pour les deux ;
* calculer automatiquement la plus petite taille ;
* redimensionner automatiquement les textes pour les faire tenir.

La logique actuelle reste valable :

> si le texte est trop important pour l'espace disponible, il peut sortir de l'écran.

La responsabilité du découpage correct des blocs reste du côté de la préparation du chant.

---

# Mise en gras et mise en forme du texte

La mise en forme déjà supportée par le mode simple doit être **strictement conservée pour chacun des deux textes**.

En particulier, si le mode simple permet actuellement d'afficher certaines parties du texte en gras, cette information doit continuer à fonctionner en mode double.

Donc :

```text
bloc gauche → conserve son gras / sa mise en forme
bloc droit  → conserve son gras / sa mise en forme
```

Il ne faut pas :

* supprimer les balises ou informations de gras du texte droit ;
* transformer tout le texte droit selon le style du texte gauche ;
* perdre la mise en forme lors de la construction des deux `<div>` ;
* traiter le contenu comme du texte brut si le renderer simple applique aujourd'hui une transformation particulière.

Le rendu des contenus gauche et droit doit réutiliser autant que possible **la même mécanique de rendu textuel que le mode simple**.

Exemple conceptuel :

```text
GAUCHE :
Ne crains pas,
JE SUIS TON DIEU

DROITE :
Je t'ai appelé
PAR TON NOM
```

Si certaines parties sont en gras dans les données, elles doivent le rester indépendamment dans chaque colonne.

---

# Synthèse des paramètres graphiques

En mode double :

| Paramètre            | Partie gauche                     | Partie droite                     |
| -------------------- | --------------------------------- | --------------------------------- |
| Couleur de fond      | bloc gauche                       | bloc gauche                       |
| Image de fond        | bloc gauche sur 100 % de la slide | bloc gauche sur 100 % de la slide |
| Couleur du texte     | bloc gauche                       | bloc gauche                       |
| Police               | bloc gauche                       | **bloc droit**                    |
| Taille de police     | bloc gauche                       | **bloc droit**                    |
| Gras / mise en forme | bloc gauche                       | **bloc droit**                    |
| Padding              | règle spéciale double             | règle spéciale double             |

La slide droite conserve toutes ses propriétés dans les données.

Aucune donnée ne doit être écrasée ou enregistrée différemment.

Ces règles ne concernent que le rendu lorsque deux blocs sont associés.

---

# CAS 1 — Refrain seul puis refrain + couplet

Règle fonctionnelle :

```text
R

R | C1

R

R | C2
```

Le refrain seul est affiché avec le renderer simple actuel.

Le couple :

```text
R | C1
```

est affiché en double.

Dans ce cas :

* le refrain est à gauche ;
* le couplet est à droite ;
* le fond du refrain s'applique à toute la slide ;
* la couleur du refrain s'applique aux deux textes ;
* le refrain conserve sa police et sa taille ;
* le couplet conserve sa propre police et sa propre taille ;
* chaque texte conserve sa propre mise en gras.

Exemple avec plusieurs blocs :

```text
Ra
Rb

Ra | C1a
Rb | C1b
```

---

# CAS 2 — Refrain toujours affiché avec le couplet

Règle fonctionnelle :

```text
R | C1
R | C2
R | C3
```

Chaque slide utilise le mode double.

Le refrain est à gauche.

Le couplet est à droite.

Les règles graphiques sont exactement les mêmes que pour le CAS 1.

---

# Bouton Refrain

Dans les CAS 1 et 2, le bouton `Refrain` de la Remote doit continuer à pouvoir afficher le refrain seul.

Lorsqu'un refrain est demandé seul :

> utiliser strictement le renderer simple actuel.

Il ne faut pas produire :

```text
R | vide
```

Il faut produire une vraie slide simple :

```text
R
```

centrée sur toute la largeur de l'écran et avec tous ses paramètres propres.

---

# Synchronisation lorsque les deux côtés ont plusieurs blocs

Les deux séquences avancent bloc par bloc.

Exemple :

```text
R = Ra, Rb
C1 = C1a, C1b

Ra | C1a
Rb | C1b
```

Si une séquence se termine avant l'autre, son dernier bloc reste affiché jusqu'à la fin de l'autre.

Exemple :

```text
R = Ra, Rb
C1 = C1a, C1b, C1c
```

Affichage :

```text
Ra | C1a
Rb | C1b
Rb | C1c
```

Inversement :

```text
R = Ra, Rb, Rc
C1 = C1a, C1b
```

Affichage :

```text
Ra | C1a
Rb | C1b
Rc | C1b
```

Il ne faut revenir au début d'une séquence qu'une fois que **les deux séquences sont arrivées à leur fin** et que l'on passe au groupe suivant.

---

# CAS 3 — Deux couplets côte à côte sans refrain

Règle fonctionnelle :

```text
C1 | C2
C3 | C4
C5
```

Pour une paire complète :

```text
C1 | C2
```

C1 est le bloc gauche.

C2 est le bloc droit.

Donc :

* fond de C1 sur toute la slide ;
* couleur de texte de C1 pour les deux textes ;
* police de C1 pour C1 ;
* police de C2 pour C2 ;
* taille de C1 pour C1 ;
* taille de C2 pour C2 ;
* gras/mise en forme de C1 conservés ;
* gras/mise en forme de C2 conservés.

Même règle pour :

```text
C3 | C4
```

---

# CAS 3 — Nombre impair de couplets

Ce cas est important.

Exemple :

```text
C1
C2
C3
C4
C5
```

La projection doit produire :

```text
C1 | C2

C3 | C4

C5
```

Le dernier couplet ne possède aucun partenaire.

## Règle impérative

Le dernier couplet doit être affiché avec le **renderer simple**.

Il ne faut surtout pas afficher :

```text
C5 | vide
```

avec C5 limité à seulement 50 % de la largeur.

Il faut afficher une vraie slide simple :

```text
┌───────────────────────────────────────────────┐
│                                               │
│                     C5                        │
│                                               │
└───────────────────────────────────────────────┘
```

avec :

* pleine largeur ;
* paramètres graphiques propres à C5 ;
* police propre à C5 ;
* taille propre à C5 ;
* couleur propre à C5 ;
* fond propre à C5 ;
* mise en gras propre à C5 ;
* padding normal du mode simple ;
* centrage normal du mode simple.

---

# CAS 3 avec blocs découpés

Les règles de synchronisation restent identiques.

Exemple :

```text
C1 = C1a, C1b
C2 = C2a, C2b
```

Projection :

```text
C1a | C2a
C1b | C2b
```

Si C1 possède deux blocs et C2 trois :

```text
C1a | C2a
C1b | C2b
C1b | C2c
```

Le dernier bloc de C1 reste donc affiché.

Lorsqu'un bloc est maintenu, son rendu graphique propre doit naturellement rester identique.

---

# Autres blocs du chant

Le moteur existant peut contenir :

* pont ;
* pré-refrain ;
* refrain final ;
* autres types déjà supportés.

Ne pas inventer de comportement nouveau pour ces blocs.

Si un de ces éléments n'est pas explicitement impliqué dans une paire double, conserver son affichage simple actuel.

Ne pas afficher artificiellement un bloc seul dans une demi-largeur.

La règle doit rester :

```text
deux contenus explicitement associés
→ affichage double

un seul contenu
→ affichage simple
```

---

# Séparation entre logique musicale et renderer

Conserver autant que possible une séparation nette.

Le renderer doit recevoir conceptuellement soit :

```text
SLIDE SIMPLE

contenu = A
style = A
```

soit :

```text
SLIDE DOUBLE

contenu gauche = A
contenu droite = B

fond global = A
couleur globale du texte = A

police gauche = A
taille gauche = A
mise en forme gauche = A

police droite = B
taille droite = B
mise en forme droite = B
```

Le renderer ne devrait pas avoir à reconstruire lui-même toute la structure musicale du chant si cette information peut être préparée proprement en amont.

Cependant, respecter l'architecture actuelle du projet et éviter un refactoring massif.

---

# Cas à tester

## Test 1 — Slide simple classique

Vérifier qu'une slide normale reste strictement identique à avant la modification.

Tester notamment :

* police ;
* taille ;
* couleur ;
* gras ;
* fond ;
* image de fond ;
* padding.

---

## Test 2 — Refrain + couplet

Projection :

```text
R | C1
```

Vérifier :

* deux textes côte à côte ;
* 50 % / 50 % ;
* pas de séparateur ;
* fond du refrain sur tout l'écran ;
* couleur du refrain pour les deux textes ;
* police du refrain à gauche ;
* police du couplet à droite ;
* taille du refrain à gauche ;
* taille du couplet à droite ;
* gras conservé indépendamment.

---

## Test 3 — Polices et tailles différentes

R possède :

```text
Montserrat
60 px
```

C1 possède :

```text
Arial
48 px
```

Résultat attendu :

```text
R    → Montserrat 60 px
C1   → Arial 48 px
```

Ne pas homogénéiser automatiquement les deux textes.

---

## Test 4 — Couleurs différentes

R possède :

```text
fond noir
texte blanc
```

C1 possède :

```text
fond blanc
texte noir
```

Résultat attendu en double :

```text
fond global : noir
texte R     : blanc
texte C1    : blanc
```

La police et la taille de C1 restent cependant celles de C1.

---

## Test 5 — Mise en gras

Créer deux blocs comportant chacun des portions de texte en gras.

Vérifier que le mode double restitue exactement les mêmes mises en forme que le mode simple pour chaque bloc.

La construction de la zone droite ne doit pas perdre la mise en gras.

---

## Test 6 — Bouton Refrain

Dans un chant en CAS 2, demander le refrain depuis la Remote.

Le résultat doit être :

```text
R
```

sur toute la largeur.

Pas :

```text
R | vide
```

---

## Test 7 — Couplets pairs

Pour :

```text
C1
C2
C3
C4
```

projection :

```text
C1 | C2
C3 | C4
```

---

## Test 8 — Couplets impairs

Pour :

```text
C1
C2
C3
C4
C5
```

projection :

```text
C1 | C2
C3 | C4
C5
```

Vérifier que C5 utilise bien une vraie slide simple pleine largeur avec tous ses paramètres propres.

---

## Test 9 — Longueur différente gauche/droite

Pour :

```text
A = Aa, Ab
B = Ba, Bb, Bc
```

projection :

```text
Aa | Ba
Ab | Bb
Ab | Bc
```

---

## Test 10 — Image de fond

Si le bloc gauche possède une image de fond et le bloc droit une autre :

* seule l'image du bloc gauche doit être utilisée ;
* elle doit couvrir l'écran selon le comportement actuel ;
* elle doit continuer à occuper 100 % de la slide ;
* elle ne doit pas être redimensionnée dans une moitié d'écran ;
* aucune image propre à la colonne droite ne doit apparaître.

---

## Test 11 — Padding

Avec un padding `P`, vérifier que le double affichage produit bien :

```text
P/2 | texte gauche | P/4 | P/4 | texte droite | P/2
```

et que le mode simple conserve exactement le padding `P` actuel.

---

# Contraintes de modification

Ne pas :

* modifier la base de données ;
* créer de migration ;
* modifier les formulaires ;
* modifier la Remote ;
* modifier les boutons ;
* modifier les raccourcis clavier ;
* modifier le fonctionnement du bouton Refrain ;
* créer des séparateurs graphiques ;
* ajouter des paramètres utilisateur pour gérer les colonnes ;
* créer un redimensionnement automatique complexe du texte ;
* écraser les paramètres enregistrés du bloc droit ;
* forcer la police du bloc gauche sur le bloc droit ;
* forcer la taille du bloc gauche sur le bloc droit ;
* perdre la mise en gras ou les mises en forme existantes ;
* refactorer des éléments sans rapport direct avec cette fonctionnalité.

---

# Travail attendu de Codex

1. Inspecter le renderer actuel de la page projetée.
2. Identifier la structure HTML actuelle de la slide simple.
3. Identifier précisément comment le texte simple applique :

   * police ;
   * taille ;
   * couleur ;
   * gras ;
   * autres mises en forme ;
   * fond ;
   * padding.
4. Conserver strictement le renderer simple.
5. Ajouter un renderer double aussi proche que possible de l'existant.
6. Faire en sorte que les deux zones restent obligatoirement côte à côte.
7. Appliquer la redistribution du padding définie dans ce document.
8. Utiliser le fond du bloc gauche sur 100 % de la slide.
9. Utiliser la couleur de texte du bloc gauche pour les deux zones.
10. Conserver la police propre du bloc gauche et la police propre du bloc droit.
11. Conserver la taille propre du bloc gauche et la taille propre du bloc droit.
12. Réutiliser la mécanique existante du mode simple pour conserver le gras et les autres mises en forme dans les deux zones.
13. Afficher une vraie slide simple lorsqu'un contenu n'a pas de partenaire.
14. Respecter la règle particulière du dernier couplet impair du CAS 3.
15. Vérifier que le bouton Refrain continue à produire un affichage simple.
16. Vérifier les cas où les deux séquences possèdent un nombre différent de blocs.
17. Ajouter ou adapter les tests existants si le projet en possède autour du renderer.

À la fin, fournir un résumé court indiquant :

* les fichiers modifiés ;
* comment le mode simple et le mode double sont distingués ;
* comment les deux zones sont construites ;
* comment le padding est calculé ;
* comment le fond global est choisi ;
* comment sont gérées séparément les polices et tailles gauche/droite ;
* comment la couleur commune est appliquée ;
* comment le gras et les mises en forme sont conservés ;
* comment est traité le dernier couplet impair ;
* les tests réalisés ;
* les éventuelles limites constatées sans les corriger hors périmètre.
