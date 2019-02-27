.. _SuiteStorageEtc:

Suite Storage, Discovery, Revision Control, and Deployment
==========================================================

Small groups of cylc users can of course share suites by manual copying,
and generic revision control tools can be used on cylc suites as for any
collection of files. Beyond this cylc does not have a built-in solution
for suite storage and discovery, revision control, and deployment, on a
network. That is not cylc's core purpose, and large sites may have
preferred revision control systems and suite meta-data requirements that
are difficult to anticipate. We can, however, recommend the use of
*Rose* to do all of this very easily and elegantly with cylc suites.


.. _Rose:

Rose
----

**Rose** is *a framework for managing and running suites of
scientific applications*, developed at the Met Office for use with
cylc. It is available under the open source GPL license.

- `Rose documentation <http://metomi.github.io/rose/doc/rose.html>`_
- `Rose source repository <https://github.com/metomi/rose>`_


.. only:: builder_html

   .. include:: custom/whitespace_include
