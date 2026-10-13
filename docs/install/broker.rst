1. Broker (Mosquitto with dynsec)
=================================

You need Mosquitto 2.x with its dynamic-security plugin, plus ``mosquitto-clients``.

Check the plugin
----------------

Find the plugin's path on the broker:

.. code-block:: bash

   find / -name mosquitto_dynamic_security.so 2>/dev/null

On Debian it is usually ``/usr/lib/x86_64-linux-gnu/mosquitto_dynamic_security.so``.

Remove the old password file
----------------------------

dynsec replaces the password file. Before going further, back up the broker's configuration, then remove its ``password_file`` line:

.. code-block:: bash

   cp -a /etc/mosquitto/conf.d/default.conf /root/default.conf.bak
   sed -i 's|^password_file |# password_file |' /etc/mosquitto/conf.d/default.conf

Do not restart the broker yet. Without the plugin configured, it would start with no login method at all.

Add the dynsec configuration
----------------------------

Create ``/etc/mosquitto/conf.d/dynsec.conf``:

.. code-block:: text

   allow_anonymous false
   plugin <plugin-path>
   plugin_opt_config_file /var/lib/mosquitto/dynamic-security.json

Create the service account and your admin login
-----------------------------------------------

The repository's ``mosquitto/setup-dynsec.sh`` does the bootstrap. Copy it to the broker, make it executable, and run it with your administrator username:

.. code-block:: bash

   /root/setup-dynsec.sh <admin-username>

The script asks for two passwords at its prompts:

* the password for ``portal-svc``, the service account the portal uses to talk to the broker
* the password for your administrator login

The script creates ``portal-svc`` with dynsec administration rights only, creates the ``portal-admin`` role, creates your login and gives it that role. It then restarts Mosquitto.

Check it
--------

* Mosquitto listens on ports 1883 and 8883.
* ``/var/lib/mosquitto/dynamic-security.json`` lists the two clients, ``portal-svc`` and your login.

.. warning::

   The script removes the old password-file login. Any device that still uses it stops connecting. Re-create those devices' accounts in the portal, or in the broker, before you run the script.
