puresec-generate-roles
======================

A CLI tool for creating cloud roles with least privilege permissions
using static code analysis.

Install
-------

.. code:: bash

   pip install --process-dependency-links git+ssh://git@github.com/puresec/puresec-generate-roles.git

Usage
-----

.. code:: bash

    puresec-gen-roles --help

Development
-----------

.. code:: bash

    pip install -r requirements.txt
    nosetests -c nose.cfg
