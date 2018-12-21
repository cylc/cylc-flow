.. _Requirements:

Installation
============

Cylc runs on Linux. It is tested quite thoroughly on modern RHEL and Ubuntu
distros. Some users have also managed to make it work on other Unix variants
including Apple OS X, but they are not officially tested and supported.

Third-Party Software Packages
-----------------------------

**Python 2** ``>=`` **2.6** is required. **Python 2** ``>=`` **2.7.9** is
recommended for the best security. `Python <https://python.org/>`_ 2 should
already be installed in your Linux system.

For Cylc's HTTPS communications layer:

- `OpenSSL <https://www.openssl.org/>`_
- `pyOpenSSL <http://www.pyopenssl.org/>`_
- `python-requests <http://docs.python-requests.org/>`_
- **python-urllib3** - should be bundled with python-requests

The following packages are highly recommended, but are technically optional as
you can construct and run suites without dependency graph visualisation or
the Cylc GUIs:

- `PyGTK <http://www.pygtk.org>`_ - GUI toolkit.

  .. note::

     PyGTK typically comes with your system Python. It is allegedly quite
     difficult to install if you need to do so for another Python version.

- `Graphviz <http://www.graphviz.org>`_ - graph layout engine (tested 2.36.0)
- `Pygraphviz <http://pygraphviz.github.io/>`_ - Python Graphviz interface
  (tested 1.2). To build this you may need some *devel* packages too:
  
  - python-devel
  - graphviz-devel

The Cylc Review service does not need any further packages to those
already required (Python 2) and bundled with Cylc (CherryPy and Jinja2).

The following packages are necessary for running all the tests in Cylc:

- `mock <https://mock.readthedocs.io>`_

The User Guide is generated from LaTeX source files by running
``make`` in the top level Cylc directory. The specific packages
required may vary by distribution, e.g.:

- texlive
- texlive-tocloft
- texlive-framed
- texlive-preprint (for ``fullpage.sty``)
- texlive-tex4ht
- texlive-generic-extra (for ``dirtree.sty``)

To generate the HTML User Guide **ImageMagick** is also needed.

In most modern Linux distributions all of the software above can be installed
via the system package manager. Otherwise download packages manually and follow
their native installation instructions. To check that all (non LaTeX packages)
are installed properly:

.. code-block:: none

   $ cylc check-software
   Checking your software...

   Individual results:
   =============================================================================
   Package (version requirements)                        Outcome (version found)
   =============================================================================
                               *REQUIRED SOFTWARE*                                 
   Python (2.6+, <3)...................FOUND & min. version MET (2.7.12.final.0)

     *OPTIONAL SOFTWARE for the GUI & dependency graph visualisation*           
   Python:pygtk (2.0+).........................FOUND & min. version MET (2.24.0)
   graphviz (any).................................................FOUND (2.38.0)
   Python:pygraphviz (any).........................................FOUND (1.3.1)

                   *OPTIONAL SOFTWARE for the HTML User Guide*                     
   ImageMagick (any).............................................FOUND (6.8.9-9)

              *OPTIONAL SOFTWARE for the HTTPS communications layer*                
   Python:urllib3 (any)...........................................FOUND (1.13.1)
   Python:OpenSSL (any)...........................................FOUND (17.2.0)
   Python:requests (2.4.2+).....................FOUND & min. version MET (2.9.1)

                   *OPTIONAL SOFTWARE for the LaTeX User Guide*                     
   TeX:framed (any)..................................................FOUND (n/a)
   TeX (3.0+)..............................FOUND & min. version MET (3.14159265)
   TeX:preprint (any)................................................FOUND (n/a)
   TeX:tex4ht (any)..................................................FOUND (n/a)
   TeX:tocloft (any).................................................FOUND (n/a)
   TeX:texlive (any).................................................FOUND (n/a)
   =============================================================================

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

   $ cylc check-software Python graphviz imagemagick

With arguments, check-software provides an exit status indicating a
collective pass (zero) or a failure of that number of packages to satisfy
the requirements (non-zero integer).

Software Bundled With Cylc
--------------------------

Cylc bundles several third party packages which do not need to be installed
separately.

- `cherrypy <http://www.cherrypy.org/>`_ **6.0.2** (slightly modified): a pure
  Python HTTP framework that we use as a web server for communication between
  server processes (suite server programs) and client programs (running tasks,
  GUIs, CLI commands).

  - Client communication is via the Python
    `requests <http://docs.python-requests.org/>`_ library if available
    (recommended) or else pure Python via **urllib2**.

- `Jinja2 <http://jinja.pocoo.org/>`_ **2.10**: a full featured template
  engine for Python, and its dependency
  `MarkupSafe <http://www.pocoo.org/projects/markupsafe/>`_ **0.23**; both
  BSD licensed.

- the `xdot <https://github.com/jrfonseca/xdot.py>`_ graph viewer (modified),
  LGPL licensed.


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
adding a ``<cylc-dir>/etc/job-init-env.sh`` file and populate it with the
appropriate contents. If customisation is still required, you can add your own
``${HOME}/.cylc/job-init-env.sh`` file and populate it with the
appropriate contents.

- ``${HOME}/.cylc/job-init-env.sh``
- ``<cylc-dir>/etc/job-init-env.sh``

The job will attempt to source the first of these files it finds to set up its
environment.

.. _RTAST:

Automated Tests
^^^^^^^^^^^^^^^

The cylc test battery is primarily intended for developers to check that
changes to the source code don't break existing functionality.

.. note::

   Some test failures can be expected to result from suites timing out,
   even if nothing is wrong, if you run too many tests in parallel. See
   ``cylc test-battery --help``.
