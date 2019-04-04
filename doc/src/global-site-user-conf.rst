.. _SiteAndUserConfiguration:

Global (Site, User) Configuration Files
=======================================

Cylc site and user global configuration files contain settings that affect all
suites. Some of these, such as the range of network ports used by cylc,
should be set at site level. Legal items, values, and system defaults are
documented in (:ref:`SiteRCReference`).

.. code-block:: bash

   # cylc site global config file
   <cylc-dir>/etc/global.rc

Others, such as the preferred text editor for suite configurations,
can be overridden by users,

.. code-block:: bash

   # cylc user global config file
   ~/.cylc/$(cylc --version)/global.rc  # e.g. ~/.cylc/7.8.2/global.rc

The file ``<cylc-dir>/etc/global.rc.eg`` contains instructions on how
to generate and install site and user global config files:

.. literalinclude:: ../../etc/global.rc.eg
   :language: none
