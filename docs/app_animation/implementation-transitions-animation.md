# Specification d'implementation - transitions de projection

## Objet du chantier

Ce document decrit le futur chantier de mise en place des transitions visuelles pendant une projection `Lyrics Slide Show`.

Il doit guider l'implementation sans casser le fonctionnement actuel de `app_animation`.
L'objectif est d'introduire un mecanisme maintenable, capable d'accueillir plus tard de nouvelles transitions par evolution fonctionnelle, sans devoir reconstruire tout le rendu ou ajouter des couches paralleles.

Ce chantier concerne trois niveaux complementaires :

1. une transition par defaut enregistree au niveau general de l'`Animation` ;
2. une transition active modifiable pendant le live dans la `remote` ;
3. un afficheur capable de passer proprement d'un frame visuel complet a un autre avec un moteur de transitions modulaire.

Avant toute implementation, examiner le fonctionnement reel du projet et adapter les noms de modeles, vues, evenements, payloads, fichiers JavaScript et composants aux conventions existantes.
Ne pas creer en parallele un nouveau systeme de session, de synchronisation, de rendu ou de prechargement si un mecanisme equivalent existe deja.

## Philosophie runtime : animation, remote, afficheur

Dans `Lyrics Slide Show`, les responsabilites sont distinctes.

### Animation

Une `Animation` est une configuration persistante :

- playlist ordonnee ;
- parametres visuels par defaut ;
- overrides par chant et par couplet ;
- preference de transition par defaut.

L'animation en base ne represente pas l'etat live courant.
Modifier la preference de transition d'une animation pendant qu'une projection existe ne modifie pas silencieusement la transition active de cette session live.
La nouvelle preference s'applique a la prochaine nouvelle session de projection.

### Remote

La remote `lyrics_slide_show.html` est la console du manager et l'autorite fonctionnelle du runtime.

Elle possede :

- l'etat live de projection ;
- la cle de synchronisation avec l'afficheur ;
- les donnees fraiches servant au rendu ;
- la transition active ;
- l'indicateur visible de transition ;
- les changements manuels et les raccourcis.

La remote construit et envoie les ordres metier a l'afficheur.
Chaque nouvel ordre d'affichage doit transporter le frame complet a rendre et la transition a utiliser pour passer du frame actuellement visible au nouveau frame.

### Afficheur

L'afficheur `lyrics_slide_show_display.html` est une surface de rendu.

Il ne doit pas :

- reconstruire l'etat metier ;
- corriger la navigation recue ;
- charger toutes les slides dans une pseudo-base JavaScript ;
- devenir la source de verite du contenu de l'animation ;
- conserver un etat metier de transition ayant priorite sur la remote.

L'afficheur applique le dernier ordre valide recu.
Si un message d'affichage indique une transition, cette valeur fait foi, meme si l'afficheur possede localement une ancienne valeur.
Une transition absente, inconnue ou inutilisable est interpretee comme `direct`.

## Resultat fonctionnel attendu

Une animation possede une seule transition par defaut.
Au lancement d'une nouvelle session de projection, cette valeur initialise la transition active de la remote.
Pendant le direct, l'animateur peut changer la transition active sans modifier la preference enregistree dans l'animation.

Trois transitions sont proposees :

| Identifiant stable | Libelle | Comportement |
|---|---|---|
| `direct` | Direct | remplacement instantane ; mode sur |
| `fade` | Fondu | apparition tres courte du nouveau frame par opacite |
| `wipe` | Balayage | revelation du nouveau frame de gauche a droite |

`Direct` est :

- la valeur par defaut des animations existantes ;
- la valeur selectionnee par l'action live `Forcer Direct` ;
- le repli obligatoire en cas de valeur absente, inconnue ou d'echec d'une strategie.

Le cycle de l'action `Transition suivante` est strictement :

```text
Direct -> Fondu -> Balayage -> Direct
```

Il n'existe pas, dans ce chantier, de transition configuree par slide, par bloc ou par chant.
Aucune duree, direction ou option avancee n'est configurable par l'utilisateur.

