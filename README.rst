MoinMoin
========

MoinMoin is a wiki engine - a software you can use to run your own wiki site.

This is a fork of MoinMoin 1.x that runs on Python 3.10 and newer.

Docker
======

Pull the latest image from GitHub Container Registry and initialize an empty
directory owned by your user.

.. code-block:: console

   $ docker pull ghcr.io/zhongkechen/py3moin:latest
   $ mkdir py3moin-data
   $ docker run --rm --user "$(id -u):$(id -g)" \
       -v "$PWD/py3moin-data:/data" \
       ghcr.io/zhongkechen/py3moin:latest py3moin-init

The initializer copies the data and underlay templates, ``wikiconfig.py``,
``moin.wsgi``, and ``uwsgi.ini`` from the image's ``/app/wiki`` directory into
the mounted ``/data`` directory.
It refuses to initialize a nonempty directory. For an existing instance, skip
initialization and start the container with the existing directory mounted.

Start the wiki with the same user and group so it can write to the mounted
directory.

.. code-block:: console

   $ docker run -d \
       --name py3moin \
       --restart unless-stopped \
       --user "$(id -u):$(id -g)" \
       -p 127.0.0.1:8080:8080 \
       -v "$PWD/py3moin-data:/data" \
       ghcr.io/zhongkechen/py3moin:latest

Open http://localhost:8080/ in a browser. Wiki content and configuration are
stored in ``py3moin-data``. Back up this directory and edit
``py3moin-data/wikiconfig.py`` to configure the instance. The default
configuration grants anonymous visitors read access. The WSGI entry point
serves the built-in static assets.

The same image is also available from Docker Hub as
``docker.io/ch3n2k/py3moin:latest``.

Documentation
=============

- `Python 3 installation and administration <docs/PYTHON3.rst>`_
- `Current requirements <docs/REQUIREMENTS>`_
- `Upstream MoinMoin 1.x release history <docs/CHANGES>`_
- `Historical data format conversions <docs/README.migration>`_
