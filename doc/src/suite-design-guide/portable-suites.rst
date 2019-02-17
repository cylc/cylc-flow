.. _Portable Suites Label:

Portable Suites
===============

A *portable* or *interoperable* suite can run "out of the box" at
different sites, or in different environments such as research and operations
within a site.  For convenience we just use the term *site portability*.

Lack of portability is a major barrier to collaborative development when
sites need to run more or less the same workflow, because it is very
difficult to translate changes manually between large, complicated suites.

Most suites are riddled with site-specific details such as local build
configurations, file paths, host names, and batch scheduler directives, etc.;
but it is possible to cleanly factor all this out to make a portable suite.
Significant variations in workflow structure can even be accommodated quite
easily. If the site workflows are *too different*, however, you may decide
that it is appropriate for each site to maintain separate suites.

The recommended way to do this, which we expand on below, is:

- Put all site-specific settings in include-files loaded at the end
  of a generic "core" suite definition.
- Use "optional" app config files for site-specific variations
  in the core suite's Rose apps.
- (Make minimal use of inlined site switches too, if necessary).
- When referencing files, reference them within the suite structure and
  use an install task to link external files in.

The result should actually be tidier than the original in one respect: all
the messy platform-specific resource directives etc., will be hidden away in
the site include-files.


The Jinja2 SITE Variable
------------------------

First a suite Jinja2 variable called ``SITE`` should be set to the site
name, either in ``rose-suite.conf``, or in the suite definition itself
(perhaps automatically, by querying the local environment in some way).

.. code-block:: cylc

   #!Jinja2
   {% set SITE = "niwa" %}
   #...

This will be used to select site-specific configuration, as described below.


Site Include-Files
------------------

If a section heading in a suite.rc file is repeated the items under it simply
add to or override those defined under the same section earlier in the file
(but note :ref:`List Item Override In Site Include-Files`).
For example, this task definition:

.. code-block:: cylc

   [runtime]
       [[foo]]
           script = run-foo.sh
           [[[remote]]]
               host = hpc1.niwa.co.nz

can equally be written like this:

.. code-block:: cylc

   [runtime]  # Part 1 (site-agnostic).
       [[foo]]
           script = run-foo.sh
   [runtime]  # Part 2 (site-specific).
       [[foo]]
           [[[remote]]]
               host = hpc1.niwa.co.nz

.. note::

   If Part 2 had also defined ``script`` the new value would
   override the original. It can sometimes be useful to set a widely used
   default and override it in a few cases, but be aware that this can
   make it more difficult to determine the origin of affected values.

In this way all site-specific ``[runtime]`` settings, with their
respective sub-section headings, can be moved to the end of the file, and then
out into an include-file (file inclusion is essentially just literal inlining):

.. code-block:: cylc

   #...
   {% set SITE = "niwa" %}

   # Core site-agnostic settings:
   #...
   [runtime]
       [[foo]]
           script = run-foo.sh
   #...

   # Site-specific settings:
   {% include 'site/' ~ SITE ~ '.rc' %}

where the site include-file ``site/niwa.rc`` contains:

.. code-block:: cylc

   # site/niwa.rc
   [runtime]
       [[foo]]
           [[[remote]]]
               host = hpc1.niwa.co.nz


Site-Specific Graphs
--------------------

Repeated ``graph`` strings under the same graph section headings are
always additive (graph strings are the only exception to the normal repeat item
override semantics). So, for instance, this graph:

.. code-block:: cylc

   [scheduling]
       initial cycle point = 2025
       [[dependencies]]
           [[[P1Y]]]
               graph = "pre => model => post => niwa_archive"

can be written like this:

.. code-block:: cylc

   [scheduling]
       initial cycle point = 2025
       [[dependencies]]
           [[[P1Y]]]
               graph = "pre => model => post"
           [[[P1Y]]]
               graph = "post => niwa_archive"

and again, the site-specific part can be taken out to a site include-file:

.. code-block:: cylc

   #...
   {% set SITE = "niwa" %}

   # Core site-agnostic settings.
   #...
   [scheduling]
       initial cycle point = 2025
       [[dependencies]]
           [[[P1Y]]]
               graph = "pre => model => post"
   #...
   # Site-specific settings:
   {% include 'site/' ~ SITE ~ '.rc' %}

where the site include-file ``site/niwa.rc`` contains:

.. code-block:: cylc

   # site/niwa.rc
   [scheduling]
       [[dependencies]]
           [[[P1Y]]]
               graph = "post => niwa_archive"

Note that the site-file graph needs to define the dependencies of the
site-specific tasks, and thus their points of connection to the core
suite - which is why the core task ``post`` appears in the graph here (if
``post`` had any site-specific runtime settings, to get it to run at
this site, they would also be in the site-file).


.. _Inlined Site-Switching:

Inlined Site-Switching
----------------------

It may be tempting to use inlined switch blocks throughout the suite instead of
site include-files, but *this is not recommended* - it is verbose and
untidy (the greater the number of supported sites, the bigger the
mess) and it exposes all site configuration to all users:

