# Popup Message Box Contract

`Lyrics Slide Show` expose une API popup globale via `window.LSSMessageBox`.

Ce document décrit l’implémentation actuelle de `static/js/message_box.js`.

## Loading Contract

- `templates/base.html` charge globalement `static/js/message_box.js`
- l’hôte popup global est `<div id="lss-messagebox-root" hidden></div>`
- le popup utilise `window.LSS_THEME_CONFIG`
- l’icône de fermeture dépend du thème actif et du `prefers-color-scheme`
- `page_scripts` est injecté après `message_box.js`, ce qui permet aux pages d’utiliser immédiatement `window.LSSMessageBox`

## Public API

### `window.LSSMessageBox.show(config)`

Retourne une `Promise` résolue avec :

```js
{
  reason: "button" | "close" | "escape" | "programmatic",
  buttonId: string | null,
  values: { [fieldId]: string },
  payload?: unknown
}
```

### `window.LSSMessageBox.alert(config)`

Wrapper de `show(config)`.

Bouton par défaut :

```js
buttons: [{ id: "ok", label: "OK", tone: "neutral" }]
```

`showCloseButton` passe à `false` par défaut.

### `window.LSSMessageBox.confirm(config)`

Wrapper de `show(config)`.

Boutons par défaut :

```js
buttons: [
  { id: "yes", label: "Oui", tone: "success" },
  { id: "no", label: "Non", tone: "neutral" }
]
```

`showCloseButton` passe à `false` par défaut.

### `window.LSSMessageBox.prompt(config)`

Wrapper de `show(config)`.

Boutons par défaut :

```js
buttons: [
  { id: "confirm", label: "Confirmer", tone: "success", validate: true },
  { id: "cancel", label: "Annuler", tone: "neutral", validate: false }
]
```

`showCloseButton` passe à `false` par défaut.

### `window.LSSMessageBox.close(result?)`

Ferme programmatiquement le popup actif.

Résultat :

```js
{
  reason: "programmatic",
  buttonId: null,
  values: currentFieldValues,
  ...result
}
```

Retourne `true` si un popup a été fermé, sinon `false`.

### `window.LSSMessageBox.isOpen()`

Retourne `true` si un popup est actif.

## `show(config)` shape

```js
{
  title: "Popup title",
  messageMarkdown: "Message with **Markdown**",
  size: "compact" | "default" | "wide",
  showCloseButton: true,
  initialFocus: "close" | "first-field" | "button:<id>" | "action:<id>" | "field:<id>",
  enterButtonId: "confirm",
  escapeButtonId: "cancel",
  buttons: [],
  actionList: { items: [] },
  fields: [],
  onFieldChange(context) {},
  preview: { label: "", text: "", className: "" },
  fontSamples: [{ fontFamily: "", sample: "", label: "" }],
  tabbedSelect: {
    fieldId: "target_field",
    fieldLabel: "",
    initialTabId: "main",
    submitButtonId: "confirm",
    size: 8,
    tabs: []
  }
}
```

Règles de normalisation :

- `config` absent ou invalide devient un objet vide
- `title` et `messageMarkdown` sont toujours normalisés en chaînes
- `size` invalide retombe sur `"default"`
- `buttons` et `fields` retombent sur `[]`
- `actionList` est optionnel
- si `fields.length > 0` et `buttons.length === 0`, une erreur est levée
- si `buttons.length === 0`, `showCloseButton` est forcé à `true`
- sinon `showCloseButton` vaut `true` sauf si explicitement `false`
- `onFieldChange` n’est conservé que si c’est une fonction
- `preview`, `fontSamples` et `tabbedSelect` sont optionnels

## `actionList`

`actionList` ajoute une liste d’actions cliquables dans `lss-messagebox-content`, avant le footer.

Shape :

```js
{
  ariaLabel: "Choix disponibles",
  items: [
    {
      id: "prefix-1",
      label: "Pont",
      description: "Transition",
      payload: { prefixId: "prefix-1" }
    }
  ]
}
```

Règles :

