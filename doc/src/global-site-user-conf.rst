.. _SiteAndUserConfiguration:

Global (Site, User) Configuration Files
=======================================

Cylc site and user global configuration files contain settings that affect all
suites. Some of these, such as the range of network ports used by cylc,
should be set in the site ``global.rc`` config file. Legal items,
values, and system defaults are documented in (:ref:`SiteRCReference`).

Others, such as the preferred text editor for suite configurations,
can be overridden by users in ``~/.cylc/<CYLC_VERSION>/global.rc``

.. literalinclude:: ../../cylc/flow/etc/global.rc.eg
   :language: none