.. code-block:: cylc

   #...
   [runtime]
       [[model]]
           script = run-model.sh
   {# Site switch blocks not recommended:#}
   {% if SITE == 'niwa' %}
           [[[job]]]
               batch system = loadleveler
           [[[directives]]]
               # NIWA Loadleveler directives...
   {% elif SITE == 'metoffice' %}
           [[[job]]]
               batch system = pbs
           [[[directives]]]
               # Met Office PBS directives...
   {% elif SITE == ... %}
               #...
   {% else %}
       {{raise('Unsupported site: ' ~ SITE)}}
   {% endif %}
       #...

Inlined switches can be used, however, to configure exceptional behaviour at
one site without requiring the other sites to duplicate the default behaviour.
But be wary of accumulating too many of these switches:

.. code-block:: cylc

   # (core suite.rc file)
   #...
   {% if SITE == 'small' %}
      {# We can't run 100 members... #}
      {% set ENSEMBLE_SIZE = 25 %}
   {% else %}
      {# ...but everyone else can! #}
      {% set ENSEMBLE_SIZE = 100 %}
   {% endif %}
   #...

Inlined switches can also be used to temporarily isolate a site-specific
change to a hitherto non site-specific part of the suite, thereby avoiding the
need to update all site include-files before getting agreement from the suite
owner and collaborators.


Site-Specific Suite Variables
-----------------------------

It can sometimes be useful to set site-specific values of suite variables that
aren't exposed to users via ``rose-suite.conf``. For example, consider
a suite that can run a special post-processing workflow of some kind at sites
where IDL is available. The IDL-dependence switch can be set per site like this: 

.. code-block:: cylc

   #...
   {% from SITE ~ '-vars.rc' import HAVE_IDL, OTHER_VAR %}
   graph = """
     pre => model => post
   {% if HAVE_IDL %}
         post => idl-1 => idl-2 => idl-3
   {% endif %}
           """

where for ``SITE = niwa`` the file ``niwa-vars.rc`` contains:

.. code-block:: cylc

   {# niwa-vars.rc #}
   {% set HAVE_IDL = True %}
   {% set OTHER_VAR = "the quick brown fox" %}

Note we are assuming there are significantly fewer options (IDL or not, in this
case) than sites, otherwise the IDL workflow should just go in the site
include-files of the sites that need it.


Site-Specific Optional Suite Configs
------------------------------------

During development and testing of a portable suite you can use an optional Rose
suite config file to automatically set site-specific suite inputs and thereby
avoid the need to make manual changes every time you check out and run a new
version. The site switch itself has to be set of course, but there may be other
settings too such as model parameters for a standard local test domain. Just
put these settings in ``opt/rose-suite-niwa.conf`` (for site "niwa")
and run the suite with ``rose suite-run -O niwa``.


Site-Agnostic File Paths in App Configs
---------------------------------------

Where possible apps should be configured to reference files within the suite
structure itself rather than outside of it. This makes the apps themselves
portable and it becomes the job of the install task to ensure all required
source files are available within the suite structure e.g. via symlink into
the share directory. Additionally, by moving the responsibility of linking
files into the suite to an install task you gain the added benefit of knowing
if a file is missing at the start of a suite rather than part way into a run.


Site-Specific Optional App Configs
----------------------------------

Typically a few but not all apps will need some site customization, e.g. for
local archive configuration, local science options, or whatever. To avoid
explicit site-customization of individual task-run command lines use Rose's
built-in *optional app config* capability:

.. code-block:: cylc

   [runtime]
       [[root]]
           script = rose task-run -v -O '({{SITE}})'

Normally a missing optional app config is considered to be an error, but the 
round parentheses here mean the named optional config is optional - i.e.
use it if it exists, otherwise ignore.

With this setting in place we can simply add a ``opt/rose-app-niwa.conf`` to
any app that needs customization at ``SITE = niwa``.


An Example
----------

The following small suite is not portable because all of its tasks are
submitted to a NIWA HPC host; two task are entirely NIWA-specific in that they 
respectively install files from a local database and upload products to a local
distribution system; and one task runs a somewhat NIWA-specific configuration
of a model. The remaining tasks are site-agnostic apart from local job host
and batch scheduler directives.

.. code-block:: cylc

   [cylc]
       UTC mode = True
   [scheduling]
       initial cycle point = 2017-01-01
       [[dependencies]]
           [[[R1]]]
               graph = install_niwa => preproc
           [[[P1D]]]
               graph = """
                   preproc & model[-P1D] => model => postproc => upload_niwa
                   postproc => idl-1 => idl-2 => idl-3"""
   [runtime]
       [[root]]
           script = rose task-run -v
       [[HPC]]  # NIWA job host and batch scheduler settings.
           [[[remote]]]
               host = hpc1.niwa.co.nz
           [[[job]]]
               batch system = loadleveler
           [[[directives]]]
               account_no = NWP1623
               class = General
               job_type = serial  # (most jobs in this suite are serial)
       [[install_niwa]]  # NIWA-specific file installation task.
           inherit = HPC
       [[preproc]]
           inherit = HPC
       [[model]]  # Run the model on a local test domain.
           inherit = HPC
           [[[directives]]]  # Override the serial job_type setting.
               job_type = parallel
           [[[environment]]]
               SPEED = fast
       [[postproc]]
           inherit = HPC
       [[upload_niwa]]  # NIWA-specific product upload.
           inherit = HPC

To make this portable, refactor it into a core suite.rc file that contains the
clean site-independent workflow configuration and loads all site-specific
settings from an include-file at the end:

.. code-block:: cylc

   # suite.rc: CORE SITE-INDEPENDENT CONFIGURATION.
   {% set SITE = 'niwa' %}
   {% from 'site/' ~ SITE ~ '-vars.rc' import HAVE_IDL %}
   [cylc]
       UTC mode = True
   [scheduling]
       initial cycle point = 2017-01-01
       [[dependencies]]
           [[[P1D]]]
               graph = """
   preproc & model[-P1D] => model => postproc
   {% if HAVE_IDL %}
       postproc => idl-1 => idl-2 => idl-3
   {% endif %}
                       """
   [runtime]
       [[root]]
           script = rose task-run -v -O '({{SITE}})'
       [[preproc]]
           inherit = HPC
       [[preproc]]
           inherit = HPC
       [[model]]
           inherit = HPC
           [[[environment]]]
               SPEED = fast
   {% include 'site/' ~ SITE ~ '.rc' %}

plus site files ``site/niwa-vars.rc``:

.. code-block:: cylc

   # site/niwa-vars.rc: NIWA SITE SETTINGS FOR THE EXAMPLE SUITE.
   {% set HAVE_IDL = True %}

and ``site/niwa.rc``:

.. code-block:: cylc

   # site/niwa.rc: NIWA SITE SETTINGS FOR THE EXAMPLE SUITE.
   [scheduling]
       [[dependencies]]
           [[[R1]]]
               graph = install_niwa => preproc
           [[[P1D]]]
               graph = postproc => upload_niwa
   [runtime]
       [[HPC]]
           [[[remote]]]
               host = hpc1.niwa.co.nz
           [[[job]]]
               batch system = loadleveler
           [[[directives]]]
               account_no = NWP1623
               class = General
               job_type = serial  # (most jobs in this suite are serial)
       [[install_niwa]]  # NIWA-specific file installation.
       [[model]]
           [[[directives]]]  # Override the serial job_type setting.
               job_type = parallel
       [[upload_niwa]]  # NIWA-specific product upload.

and finally, an optional app config file for the local model domain:

.. code-block:: bash

   app/model/rose-app.conf  # Main app config.
   app/model/opt/rose-app-niwa.conf  # NIWA site settings.

Some points to note:

- It is straightforward to extend support to a new site by copying an
  existing site file(s) and adapting it to the new job host and batch
  scheduler etc.
- Batch system directives should be considered site-specific unless
  all supported sites have the same batch system and the same host
  architecture (including CPU clock speed and memory size etc.).
- We've assumed that all tasks run on a single HPC host at both
  sites. If that's not a valid assumption the ``HPC`` family
  inheritance relationships would have to become site-specific.
- Core task runtime configuration aren't needed in site files at all
  if their job host and batch system settings can be defined in common
  families that are (``HPC`` in this case).


.. _Collaborative Development Model:

Collaborative Development Model
-------------------------------

Official releases of a portable suite should be made from the suite trunk.

Changes should be developed on feature branches so as not to affect other users
of the suite.

Site-specific changes shouldn't touch the core suite.rc file, just the relevant
site include-file, and therefore should not need close scrutiny from other
sites.

Changes to the core suite.rc file should be agreed by all stakeholders, and
should be carefully checked for effects on site include-files:

- Changing the name of tasks or families in the core suite may break
  sites that add configuration to the original runtime namespace.
- Adding new tasks or families to the core suite may require
  corresponding additions to the site files.
- Deleting tasks or families from the core suite may require
  corresponding parts of the site files to be removed. And also, check for
  site-specific triggering off of deleted tasks or families.

However, if the owner site has to get some changes into the trunk before all
collaborating sites have time to test them, version control will of course
protect those lagging behind from any immediate ill effects.

When a new feature is complete and tested at the developer's site, the suite
owner should check out the branch, review and test it, and if necessary request
that other sites do the same and report back. The owner can then merge the
new feature to the trunk once satisfied.

All planning and discussion associated with the change should be documented on
MOSRS Trac tickets associated with the suite.


Research-To-Operations Transition
---------------------------------

Under this collaborative development model it is *possible* to use the
same suite in research and operations, largely eliminating the difficult
translation between the two environments. Where appropriate, this can save
a lot of work.

Operations-specific parts of the suite should be factored out (as for site
portability) into include-files that are only loaded in the operational
environment. Improvements and upgrades can be developed on feature branches in
the research environment. Operations staff can check out completed feature
branches for testing in the operational environment before merging to trunk or
referring back to research if problems are found. After sufficient testing the
new suite version can be deployed into operations.

.. note::

   This obviously glosses over the myriad complexities of the technical
   and scientific testing and validation of suite upgrades; it merely describes
   what is possible from a suite design and collaborative development
   perspective.
