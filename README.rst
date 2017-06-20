puresec-cli
===========

PureSec CLI tools for improving the security of your serverless applications.

Installation
------------

.. code:: bash

   sudo pip3 install git+https://github.com/puresec/puresec-cli.git

Usage
-----

gen-roles
.........

Automatically generates least privileged roles for your functions.

.. code:: bash

   puresec gen-roles --help

Arguments
^^^^^^^^^

Some arguments are required, some arguments are inferred from the project,
and some arguments are just optional. ``gen-roles`` will try to work with a minimal
set of arguments, since it supports the simplest project (of a single code file uploaded manually
to your serverless provider).

However, the more ``gen-roles`` knows about your project (either from arguments
or from inference), the better output you'll receive.

Here are some example scenarios:

**Minimum requirements:** ``gen-roles`` must know your provider and your runtime.
You can provide those explicitly with ``--provider`` and ``--runtime``. This will make ``gen-roles``
oblivious to which functions actually exist, and will assume that the whole project is one big function (beautifully called ``UnnamedFunction``).

**Resource template (e.g CloudFormation's JSON):** a resource template (supplied with ``--resource-template`` along with ``--provider``)
will let ``gen-roles`` know which functions and other resources exist in your production environment. It will also
exempt you from specifying the ``--runtime`` since this is specified within the resource template (on a per-function basis).
Hopefully each of your functions lives in a different subdirectory of the project, so ``gen-roles`` can let you know
which roles each specific function needs.

**Framework (e.g Serverless):** by supplying ``--framework`` you don't need to supply ``--provider`` since
it is specified within the framework's configuration, and you don't need to supply ``--resource-template``
since it's your framework's responsibility to generate one (which ``gen-roles`` will do for you).
**This is by far the best and simplest option.**

One last thing: if you only want to generate roles for a specific function, use ``--function``.
Make sure you specify the same name as the one in the framework's configuration (if applicable),
rather than the name in your production environment.

Output
^^^^^^

Depending on the arguments, ``gen-roles`` will either change files in your project
(make sure you're using ``git`` to see what exactly happened!), or simply output the generated roles.
The output will be in a format matching the provider's resource template so that you can copy-paste it.

Warnings
^^^^^^^^

TODO

Anonymous statistics
....................

In order to continue improving this tool, the CLI will be sending anonymous statistics about your usage.
All reported information contains non-personal predictable information from your execution, along with a
random unique identifier that is attach to you. Predictable means that it won't send any local paths, function names, etc.

To opt out of anonymous statistics simply run:

.. code:: bash

    puresec --stats disable # or 'enable' if it's a wonderful day

One final report will be transmitted about your unsubscription, with no further details.

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