- `actionList.items` doit être un tableau non vide
- chaque entrée doit définir un `id` non vide
- `label` retombe sur `id`
- `description` est optionnel
- `payload` est optionnel et doit être un objet s’il est fourni
- le rendu utilise de vrais `<button type="button">`, donc clavier et focus visible couvrent toute l’entrée
- la liste est affichée verticalement dans le corps principal du popup
- une entrée sans `description` n’affiche que son `label`

Résultat au clic ou à l’activation clavier :

```js
{
  reason: "button",
  buttonId: null,
  values: currentFieldValues,
  payload: {
    actionListItemId: "prefix-1",
    prefixId: "prefix-1"
  }
}
```

`buttonId` reste réservé aux vrais boutons de footer.

## Buttons

Chaque bouton supporte :

```js
{
  id: "confirm",
  label: "Confirmer",
  description: "Optional helper text",
  tone: "neutral" | "success" | "warning" | "danger",
  disabled: false,
  validate: true,
  onClick(context) {}
}
```

Règles :

- `id` non vide obligatoire
- `label` retombe sur `id`
- `description` est optionnel et s’affiche sous le label si présent
- `tone` invalide retombe sur `"neutral"`
- `disabled` est coercé en booléen
- `validate` n’est conservé que s’il est explicitement booléen
- `onClick` n’est conservé que si c’est une fonction

## Fields

Le popup supporte au maximum `12` champs.

Types supportés :

- `text`
- `email`
- `password`
- `textarea`
- `color`
- `number`
- `select`
- `datetime-local`
- `shortcut-slots`

Shape générale :

```js
{
  id: "email",
  label: "Adresse e-mail",
  type: "text",
  value: "",
  readonly: false,
  placeholder: "",
  required: true,
  autocomplete: "email",
  maxLength: 255,
  rows: 4,
  min: 0,
  max: 100,
  step: 1,
  size: 8,
  options: [{ value: "a", label: "Option A" }],
  slotCount: 3,
  emptySlotLabel: "Aucun",
  captureSlotLabel: "Appuyer sur une touche",
  clearSlotLabel: "Effacer ce raccourci"
}
```

Règles de normalisation :

- `id` non vide obligatoire
- `type` invalide retombe sur `"text"`
- `label` retombe sur `id`
- `value`, `placeholder`, `autocomplete` sont normalisés en chaînes
- `readonly` et `required` sont coercés en booléens
- `maxLength` n’est utilisé que s’il est strictement positif
- `rows` ne s’applique qu’à `textarea`, sinon `4`
- `min`, `max`, `step` s’appliquent aux champs compatibles quand ce sont des nombres finis
- `options` ne s’applique qu’à `select`
- `size` ne s’applique qu’à `select` si > 1
- `slotCount` ne s’applique qu’à `shortcut-slots`, défaut `3`, maximum `3`

Comportement rendu :

- les champs sont rendus dans un `<form novalidate>`
- `readonly=true` rend `input` et `textarea` non éditables mais focusables
- `select` choisit la première option si la valeur courante n’existe pas
- `shortcut-slots` rend jusqu’à trois slots clickables, sérialisés en CSV dans un input caché
- les erreurs de validation sont affichées inline
- les valeurs retournées sont toujours des chaînes

## `tabbedSelect`

`tabbedSelect` permet de piloter un champ `select` existant à travers des onglets.

Contraintes :

- `fieldId` doit cibler un champ `select` existant
- `tabs` doit contenir au moins un onglet
- chaque onglet a un `id`, un `label`, une liste `options` et éventuellement `emptyMessage`
- `initialTabId` retombe sur le premier onglet si invalide
- `submitButtonId` peut désactiver dynamiquement un bouton si l’onglet actif n’a aucune option

## `preview` et `fontSamples`

- `preview` ajoute un aperçu visuel live dans le corps du popup
- `fontSamples` ajoute une galerie d’aperçus de polices

Ces deux mécanismes sont purement front et n’ajoutent aucune logique métier.

## Callback Context

Le callback d’un bouton reçoit :

