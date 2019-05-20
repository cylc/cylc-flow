.. _Requirements:

Installation
============

Cylc runs on Linux. It is tested quite thoroughly on modern RHEL and Ubuntu
distros. Some users have also managed to make it work on other Unix variants
including Apple OS X, but they are not officially tested and supported.

Third-Party Software Packages
-----------------------------

Requirements:

- Python 3.7+

  - `python-jose <https://pypi.org/project/python-jose/>`_
  - `zmq <https://pypi.org/project/zmq/>`_
  - `colorama <https://pypi.org/project/colorama/>`_

The following packages are necessary for running tests in Cylc:

- `pytest <https://pytest.org>`_

To generate the HTML User Guide, you will need:

- `Sphinx <http://www.sphinx-doc.org/en/master/>`_ of compatible version,
  ``>=`` **1.5.3** and ``<=`` **1.7.9**.

To check that dependencies are installed and environment is configured
correctly run ``cylc check-software``:

.. code-block:: none

   $ cylc check-software
   Checking your software...

   Individual results:
   ================================================================================
   Package (version requirements)                           Outcome (version found)
   ================================================================================
                                 *REQUIRED SOFTWARE*
   Python (3+).............................FOUND & min. version MET (3.7.2.final.0)
   Python:zmq (any)..................................................FOUND (17.1.2)
   Python:jose (any)..................................................FOUND (2.0.2)
   Python:colorama (any)..............................................FOUND (0.4.1)

                 *OPTIONAL SOFTWARE for the configuration templating*
   Python:EmPy (any)..................................................FOUND (3.3.2)

                    *OPTIONAL SOFTWARE for the HTML documentation*
   Python:sphinx (1.5.3+)..........................FOUND & min. version MET (1.8.4)
   ================================================================================

   Summary:
                             ****************************
                                Core requirements: ok
                                Full-functionality: ok
                             ****************************


If errors are reported then the packages concerned are either not installed or
not in your Python search path.

.. note::

   ``cylc check-software`` has become quite trivial as we've removed or
   bundled some former dependencies, but in future we intend to make it
   print a comprehensive list of library versions etc. to include in with
   bug reports.

To check for specific packages only, supply these as arguments to the
``check-software`` command, either in the form used in the output of
the bare command, without any parent package prefix and colon, or
alternatively all in lower-case, should the given form contain capitals. For
example:

.. code-block:: bash

   $ cylc check-software graphviz Python urllib3

With arguments, check-software provides an exit status indicating a
collective pass (zero) or a failure of that number of packages to satisfy
the requirements (non-zero integer).

Software Bundled With Cylc
--------------------------

Cylc bundles several third party packages which do not need to be installed
separately.

- `Jinja2 <http://jinja.pocoo.org/>`_ **2.10**: a full featured template
  engine for Python, and its dependency
  `MarkupSafe <http://www.pocoo.org/projects/markupsafe/>`_ **0.23**; both
  BSD licensed.


.. _InstallCylc:

Installing Cylc
---------------

Cylc releases can be downloaded from `GitHub <https://cylc.github.io/cylc>`_.

The wrapper script ``usr/bin/cylc`` should be installed to
the system executable search path (e.g. ``/usr/local/bin/``) and
modified slightly to point to a location such as ``/opt`` where
successive Cylc releases will be unpacked side by side.

To install Cylc, unpack the release tarball in the right location, e.g.
``/opt/cylc-7.7.0``, type ``make`` inside the release
directory, and set site defaults - if necessary - in a site global config file
(below).

Make a symbolic link from ``cylc`` to the latest installed version:
``ln -s /opt/cylc-7.7.0 /opt/cylc``. This will be invoked by the
central wrapper if a specific version is not requested. Otherwise, the
wrapper will attempt to invoke the Cylc version specified in
``$CYLC_VERSION``, e.g. ``CYLC_VERSION=7.7.0``. This variable
is automatically set in task job scripts to ensure that jobs use the same Cylc
version as their parent suite server program.  It can also be set by users,
manually or in login scripts, to fix the Cylc version in their environment.

Installing subsequent releases is just a matter of unpacking the new tarballs
next to the previous releases, running ``make`` in them, and copying
in (possibly with modifications) the previous site global config file.


.. _LocalInstall:

Local User Installation
^^^^^^^^^^^^^^^^^^^^^^^

It is easy to install Cylc under your own user account if you don't have
root or sudo access to the system: just put the central Cylc wrapper in
``$HOME/bin/`` (making sure that is in your ``$PATH``) and
modify it to point to a directory such as ``$HOME/cylc/`` where you
will unpack and install release tarballs. Local installation of third party
dependencies like Graphviz is also possible, but that depends on the particular
installation methods used and is outside of the scope of this document.

Create A Site Config File
^^^^^^^^^^^^^^^^^^^^^^^^^

Site and user global config files define some important parameters that affect
all suites, some of which may need to be customized for your site.
See :ref:`SiteAndUserConfiguration` for how to generate an initial site file and
where to install it. All legal site and user global config items are defined
in :ref:`SiteRCReference`.


.. _Configure Site Environment on Job Hosts:

Configure Site Environment on Job Hosts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If your users submit task jobs to hosts other than the hosts they use to run
their suites, you should ensure that the job hosts have the correct environment
for running cylc. A cylc suite generates task job scripts that normally invoke
``bash -l``, i.e. it will invoke bash as a login shell to run the job
script. Users and sites should ensure that their bash login profiles are able
to set up the correct environment for running cylc and their task jobs.

Your site administrator may customise the environment for all task jobs by
adding a site ``job-init-env.sh`` file and populate it with appropriate contents. If customisation is still required, you can add your own
``${HOME}/.cylc/job-init-env.sh`` file and populate it with the
appropriate contents.

.. TODO: define site global config dir under cylc-8

The job will attempt to source the first of these files it finds to set
up its environment.
