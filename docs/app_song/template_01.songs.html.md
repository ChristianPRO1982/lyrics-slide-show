# Design of Template `songs.html`

## Guiding Idea

C'est un outil central du site.
La recherche, si on est connecté, permet de filtrer les chansons de façon assez fine.
Cette recherche pourra être utilisée dans la partie "animations".

## design

### panneau section

mettre le nom du groupe sélectionné tel que : {% block section_title %}{{ selected_group.name }}{% endblock %}

mettre l'icone static/icons/ui/normal/512/light/songs.png selon le thème et le mode