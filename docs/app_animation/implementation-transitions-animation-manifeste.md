# Spécification d’implémentation — manifeste des transitions

## Objet du chantier

Ajouter à Lyrics Slide Show un **manifeste technique central des transitions**, stocké dans un fichier JSON.

Ce manifeste doit devenir la source de vérité permettant de savoir :

* quelles transitions existent ;
* lesquelles sont actuellement activées ;
* dans quel ordre elles sont proposées ;
* quels paramètres techniques simples leur sont associés.

Il doit notamment alimenter :

* le modèle et les formulaires Django ;
* les templates de création et modification d’une animation ;
* la remote ;
* le cycle « transition suivante » ;
* les données runtime envoyées à la remote ;
* les paramètres nécessaires au moteur de transitions côté afficheur.

Le manifeste ne contient pas l’algorithme graphique des transitions.

Les implémentations restent dans le JavaScript de l’afficheur.

---

# 1. Principe général

Séparer clairement :

## Manifeste des transitions

Le manifeste JSON décrit :

> quelles transitions Lyrics Slide Show expose et avec quels paramètres techniques.

## Registre des stratégies JS

L’afficheur décrit :

> comment exécuter chaque transition.

Conceptuellement :

```text
Manifeste JSON
      ↓
Django
      ↓
formulaires + remote
      ↓
ordre d'affichage
      ↓
transition id + paramètres
      ↓
afficheur
      ↓
registre des stratégies JS
```

---

# 2. Emplacement

Créer un fichier technique dédié au catalogue des transitions.

Par exemple :

`app_animation/transitions.json`

ou un emplacement équivalent cohérent avec l’organisation réelle du projet.

Ce fichier est :

* versionné avec le code ;
* lu par Django ;
* non modifiable par les utilisateurs ;
* non stocké en base de données.

Il ne s’agit pas d’un fichier de documentation.

---

# 3. Structure JSON

Prévoir une structure JSON extensible.

Exemple conceptuel :

```json
{
  "default": "direct",
  "transitions": [
    {
      "id": "direct",
      "label": "Direct",
      "enabled": true,
      "order": 0,
      "params": {
        "duration_ms": 0
      }
    },
    {
      "id": "fade",
      "label": "Fade",
      "enabled": true,
      "order": 1,
      "params": {
        "duration_ms": 120
      }
    },
    {
      "id": "wipe",
      "label": "Horizontal wipe",
      "enabled": true,
      "order": 2,
      "params": {
        "duration_ms": 180,
        "direction": "left_to_right"
      }
    }
  ]
}
```

La structure exacte peut être adaptée légèrement aux conventions du projet, mais conserver les principes décrits dans cette spécification.

---

# 4. Identifiants des transitions

Les identifiants techniques initiaux sont :

* `direct`
* `fade`
* `wipe`

Ne pas utiliser `wipe_horizontal`.

L’identifiant `wipe` est volontairement plus générique afin de permettre ultérieurement d’ajouter plusieurs directions sans changer l’identité fonctionnelle de la transition.

Les identifiants sont :

* stables ;
* techniques ;
* en anglais ;
* indépendants des traductions affichées à l’utilisateur.

Ils peuvent être persistés en base dans les animations.

---

# 5. Noms et internationalisation

Ne jamais mettre dans le manifeste un libellé uniquement français tel que :

```json
"label": "Balayage"
```

Deux approches sont acceptables.

## Option A — nom anglais

Par exemple :

```json
"label": "Wipe"
```

Django réalise ensuite la traduction vers le français.

## Option B — clé i18n

Par exemple :

```json
"label_key": "transition_wipe"
```

Django ou le frontend résout ensuite cette clé via le système i18n existant.

Privilégier l’approche qui s’intègre le mieux au fonctionnement actuel de l’internationalisation du projet.

Le principe obligatoire est :

> Le manifeste ne doit jamais devenir une source de libellés français non internationalisables.

Les traductions doivent continuer à utiliser le mécanisme i18n existant du projet.

---

# 6. Champs communs

Chaque transition possède au minimum :

## `id`

Identifiant technique stable.

Exemple :

```json
"id": "fade"
```

## `enabled`

Indique si la transition est actuellement disponible dans Lyrics Slide Show.

Exemple :

```json
"enabled": true
```

## `order`

Détermine l’ordre d’affichage et l’ordre du cycle « transition suivante ».

Exemple :

```json
"order": 1
```

## Libellé

Soit :

```json
"label": "Fade"
```

soit une clé de traduction telle que :

```json
"label_key": "transition_fade"
```

selon l’intégration i18n retenue.

## `params`

Objet contenant les paramètres techniques propres à la transition.

Exemple :

```json
"params": {
  "duration_ms": 120
}
```

---

# 7. Transition par défaut

