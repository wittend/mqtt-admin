For ordinary users
==================

You use the portal to change the password for your MQTT account. You don't need a VPN or any software.

What you need
-------------

* Your MQTT username and current password. Your administrator gives you these.
* A web browser on any device with internet access.

Change your password
--------------------

1. Open the portal's address, ``https://<portal-host>/account``. It takes you to the sign-in page.
2. Sign in with your MQTT username and current password.
3. Enter your current password, then the new password twice.
4. Submit the form. The portal confirms the change and asks you to sign in again with the new password.

.. important::

   Your MQTT devices and applications use the same password. After you change it, update every device or application that connects with your account. Until you do, they cannot connect.

Password rules
--------------

* At least 12 characters, and at most 128.
* It must not contain your username.
* It must use at least five different characters. A password made of one character repeated is refused.

If the portal refuses a password, it tells you which rule failed.

Sign-in limits
--------------

After five wrong passwords for one account within 15 minutes, the portal refuses further attempts on that account until the 15 minutes pass. Twenty wrong attempts from one address in the same period also trigger a refusal. Wait 15 minutes and try again.

Sessions
--------

Your sign-in lasts 30 minutes from the time you sign in. If you see the sign-in page again, sign in once more.

When you change your password, the portal signs you out in that browser. You must sign in with the new password.

Problems
--------

* **"Invalid username or password."** Check the username and password. Passwords are case-sensitive.
* **"Too many failed attempts."** Wait 15 minutes. Then try again with the correct password, or ask an administrator to reset it.
* **"The current password is wrong."** When changing a password, the current password must be entered correctly.
* **"Form expired."** The page was open too long. Reload the page and submit it again.
* **Page does not load.** Check the address, then ask your administrator whether the portal is running.
