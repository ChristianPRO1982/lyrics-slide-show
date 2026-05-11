# Design of Template `songs.html`

## Guiding Idea

C'est un outil central du site.
La recherche, si on est connecté, permet de filtrer les chansons de façon assez fine.
Cette recherche pourra être utilisée dans la partie "animations".

## design

### panneau section

mettre le nom du groupe sélectionné tel que : {% block section_title %}{{ selected_group.name }}{% endblock %}

mettre l'icone static/icons/ui/normal/512/light/songs.png selon le thème et le mode

### panneau outils

TEXTE : "💫 Afficher mes favoris"
si le mode favoris temporaire est actif :
TEXTE : "Mode favoris temporaire actif."
TEXTE : "Revenir à ma recherche enregistrée"
TEXTE : <hr>
TEXTE : "Chants : 742"
TEXTE : Recherche ⓘ : 742"
TEXTE : Total ⓘ : 742"

### en-tête principal

sur-titre : "Chants"
titre : "Listes des chants"

### encadré résumé

TEXTE : """
✔️ : Chant validé
✔️⁉️ : Chant validé avec des messages
📄 : Chant sous licence
📱 : Smartphone view
🖨️💯: Impression du chant - avec un refrain entre chaque couplet
🖨️1️⃣ : Impression du chant - avec un seul refrain
"""

### contenu principal / carte de thème 1

Recherche
Recherche avancée

Quand le mode `💫 Afficher mes favoris` est actif, le formulaire de recherche affiché doit conserver les critères enregistrés du membre.
Le mode favoris est un filtre momentané des résultats et ne doit pas réécrire ni vider le formulaire.

### contenu principal / carte de thème 2

Nouveau chant

### pied de contenu

liste des chants