Le manifeste contient :

```json
"default": "direct"
```

Cette valeur constitue la transition par défaut du système.

Le code Django ne doit pas maintenir une seconde définition indépendante de cette valeur.

`direct` reste également le fallback obligatoire en cas d’erreur ou de valeur inconnue.

---

# 8. Activation et désactivation

Le champ :

```json
"enabled": false
```

permet de mettre une transition en stand-by sans supprimer son code.

Une transition désactivée :

* n’est plus proposée dans les formulaires ;
* n’est plus proposée dans la remote ;
* n’apparaît plus dans le cycle « transition suivante » ;
* reste éventuellement implémentée dans le JavaScript ;
* peut être réactivée ultérieurement en modifiant uniquement le manifeste.

Ce comportement permet de désactiver rapidement une transition problématique sans supprimer son implémentation.

---

# 9. Paramètres techniques

Le manifeste doit pouvoir contenir quelques paramètres techniques simples propres aux transitions.

Dans cette première version, utiliser au minimum :

## `duration_ms`

Durée de la transition en millisecondes.

Exemples :

```json
"duration_ms": 0
```

pour `direct`.

```json
"duration_ms": 120
```

pour `fade`.

```json
"duration_ms": 180
```

pour `wipe`.

Le JavaScript ne doit pas maintenir une deuxième valeur codée en dur différente.

La stratégie doit utiliser la valeur provenant du manifeste.

---

# 10. Paramètre `direction` de `wipe`

La transition :

```text
wipe
```

est actuellement implémentée uniquement :

```text
left_to_right
```

Le manifeste doit donc pouvoir contenir :

```json
"params": {
  "duration_ms": 180,
  "direction": "left_to_right"
}
```

Dans cette première version :

* seule `left_to_right` est supportée ;
* ne pas ajouter de sélecteur utilisateur de direction ;
* ne pas créer de liste complexe de directions disponibles ;
* ne pas anticiper toute l’architecture future.

Le paramètre existe afin que l’identité `wipe` ne soit pas liée définitivement à une orientation horizontale ou à une direction précise.

Plus tard, si l’implémentation JS supporte d’autres valeurs, le manifeste pourra utiliser par exemple :

```text
right_to_left
top_to_bottom
bottom_to_top
```

sans avoir à renommer la transition elle-même.

---

# 11. Paramètres spécifiques à certaines transitions

Tous les paramètres ne doivent pas être présents sur toutes les transitions.

Par exemple :

`fade` n’a pas besoin de `direction`.

Éviter les structures telles que :

```json
{
  "direction": null,
  "zoom": null,
  "blur": null
}
```

sur toutes les transitions.

Chaque transition possède uniquement les paramètres dont elle a réellement besoin.

L’objet `params` permet cette extensibilité.

---

# 12. Lecture du manifeste côté Django

Créer une petite couche de lecture/validation côté Django.

Elle doit permettre au reste de l’application d’obtenir facilement :

* toutes les transitions ;
* uniquement les transitions activées ;
* la transition par défaut ;
* les identifiants valides ;
* les `choices` Django ;
* le catalogue runtime destiné à la remote ;
* la configuration d’une transition par identifiant.

Éviter de relire et retraiter manuellement le JSON dans plusieurs vues ou formulaires.

Un module Python simple chargé de lire et exposer le manifeste suffit.

Ne pas créer une architecture de configuration complexe.

---

# 13. Validation du manifeste

Valider au minimum :

* présence de `default` ;
* présence de `transitions` ;
* identifiants uniques ;
* identifiants non vides ;
* ordre valide ;
* `enabled` booléen ;
* `params` objet ;
* `duration_ms` entier positif ou nul ;
* transition par défaut existante ;
* `direct` existante ;
* `direct` activée ;
* `duration_ms` de `direct` égal à `0`.

Pour `wipe`, si `direction` est présente dans cette première version, accepter uniquement :

```text
left_to_right
```

Une erreur de configuration doit être détectable clairement pendant les tests ou au chargement approprié de l’application.

Ne pas laisser une erreur de JSON produire silencieusement des comportements incohérents.

---

# 14. Utilisation par le modèle Animation

Le champ de transition par défaut d’une animation doit utiliser les identifiants du manifeste.

Les choix proposés doivent être construits uniquement à partir des transitions :

```text
enabled = true
```

La valeur système par défaut doit provenir du champ :

```json
"default"
```

du manifeste.

---

# 15. Cas d’une transition désactivée déjà enregistrée en base

Il est possible qu’une animation existante contienne :

```text
wipe
```

alors que `wipe` a ensuite été désactivée dans le manifeste.

Ce cas ne doit pas casser l’animation.

Au runtime :

> une transition persistée mais actuellement désactivée doit se replier sur `direct`.

