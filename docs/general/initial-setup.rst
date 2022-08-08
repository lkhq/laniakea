Initial Setup
=============

If you're interested in running Laniakea in a container, see `the
Dockerfiles found here <https://github.com/lkhq/laniakea/tree/master/tests/ci/>`__
Please note that we only use those for testing and do not recommend using them in production!

Requirements
------------

Laniakea requires a postgresql database, and the meson build tool to
get up and running. If you don’t already have those packages
installed, install them now;

.. code-block:: bash

    sudo apt install pkg-config meson postgresql libappstream-dev gir1.2-appstream-1.0 ostree flatpak flatpak-builder podman npm
    # Install python dependencies 
    sudo apt install python3-pip python3-setuptools python3-virtualenv python3-pytest python3-gi python3-cairo-dev python3-sqlalchemy python3-alembic python3-psycopg2 python3-nacl python3-debian python3-apt python3-zmq python3-yaml python3-systemd python3-flask python3-flask-restful python3-pytest-flask python3-humanize python3-marshmallow

Build
-----

Create a build directory below the top-level directory that holds the
meson.build file and call meson from it;

| $ mkdir build && cd build $ meson -Dwebgui=true -Drubicon=true
  -Dlighthouse=true -Ddebcheck=true
| -Dspears=true -Dsynchrotron=true -Dplanter=true -Dariadne=true ../ $
  ninja

Configure
---------

Then edit /etc/laniakea/base-config.toml and add the database settings
you care about.
See `base-config.toml.sample <https://github.com/lkhq/laniakea/blob/master/contrib/base-config.toml.sample>`__
for an example. Also don’t forget to create the db and user. The
configuration will need “ProjectName” and “Database” to be set, the
other values can be ignored.

$ lk-admin core –-init-db
$ lk-admin core -–config

Answer all the questions it asks.

$ ./src/webswview/manage.py run

A webserver will be running, serving a version of webswview. The site
will probably be quite empty, because there are no packages and apps in
the database

[ placeholder to sync with another postgres db? ]

TODO
----

Troubleshooting
---------------

You may run into an error around the python module ‘pyd’

::

   Run-time dependency pyd found: NO (tried pkgconfig and cmake)
   meson.build:21:0: ERROR: Dependency "pyd" not found, tried pkgconfig and cmake

Simply follow the instructions above to build pyd from source.
