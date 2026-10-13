4. Admin page over Tailscale
=============================

The admin page is served only to devices on your tailnet. Tailscale's own sign-in and device approval decide who gets in.

Install Tailscale on the Caddy container
----------------------------------------

.. code-block:: bash

   curl -fsSL https://tailscale.com/install.sh | sh

Use userspace networking
------------------------

Tailscale normally needs the kernel's TUN device. Containers often lack it, and passing it through can be fiddly. Userspace mode avoids the device entirely.

Set the flag in ``/etc/default/tailscaled``:

.. code-block:: text

   FLAGS="--tun=userspace-networking"

Then start the service:

.. code-block:: bash

   systemctl enable --now tailscaled

Join the tailnet
----------------

.. code-block:: bash

   tailscale up --hostname=caddy

Open the login URL it prints and approve the device. Note its tailnet address:

.. code-block:: bash

   tailscale ip -4

Turn on HTTPS certificates
--------------------------

In the Tailscale admin console, enable **HTTPS Certificates**. The admin page needs HTTPS, and this setting provides it.

Serve the admin page
--------------------

.. code-block:: bash

   tailscale serve --bg --https=443 http://<app-ip>:8080
   tailscale serve status

``serve status`` shows the address of the admin page, which has the form ``https://<caddy-node>.<tailnet-name>.ts.net/``.

Limit who can reach it
----------------------

Use Tailscale's access rules to decide which people and devices may reach the Caddy node. Otherwise every device on your tailnet can reach the sign-in page.