## 1. Transition par defaut de l'animation

### Donnee persistee

Ajouter a l'`Animation` un champ representant sa transition par defaut.
Utiliser des valeurs techniques stables et independantes des libelles traduits ou affiches.

Contraintes :

- valeur obligatoire ;
- choix limite a `direct`, `fade` et `wipe` ;
- valeur par defaut : `direct` ;
- migration des animations existantes vers `direct` ;
- validation cote serveur, meme si le formulaire limite deja les choix.

### Interfaces de creation et modification

Ajouter le choix de la transition :

- lors de la creation de l'animation ;
- dans la page existante qui porte les parametres generaux ou la mise en forme de l'animation.

Le controle doit rester simple : un choix parmi les trois transitions, avec `Direct` preselectionne pour une nouvelle animation.
Ne pas ajouter de duree, de direction, d'option avancee ou de reglage par slide.

## 2. Transition active dans la remote

La transition active est un etat live gere par la remote, pas une modification de l'animation en base et pas un etat metier autonome de l'afficheur.

Cycle de vie :

- nouvelle session : initialiser la transition active avec la preference de l'animation ;
- changement live : modifier uniquement l'etat runtime de la remote ;
- retour a la remote avec la meme cle : conserver la cle de synchronisation et la transition active via le mecanisme de persistance deja utilise ;
- rechargement de la remote avec la meme session : restaurer la transition active depuis cet etat ;
- nouvelle cle ou nouvelle session : repartir de la preference enregistree dans l'animation.

Inspecter le mecanisme actuel de conservation de la cle et de l'etat local avant de choisir l'emplacement de cette valeur.
Etendre ce mecanisme plutot que creer une seconde notion concurrente de session.

### Controle visible

La remote doit afficher clairement la transition active et permettre de choisir l'une des trois valeurs.

Changer la transition active :

- met a jour l'indicateur de la remote ;
- persiste l'etat live de la remote selon le mecanisme existant ;
- n'altere pas visuellement le frame deja affiche ;
- s'applique au prochain ordre d'affichage envoye par la remote.

La remote n'a pas besoin d'envoyer une commande separee a l'afficheur uniquement pour annoncer que la transition active a change.
Pour executer un changement d'ecran, l'afficheur utilise la transition incluse dans l'ordre d'affichage lui-meme.

### Raccourcis

Ajouter deux actions au systeme existant de raccourcis clavier et de pedalier.
Ne pas coder des touches en dur si les raccourcis sont configurables aujourd'hui.

1. `Transition suivante`
   - cycle obligatoire : `Direct -> Fondu -> Balayage -> Direct` ;
   - met a jour l'indicateur de la remote ;
   - modifie la transition active pour les prochains ordres d'affichage.

2. `Forcer Direct`
   - selectionne `Direct` quelle que soit la transition courante ;
   - si `Direct` est deja actif, l'action reste sans effet secondaire ;
   - modifie la transition active pour les prochains ordres d'affichage.

Dans cette premiere implementation, `Forcer Direct` n'a pas a interrompre une transition deja commencee.
Les transitions prevues sont tres courtes ; une transition deja lancee peut aller jusqu'a son terme normal.
Les vraies nouvelles commandes de navigation rapides restent en revanche gerees par la regle "derniere demande prioritaire".

Reutiliser le mecanisme actuel de declaration, personnalisation et affichage des raccourcis.
Fournir des identifiants d'action stables afin que les affectations enregistrees ne dependent pas des libelles.

## 3. Contrat remote vers afficheur

### Ordres d'affichage complets

La remote reste la source des donnees fraiches.
Chaque nouvel ordre d'affichage doit fournir toutes les donnees necessaires au rendu du nouveau frame :

- mode du frame ;
- texte brut ;
- blocs gauche et droit si necessaire ;
- styles resolus ;
- couleurs ;
- police, taille, poids et padding ;
- fond uni ou image ;
- donnees du QR code ;
- toute autre donnee deja attendue par l'afficheur.