La remote ne doit pas proposer cette transition comme choix actif normal.

Ne pas exiger une migration de base simplement parce qu’une transition a été temporairement désactivée.

---

# 16. Formulaires et templates

Les formulaires de création et modification d’une animation doivent obtenir leur liste depuis le manifeste via la couche Django.

Les templates ne doivent jamais contenir manuellement :

```text
Direct
Fade
Wipe
```

Les templates doivent afficher les choix fournis par Django.

Ajouter ou retirer une transition activée dans le manifeste doit modifier automatiquement les options visibles.

---

# 17. Remote

La remote reçoit depuis Django les transitions activées.

Exemple conceptuel de runtime :

```json
{
  "transitions": [
    {
      "id": "direct",
      "label": "Direct",
      "params": {
        "duration_ms": 0
      }
    },
    {
      "id": "fade",
      "label": "Fondu",
      "params": {
        "duration_ms": 120
      }
    },
    {
      "id": "wipe",
      "label": "Balayage",
      "params": {
        "duration_ms": 180,
        "direction": "left_to_right"
      }
    }
  ]
}
```

Les libellés peuvent ici être déjà traduits par Django avant d’être envoyés au JavaScript.

La remote ne doit pas posséder sa propre liste indépendante.

---

# 18. Cycle « Transition suivante »

Le cycle doit utiliser l’ordre des transitions activées fourni par le manifeste.

Avec le manifeste initial :

```text
direct → fade → wipe → direct
```

Ne pas coder cette succession avec des conditions spécifiques.

Le comportement doit rester générique.

Ainsi, si plus tard le manifeste devient :

```text
direct
fade
wipe
dissolve
```

la remote doit automatiquement produire :

```text
direct → fade → wipe → dissolve → direct
```

sans modification de la logique de cycle.

---

# 19. Données envoyées à l’afficheur

Chaque nouvel ordre d’affichage doit contenir suffisamment d’informations pour que l’afficheur exécute la transition demandée.

Au minimum :

* identifiant de transition ;
* paramètres techniques nécessaires.

Conceptuellement :

```json
{
  "transition": {
    "id": "wipe",
    "params": {
      "duration_ms": 180,
      "direction": "left_to_right"
    }
  }
}
```

La structure exacte doit être adaptée au protocole actuel.

L’afficheur ne doit pas devoir charger directement le fichier JSON.

La remote reste la source de vérité du runtime et transmet la configuration nécessaire avec l’ordre d’affichage.

---

# 20. Registre JS de l’afficheur

L’afficheur possède un registre de stratégies.

Conceptuellement :

```text
direct → DirectStrategy
fade   → FadeStrategy
wipe   → WipeStrategy
```

Le registre ne doit pas recopier :

* le libellé ;
* l’ordre ;
* `enabled` ;
* la durée ;
* la direction configurée.

Il ne contient que la correspondance entre :

```text
transition id
```

et :

```text
implémentation graphique
```

---

# 21. Consommation des paramètres par les stratégies JS

Les stratégies doivent utiliser les paramètres transmis.

Par exemple, `FadeStrategy` doit utiliser :

```text
duration_ms
```

reçu depuis le manifeste via la remote.

`WipeStrategy` doit utiliser :

* `duration_ms` ;
* `direction`.

Éviter d’avoir simultanément :

```text
duration_ms = 180
```

dans le manifeste et :

```text
const duration = 180
```

dans la stratégie JS.

Le manifeste doit être réellement utilisé comme configuration technique.

---

# 22. Responsabilité du JavaScript

Le manifeste décrit les paramètres.

Le JavaScript conserve la responsabilité de leur interprétation.

Par exemple, pour :

```json
"direction": "left_to_right"
```

le manifeste ne doit pas contenir :

* CSS ;
* `clip-path` ;
* classes DOM ;
* fonctions ;
* logique d’animation.

Ces détails restent entièrement dans `WipeStrategy`.

---

# 23. Valeur inconnue ou non supportée

Si l’afficheur reçoit :

```text
transition.id = quelque_chose
```

sans stratégie correspondante :

* loguer éventuellement un warning ;
* afficher immédiatement le frame entrant ;
* utiliser le comportement `direct`.

Une erreur de stratégie ne doit jamais bloquer la projection.

---

# 24. Cohérence manifeste / stratégies

Ajouter des tests permettant de détecter le cas suivant :

> une transition est activée dans le manifeste mais aucune stratégie JS correspondante n’existe.

L’objectif est d’éviter qu’une transition apparaisse dans la remote sans être réellement exécutable.

Ne pas créer pour cela un framework complexe.

Une vérification simple adaptée à l’architecture du projet suffit.

---

# 25. Ajout futur d’une transition

L’ajout d’une nouvelle transition doit idéalement nécessiter seulement :

