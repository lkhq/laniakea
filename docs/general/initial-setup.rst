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
    sudo apt install --no-install-recommends flatpak
    sudo apt install flake8 pylint mypy pylint isort black # if you want to add code linting / test support
    sudo pip install firehose # or install python3-firehose from Debian unstable/experimental

If you want to use the web-based GUI, you will also need these modules installed:

.. code-block:: bash

    sudo apt install python3-flask python3-flask-restful python3-flask-login npm
    sudo pip install Flask-Caching

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

    # master group, for the lesser groups to exchange files with master
    sudo addgroup --system lkmaster
    # generic user for various administrative tasks, e.g. archive creation & management
    # NOTE: This user needs a HOME directory, mostly because of GnuPG silliness
    sudo adduser --system --disabled-login --disabled-password --ingroup lkmaster lkmaster
    # user for the "Lighthouse" message relay service & job distribution system
    sudo adduser --system --disabled-login --disabled-password --no-create-home lklighthouse
    # user for web services as well as the Matrix bot
    sudo adduser --system --disabled-login --disabled-password --no-create-home --ingroup www-data lkweb
    # web user needs to be a member of the master user group for HTTPS web uploads
    sudo adduser lkweb lkmaster

2. Create database
******************

Create a new PostgreSQL database and user for Laniakea:

.. code-block:: bash

    sudo -u postgres psql -c "CREATE USER lkmaster WITH PASSWORD 'notReallySecret';" # ensure to change the DB user password!
    sudo -u postgres psql -c "CREATE DATABASE laniakea WITH OWNER lkmaster;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE laniakea TO lkmaster;"
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

To set up a new Debian package archive with multiple repositories, check out the commands that
``lk-admin archive`` provides:

.. code-block:: shell-session

    $ lk-admin archive --help

You can run the individual, interactive commands to first add a new repository to the archive, add suites,
add architectures, associate suites and repositories etc.
You can also decide instead of going the interactive route, to create your configuration as a TOML file
and have ``lk-admin`` import it to apply your configuration.
The TOML file format follows the CLI arguments of ``lk-admin archive`` you can find an example
in the Laniakea testsuite as `archive-config.toml <https://github.com/lkhq/laniakea/blob/master/tests/test_data/config/archive-config.toml>`__.

You can import your own file like this to set up your archive configuration:

.. code-block:: shell-session

    $ lk-admin archive add-from-config ./archive-config.toml

This action, if run multiple times, should not add suites multiple times, it will however override existing
properties of suites with the same time.
Deleting suites, architectures or repositories is currently not possible.

Autobuilder Setup
-----------------

TODO

Web Service Setup
-----------------

To use any web service in production, first ensure that uWSGI is installed:

.. code-block:: bash

    $ sudo apt install uwsgi uwsgi-plugin-python3
    # if you want Nginx as web server:
    $ sudo apt install nginx

Web Dashboard Service
*********************

In order to configure the web dashboard service, create the necessary configuration in
``/var/lib/laniakea/webdash/config.cfg``:

.. code-block:: python

    PROJECT = 'PurrOS'
    SECRET_KEY = '<secret_key_here>'

    CACHE_TYPE = 'FileSystemCache'
    CACHE_DIR = '/var/lib/laniakea/webdash/cache/'

    DEBUG = False
    TESTING = False

Set the caching backend you want (filesystem, redis, memcached, ...) and ensure you generate a new
secret key. Generating a secret key is asy with this Python snippet:

.. code-block:: python

    import secrets
    print(secrets.token_hex(32))

Then make sure the web application directory has the correct ownership, and launch it
using ``systemctl``:

.. code-block:: shell-session

    $ sudo chown -Rv lkweb:www-data /var/lib/laniakea/webdash/
    $ sudo systemctl restart laniakea-webdash ; sudo systemctl status laniakea-webdash


You can then configure your webserver to serve the right static content
from the web application (depending on your template choice) and configure it
to use the uWSGI web application at ``/run/laniakea-webdash/webdash.sock``.

Software Viewer Service
***********************

Just like with the web dashboard service, we create a configuration file for the software
viewer web application:
``/var/lib/laniakea/webdash/config.cfg``:

.. code-block:: python

    PROJECT = 'PurrOS'
    SECRET_KEY = '<secret_key_here>'

    THEME = 'default'
    CACHE_TYPE = 'FileSystemCache'
    CACHE_DIR = '/var/lib/laniakea/webswview/cache/'

    DEBUG = False
    TESTING = False

Make sure to configure caching and secrets just like the web dashboard.
Then change the directory ownership if necessary and launch the application:

.. code-block:: shell-session

    $ sudo chown -Rv lkweb:www-data /var/lib/laniakea/webswview/
    $ sudo systemctl restart laniakea-webswview ; sudo systemctl status laniakea-webswview

You can then configure your webserver to serve the right static content
from the web application (depending on your template choice) and configure it
to use the uWSGI web application at ``/run/laniakea-webswview/webswview.sock``.

Artifact Upload Service
***********************

The build workers as well as user upload artifacts (packages, ISO images, Flatpak builds, ...)
to the archive using `dput(1)` via HTTPS.
Just like with the other web applications, we create a configuration file:
``/var/lib/laniakea/webupload/config.cfg``:

.. code-block:: python

    SECRET_KEY = '<secret_key_here>'

    DEBUG = False
    TESTING = False

This tool does not need much configuration except for the secret key for future use.
Then create the incoming directory in your Laniakea workspace (adjust as needed!)
and give it the proper permissions, so the `lkweb` user can write, and the `lkmaster`
user can read and delete files:

.. code-block:: shell-session

    $ sudo mkdir /var/lib/laniakea/webupload/logs
    $ sudo chown lkweb:www-data /var/lib/laniakea/webupload/logs
    $ sudo mkdir /srv/laniakea-ws/archive-incoming
    $ sudo chown -Rv lkweb:lkmaster /srv/laniakea-ws/archive-incoming
    $ sudo chmod -Rv g+rw /srv/laniakea-ws/archive-incoming

You can then configure your webserver to serve this web applcation
in the right location, using socket ``/run/laniakea-upload/webupload.sock``.

Keep in mind that you need to allow for a pretty high HTTP body size to allow for large uploads.
If you are using Nginx, you can use this configuration snippet to serve the upload application from
a subdirectory:

.. code-block:: nginx

    location /_upload {
        client_max_body_size 3G;

        include     uwsgi_params;
        uwsgi_pass  unix:/run/laniakea-upload/webupload.sock;
        uwsgi_param SCRIPT_NAME /_upload;
    }

Troubleshooting
---------------

TODO
