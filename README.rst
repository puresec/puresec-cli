Core engine for `serverless-puresec-cli <https://github.com/puresec/serverless-puresec-cli/>`_
..............................................................................................

Usage
-----

See Serverless plugin: `serverless-puresec-cli <https://github.com/puresec/serverless-puresec-cli/>`_.

Development
-----------

Install dependencies, run the tests, and run the CLI (without ``pip`` installing).

.. code:: bash

    pip install -r requirements.txt
    nosetests -c nose.cfg
    python -m puresec_cli --help

Then fork and pull request!

Release
----------

#. Set ``__version__`` in ``puresec_cli/__init__.py``
#. Set ``analytics.write_key`` in ``puresec_cli/stats.py``

Anonymous statistics
--------------------

In order to continue improving this tool, the CLI will be sending anonymous statistics about your usage.
All reported information contains non-personal predictable information from your execution, along with a
random unique identifier that is attach to you. Predictable means that it won't send any local paths, function names, etc.

To opt out of anonymous statistics simply run:

.. code:: bash

    puresec --stats disable # or 'enable' if it's a wonderful day

One final report will be transmitted about your unsubscription, with no further details.
