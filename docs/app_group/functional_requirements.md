# App Group Functional Requirements

`app_group` manages groups as practical perimeters used to organize and protect the `animations` of `Lyrics Slide Show`.

A group is not a social space, not a directory, and not a community-management tool. Its function is intentionally narrow:

- group the animations of a shared perimeter,
- control who can access that perimeter,
- allow local collaboration without turning the product into a social network.

The global rules from `docs/general_overview.md` apply. This document only defines the functional contract specific to `app_group`.

## Privacy

`app_group` is one of the rare places where a small part of human identity becomes visible, and that visibility must stay minimal.

In technical documentation and code-oriented specifications, the role name remains `group admin`.

In the French user-facing interface, that same role is labeled `responsable de groupe`.

- `group admins` may view `username`, `first_name`, and `last_name` of the members of their group in order to manage it,
- a simple member only sees the `username` values of the `group admins`,
- there must be no public directory,
- there must be no social profile, messaging tool, or broad exposure of members.

## Source Of Truth And Data

For PostgreSQL, the functional tables of `app_group` are `g_groups`, `g_group_user`, and `g_group_user_ask_to_join`.

All relations to an authenticated user must rely only on `users.users.id`, as a `UUID`, never on `username`.

## Official Group Statuses

The only official business statuses for a group are:

- `open`: accessible without authentication,
- `private`: authentication and group membership are required,
- `private_with_secret`: accessible through a secret even without authentication.

`docs/general_overview.md` is authoritative for this terminology. `app_group` must not redefine groups as a simple `Open` / `Closed` pair.

A secret only makes sense for a `private_with_secret` group.

- a `private` group never becomes accessible through a secret alone,
- rotating the secret immediately invalidates the previous one,
- if the group stops using the `private_with_secret` status, the previous secret must no longer grant access.

## Administration Rules

Only an authenticated member may create a group.

The creator of a group immediately becomes a `group admin` of that group.

The following actions are reserved to `group admins`, `moderators`, and `admins`:

- modify group settings,
- delete the group,
- accept or reject a join request,
- promote or demote another member as `group admin`,
- change the group status,
- create, replace, or remove the secret of a `private_with_secret` group.

A group may have several `group admins`, but it must always keep at least one.

Neither a `group admin`, nor a `moderator`, nor an `admin` may remove that role from the last remaining `group admin`.

Rare exception:

- if the last remaining `group admin` deletes their own account, the group may temporarily end up without any `group admin`,
- in that case, a `moderator` or `admin` must be able to appoint a new `group admin` to restore normal group governance.

## Membership And Selection

Everyone may access the group list.

The selection rules are:

- everyone may select an `open` group,
- only an authenticated user who belongs to the group may select a `private` group,
- everyone may select a `private_with_secret` group if they know the current secret,
- an authenticated member who already belongs to the group may also select that `private_with_secret` group without re-entering the secret.

Only authenticated members may request to join a group.

The group list page must allow:

- displaying the group name,
- displaying its official business status,
- indicating whether secret-based access is active,
- selecting the group according to the rules above,
- requesting to join a group when that makes sense,
- seeing that a request is already pending and cancelling it,
- accessing group edition for `group admins`, `moderators`, and `admins`.

## Relation To Animations

Selecting a group is used to access the features of `app_animation`.

`app_group` does not define the internal business rules of animations, but it must respect this global contract:

- a selected group is a prerequisite for working on an animation,
- a guest may work inside an `open` group,
- a guest may also work inside a `private_with_secret` group if they know the secret,
- a `private` group remains restricted to authenticated members who belong to it.

## Vocabulary

The following terms must be used consistently in documentation and implementation:

- `group`,
- `group admin`: technical documentation term; French UI label `responsable de groupe`,
- `open`,
- `private`,
- `private_with_secret`,
- `group secret`.
