Installation
============

Build the pieces in this order. Each step needs the addresses from the previous one.

Before you start, decide and write down:

* ``<broker-ip>``: the Mosquitto container's address
* ``<app-ip>``: the portal container's address
* ``<caddy-ip>``: the Caddy container's address
* ``<portal-host>``: the public name for the account page, such as ``accounts.example.org``
* ``<caddy-node>``: the name the Caddy container takes on your tailnet
* ``<lan-subnet>``: your LAN subnet, such as ``192.0.2.0/24``

Replace these placeholders everywhere they appear. The examples on these pages use them as written.

.. toctree::
   :maxdepth: 1

   broker
   app
   caddy
   tailnet
   verify
