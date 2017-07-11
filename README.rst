Core engine for `serverless-puresec-cli <https://github.com/puresec/serverless-puresec-cli/>`_
..............................................................................................

Requirements
------------

- Python 3.4+

Usage
-----

See Serverless plugin: `serverless-puresec-cli <https://github.com/puresec/serverless-puresec-cli/>`_.

Development
-----------

Install dependencies, run the tests, and run the CLI (without ``pip`` installing).

.. code:: bash

    ./setup.py install
    ./setup.py test
    python3 -m puresec_cli --help

Then fork and pull request!

Release
-------

#. Set ``__version__`` in ``puresec_cli/__init__.py``
#. Commit, and run ``git tag vX.X.X`` replacing ``X.X.X`` with the new version
#. Set ``analytics.write_key`` in ``puresec_cli/stats.py`` **DON'T COMMIT IT**
#. Run ``./setup.py sdist upload``
#. Update version of https://github.com/puresec/serverless-puresec-cli
#. Update backend latest version

Anonymous statistics
--------------------

In order to continue improving this tool, the CLI will be sending anonymous statistics about your usage.
All reported information contains non-personal predictable information from your execution, along with a
random unique identifier that is attach to you. Predictable means that it won't send any local paths, function names, etc.

To opt out of anonymous statistics simply run:

.. code:: bash

    puresec --stats disable # or 'enable' if it's a wonderful day

One final report will be transmitted about your unsubscription, with no further details.
