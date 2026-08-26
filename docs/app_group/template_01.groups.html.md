# Design of Template `groups.html`

## Guiding Idea

- list the groups currently available in the database,
- allow selecting a working group for the rest of the site,
- expose the creation, join-request, leave, and management entry points that are allowed for the current user.

## Group List

- sorted alphabetically,
- all groups are displayed on a single page,
- each card shows:
  - group name,
  - status marker `🌐` / `🔐` / `🔐📱`,
  - optional info preview,
  - optional visible usernames of group admins,
  - membership marker when relevant,
  - allowed actions.

Info behavior:
- if `info` is longer than 50 characters, the card first shows a truncated preview,
- a local toggle expands the full text inline,
- line breaks are rendered visually.

Search behavior:
- JavaScript local search only,
- case-insensitive and accent-insensitive,
- filtering starts from the third character,
- a floating `🔎` anchor scrolls to the search field.

## Actions

Possible actions per card:
- `Sélectionner` when the group is directly accessible,
- `Sélectionner avec secret` when the group is `private_with_secret` but not yet accessible in the current session,
- `Demander à rejoindre` for an authenticated non-member on a closed group,
- `Annuler la demande` when a join request is already pending,
- `Quitter le groupe` for a current member,
- `Modifier le groupe` for a group manager.

Membership markers:
- `👩🏾‍🔧` = current user is group admin,
- `👥` = current user is member,
- `📩` = current user has a pending join request.

## Layout

- section panel uses the themed `groups` icon,
- tools panel shows the currently selected group or `Pas de groupe sélectionné.`,
- the tools panel also exposes `Modifier` when the selected group is manageable,
- mobile side content shows a compact summary of the current selection,
- page header:
  - overtitle = `Groupes`,
  - title = `Liste des groupes`,
- summary box reminds the meaning of `🌐`, `🔐`, and `🔐📱`,
- main content contains:
  - floating search shortcut,
  - create-group card,
  - access-rules explanation card,
- content footer contains the search field and the full list of group cards.

## Functional Explanations

- an open `🌐` group can be selected freely,
- a closed `🔐` group is reserved to members unless a valid secret is provided,
- a closed-with-secret `🔐📱` group keeps the same management rules as a closed group; the secret only opens temporary selection access for the current session,
- requesting membership is only available for authenticated non-members on closed groups,
- creating a group is reserved to authenticated users and the created group starts open.
