Spark Worker Setup
==================

This document describes the setup process for a Laniakea Spark Worker.
Spark is the generic Laniakea job runner and package build executor.
It is able to perform a variety of tasks on Laniakea on build-farms, like building
packages or distribution ISO images.

.. note::
    Spark workers are not intended to be set up manually. You will usually want to spawn and update
    them fully automatically, for example by using a toolk like `Ansible <https://www.ansible.com/>`__.
    We provide an Ansible template to provision Spark workers at `github.com/lkhq/spark-setup <https://github.com/lkhq/spark-setup>`__.

This document assumes you already set up a working Laniakea installation, and you know
the riquired Lighthouse credentials.

Requirements
------------

All of the worker's dependencies are contained within Debian.
If you are not using the Ansible recipe, you need to install them manually:

.. code-block:: bash

    sudo apt install \
        python3-debian \
    	python3-zmq \
    	python3-setuptools \
    	python3-firehose \
    	gnupg \
    	dput-ng \
    	debspawn

You can the install Spark:

.. code-block:: bash

    pip install git+https://github.com/lkhq/laniakea-spark.git


1. Add lkspark user and group
-----------------------------

.. code-block:: bash

    adduser --system --home=/var/lib/lkspark lkspark
    addgroup lkspark
    chown lkspark:lkspark /var/lib/lkspark


2. Write spark.toml
-------------------

Create ``/etc/laniakea/spark.toml`` with the respective information for your deployment:

.. code-block:: toml

    LighthouseServer = 'tcp://master.example.org:5570'
    AcceptedJobs = [
        'package-build',
        'os-image-build'
    ]
    MachineOwner = 'ACME Inc.'
    GpgKeyID = 'DEADBEEF<gpg_fingerprint>'


3. Create RSA sign-only GnuPG key and Curve25519 key and register them
----------------------------------------------------------------------

Run ``lk-keytool`` to create a new certificate for the build server so it can
communicate with the master server via a secure channel:

.. code-block:: bash

    lk-keytool key-new \
        --id=hydrogen \
        --name='Hydrogen Worker' \
        --email=hydrogen@workers.wayne-enterprises.tld \
        --organization='Wayne Enterprises' \
        ./output-dir

On the **master server** you then need to install the just generated public key
to allow the Lighthouse instance running there to communicate with the worker:

.. code-block:: bash

    lk-keytool install-trusted-key hydrogen ./output-dir/hydrogen.key

You will also need to create a PGP key for signing of generated packages/build-aertifacts:

.. code-block:: bash

    gpg --export-secret-key -a myname@workers.wayne-enterprises.tld > myname_secret.gpg && \
    gpg --armor --export "myname@bworkers.wayne-enterprises.tld" > myname.gpg && \
    chmod go-rwx *secret.gpg

You should then add this key on the master server as the upload key of a non-human upload user.

4. Make Debspawn images
-----------------------

TODO

5. Add Lighthouse server key to Spark
-------------------------------------

TODO

6. Configure dput-ng
--------------------

TODO

7. Restart worker and test it
-----------------------------

TODO
