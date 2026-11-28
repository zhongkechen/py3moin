Installing and operating Py3Moin
================================

Py3Moin continues the MoinMoin 1.x wiki engine on Python 3. The
``py3moin`` package version is independent of MoinMoin 2, the separate
rewrite. This guide uses the 1.9 filesystem instance layout.

Install from a source checkout
------------------------------

Use Python 3.10 or later. The commands below use a POSIX shell and start
in the repository root. Keep the instance data in a separate directory so
that replacing the checkout or virtual environment leaves it intact.

.. code-block:: sh

   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install .

   instance="$PWD/../py3moin-instance"
   mkdir -m 700 "$instance"
   cp -R wiki/data "$instance/"
   cp wiki/config/wikiconfig.py "$instance/"
   tar -xf wiki/underlay.tar -C "$instance"

   moin --config-dir="$instance" server standalone --hostname=127.0.0.1 --port=8080

Open http://127.0.0.1:8080/ and follow a Help link. The default server
also serves packaged CSS, JavaScript, and images. The static URL prefix
is generated from the package version. If you change the mount path,
review ``url_prefix_static`` in the sample configuration.

The standalone server is suitable for local use and staging. The Docker
image uses uWSGI for deployments. See the `Docker workflow`_ and the
`first-run change`_ for the image initializer and persistent mount commands.
The initializer requires an empty directory. Run initialization and the
server with the same user and group.

.. _Docker workflow: ../.github/workflows/docker-publish.yml
.. _first-run change: https://github.com/zhongkechen/py3moin/pull/39

Instance layout and permissions
-------------------------------

``wikiconfig.py`` selects the wiki directories and settings. It is Python
code. Restart the server after changing it. The default layout contains
``data/pages`` for page revisions and attachments, ``data/user`` for user
profiles, ``data/plugin`` for site plugins, and ``underlay/pages`` for
bundled system and help pages. Docker adds ``moin.wsgi`` and ``uwsgi.ini``
to the instance directory.

The server account needs read access to the configuration and underlay,
and write access to the data, user, and cache directories. Keep the
instance directory outside any web server document root. Use the same
account for maintenance commands and preserve access restrictions when
copying data. Back up the instance, including any separately configured
user or plugin directories and any custom underlay content.

Migrate a Python 2 MoinMoin 1.9 instance
-------------------------------------

1. Pause writes on the old wiki and back up its configuration, data,
   underlay, external user directory, and custom plugins. Keep the old
   runtime and an untouched backup available for rollback.
2. Create an isolated staging instance using the source instructions above
   or an initialized Docker directory. Stop the staging server and put a
   copy of the old data and underlay at the paths selected by the staging
   configuration. Copy a separate ``user_dir`` too, if applicable. Keep
   page directories, ``current`` pointers, revision files, attachments,
   user profiles, and logs together.
3. Start from the current sample ``wikiconfig.py`` and port your settings.
   Recheck ACLs, account names, mail, farm mappings, and the static URL
   prefix. Review and port each plugin to Python 3 and the current Request
   and Context interfaces before enabling it. Stage without external mail
   delivery while checking accounts and content.
4. With the staging server stopped, clear inherited caches and sessions as
   the staging service account. Use the staging URL and configuration.
   Users will sign in again after the migration.

   .. code-block:: sh

      moin --config-dir="$instance" --wiki-url=http://127.0.0.1:8080/ maint cleancache
      mv "$instance/data/cache/__session__" "$instance/data/cache/__session__.before-migration"

   The second command applies when that default session directory exists.
   If you configured ``session_dir`` separately, set aside that directory
   instead. The server recreates it as needed. ``cleancache`` also clears
   editor drafts. Keep the pre-migration snapshot if you need those drafts.
5. Start staging and validate a current page, an old revision, a login,
   an attachment download, an edit, search, and a restricted page with
   both authorized and anonymous users. Check any optional features you
   rely on. Compare the recovered content against the backup.
6. During cutover, freeze writes, take a fresh backup, and repeat the
   validated copy and cache steps for the final snapshot. If rollback is
   required, stop the new server and restore the old runtime and the
   untouched pre-cutover snapshot. Preserve any later writes separately
   for reconciliation before resuming updates on the old wiki.

For source data older than MoinMoin 1.9, use the `historical conversion
notes`_ to reach a working 1.9 instance first.

.. _historical conversion notes: README.migration

Accounts and help pages
-----------------------

Run account commands from the virtual environment as the wiki service
account. ``moin account create --help`` lists its options. Set
``superuser = ['WikiAdmin']`` in ``wikiconfig.py`` and restart for the
administrator tools. Superuser status and page ACL rights are configured
separately. The default policy restricts web registration to superusers.

Use the browser's password preferences for a signed-in account. A wiki
with working mail settings can also deliver a password reset link.
Reversible account disabling and profile deletion are tracked in
`issue #30`_. Markdown page support is tracked in `issue #29`_.

The supplied underlay includes ``LanguageSetup`` and English help pages.
Use ``language_default`` for the site's default language and
``page_front_page`` for its landing page. Keep local pages in ``data`` and
review any customized underlay files before replacing the bundled help
content on upgrade. The language-package installer requires a superuser
and actual package attachments on ``LanguageSetup``. The bundled archive
provides help pages but contains no language-package ZIP attachments.

.. _issue #30: https://github.com/zhongkechen/py3moin/issues/30
.. _issue #29: https://github.com/zhongkechen/py3moin/issues/29

Development and optional services
---------------------------------

Install the checkout into a virtual environment as above, then run:

.. code-block:: sh

   python -m pytest -q tests/
   PYTHONWARNINGS=error::SyntaxWarning python -m compileall -q -f MoinMoin
   python -m pip wheel --no-deps --wheel-dir dist .

The `Python compatibility workflow`_ defines the test selection and
Python matrix. The selected checks cover Python compatibility, request
handling, persistence, attachment, rendering, and search regressions.
The main ``tests/`` suite can also be run locally. The historical data
conversion tests under ``MoinMoin/script/migration`` are outside that
suite. The Docker workflow defines its separate image checks.

The basic wiki uses built-in search and local account authentication.
Indexed Xapian search, LDAP, OpenID, and real SMTP delivery require
additional configuration or services and are outside the standard
compatibility checks. Xapian falls back to built-in search when bindings
are missing. OpenID has an optional ``openid`` dependency extra. The
legacy XSLT and DocBook integrations belong to the historical upstream
installation notes. Keep ``allow_xslt`` disabled.

.. _Python compatibility workflow: ../.github/workflows/python-compat.yml
