puresec-cli
======================

Install
-------

.. code:: bash

   sudo pip3 install git+https://github.com/puresec/puresec-cli.git

Usage
-----

.. code:: bash

    puresec --help

Development
-----------

.. code:: bash

    pip install -r requirements.txt
    nosetests -c nose.cfg
    python -m puresec_cli --help

Release
----------

#. Set ``__version__`` in ``puresec_cli/__init__.py``
#. Set ``analytics.write_key`` in ``puresec_cli/stats.py``

