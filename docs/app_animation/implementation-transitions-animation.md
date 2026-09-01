# Spécification d’implémentation — transitions des slides

## Objet du chantier

Implémenter les transitions de Lyrics Slide Show à trois niveaux complémentaires :

1. une transition par défaut enregistrée au niveau général de l’animation ;
2. une transition active modifiable pendant la projection, notamment avec deux nouveaux raccourcis ;
3. un afficheur fiable utilisant le payload complet envoyé par la remote, avec un moteur de transitions modulaire et suffisamment extensible pour les besoins futurs.

Ce document est une consigne d’implémentation. Avant toute modification, examiner le fonctionnement réel du projet et adapter les noms de modèles, vues, événements, payloads, fichiers JavaScript et composants aux conventions existantes. Ne pas créer en parallèle un nouveau système de session, de synchronisation ou de rendu si un mécanisme équivalent existe déjà.

## Résultat fonctionnel attendu

Une animation possède une seule transition par défaut. Au lancement d’une nouvelle session de projection, cette valeur devient la transition active. Pendant le direct, l’animateur peut changer la transition active sans modifier la préférence enregistrée dans l’animation.

Trois transitions sont proposées :

| Identifiant stable conseillé | Libellé | Comportement |
|---|---|---|
| `direct` | Direct | remplacement instantané ; mode sûr |
| `fade` | Fondu | apparition très courte de la nouvelle slide par opacité |
| `wipe_horizontal` | Balayage | révélation de la nouvelle slide de gauche à droite |

`Direct` est la valeur par défaut des animations existantes et le repli obligatoire en cas de valeur inconnue ou d’échec d’une transition.

Il n’existe pas, dans ce chantier, de transition configurée par slide, par bloc ou par chant.

## 1. Transition par défaut de l’animation

### Donnée persistée

Ajouter à l’animation un champ représentant sa transition par défaut. Utiliser des valeurs techniques stables et indépendantes des libellés traduits ou affichés à l’utilisateur.

Contraintes :

- valeur obligatoire ;
- choix limité à `direct`, `fade` et `wipe_horizontal` ;
- valeur par défaut : `direct` ;
- migration des animations existantes vers `direct` ;
- validation côté serveur, même si le formulaire limite déjà les choix.

### Interfaces de création et de modification

Ajouter le choix de la transition :

- lors de la création de l’animation ;
- dans la page existante qui porte les paramètres généraux ou la mise en forme de l’animation.

Le contrôle doit rester simple : un choix parmi les trois transitions, avec `Direct` présélectionné pour une nouvelle animation. Ne pas ajouter de durée, de direction, d’option avancée ou de réglage par slide.

Modifier cette préférence pendant qu’une projection existe ne doit pas modifier silencieusement la transition active de cette session. La nouvelle préférence s’appliquera à la prochaine nouvelle session de projection.

## 2. Transition active pendant la projection

### Cycle de vie

La transition active est un état de la session de projection, pas une modification de l’animation en base de données.

- Nouvelle session : initialiser la transition active avec la préférence de l’animation.
- Changement en live : modifier uniquement l’état de session.
- Sortie de la remote vers la modification de l’animation, puis retour à la remote avec la même clé : conserver la clé de synchronisation et la transition active.
- Rechargement ou reconnexion avec la même session : restaurer la transition active par le mécanisme de persistance déjà utilisé par le projet.
- Nouvelle clé ou nouvelle session : repartir de la préférence enregistrée dans l’animation.

Inspecter le mécanisme actuel de conservation de la clé avant de choisir l’emplacement de cet état. Étendre ce mécanisme plutôt que créer une seconde notion concurrente de session.

### Contrôle visible dans la remote

La remote doit afficher clairement la transition active et permettre de choisir l’une des trois valeurs. Le changement doit être transmis à l’afficheur sans rechargement et sans provoquer de changement visuel de la slide déjà affichée.

Le changement de `fade` vers `wipe_horizontal`, ou inversement, s’applique à la prochaine navigation. Il ne transforme pas une transition déjà commencée en un autre effet.

Le passage à `direct` joue le rôle de débrayage : s’il intervient pendant une transition, finaliser immédiatement et proprement la slide entrante, nettoyer l’état transitoire, puis utiliser `Direct` pour les navigations suivantes.

### Deux nouveaux raccourcis

Ajouter deux actions au système existant de raccourcis clavier et de pédalier. Ne pas coder des touches en dur si les raccourcis sont configurables aujourd’hui.

1. **Transition suivante**
   - cycle obligatoire : `Direct → Fondu → Balayage → Direct` ;
   - met à jour l’indicateur de la remote ;
   - transmet la nouvelle transition active à l’afficheur.

