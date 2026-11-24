Account lifecycle
=================

The account browser is available to superusers from the ``SystemAdmin``
page. Open **User account browser** and use **Disable user**, **Enable
user**, or **Delete user**. Deletion opens a separate confirmation form.

You can run the same operations with ``moin`` as the user who owns the
wiki instance. Use the instance configuration directory and URL.

.. code-block:: sh

   moin --config-dir=/srv/wiki --wiki-url=https://wiki.example.org/ account disable --name ExampleUser
   moin --config-dir=/srv/wiki --wiki-url=https://wiki.example.org/ account enable --name ExampleUser
   moin --config-dir=/srv/wiki --wiki-url=https://wiki.example.org/ account delete --name ExampleUser

Each command also accepts ``--uid`` in place of ``--name``. Select by ID
if a legacy username matches several profiles. The delete command
permanently removes the selected profile. The associated wiki pages,
attachments, and revision history stay on disk.

A disabled account retains its username, email, password hash and
subscriptions. Its username and email stay reserved. The account cannot
sign in or receive wiki notifications while disabled, and an existing
session stops granting access. Enabling makes the stored settings usable
again.

Older disable commands sometimes appended ``-<user ID>`` to the name and
email, and emptied subscriptions. Enabling restores the original name and
email when those values can be recovered without colliding with other
profiles. If there is a conflict, the operation leaves the account
disabled and reports the conflict for an administrator to resolve.
Previously discarded subscriptions can be restored from a backup or
recreated by the user.
