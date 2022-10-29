Initial Setup
=============

Requirements
------------

Laniakea requires a PostgreSQL database with the ``debversion`` extension, and the Meson build tool to
get up and running, as well as several Python modules and utilities.
To install every requirement needed except for components needed for the web services,
you can use this command on Debian-based systems (Debian 12 or newer required):

.. code-block:: bash

    sudo apt install pkg-config meson postgresql postgresql-*-debversion \
                     gir1.2-appstream-1.0 appstream ostree apt-utils \
                     python3-packaging python3-systemd python3-humanize \
                     python3-tornado python3-sqlalchemy python3-alembic  \
                     python3-psycopg2 python3-debian python3-zmq python3-yaml \
                     python3-marshmallow python3-nacl python3-apt python3-pebble \
                     python3-click python3-requests python3-apscheduler \
                     python3-gi python3-rich python3-tomlkit python3-voluptuous \
                     python3-pip dose-builddebcheck dose-distcheck
    sudo apt install --no-install-recommends flatpak flatpak-builder
    sudo apt install flake8 pylint mypy pylint isort black # if you want to add code linting / test support
    sudo pip install firehose # or install python3-firehose from Debian unstable/experimental

If you want to use the web-based GUI, you will also need these modules installed:

.. code-block:: bash

    sudo apt install python3-flask python3-flask-caching \
                     python3-flask-restful python3-flask-login npm

If you want to use the Matrix bot, you will need Mautrix:

.. code-block:: bash

    sudo pip install mautrix

(for pip modules, installing globally should work fine, but we still recommend virtual environments on
production systems)

Build
-----

Create a build directory below the top-level directory that holds the
meson.build file and call Meson from it.
There is a multitude of configuration options for Laniakea to enable/disable specific modules.
Here are some of the most common configurations:

Build without web frontend & without tests
******************************************
.. code-block:: bash

    mkdir build && cd build
    meson -Dwebgui=false -Dlinting=false ..
    ninja

Build web frontend & Matrix bot only, no tests
**********************************************
.. code-block:: bash

    mkdir build && cd build
    meson -Dlinting=false -Dwebgui=true -Dmirk=true -Dcli-admin=false
          -Dlighthouse=false -Dscheduler=false -Dmailgun=false \
          -Drubicon=false -Ddebcheck=false -Dspears=false \
          -Dsynchrotron=false -Dariadne=false ..
    ninja

Build everything (including test support)
*****************************************
.. code-block:: bash

    mkdir build && cd build
    meson -Dmirk=true ..
    ninja

If you want to, you can install Laniakea system-wide. No system service that Laniakea creates will run
without a configuration file present, the system will be inert unless configured.

.. code-block:: bash

    cd build && sudo ninja install

Basic Configuration
-------------------

1. Add system user accounts
***************************

You will need to add some system users for Laniakea services to use:

.. code-block:: bash

    # generic user for various administrative tasks, e.g. archive creation & management
    sudo adduser --system --disabled-login --disabled-password --no-create-home lkmaster
    # user for the "Lighthouse" message relay service & job distribution system
    sudo adduser --system --disabled-login --disabled-password --no-create-home lklighthouse
    # user for web services as well as the Matrix bot
    sudo adduser --system --disabled-login --disabled-password --no-create-home --ingroup www-data lkweb

2. Create database
******************

Create a new PostgreSQL database and user for Laniakea:

.. code-block:: bash

    sudo -u postgres psql -c "CREATE DATABASE laniakea;"
    sudo -u postgres psql -c "CREATE USER lkmaster WITH PASSWORD 'notReallySecret';" # ensure to change the DB user password!
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE laniakea to lkmaster;"
    sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS debversion;" laniakea

3. Create basic configuration & populate database
*************************************************

Edit ``/etc/laniakea/base-config.toml`` and add the database settings.
Use the `base-config.toml.sample <https://github.com/lkhq/laniakea/blob/master/contrib/base-config.toml.sample>`__
file for reference.
Essential values for the configuration are ``ProjectName`` and the fields in ``Database``, the other
values are optional, depending on which Laniakea features you are using.

To create the initial database run the following command:

.. code-block:: shell-session

    $ lk-admin core db-init

Now set some elemental settings using an interactive shell wizard:

.. code-block:: shell-session

    $ lk-admin core configure-all

Package Archive Setup
---------------------

TODO

Autobuilder Setup
-----------------

TODO

Web Service Setup
-----------------

TODO

Troubleshooting
---------------

TODO
