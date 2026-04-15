# Design of Template `groups.html`

## Guiding Idea

* simple list of the groups currently stored in the database
* access the modification page of a group if the user is a group admin of that group or a moderator
* select a group in order to work in the site's `animations` section

## Group List

* sorted alphabetically
* display an invisible grid with: `| group name + status [🌐/🔐/🔐📱] | info (first 50 characters then "..." with a link to show the rest) | <ACTIONS> |`
* all groups are displayed on a single page
* a group can be searched through a JavaScript search field: case-insensitive and accent-insensitive search, starting from the third character

### `<ACTIONS>`

* select if allowed, otherwise nothing
* request membership / or member / or group admin / or pending request with `💪/👥/📩`
* modify the group if allowed, otherwise nothing

## Design

* section panel = `static/icons/ui/normal/512/light/groups.png` depending on theme and mode
* tools panel = indicates the currently selected group, and if there is no selected group then show `"no group selected"`
* mobile panel = tools panel
* main header
  * overtitle = `"Groups"`
  * title = `"Group List"`
* summary box = reminder of the meaning of `🌐/🔐/🔐📱`
* main content = search bar then group list
* content footer = explanation of how it works (see above)

## Search Reminder

A link to the search bar is available through the `"🔎"` link, always floating at the top right of the screen.

## Functional Explanations

An “open 🌐” group can be joined by any logged-in person. There is no restriction other than being logged in.< hr >
A “closed 🔐” group is accessible only to users who are logged into the site and whose affiliation with the group has been established.< hr >
The token is permanent and allows the people who received it to connect to the group. They do not need to have an account on the site or be logged in.

To create a token 📱 or generate a new one, click the checkbox “create a new token”. If a token already existed, it will be destroyed. A group with a token can be accessed only by group members and by those who know the token; if the group is private, the token still allows access to it.

It is also possible to delete the token with the checkbox “delete the token”.
