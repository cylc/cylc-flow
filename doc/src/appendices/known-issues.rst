.. _KnownIssues:

Known Issues
============


.. _CurrentKnownIssues:

Current Known Issues
--------------------

The best place to find current known issues is on
`GitHub <https://github.com/cylc/cylc-flow/issues>`_.


.. _NotableKnownIssues:

Notable Known Issues
--------------------


.. _PipeInJobScripts:

Use of pipes in job scripts
^^^^^^^^^^^^^^^^^^^^^^^^^^^

In bash, the return status of a pipeline is normally the exit status of the
last command. This is unsafe, because if any command in the pipeline fails, the
script will continue nevertheless.

For safety, a cylc task job script running in bash will have the
``set -o pipefail`` option turned on automatically. If a pipeline
exists in a task's ``script``, etc section, the failure of any part of
a pipeline will cause the command to return a non-zero code at the end, which
will be reported as a task job failure. Due to the unique nature of a pipeline,
the job file will trap the failure of the individual commands, as well as the
whole pipeline, and will attempt to report a failure back to the suite twice.
The second message is ignored by the suite, and so the behaviour can be safely
ignored. (You should probably still investigate the failure, however!)


.. only:: builder_html

   .. include:: ../custom/whitespace_include
