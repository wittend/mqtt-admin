For administrators
==================

Administrators manage broker accounts from the admin page. The page is reachable only from your tailnet (see :doc:`/install/tailnet`).

Sign in
-------

Open ``https://<caddy-node>.<tailnet-name>.ts.net/admin/login`` on a device that is on your tailnet. Sign in with your administrator login. Anyone signed in as an administrator must hold the ``portal-admin`` role.

The admin page refuses everyone else. Outside the tailnet, the address returns a page not found.

The user list
-------------

The page lists every account on the broker, with its display name, its roles, and any ``disabled`` flag. Some accounts are marked as managed outside the portal:

* ``portal-svc``, the service account the portal uses. It cannot be changed from the portal.
* Your own account. You can change your password on ``/account``, but you cannot disable, delete or remove your own administrator role from the admin page.

Add a user
----------

Use the **Add a user** form:

1. Enter a username. Usernames may use letters, digits, and ``. _ @ -``, up to 64 characters.
2. Optionally enter a display name.
3. Enter an initial password. It must meet the password rules in :doc:`users`.
4. Tick the roles the account needs.
5. Submit the form.

Reset a password
----------------

Open the user's **Reset password** section, enter a new password that meets the rules, and set it. Tell the user the new password through a channel you trust, and ask them to change it at ``/account`` straight away.

Disable, enable or delete
-------------------------

**Disable** blocks the account from connecting, and **Enable** restores it. Deleting an account removes it from the broker. A deleted account cannot be recovered; re-create it if needed.

Roles
-----

Roles grant topic permissions on the broker. Each role appears as a checkbox on the user's **Roles** section. Changes apply when you save.

``portal-admin`` is special: it grants access to this admin page and no broker topics. Remove it from an account to stop that account signing in as an administrator. The change takes effect on the account's next request.

Import users from a CSV file
----------------------------

Use **Import users from CSV** to create many accounts at once.

The file:

* is UTF-8 text (a byte-order mark is accepted),
* has a header row with the columns ``username``, ``password``, ``textname`` and ``roles``. Column names are not case-sensitive. Only ``username`` and ``password`` are required.
* separates several roles in one cell with semicolons, for example ``sensor-publisher;dashboard``,
* has at most 500 rows, and is at most 256 KB.

Example:

.. code-block:: text

   username,password,textname,roles
   sensor01,<initial-password>,Garage sensor,sensor-publisher
   dashboard01,<initial-password>,Wall display,dashboard;sensor-reader

How the import works:

* Every row is checked before anything is created. Errors list each problem with its line number, and the import creates nothing.
* A row fails if its username is invalid, already exists, or is repeated in the file; if its password breaks the rules; or if it names a role that does not exist.
* Once the file passes checking, accounts are created one at a time. If the broker refuses one, the import stops there and says which account failed. Accounts created before that point remain. Correct the file, remove the accounts already created, and import again.

.. warning::

   The CSV file contains plaintext passwords. Delete it once the import is finished, and do not send it by e-mail or leave it on a shared drive.

Sign out
--------

Use **Sign out** at the top of the page. Sessions also end 30 minutes after you sign in.