Le message d'affichage contient conceptuellement :

```text
ordre d'affichage = frame complet a rendre + transition demandee
```

Le protocole exact doit rester adapte au code existant.
L'important est que l'afficheur puisse rendre le frame entrant et savoir quelle transition appliquer depuis le message lui-meme.

Cette regle garantit le scenario suivant :

1. une projection est en cours et sa cle reste active ;
2. l'utilisateur quitte la remote pour corriger l'animation ;
3. il revient sur la remote sans recreer la liaison ;
4. il selectionne la slide corrigee ;
5. la remote envoie un nouveau payload complet ;
6. l'afficheur rend immediatement les donnees corrigees.

Un ordre ne doit jamais etre ignore au seul motif que l'identifiant de slide, le `projectionIndex`, le chant ou le texte semble identique au frame courant.

### Messages metier uniquement

La remote envoie des ordres metier, pas des instructions graphiques internes.

Elle ne doit pas envoyer :

- l'ordre des couches A/B ;
- les classes CSS temporaires ;
- la fin d'une animation ;
- l'inversion des buffers ;
- des instructions de `transitionend` ;
- la structure interne des `div` de l'afficheur.

Ces details appartiennent exclusivement a l'afficheur.

### Heartbeat

Le heartbeat maintient ou verifie la liaison.
Il peut transporter l'etat courant pour permettre une resynchronisation ou une restauration technique.

Regle obligatoire :

```text
La reception d'un heartbeat ne doit jamais declencher ni rejouer une transition visuelle.
```

Un heartbeat n'est pas une nouvelle navigation.
Le moteur de transition doit distinguer un ordre d'affichage reel d'un message de presence ou de maintenance.

### Deduplication des messages

Le transport peut faire transiter un meme ordre logique par plusieurs mecanismes, par exemple `BroadcastChannel` puis fallback `localStorage`.
L'afficheur doit traiter un meme message logique une seule fois.

S'appuyer sur l'identifiant unique deja present dans les messages, actuellement le `nonce`, ou sur le mecanisme equivalent existant au moment de l'implementation.

Regles :

- un meme `nonce` ne produit qu'une seule execution ;
- un doublon recu via deux transports differents est ignore apres la premiere execution ;
- la deduplication ne se base jamais sur l'identifiant de slide, le `projectionIndex`, le chant, le texte ou le contenu du frame ;
- deux messages differents doivent toujours pouvoir etre executes meme s'ils visent la meme slide ou le meme contenu.

Cette distinction est indispensable pour permettre une correction live puis la reprojection immediate du meme ecran avec des donnees modifiees.

## 4. Frames visuels concernes

Les transitions concernent le passage :

```text
frame actuellement visible -> nouveau frame
```

Elles ne concernent pas uniquement les slides contenant des paroles.

Tous les modes d'affichage qui resultent d'un nouvel ordre de projection doivent pouvoir etre atteints avec la transition active, notamment :

- slide simple ;
- slide double ;
- ecran noir ;
- QR code ;
- rappel F11 ;
- autres frames visuels existants ;
- `idle` si son affichage resulte d'un ordre reel.

L'ecran noir n'est pas une commande d'arret d'urgence des transitions.
C'est un frame normal de projection permettant de ne rien afficher lorsque necessaire.
Il beneficie donc de la transition active comme les autres frames.

## 5. Afficheur : rendu A/B de frames complets

### Principe

Conserver deux couches plein ecran, A et B, toujours superposees au meme emplacement :

- une couche active, actuellement visible ;
- une couche inactive, disponible pour rendre le nouveau frame.

Ces couches representent deux etats visuels complets de l'afficheur :

- frame sortant ;
- frame entrant.

Elles ne sont pas seulement des "couches de slide".

A la reception d'un ordre d'affichage valide :

