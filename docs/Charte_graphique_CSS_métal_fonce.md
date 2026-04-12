Étape 1 — charte graphique de base

À partir de ton bouton, je te propose une direction visuelle claire et exploitable directement pour ensuite écrire le CSS.

**Nom d’ambiance**
**Neo Steel Night**

On garde l’idée :
fond très sombre, métal brossé noir/bleu, contours lumineux, rendu net, moderne, carré, presque “console premium / scène électro”.

## 1. Identité visuelle

Le style repose sur 4 couches qui travaillent ensemble :

**Le fond**
Très sombre, presque noir, avec une légère dérive bleu électrique pour éviter un noir plat.

**La matière**
Métal noir brossé, froid, discret, sans reflets trop blancs.

**Les bordures**
Double contour rigide, parfaitement carré, avec liserés lumineux bleu électrique et vert acier.

**Les halos**
Lumières diffuses autour des composants, avec micro-variations au scroll pour donner une sensation vivante.

---

## 2. Palette de couleurs

### Fonds

* `--bg-page: #03070d`
* `--bg-page-alt: #07111d`
* `--bg-panel: #0a0f17`
* `--bg-panel-deep: #05080d`

### Métal / surfaces

* `--metal-dark: #111722`
* `--metal-mid: #1b2430`
* `--metal-line: #2e3947`
* `--metal-specular: #8e9bab`

### Néons

* `--neon-blue: #19b8ff`
* `--neon-blue-strong: #4fd8ff`
* `--steel-green: #5fae9d`
* `--steel-green-strong: #89d3bf`

### Lumières et ombres

* `--glow-blue: rgba(25, 184, 255, 0.38)`
* `--glow-green: rgba(95, 174, 157, 0.30)`
* `--glow-mix: rgba(80, 210, 220, 0.20)`
* `--shadow-deep: rgba(0, 0, 0, 0.65)`

---

## 3. Formes

Ici il faut être strict :

* **radius global : 0**
* coins francs
* biseaux très légers possibles uniquement en décor visuel
* contours nets
* pas d’aspect “soft UI”
* pas d’effet plastique

Donc :

* surfaces carrées
* boutons carrés
* cards carrées
* inputs carrés
* cadres rigides

---

## 4. Matière

Le cœur du visuel doit être un **métal sombre brossé horizontalement**.

Effet recherché :

* base très sombre
* brossage fin horizontal
* léger gradient vertical
* très faible reflet central
* pas de chrome miroir trop fort

Le métal doit rester sobre pour laisser la vedette aux bordures lumineuses.

---

## 5. Bordures

Le bouton source montre bien une logique à reprendre :

### Structure recommandée

* **bordure externe** : métallique froide
* **bordure interne** : liseré sombre fin
* **halo externe** : bleu électrique + vert acier
* **accent lumineux ponctuel** : coins ou segments de bordure

### Répartition couleur

* haut/gauche : dominante bleu électrique
* bas/droite : mélange bleu électrique / vert acier
* quelques points lumineux localisés pour donner du relief

Le vert acier ne doit pas devenir “vert gaming fluo”.
Il doit rester métallique, froid, un peu sophistiqué.

---

## 6. Fond de page

Pour éviter que les halos disparaissent, le fond doit être très sombre avec légère texture lumineuse.

### Recommandation

* fond principal quasi noir bleuté
* léger radial gradient discret au centre ou derrière les composants clés
* bruit visuel très léger optionnel
* zones lumineuses diffuses très faibles, pas partout

Exemple d’intention :

* centre : bleu nuit très léger
* bords : noir profond

---

## 7. Effets lumineux

Il faut distinguer 3 types d’effets.

### Halo fixe

Autour des composants principaux :

* faible diffusion
* bleu + vert acier
* opacité maîtrisée
* flou large mais discret

### Glow de bordure

Collé au contour :

* plus précis
* plus intense
* presque “tube néon intégré dans le métal”

### Accent mobile

Au scroll :

* variation légère de l’intensité
* translation subtile d’un reflet ou d’un halo
* jamais disco
* sensation premium, pas gadget

---

## 8. Animation au scroll

L’idée n’est pas que tout bouge, mais que la lumière “respire” avec la page.

### Ce qui peut changer avec le scroll

* intensité du halo bleu
* intensité du halo vert acier
* position d’un reflet spéculaire
* opacité d’une nappe lumineuse de fond
* léger décalage de gradient sur les bordures

### Ce qu’il faut éviter

* changements brutaux
* flash
* rotation trop visible
* couleurs trop saturées
* animation permanente agressive

### Intention

Quand on scroll :

* le site semble réagir à la navigation
* les halos gagnent légèrement en vie
* certains cadres paraissent “alimentés”

---

## 9. Hiérarchie d’usage

### Éléments primaires

Boutons importants, encadrés clés, zone active :

* glow bleu plus fort
* présence possible du vert acier en secondaire
* contraste marqué

### Éléments secondaires

Cards, inputs, panneaux :

* glow plus faible
* métal plus dominant
* lumière plus discrète

### Éléments de fond

Sections, séparateurs :

* quasi pas de glow
* juste une structure sombre et nette

---

## 10. Ton global

Le rendu doit évoquer :

* technique
* scène musicale
* projection
* électronique premium
* sobriété moderne

Et non :

* cyberpunk multicolore
* gaming excessif
* néon rose/violet dominant
* interface cartoon

---

## 11. Tokens de direction CSS

Voici la base que je te conseille pour le futur CSS :

```css
:root {
    --bg-page: #03070d;
    --bg-page-alt: #07111d;
    --bg-panel: #0a0f17;
    --bg-panel-deep: #05080d;

    --metal-dark: #111722;
    --metal-mid: #1b2430;
    --metal-line: #2e3947;
    --metal-specular: #8e9bab;

    --neon-blue: #19b8ff;
    --neon-blue-strong: #4fd8ff;
    --steel-green: #5fae9d;
    --steel-green-strong: #89d3bf;

    --glow-blue: rgba(25, 184, 255, 0.38);
    --glow-green: rgba(95, 174, 157, 0.30);
    --glow-mix: rgba(80, 210, 220, 0.20);

    --shadow-deep: rgba(0, 0, 0, 0.65);

    --radius-none: 0;
    --border-width-outer: 2px;
    --border-width-inner: 1px;
}
```

## 12. Règle directrice essentielle

La bonne formule, c’est :

**90% sobriété sombre métallique**
**10% lumière néon contrôlée**

C’est ce contraste qui donnera le côté haut de gamme.

Go, et à l’étape suivante je te fais **le squelette CSS complet de la charte** :
fond global, panneau, bouton, bordures néon, halos et base pour animation au scroll.
