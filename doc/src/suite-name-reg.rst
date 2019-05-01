.. _SuiteRegistration:

Suite Name Registration
=======================

Suite Registration
------------------

Cylc commands target suites via their names, which are relative path names
under the suite run directory (``~/cylc-run/`` by default). Suites can
be grouped together under sub-directories. E.g.:

.. code-block:: bash

   $ cylc print -t nwp
   nwp
    |-oper
    | |-region1  Local Model Region1       /home/oliverh/cylc-run/nwp/oper/region1
    | `-region2  Local Model Region2       /home/oliverh/cylc-run/nwp/oper/region2
    `-test
      `-region1  Local Model TEST Region1  /home/oliverh/cylc-run/nwp/test/region1

Suite names can be pre-registered with the ``cylc register`` command,
which creates the suite run directory structure and some service files
underneath it. Otherwise, ``cylc run`` will do this at suite start up.


.. _SuiteNames:

Suite Names
-----------

Suite names are not validated. Names for suites can be anything that is a
`valid filename <https://en.wikipedia.org/wiki/Filename#Comparison_of_filename_limitations>`_ within your operating system's file system,
e.g. for Linux any name that does not contain any forward slash characters
(``/``) and is not too long (as described under :ref:`TaskNames`).


.. only:: builder_html

   .. include:: custom/whitespace_include