1. dedupliquer le message ;
2. resoudre la transition demandee depuis le message, avec repli `direct` ;
3. rendre integralement le frame entrant dans la couche inactive ;
4. verifier que la couche entrante est prete autant que le permet le navigateur ;
5. executer la strategie entre couche sortante et couche entrante ;
6. declarer la couche entrante comme active ;
7. nettoyer l'ancienne couche afin qu'elle devienne le prochain buffer inactif.

Les couches ne doivent jamais etre replacees cote a cote ou restructurees lors d'un changement de transition.
Le DOM stable est une contrainte de robustesse.

### Renderer commun

Il doit exister un seul chemin de rendu du frame vers une couche.
Ce renderer reprend toutes les capacites actuelles de l'afficheur, notamment :

- attente / idle ;
- slide simple ;
- slide double ;
- ecran noir ;
- QR code ;
- rappel F11 ;
- texte brut via `textContent` ;
- styles resolus ;
- fonds unis et images.

Ne pas creer un renderer par transition.
Une transition recoit deux couches deja rendues et ne connait pas la structure fonctionnelle du frame.

Une strategie de transition ne doit connaitre :

- ni les chants ;
- ni les blocs ;
- ni le mode double ;
- ni le QR code ;
- ni le noir ;
- ni la base de donnees ;
- ni le protocole de la remote.

### Mode double a preserver strictement

Le mode double fonctionne aujourd'hui et doit etre considere comme reference fonctionnelle.

Le refactoring du renderer necessaire aux couches A/B doit reproduire strictement le comportement actuel des modes simple et double.
Le chantier des transitions ne doit modifier :

- ni les regles fonctionnelles du mode double ;
- ni les styles ;
- ni la repartition des blocs ;
- ni le choix des couleurs ;
- ni les polices ;
- ni les tailles ;
- ni les fonds ;
- ni les espacements.

Le renderer actuel peut etre restructure juste assez pour rendre le meme resultat dans la couche A ou dans la couche B.
Il ne doit pas etre corrige, reinterprete ou redessine dans ce chantier.

## 6. Moteur de transitions modulaire

Prevoir quatre responsabilites distinctes, qui peuvent rester de simples fonctions ou de petits objets si cela correspond mieux au code existant :

| Responsabilite | Role |
|---|---|
| Renderer | construire un frame complet dans une couche demandee |
| Registre | declarer les transitions disponibles et leurs metadonnees |
| Resolveur | choisir l'identifiant de transition a appliquer |
| Moteur | executer et nettoyer la strategie choisie entre deux couches |

Ce decoupage doit permettre plus tard d'ajouter une strategie ou de faire evoluer la provenance du choix de transition.
Il ne s'agit pas de creer un systeme de plugins dynamiques.

### Registre

Centraliser au minimum, pour chaque transition :

- identifiant stable ;
- libelle ;
- ordre dans le cycle ;
- duree par defaut interne ;
- implementation associee.

La liste utilisee par le formulaire, la remote et le moteur doit provenir d'une definition coherente.
Eviter de recopier des listes divergentes dans plusieurs fichiers lorsque la pile actuelle permet de les partager proprement.

Transitions disponibles :

- `direct` ;
- `fade` ;
- `wipe`.

### Resolveur

Aujourd'hui, le resolveur applique la transition demandee dans le message d'affichage et se replie sur `direct`.

La provenance du choix doit rester cachee derriere un point d'entree unique.
Le renderer et les strategies ne lisent pas directement le modele `Animation`, l'etat local de la remote ou un eventuel etat local de l'afficheur.

Cette frontiere devra permettre plus tard, sans l'implementer maintenant, de faire evoluer la priorite vers quelque chose comme :

```text
choix live de la remote -> eventuelle transition de slide -> eventuelle transition de chant -> preference d'animation -> Direct
```

Ne creer aujourd'hui aucun champ, ecran ou comportement par slide, par bloc ou par chant.

### Contrat commun des strategies

Les trois strategies respectent le meme cycle de vie conceptuel :

