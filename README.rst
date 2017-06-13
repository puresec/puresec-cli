puresec-generate-roles
======================

A CLI tool for creating cloud roles with least privilege permissions
using static code analysis.

Install
-------

.. code:: bash

   sudo pip3 install --process-dependency-links git+https://github.com/puresec/puresec-generate-roles.git

Usage
-----

.. code:: bash

    puresec-gen-roles --help

Development
-----------

.. code:: bash

    pip install -r requirements.txt
    nosetests -c nose.cfg
    python -m puresec_generate_roles --help

