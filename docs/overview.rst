Overview
========

What the portal does
--------------------

* **Ordinary users** sign in with their broker username and password at ``/account``, then change their own password. The page is public over HTTPS.
* **Administrators** sign in at ``/admin`` and manage every account: create, reset a password, enable or disable, set roles, and delete. They can also import many accounts from a CSV file.
* **Devices and applications** keep connecting to the broker as they do now. A password change in the portal is the password those clients must use.

How accounts are stored
-----------------------

Accounts are kept by Mosquitto's dynamic-security plugin (dynsec), not in a password file. Changes take effect immediately, without restarting the broker.

The portal never reads the broker's files. It talks to dynsec over MQTT, using a service account (``portal-svc``) that has only dynsec administration rights. That account holds no topic permissions.

Administrators are identified by the ``portal-admin`` role. The app checks this role on every request, so removing it from an account locks that account out at once.

Design decisions
----------------

Passwords are checked by logging in as the user
    dynsec has no "check password" command. To verify a password, the app opens a broker connection as that user and reports whether the broker accepted it.

The admin page is not on the public name
    Caddy returns 404 for ``/admin`` on the public site. The admin page is served only to devices on the administrator's Tailscale network (tailnet).

    Caddy first tried to limit ``/admin`` by client address. The router can make some outside requests appear to come from its own LAN address, so an address check on the public name cannot be trusted.

Rate limits on sign-in
    Five failed sign-ins for one user, or twenty for one address, within 15 minutes are refused until the window passes.

Sessions and forms
    Sessions end 30 minutes after sign-in. Every form carries a CSRF token. Cookies are ``SameSite=Strict`` and, with the default setting, ``Secure``. Pages are sent with ``Cache-Control: no-store`` and a restrictive Content-Security-Policy.

Repository
----------

The source is in the project repository, under ``src/mqtt_admin``. Deployment files are in ``deploy/`` and ``mosquitto/``.