- preparer les deux couches visuelles ;
- executer ou terminer immediatement ;
- pouvoir etre annulees ou neutralisees par une nouvelle commande plus recente ;
- nettoyer toutes les classes, styles temporaires, temporisateurs et ecouteurs ;
- signaler au moteur que la couche entrante est devenue active.

Le choix exact des fonctions et classes doit suivre le style du code existant.
L'objectif est d'eviter les conditions `if direct`, `if fade`, etc. dispersees dans l'afficheur.

### Direct

`Direct` est enregistre comme une strategie normale afin de respecter le meme contrat que les autres, mais il court-circuite toute animation temporelle :

- rendu du frame entrant avec le renderer commun dans la couche inactive ;
- permutation immediate des couches ;
- aucun timer ;
- aucune attente d'evenement CSS ;
- aucune interpolation ;
- nettoyage synchrone de tout etat transitoire precedent.

Il ne doit pas posseder un second moteur de rendu ni un element HTML reserve.

### Fondu

- La couche sortante reste stable pendant que la couche entrante apparait par opacite.
- Le contenu ne se deplace pas.
- Duree initiale cible : environ 120 ms, ajustable dans une constante interne apres test, avec une plage raisonnable de 100 a 150 ms.
- A la fin, seule la couche entrante reste active et tous les styles temporaires sont retires.

### Balayage

- Direction unique dans ce chantier : de gauche a droite.
- Le nouveau frame est revele progressivement au-dessus de l'ancien.
- Aucun texte ni fond ne doit glisser, se comprimer ou changer d'echelle.
- Duree initiale cible : environ 180 ms, ajustable dans une constante interne apres test, avec une plage raisonnable de 150 a 200 ms.
- Utiliser une technique CSS adaptee aux navigateurs cibles et limitant les recalculs et repeints, particulierement avec une image Full HD.
- Activer les optimisations comme `will-change` seulement pendant l'effet, puis les retirer.

Ne pas ajouter de balayage vertical, de choix de direction, de flou, de zoom, de rotation ou de micro-deplacement.

## 7. Interruptions, commandes rapides et erreurs

Le moteur doit rester deterministe quand l'utilisateur navigue rapidement.

### Nouvelle commande pendant une transition

Appliquer la regle "derniere demande prioritaire", sans construire une longue file d'attente :

1. neutraliser proprement la transition en cours ;
2. stabiliser les couches dans un etat coherent ;
3. rendre le frame le plus recemment demande dans la couche inactive ;
4. lancer la transition demandee par ce nouveau message.

Une ancienne fin d'animation ne doit jamais pouvoir inverser les couches apres le lancement d'une transition plus recente.
Utiliser le mecanisme adapte au projet : jeton d'operation, identifiant monotone, annulation d'ecouteur ou equivalent.

### Erreur de strategie

Si une transition ne peut pas etre resolue, preparee ou terminee :

- nettoyer l'etat transitoire ;
- afficher la couche entrante immediatement ;
- revenir a un etat A/B coherent ;
- utiliser `Direct` comme repli ;
- ne jamais laisser un ecran vide, semi-transparent ou partiellement balaye.

Le mode sur doit etre independant d'un evenement `transitionend` ou d'un timer appartenant aux effets animes.

## 8. Images de fond et prechargement

Le projet possede deja un mecanisme de prechargement des images de fond dans la remote a partir de `backgroundUrls`.

Le chantier des transitions doit :

- analyser ce mecanisme existant ;
- le conserver autant que possible ;
- continuer a exploiter le cache HTTP du navigateur ;
- tenir compte du fait que remote et afficheur fonctionnent sur le meme navigateur et le meme ordinateur ;
- verifier que les ressources deja chargees beneficient du cache partage avec le renderer A/B.

Ne pas creer systematiquement un second systeme de prechargement cote afficheur.
Un mecanisme supplementaire cote afficheur ne doit etre ajoute que si le fonctionnement reel ou les tests montrent un probleme concret.

Conserver les regles suivantes :

