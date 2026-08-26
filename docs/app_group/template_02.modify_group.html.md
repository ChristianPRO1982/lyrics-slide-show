# Design of Template `modify_group.html`

## Guiding Idea

- manage the settings of one group,
- manage its secret-based access helpers,
- review join requests,
- manage current members,
- delete the group with explicit confirmation.

## Layout

- section panel uses the themed `groups` icon,
- top contextual action returns to `Liste des groupes`,
- tools panel contains a compact status card for the current group,
- mobile side panel contains the same compact status summary,
- page header:
  - overtitle = `Groupes`,
  - title = current group name,
- summary box reminds the meaning of `🌐/🔐/🔐📱` and the last-admin rule.

## Tools Panel

The tools panel shows:
- group name,
- business status icon and label,
- a message when this group is currently selected,
- otherwise, a button to select this group when the current user/session is allowed to do so.

It does not contain the QR code, the share link, or the secret-management buttons.

## Main Content

### Main Settings

The page exposes a settings form with:
- group name,
- group info,
- opening mode through `is_open` (`open` / `private`).

The form uses the unsaved-changes guard.

### Group Secret

A dedicated card handles the secret workflow:
- current secret presence state,
- full share link when a secret exists,
- button to copy the link,
- QR code generated from that link,
- button to copy the QR code,
- action to create or replace the secret,
- action to remove the secret.

These actions require confirmation popups.

## Content Footer

### Join Requests

If pending requests exist, the page shows a list of requesters with:
- username,
- first name when available,
- last name when available,
- one review action opening an `Accepter / refuser` popup.

### Group Members

The page shows all current members with:
- username,
- first name when available,
- last name when available,
- `Responsable du groupe` marker when applicable,
- explicit `Dernier responsable du groupe.` state for the final remaining group admin.

Possible member actions:
- `Nommer responsable`,
- `Retirer responsable`,
- `Retirer du groupe`.

The last remaining group admin does not get normal demotion/removal actions.

### Group Deletion

A dedicated deletion card shows:
- current member count,
- current count of upcoming animations,
- a destructive action guarded by a translated textual confirmation word entered through a popup.
