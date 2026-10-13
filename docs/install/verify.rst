5. Verify the installation
==========================

Work through these checks after installation.

Public side
-----------

From a network outside yours, such as a phone on mobile data:

* ``https://<portal-host>/account/login`` loads the sign-in page.
* ``https://<portal-host>/admin/login`` returns 404.

Tailnet side
------------

From a device on your tailnet:

* ``https://<caddy-node>.<tailnet-name>.ts.net/admin/login`` loads the administrator sign-in page.

Accounts
--------

Sign in to the administrator page with your administrator login and check:

1. The user list appears, with your login in it.
2. Create a test user with a role, then reset its password.
3. Delete the test user.
4. Import a small CSV file with one deliberately bad row. Nothing should be created. The error should name the correct line.

Then sign in to ``/account`` as an ordinary user, change the password, and sign in again with the new one. Restore a known-good password afterwards.

Broker
------

Connect an MQTT client with a portal account, and publish to a test topic. If the client connects, the portal and dynsec are working together.
