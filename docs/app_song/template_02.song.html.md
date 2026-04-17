# Design of Template `song.html`

## Guiding Idea

C'est la page de lecture d'un chant.

Elle doit permettre de consulter rapidement les informations principales du chant, puis de lire le texte rendu avec la même logique fonctionnelle que celle utilisée pour les animations et les impressions.

Cette page n'est pas une page d'édition.
Elle sert d'abord à vérifier, afficher, copier ou imprimer le chant.

## design

### panneau section

mettre le nom du groupe sélectionné tel que : {% block section_title %}{{ selected_group.name }}{% endblock %}

mettre l'icone static/icons/ui/normal/512/light/songs.png selon le thème et le mode

### panneau outils

TEXTE : "← Retour à la liste"
TEXTE : <hr>
TEXTE : "Afficher"
TEXTE : "📱 Smartphone view"
TEXTE : "🖨️ Impression"

si le chant n'est pas validé :

TEXTE : <hr>
TEXTE : "Modifier"
TEXTE : "Supprimer"

### en-tête principal

sur-titre : "Chant"
titre : titre complet du chant

Le titre complet doit contenir :

- le titre,
- le sous-titre si présent,
- le marqueur de validation si le chant est validé,
- le marqueur de licence si le chant est sous licence.

### encadré résumé

TEXTE : description du chant avec les <br>

### contenu principal / carte de thème 1

Métadonnées du chant

Afficher :

- titre,
- sous-titre,
- description,
- statut de validation,
- licence,
- genres,
- artistes,
- groupes / bands,
- liens associés.

La description doit respecter les retours à la ligne.
Si elle est longue, afficher la première ligne puis un lien "[...]" permettant d'ouvrir le reste.
Le contenu ouvert doit proposer un lien permettant de refermer la description.

### contenu principal / carte de thème 2

Texte du chant

Afficher le texte rendu, pas seulement les blocs bruts.

Le rendu doit respecter :

- les couplets,
- les refrains,
- les refrains répétés,
- les refrains ignorés après un bloc marqué `followed`,
- les blocs `chorus_like`,
- les préfixes de blocs,
- la numérotation visible des couplets.

### contenu principal / carte de thème 3

Messages de correction

Si l'utilisateur n'a pas le droit de modifier directement le chant :

TEXTE : "Signaler une correction"

Si l'utilisateur est membre connecté :

Afficher l'historique des messages de correction du chant.

### actions principales

Mettre les actions sous les informations du chant.

À gauche :

- Afficher
- Modifier si le chant n'est pas validé
- Supprimer si le chant n'est pas validé, avec popup de validation Oui/Non sans croix

À droite :

- 📱
- 🖨️

La popup 🖨️ doit proposer :

TEXTE : """
🖨️💯: Impression du chant - avec un refrain entre chaque couplet
🖨️1️⃣ : Impression du chant - avec un seul refrain
"""

- bouton 1 : "🖨️1️⃣ copier le texte"
- bouton 2 : "🖨️💯 copier le texte"
- bouton 3 : "🖨️1️⃣ afficher le texte"
- bouton 4 : "🖨️💯 afficher le texte"

Les deux boutons de copie copient le texte dans le presse-papier.
Les deux boutons d'affichage ouvrent un template minimal sans CSS du site, uniquement avec le texte brut.