2. **Forcer Direct**
   - sélectionne `Direct` quelle que soit la transition courante ;
   - si `Direct` est déjà actif, l’action reste sans effet secondaire ;
   - sert de retour immédiat au mode sûr.

Réutiliser le mécanisme actuel de déclaration, de personnalisation et d’affichage des raccourcis. Fournir des identifiants d’action stables afin que les affectations enregistrées ne dépendent pas des libellés.

## 3. Contrat entre la remote et l’afficheur

### La remote reste la source des données fraîches

Conserver le fonctionnement par payload complet. Chaque demande d’affichage doit fournir toutes les données nécessaires au rendu de la slide : texte, blocs, styles, couleurs, fond, paramètres du double affichage et toute autre donnée déjà attendue par l’afficheur.

L’afficheur ne doit pas charger toutes les slides dans une pseudo-base JavaScript et ne doit pas devenir la source de vérité du contenu de l’animation.

Cette règle garantit le scénario suivant :

1. une projection est en cours et sa clé reste active ;
2. l’utilisateur quitte la remote pour corriger l’animation ;
3. il revient sur la remote sans recréer la liaison ;
4. il sélectionne la slide corrigée ;
5. le nouveau payload complet est rendu immédiatement par l’afficheur.

Un ordre ne doit jamais être ignoré au seul motif que l’identifiant de slide est identique à celui de la slide courante : son texte, son style ou son image peuvent avoir été modifiés pendant le live.

### Messages métier uniquement

Respecter le protocole actuel autant que possible, mais maintenir une séparation claire entre :

- l’ordre d’afficher un payload complet de slide ;
- l’ordre de changer la transition active.

La remote ne doit pas envoyer d’instructions sur les couches graphiques, l’ordre des `div`, les classes CSS, la fin d’une animation ou l’inversion des buffers. Ces détails appartiennent exclusivement à l’afficheur.

Si le protocole doit évoluer, préserver sa compatibilité avec les messages existants ou prévoir un comportement de repli explicite. Une transition absente ou inconnue doit être interprétée comme `direct`, jamais bloquer la projection.

## 4. Afficheur : rendu à deux couches

### Principe

Conserver deux couches plein écran, A et B, toujours superposées au même emplacement :

- une couche active, actuellement visible ;
- une couche inactive, disponible pour rendre le nouveau payload.

À la réception d’un payload :

1. rendre intégralement le payload dans la couche inactive ;
2. vérifier que la couche entrante est prête ;
3. exécuter la stratégie de transition active ;
4. déclarer la couche entrante comme active ;
5. réinitialiser proprement l’ancienne couche afin qu’elle devienne le prochain buffer inactif.

Les couches ne doivent jamais être replacées côte à côte ou restructurées lors d’un changement de transition. Le DOM stable est une contrainte de robustesse.

### Renderer commun

Il doit exister un seul chemin de rendu du payload vers une couche. Ce renderer reprend toutes les capacités actuelles de l’afficheur, notamment :

- texte et mise en forme ;
- fond uni ou image ;
- affichage simple ;
- affichage double ;
- styles propres aux deux blocs ;
- toute autre particularité déjà prise en charge.

Ne pas créer un renderer par transition. Une transition reçoit deux couches déjà rendues et ne connaît ni les chants, ni les blocs, ni la base de données, ni le protocole de la remote.

Refactorer le rendu existant seulement dans la mesure nécessaire pour le rendre utilisable indifféremment sur A et B. Éviter une réécriture fonctionnelle de l’afficheur dans ce chantier.

## 5. Moteur de transitions modulaire

Prévoir quatre responsabilités distinctes, qui peuvent rester de petits modules ou objets simples :

| Responsabilité | Rôle |
|---|---|
| Renderer | construire une slide dans la couche demandée |
| Registre | déclarer les transitions disponibles et leurs métadonnées |
| Résolveur | choisir l’identifiant de transition à appliquer |
| Moteur | exécuter et nettoyer la stratégie choisie entre les deux couches |

### Registre

Centraliser au minimum, pour chaque transition :

- identifiant stable ;
- libellé ;
- ordre dans le cycle ;
- durée par défaut interne ;
- implémentation associée.

La liste utilisée par le formulaire, la remote et le moteur doit provenir d’une définition cohérente. Éviter de recopier des listes divergentes dans plusieurs fichiers lorsque la pile actuelle permet de les partager proprement.

Il ne s’agit pas de créer un système de plugins dynamiques. Un registre interne sobre suffit.

### Résolveur

Aujourd’hui, le résolveur renvoie simplement la transition active de la session et se replie sur `direct`.

La provenance du choix doit néanmoins rester cachée derrière un point d’entrée unique. Le renderer et les stratégies ne doivent pas lire directement le modèle Animation ni l’état de la remote.

