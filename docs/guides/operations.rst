Operating the portal
====================

Day-to-day checks, logs and routine tasks for whoever runs the servers.

Health checks
-------------

* Public sign-in page: ``https://<portal-host>/account/login`` should load.
* Admin page: ``https://<caddy-node>.<tailnet-name>.ts.net/admin/login`` should load on the tailnet.
* Service status on each container: ``systemctl status mqtt-admin``, ``systemctl status caddy``, ``systemctl status tailscaled``, and ``systemctl status mosquitto`` on the broker.

Logs
----

.. code-block:: bash

   journalctl -u mqtt-admin -n 50 --no-pager     # app
   journalctl -u caddy -n 50 --no-pager          # Caddy
   journalctl -u mosquitto -n 50 --no-pager      # broker

Caddy records one access-log line per request only when the site block contains a ``log`` directive, which the default configuration omits. Access-log lines include visitors' addresses, so turn the directive on only while diagnosing a problem, then remove it and reload Caddy.

Changing the service password
-----------------------------

The app holds the ``portal-svc`` password in ``/etc/mqtt-admin.env``. To change it:

1. Set the new password on the broker with dynsec's ``setClientPassword`` command, run with the service account's current credentials, for example ``mosquitto_ctrl -u portal-svc -P <current> dynsec setClientPassword portal-svc <new>``. The portal cannot change this account.
2. Put the new value in ``MQTT_SVC_PASSWORD``.
3. Restart the app: ``systemctl restart mqtt-admin``.

Backups
-------

Back up these, and keep the copies protected:

* ``/var/lib/mosquitto/dynamic-security.json`` on the broker. It holds every account and role.
* ``/etc/mqtt-admin.env`` on the app container. It holds the service password and the session secret.
* The Caddy configuration, ``/etc/caddy/Caddyfile``.

Restoring the dynsec file means restoring the accounts as they were when the backup was made, so take backups after each change to the roles.

Addresses
---------

Containers must keep their addresses. Pin each address in its own container's network settings and in the router's DHCP reservations. The app trusts forwarded client addresses only from the Caddy container's address, so if that address changes, client detection breaks.

Proxmox containers
------------------

Edits to a container's configuration on the Proxmox host take effect only after a full stop and start:

.. code-block:: bash

   pct stop <id>
   pct start <id>

A reboot from inside the container may not apply such changes.

Access for installers
---------------------

When someone needs shell access to a container during installation, use a dedicated key for that job only. Remove the key from the container's ``authorized_keys`` and from the installer's machine when the job is finished. Delete any backup copies of ``authorized_keys`` as well.

Known limits
------------

* The public name has only an IPv4 address. Clients on IPv6-only networks cannot reach it.
* The sign-in rate limit counts failures per address. An IPv6 client can change address within its /64 block, so the limit is weaker for IPv6 users.
* The tests use a fake broker. Test against a real broker before relying on a change.
