Reference
=========

.. toctree::
   :maxdepth: 1

   configuration

Web routes
----------

.. list-table::
   :header-rows: 1
   :widths: 40 15 45

   * - Route
     - Method
     - Purpose
   * - ``/``
     - GET
     - Redirects to ``/account``.
   * - ``/account/login``
     - GET, POST
     - Ordinary user sign-in.
   * - ``/account``
     - GET
     - Password change form. Requires sign-in.
   * - ``/account/password``
     - POST
     - Changes the signed-in user's password.
   * - ``/account/logout``
     - POST
     - Signs out.
   * - ``/admin/login``
     - GET, POST
     - Administrator sign-in. Returns 404 outside the allowed networks.
   * - ``/admin``
     - GET
     - User list and forms. Requires an administrator.
   * - ``/admin/users``
     - POST
     - Creates one user.
   * - ``/admin/users/import``
     - POST
     - Imports users from a CSV file.
   * - ``/admin/users/{username}/password``
     - POST
     - Resets a user's password.
   * - ``/admin/users/{username}/enabled``
     - POST
     - Disables (``enabled=0``) or enables (``enabled=1``) a user.
   * - ``/admin/users/{username}/roles``
     - POST
     - Sets a user's roles to the boxes ticked.
   * - ``/admin/users/{username}/delete``
     - POST
     - Deletes a user.
   * - ``/admin/logout``
     - POST
     - Signs out of the admin page.

Every POST form carries a CSRF token. The application does not serve API documentation pages.

Roles
-----

The portal recognises one role by name, configured as ``PORTAL_ADMIN_ROLE`` (default ``portal-admin``). Holding it grants access to the admin page. It grants no broker topic permissions.

Other roles come from the broker. The portal lists them and assigns them, but does not define their topic rules. Define those on the broker with dynsec commands such as ``createRole`` and ``addRoleACL``.

Username and password rules
---------------------------

Usernames
    Letters, digits, and ``. _ @ -``. Between 1 and 64 characters.

Passwords
    At least ``min_password_length`` characters (default 12), and at most 128. Must not contain the username. Must use at least five different characters.

CSV import
----------

Columns: ``username``, ``password``, ``textname`` (optional), ``roles`` (optional, separated by semicolons). Header names are case-insensitive. The file must be UTF-8 and no more than 256 KB, with at most 500 rows. Every row is checked before any account is created.