```js
{
  buttonId,
  values,
  close(payload),
  keepOpen(),
  setFieldError(fieldId, message),
  setFieldValue(fieldId, value)
}
```

`onFieldChange(context)` reçoit :

```js
{
  fieldId,
  value,
  values,
  previewElement,
  setFieldValue(fieldId, value),
  setFieldError(fieldId, message)
}
```

## Validation Rules

- la validation n’existe que s’il y a des champs
- si `button.validate` vaut explicitement `true` ou `false`, cette valeur prime
- sinon seul le bouton par défaut déclenché par `Enter` valide
- `required=true` vérifie une valeur trim non vide
- `type="email"` vérifie la validité email native

Messages intégrés :

- `Ce champ est obligatoire.`
- `Veuillez saisir une adresse e-mail valide.`

## Markdown Support

`messageMarkdown` est rendu côté client.

Syntaxe supportée :

- paragraphes
- titres `#` à `######`
- règles horizontales `---`, `***`, `___`
- listes `-`, `*`, `1.`
- blockquotes `>`
- blocs de code fence
- code inline
- liens Markdown
- gras et emphase simple

Sécurité :

- le HTML brut est échappé
- les liens autorisés sont :
  - `http:`
  - `https:`
  - `mailto:`
  - `tel:`
  - ancres `#`
  - chemins `/`, `./`, `../`
  - URLs relatives résolues sûrement contre la page courante

## Interaction Rules

- un seul popup visible à la fois
- les popups supplémentaires sont mis en file `FIFO`
- l’ouverture ajoute `body.lss-messagebox-open`
- la fermeture retire cette classe
- le focus précédent est restauré quand possible

## Focus Rules

Focus explicite :

- `initialFocus: "close"`
- `initialFocus: "first-field"`
- `initialFocus: "button:<id>"`
- `initialFocus: "field:<id>"`

Ordre de fallback :

1. premier champ
2. bouton action par défaut `Enter`
3. bouton fermer
4. premier élément focusable restant
5. panneau du dialogue

## Keyboard Rules

- `Tab` et `Shift+Tab` sont piégés dans le popup
- si un callback de bouton est en cours, les raccourcis clavier hors `Tab` sont bloqués
- si le bouton fermer est présent, `Escape` ferme toujours le popup et ignore `escapeButtonId`
- sinon `Escape` déclenche :
  - l’unique bouton s’il n’y en a qu’un
  - le deuxième bouton par défaut s’il y en a au moins deux
  - ou `escapeButtonId` s’il correspond à un bouton existant
- `Enter` :
  - ne fait rien sans bouton
  - déclenche l’unique bouton s’il n’y en a qu’un
  - déclenche le premier bouton par défaut s’il y en a plusieurs
  - ou `enterButtonId` s’il correspond à un bouton existant
- dans `textarea`, `Enter` garde son comportement normal

## Mouse Rules

- cliquer le backdrop ne ferme pas le popup
- cliquer le bouton fermer ferme avec `reason: "close"`
- cliquer un bouton exécute ce bouton normalement

## Layout and Size Rules

- padding horizontal viewport : `16px`
- marge verticale : `12.5vh`
- hauteur max : `75vh`
- hauteur min : `200px`
- largeurs :
  - `compact` : min `320px`, max `460px`
  - `default` : min `320px`, max `680px`
  - `wide` : min `360px`, max `920px`

Le header et le footer restent visibles ; seul le body scrolle si nécessaire.

## Visual Rules

- l’icône close provient du thème actif
- les tons `neutral`, `success`, `warning`, `danger` utilisent les variables popup du thème
- les thèmes hérités (`scout`, etc.) surchargent ces tokens comme le reste du site

## Accessibility Rules

- `role="dialog"`
- `aria-modal="true"`
- `aria-labelledby` si titre présent, sinon `aria-label`
- image close avec `alt=""` et `aria-hidden="true"`
- erreurs avec `aria-live="polite"`
- champs invalides avec `aria-invalid="true"` et `aria-describedby`