- ne pas dupliquer les slides, textes, blocs ou styles dans l'afficheur ;
- une nouvelle image introduite par une correction live ne doit jamais bloquer durablement la projection ;
- si une image echoue a charger, l'afficheur doit rester dans un etat coherent et continuer la projection.

## 9. Compatibilite et hors-perimetre

L'implementation ne doit pas casser :

- la cle existante de synchronisation remote/afficheur ;
- le retour a la remote apres modification de l'animation ;
- le payload complet et les corrections visibles immediatement ;
- l'affichage simple ;
- l'affichage double ;
- les fonds unis et les images ;
- l'ecran noir ;
- le QR code ;
- le rappel F11 ;
- les boutons de navigation ;
- les raccourcis existants ;
- le plein ecran et le second ecran ;
- les comportements de reconnexion deja presents.

Ne pas introduire dans ce chantier :

- transitions par slide ;
- transitions par chant ;
- transitions par bloc ;
- durees configurables par l'utilisateur ;
- directions configurables ;
- catalogue etendu d'effets ;
- cache fonctionnel de slides dans l'afficheur ;
- systeme de plugins ;
- architecture de session supplementaire ;
- file complexe de commandes ;
- refonte generale du protocole remote/afficheur.

## 10. Demarche d'implementation future

1. Cartographier le fonctionnement existant : modele `Animation`, formulaires, creation et reprise de la cle, etat local de la remote, declaration des raccourcis, transport des messages, `nonce`, heartbeat, structure des frames, renderer display et prechargement des images.
2. Presenter brievement les fichiers qui seront modifies et signaler toute contradiction entre ce document et le code reel.
3. Ajouter le champ de transition par defaut et la migration avec `direct` comme valeur sure.
4. Ajouter le choix dans les interfaces de creation et modification de l'animation.
5. Etendre l'etat live de la remote pour stocker la transition active sans creer de session parallele.
6. Faire en sorte que chaque ordre d'affichage reel envoye par la remote transporte le frame complet et la transition a appliquer.
7. Ajouter les controles de remote et les deux actions de raccourci.
8. Refactorer le renderer display juste assez pour rendre un frame complet dans une couche A ou B, sans changer le rendu actuel.
9. Ajouter le registre, le resolveur, le moteur et les trois strategies.
10. Ajouter la deduplication par `nonce` ou mecanisme equivalent.
11. Verifier que les heartbeats ne declenchent jamais de transition visuelle.
12. Verifier le prechargement d'images existant avec le renderer A/B avant d'ajouter quoi que ce soit cote afficheur.
13. Executer les tests existants, ajouter les tests cibles manquants et rendre compte des validations manuelles necessaires sur videoprojecteur.

## 11. Criteres d'acceptation

### Modele et interfaces

- Une animation nouvelle peut etre creee avec l'une des trois transitions.
- `Direct` est preselectionne par defaut.
- Une animation existante reste utilisable apres migration et utilise `Direct`.
- La preference peut etre modifiee sans ajouter de reglage par slide, bloc ou chant.
- Modifier la preference de l'animation ne modifie pas silencieusement une session live deja ouverte.

### Autorite de la remote

- Une nouvelle session initialise la transition active depuis la preference de l'animation.
- Le changement live ne modifie pas l'animation en base.
- L'indicateur visible de la remote reste synchronise avec la transition active.
- Quitter la remote pour corriger l'animation puis y revenir conserve la cle et l'etat live de la session.
- Chaque nouvel ordre d'affichage indique la transition a appliquer.
- L'afficheur respecte toujours la transition contenue dans le nouvel ordre.
- Un etat local plus ancien de l'afficheur ne prend jamais le dessus sur la valeur envoyee par la remote.

### Raccourcis

- `Transition suivante` respecte exactement le cycle `Direct -> Fondu -> Balayage -> Direct`.
- `Transition suivante` met a jour l'indicateur de la remote.
- `Forcer Direct` selectionne `Direct` pour les prochains ordres d'affichage.
- `Forcer Direct` n'a pas besoin d'interrompre une transition courte deja commencee.
- Les nouveaux raccourcis utilisent le mecanisme de personnalisation existant.

