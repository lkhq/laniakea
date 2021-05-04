Initial Setup
=============

If you're interested in running Laniakea in Docker, see (this
document)[https://github.com/lkorigin/laniakea/blob/master/tests/ci/Dockerfile]

Requirements
------------

Laniakea requires a postgresql database, and the meson build tool to
get up and running. If you don’t already have those packages
installed, install them now;

$ sudo apt install postgresql-11 postgresql-11-debversion meson ldc
libarchive libcurl

$ git clone https://github.com/lkorigin/pyd.git $ mkdir build && cd
build $ meson –prefix=/usr –buildtype=debugoptimized $ ninja $ sudo
ninja install

| Install the necessary Python modules and compilers/libraries
  python3-pytest python3-sqlalchemy python3-alembic
  python3-flask-caching
| python3-psycopg2 python-debian python3-zmq python3-yaml flake8
| python3-systemd python3-firehose python3-humanize python3-marshmallow
| python3-tornado python3-nacl python-gobject-2 python3-pytest-flask
| python3-flask python3-flask-script python3-flask-restful
| gir1.2-appstream-1.0

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

Then edit /etc/laniakea/base-config.json and add the database settings
you care about. See
https://github.com/lkorigin/laniakea/blob/master/tests/test_data/config/base-config.json
for an example. Also don’t forget to create the db and user. The
configuration will need “ProjectName” and “Database” to be set, the
other values can be ignored.

$ ./src/admin/lk-admin.py core –init-db $ ./src/admin/lk-admin.py core
–config

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
