MoinMoin
========

MoinMoin is a wiki engine - a software you can use to run your own wiki site.

This is a fork of MoinMoin 1.x that runs on Python 3.10 and newer.

Docker
======

The latest image is published to the GitHub Container Registry. Pull it,
create a persistent instance directory, and copy the default wiki files into
that directory:

.. code-block:: console

   $ docker pull ghcr.io/zhongkechen/py3moin:latest
   $ mkdir py3moin-data
   $ docker run --rm --user "$(id -u):$(id -g)" \
       -v "$PWD/py3moin-data:/data" \
       ghcr.io/zhongkechen/py3moin:latest \
       sh -c 'cp -r /app/wiki/data /data/ &&
              cp /app/wiki/config/wikiconfig.py /app/wiki/server/moin.wsgi /data/ &&
              tar -xf /app/wiki/underlay.tar -C /data'

Create ``py3moin-data/uwsgi.ini`` with the following contents:

.. code-block:: ini

   [uwsgi]
   http-socket = 0.0.0.0:8080
   plugin = python3
   chdir = /data
   wsgi-file = /data/moin.wsgi
   master = true
   processes = 2
   threads = 2
   need-app = true

Start the wiki:

.. code-block:: console

   $ docker run -d \
       --name py3moin \
       --restart unless-stopped \
       -p 8080:8080 \
       -v "$PWD/py3moin-data:/data" \
       ghcr.io/zhongkechen/py3moin:latest

Open http://localhost:8080/ in a browser. Wiki content and configuration are
stored in ``py3moin-data``; back up this directory and edit
``py3moin-data/wikiconfig.py`` to configure the instance.

The same image is also available from Docker Hub as
``docker.io/ch3n2k/py3moin:latest``.

Documentation
=============

On the Web:

MoinMoin homepage, last seen at: https://moinmo.in/

This page also points to support resources and informations about MoinMoin
development status and plans.

For support, please try the documentation, the homepage, the irc channel
and the mailing list before contacting the MoinMoin authors directly.

Local:

- docs/CHANGES                 for a version history. READ THIS!
- docs/REQUIREMENTS            for a list of requirements.
- docs/INSTALL.html            for installation instructions.
- docs/README.migration        for data conversion instructions.

Note that the code base contains some experimental or unfinished features.
Use them at your own risk. Official features are described on the set of
help pages contained in the distribution wiki.
