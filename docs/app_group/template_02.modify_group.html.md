# Design of Template `modify_group.html`

## Guiding Idea

* allows management of all group settings and the list of its members

## Design

* section panel = `static/icons/ui/normal/512/light/groups.png` depending on theme and mode
* tools panel = indicates whether the group is open/closed + if the token exists, display the QR code, the button to copy the QR code, the link, and the button to copy the link
* mobile panel = tools panel
* main header
  * overtitle = `"Groups"`
  * title = `"Group List"`
* summary box = reminder of the meaning of `🌐/🔐/🔐📱` / reminder that the last remaining group admin cannot have that role removed until another group admin has been appointed
* main content = list of group settings
* content footer = if there are requests to become members, place the list of links here, then the list of group members with buttons next to the list to grant/remove the group admin role and to remove the member from the group