Cette frontière devra permettre plus tard, sans l’implémenter maintenant, de faire évoluer la priorité vers quelque chose comme : choix live, éventuelle transition de slide, éventuelle transition de chant, préférence d’animation, puis `Direct`.

Ne créer aujourd’hui aucun champ, écran ou comportement par slide ou par chant.

### Contrat commun des stratégies

Les trois stratégies doivent respecter le même cycle de vie conceptuel :

- préparer les deux couches ;
- exécuter ou terminer immédiatement ;
- pouvoir être annulées ou finalisées ;
- nettoyer toutes les classes, styles temporaires, temporisateurs et écouteurs ;
- signaler au moteur que la couche entrante est devenue active.

Le choix exact des fonctions et classes doit suivre le style du code existant. L’objectif est d’éviter les conditions `if direct`, `if fade`, etc. dispersées dans l’afficheur.

### Comportement de `Direct`

`Direct` est enregistré comme une stratégie normale afin de respecter le même contrat que les autres, mais il court-circuite toute animation temporelle :

- rendu du payload avec le renderer commun dans la couche inactive ;
- permutation immédiate des couches ;
- aucun timer ;
- aucune attente d’événement CSS ;
- aucune interpolation ;
- nettoyage synchrone de tout état transitoire précédent.

Il ne doit pas posséder un second moteur de rendu ni un élément HTML réservé.

### Comportement de `Fondu`

- La couche sortante reste stable pendant que la couche entrante apparaît par opacité.
- Le contenu ne se déplace pas.
- Durée initiale cible : environ 120 ms, ajustable dans une constante interne après test, avec une plage raisonnable de 100 à 150 ms.
- À la fin, seule la couche entrante reste active et tous les styles temporaires sont retirés.

### Comportement de `Balayage`

- Direction unique dans ce chantier : de gauche à droite.
- La nouvelle slide est révélée progressivement au-dessus de l’ancienne.
- Aucun texte ni fond ne doit glisser, se comprimer ou changer d’échelle.
- Durée initiale cible : environ 180 ms, ajustable dans une constante interne après test, avec une plage raisonnable de 150 à 200 ms.
- Utiliser une technique CSS adaptée aux navigateurs ciblés et limitant les recalculs et repeints, particulièrement avec une image Full HD. Activer d’éventuelles optimisations comme `will-change` seulement pendant l’effet, puis les retirer.

Ne pas ajouter de balayage vertical, de choix de direction, de flou, de zoom, de rotation ou de micro-déplacement.

## 6. Interruptions, commandes rapides et erreurs

Le moteur doit rester déterministe quand l’utilisateur navigue rapidement.

### Nouvelle navigation pendant une transition

Appliquer la règle « dernière demande prioritaire », sans construire une longue file d’attente :

1. finaliser immédiatement et proprement la transition en cours sur sa slide entrante ;
2. rendre le payload le plus récemment demandé dans la couche devenue inactive ;
3. lancer la transition active vers cette nouvelle cible.

Une ancienne fin d’animation ne doit jamais pouvoir inverser les couches après le lancement d’une transition plus récente. Utiliser le mécanisme adapté au projet — jeton d’opération, identifiant monotone, annulation d’écouteur ou équivalent — pour neutraliser les callbacks périmés.

### Erreur de stratégie

Si une transition ne peut pas être résolue, préparée ou terminée :

- nettoyer l’état transitoire ;
- afficher la couche entrante immédiatement ;
- revenir à un état A/B cohérent ;
- utiliser `Direct` comme repli ;
- ne jamais laisser un écran vide, semi-transparent ou partiellement balayé.

Le mode sûr doit être réellement indépendant d’un événement `transitionend` ou d’un timer appartenant aux effets animés.

## 7. Préchargement des images de fond

Le seul cache fonctionnel ajouté à l’afficheur concerne les ressources d’image, pas les slides.

- Réutiliser le cache HTTP du navigateur.
- Précharger et, lorsque l’API du navigateur le permet, décoder les images de fond connues pour l’animation.
- Ne pas dupliquer le texte, les blocs ou les styles de toutes les slides dans l’afficheur.
- Lorsqu’un payload corrigé introduit une nouvelle image non préchargée, lancer immédiatement son chargement et préparer la couche entrante sans casser la projection courante.
- Prévoir un repli vers le comportement actuel si l’image échoue à charger ; une erreur d’image ne doit pas bloquer indéfiniment la navigation.

Examiner d’abord comment les URL d’images sont aujourd’hui transmises et mises en cache. Si l’afficheur ne connaît pas à l’avance les URL de l’animation, un message léger listant uniquement les ressources à précharger peut être ajouté lors du chargement ou du rafraîchissement de la remote. Ce message ne doit contenir aucune copie fonctionnelle des slides et ne doit pas devenir obligatoire pour afficher un payload reçu ensuite.

## 8. Compatibilité et périmètre à préserver