### Messages et deduplication

- Un message recu deux fois avec le meme `nonce` n'est execute qu'une seule fois.
- Un doublon recu via deux transports differents est ignore apres la premiere execution.
- Deux messages differents visant la meme slide, le meme `projectionIndex`, le meme chant ou le meme texte sont executes deux fois.
- Reprojeter le meme ecran avec un nouveau message reste possible.
- La deduplication ne repose jamais sur le contenu fonctionnel du frame.

### Heartbeat

- Un heartbeat ne declenche jamais de transition visuelle.
- Un heartbeat ne rejoue pas la transition du frame courant.
- Le heartbeat peut continuer a servir a la liaison, la resynchronisation ou la restauration technique selon le mecanisme existant.

### Afficheur et transitions

- Le payload complet reste la source du rendu.
- Les transitions s'appliquent au passage entre deux frames complets, pas seulement entre deux slides de paroles.
- Les frames `slide`, `black`, `qr` et `f11-reminder` peuvent etre atteints avec la transition active lorsqu'ils resultent d'un nouvel ordre.
- Les couches A/B restent superposees et ne sont pas restructurees lors d'un changement de transition.
- `Direct`, `Fondu` et `Balayage` utilisent le meme renderer.
- `Direct` ne depend d'aucun timer ni evenement de fin d'animation.
- Des commandes rapides ne laissent jamais l'afficheur dans un etat intermediaire.
- Une transition inconnue ou en erreur finit en affichage `Direct` de la cible.
- Aucun ecran vide, fond absent durablement, contenu semi-transparent ou ancien frame residuel n'apparait.

### Mode double

- Le rendu simple reste identique au rendu actuel.
- Le rendu double reste identique au rendu actuel.
- Les couleurs, polices, tailles, poids, fonds et paddings du mode double ne changent pas.
- La repartition gauche/droite et les regles de synchronisation des blocs ne changent pas.
- Le bouton `Refrain` conserve son comportement existant.

### Images et performance

- Le prechargement existant cote remote via `backgroundUrls` est conserve.
- Le cache HTTP du navigateur est exploite.
- Aucun second prechargement cote afficheur n'est ajoute sans besoin demontre.
- Une image nouvelle recue apres correction live ne bloque pas durablement la projection.
- L'enchainement rapide de frames avec image Full HD ne provoque pas de retard accumule ou de hausse anormale durable de la charge.

## 12. Validation manuelle minimale

Tester au minimum :

- fonds unis ;
- images Full HD deja prechargees ;
- image nouvelle recue apres une correction live ;
- slide simple ;
- slide double ;
- ecran noir ;
- QR code ;
- rappel F11 ;
- navigation rapide ;
- navigation non lineaire ;
- changement de transition pendant le live ;
- action `Transition suivante` ;
- action `Forcer Direct` ;
- depart et retour sur la remote avec la meme cle ;
- reconnexion de l'afficheur ;
- reception double d'un meme message par deux transports ;
- reprojection volontaire de la meme slide par un nouveau message ;
- plein ecran sur le second ecran ;
- navigateurs officiellement supportes par le projet ;
- ordinateur peu puissant comparable a un ancien portable utilise avec un videoprojecteur.

Le test de performance attendu est pragmatique : les transitions doivent rester courtes, stables et sans accumulation de retard.
Si `Fondu` ou `Balayage` se comporte mal, le retour aux prochains ordres en `Direct` doit restaurer une projection stable.

## Definition de termine

Le chantier d'implementation sera termine lorsque les trois transitions seront selectionnables au niveau de l'animation, modifiables en live dans la remote, incluses dans chaque ordre d'affichage reel, executees par un afficheur A/B alimente par des payloads complets, dedupliquees correctement par message, et couvertes par les tests pertinents.

L'implementation doit laisser un point d'extension clair pour ajouter une strategie ou modifier plus tard la provenance du choix de transition, sans avoir implemente prematurement les transitions par slide, bloc ou chant.
