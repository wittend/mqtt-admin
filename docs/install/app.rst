2. Portal app
=============

Run the app on its own container, with a static address.

Packages and service user
-------------------------

.. code-block:: bash

   apt install -y python3 python3-venv git
   useradd -r -s /usr/sbin/nologin mqtt-admin
   mkdir -p /opt/mqtt-admin

Install the code
----------------

Copy the repository's ``main`` branch to ``/opt/mqtt-admin``, then install it into a virtual environment:

.. code-block:: bash

   python3 -m venv /opt/mqtt-admin/.venv
   /opt/mqtt-admin/.venv/bin/pip install /opt/mqtt-admin
   chown -R mqtt-admin: /opt/mqtt-admin

Configure
---------

Create ``/etc/mqtt-admin.env`` and restrict it to root:

.. code-block:: bash

   touch /etc/mqtt-admin.env && chmod 600 /etc/mqtt-admin.env

Fill it in as described in :doc:`/reference/configuration`. The most important settings are:

* ``MQTT_HOST=<broker-ip>``
* ``MQTT_SVC_PASSWORD`` set to the ``portal-svc`` password from the broker step. Leave it empty until you have that password. The app refuses to start while it is empty, so it cannot run with a placeholder.
* ``SESSION_SECRET`` set to a random value of at least 32 characters:

  .. code-block:: bash

     python3 -c 'import secrets; print(secrets.token_urlsafe(48))'

Run it under systemd
--------------------

Copy ``deploy/mqtt-admin.service`` to ``/etc/systemd/system/``. Check its ``--forwarded-allow-ips`` option: it must be Caddy's address, ``<caddy-ip>``. Then start the service:

.. code-block:: bash

   systemctl daemon-reload
   systemctl enable --now mqtt-admin
   systemctl status mqtt-admin --no-pager

Check it from the app container:

.. code-block:: bash

   python3 -c "import urllib.request as u; print(u.urlopen('http://127.0.0.1:8080/account/login').status)"

This should print ``200``. ``/admin`` returns 404 when asked from the container itself, which is correct: the admin pages accept only LAN and tailnet addresses.