L’implémentation ne doit pas casser :

- la clé existante de synchronisation remote/afficheur ;
- le retour à la remote après modification de l’animation ;
- le payload complet et les corrections visibles immédiatement ;
- l’affichage simple ;
- l’affichage double ;
- les fonds unis et les images ;
- les boutons de navigation et les raccourcis existants ;
- le plein écran et le second écran ;
- les comportements de reconnexion déjà présents.

Ne pas profiter de ce chantier pour introduire :

- des transitions par slide, bloc ou chant ;
- des durées configurables par l’utilisateur ;
- un catalogue étendu d’effets ;
- une base locale des slides dans l’afficheur ;
- un système de plugins ;
- une refonte générale du protocole ou de la session.

## 9. Démarche d’implémentation demandée à Codex

1. Cartographier le fonctionnement existant : modèle Animation, formulaires, création et reprise de la clé, état de la remote, déclaration des raccourcis, transport des messages, structure du payload, renderer et gestion des images.
2. Présenter brièvement les fichiers qui seront modifiés et signaler toute contradiction entre ce document et le code réel.
3. Ajouter le champ et la migration avec `direct` comme valeur sûre.
4. Ajouter le choix dans les interfaces concernées.
5. Étendre l’état live et la synchronisation sans créer une seconde session parallèle.
6. Refactorer le renderer existant juste assez pour rendre dans deux couches interchangeables.
7. Ajouter le registre, le résolveur, le moteur et les trois stratégies.
8. Ajouter les contrôles de remote et les deux actions de raccourci.
9. Ajouter ou adapter le préchargement des seules images de fond.
10. Vérifier les interruptions, les reconnexions, le retour après édition et les replis sur `Direct`.
11. Exécuter les tests existants, ajouter les tests ciblés manquants et rendre compte des vérifications manuelles nécessaires sur vidéoprojecteur.

## 10. Critères d’acceptation

### Modèle et interfaces

- Une animation nouvelle peut être créée avec l’une des trois transitions.
- `Direct` est présélectionné par défaut.
- Une animation existante reste utilisable après migration et utilise `Direct`.
- La préférence peut être modifiée sans ajouter de réglage par slide ou par chant.

### Session et remote

- Une nouvelle session démarre avec la préférence de l’animation.
- Le changement live ne modifie pas l’animation en base.
- Le raccourci « Transition suivante » respecte exactement l’ordre défini.
- Le raccourci « Forcer Direct » ramène immédiatement au mode sûr.
- L’indicateur visible de la remote reste synchronisé avec la transition active.
- Quitter la remote pour corriger l’animation puis y revenir conserve la clé et l’état live de la session.

### Afficheur

- Le payload complet reste la source du rendu.
- Une slide corrigée est réaffichée même si son identifiant n’a pas changé.
- Les couches A/B restent superposées et ne sont pas restructurées lors d’un changement de transition.
- `Direct`, `Fondu` et `Balayage` utilisent le même renderer.
- `Direct` ne dépend d’aucun timer ni événement de fin d’animation.
- Un changement de transition n’altère pas la slide déjà affichée.
- Des navigations rapides ne laissent jamais l’afficheur dans un état intermédiaire.
- Une transition inconnue ou en erreur finit en affichage `Direct` de la cible.
- Aucun écran noir, fond absent durablement, contenu semi-transparent ou ancienne slide résiduelle n’apparaît.

### Performances et validation manuelle

Tester au minimum :

- fonds unis ;
- images Full HD déjà préchargées ;
- image nouvelle reçue après une correction live ;
- affichage simple et double ;
- navigation rapide et navigation non linéaire ;
- changement de transition pendant le live ;
- forçage de `Direct` pendant un fondu et pendant un balayage ;
- départ et retour sur la remote avec la même clé ;
- reconnexion de l’afficheur ;
- plein écran sur le second écran ;
- navigateurs officiellement supportés par le projet ;
- un ordinateur peu puissant comparable à un ancien portable utilisé avec un vidéoprojecteur.

Le test de performance attendu est pragmatique : l’enchaînement rapide de slides avec une image Full HD ne doit pas provoquer de saccades importantes, de retard accumulé ou de hausse anormale et durable de la charge. Si `Fondu` ou `Balayage` se comporte mal, `Forcer Direct` doit restaurer immédiatement une projection stable.

## Définition de terminé

Le chantier est terminé lorsque les trois transitions sont sélectionnables au niveau de l’animation, modifiables en live avec les deux nouvelles actions de raccourci, correctement exécutées par un afficheur A/B alimenté par des payloads complets, et couvertes par les tests pertinents.

L’implémentation doit laisser un point d’extension clair pour ajouter une stratégie ou modifier plus tard la provenance du choix de transition, sans avoir implémenté prématurément les transitions par chant ou par slide.