## 1. Développer sa stratégie JS

Exemple :

```text
DissolveStrategy
```

## 2. L’enregistrer dans le registre JS

Exemple :

```text
dissolve → DissolveStrategy
```

## 3. Ajouter sa déclaration dans le manifeste

Exemple :

```json
{
  "id": "dissolve",
  "label": "Dissolve",
  "enabled": true,
  "order": 3,
  "params": {
    "duration_ms": 150
  }
}
```

Aucune modification spécifique ne doit normalement être nécessaire dans :

* le formulaire de création ;
* le formulaire de modification ;
* les templates ;
* le sélecteur de la remote ;
* le cycle « transition suivante ».

---

# 26. Mise en stand-by

Une transition peut être mise temporairement hors service simplement avec :

```json
"enabled": false
```

Son code reste présent.

Elle disparaît des interfaces utilisateur.

Cette possibilité est un objectif explicite de l’architecture.

Ne pas demander au développeur de supprimer la stratégie JS lorsqu’une transition est temporairement désactivée.

---

# 27. Pas de configuration utilisateur avancée

Les paramètres du manifeste sont des paramètres techniques de l’application.

Ils ne sont pas des préférences utilisateur.

Dans ce chantier, ne pas exposer à l’utilisateur :

* `duration_ms` ;
* `direction` ;
* ou les futurs paramètres internes.

L’utilisateur choisit seulement une transition.

Le manifeste détermine comment cette transition est configurée techniquement.

---

# 28. Pas de base de données

Ne créer aucune table de transitions.

Le manifeste décrit des capacités du code déployé.

Une transition ne peut être réellement disponible que si son implémentation JS correspondante existe.

Le stockage JSON versionné est donc volontaire.

---

# 29. Pas de système de plugins

Ne pas introduire :

* chargement dynamique de modules ;
* découverte automatique de plugins ;
* configuration administrable ;
* upload de transitions ;
* moteur générique décrivant les animations dans le JSON.

Le manifeste est un simple fichier de configuration technique versionné.

---

# 30. Tests attendus

Ajouter des tests ciblés.

## Validation du manifeste

Vérifier :

* JSON valide ;
* IDs uniques ;
* `direct`, `fade`, `wipe` présents ;
* `wipe_horizontal` absent ;
* `direct` est la valeur par défaut ;
* `direct` est activée ;
* ordres valides ;
* `duration_ms` valides.

## Configuration initiale

Vérifier :

```text
direct.duration_ms = 0
fade.duration_ms ≈ 120
wipe.duration_ms ≈ 180
wipe.direction = left_to_right
```

Les valeurs exactes peuvent suivre celles retenues dans la spécification générale des transitions.

## Enabled

Vérifier qu’une transition avec :

```json
"enabled": false
```

n’est pas exposée dans les choix utilisateur.

## Django

Vérifier que :

* les formulaires utilisent le manifeste ;
* la valeur par défaut provient du manifeste ;
* une transition désactivée n’est pas proposée.

## Runtime remote

Vérifier que :

* le catalogue actif est transmis ;
* les labels sont correctement internationalisés ;
* l’ordre est respecté ;
* les paramètres nécessaires sont disponibles.

## Cycle

Vérifier que le cycle utilise dynamiquement les transitions actives.

## Afficheur

Vérifier :

* `direct`, `fade` et `wipe` possèdent une stratégie ;
* les paramètres transmis sont utilisés ;
* un ID inconnu retombe sur `direct`.

---

# 31. Critères d’acceptation

Le chantier est terminé lorsque :

* un fichier JSON technique central décrit les transitions ;
* aucune table SQL n’a été créée ;
* les identifiants sont `direct`, `fade` et `wipe` ;
* aucun identifiant `wipe_horizontal` n’est introduit ;
* le manifeste n’utilise jamais uniquement des libellés français ;
* les libellés sont en anglais ou associés à une clé i18n ;
* les templates et formulaires tirent leurs choix du manifeste ;
* la remote tire sa liste et son ordre du manifeste ;
* `enabled` permet de mettre une transition en stand-by ;
* `duration_ms` est configurable dans le manifeste ;
* `wipe` possède actuellement `direction = left_to_right` ;
* le JavaScript utilise réellement ces paramètres ;
* les stratégies restent codées côté afficheur ;
* une transition inconnue retombe sur `direct` ;
* l’ajout futur d’une transition ne nécessite normalement aucune modification spécifique des templates ou de la logique générique de la remote.

## Principe final

Le manifeste répond à la question :

> **Quelles transitions sont actuellement disponibles et comment sont-elles paramétrées ?**

Le registre JavaScript répond à la question :

> **Comment exécuter chacune de ces transitions ?**

Cette séparation doit rester simple, technique et facilement extensible.
