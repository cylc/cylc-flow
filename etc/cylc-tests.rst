.. _RTAST:

Automated Tests
---------------

For development purposes there are four sets of tests:

Unittests
   Fast to run Python unittests.

   Location
      ``cylc/flow/tests``
   Configuration
      ``pytest.ini``
   Execution
      .. code-block:: console

         $ pytest

Regression (functional) Tests
   Large scale integration tests of the whole Cylc machinary.

   Location
      * ``tests/``
      * ``flakytests/``
   Execution
      .. code-block:: console

         $ bin/run-functional-tests DIR

   .. note::

      Some test failures can be expected to result from suites timing out,
      even if nothing is wrong, if you run too many tests in parallel. See
      ``bin/run-functional-tests --help``.

Code Style Tests
   Tests to ensure the codebase conforms to code style.

   Execution
      .. code-block:: console

         $ pycodestyle --ignore=E402,W503,W504 \
            cylc/flow \
            $(grep -l '#!.*\<python\>' bin/*)
         $ etc/bin/shellchecker
