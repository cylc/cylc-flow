Cylc Development History - Major Changes
========================================

- **pre-cylc-3**

  - early versions focused on the new
    scheduling algorithm. A suite was a collection of "task definition files"
    that encoded the prerequisites and outputs of each task,
    exposing cylc's self-organising nature. Tasks could be transferred
    from one suite to another by simply copying their taskdef files over
    and checking prerequisite and output consistency. Global suite
    structure was not easy to discern until run time (although cylc-2
    could generate resolved run time dependency graphs).

- **cylc-3**

  - a new suite design interface: dependency graph and task runtime properties
    defined in a single structured, validated, configuration file - the
    suite.rc file
  - graphical user interface
  - suite graphing.

- **cylc-4**

  - refined and organized the suite.rc file structure
  - task runtime properties defined by an efficient inheritance hierarchy
  - support for the Jinja2 template processor in suite configurations.

- **cylc-5**

  - multi-threading for continuous network request handling and job submission
  - more task states to distinguish job submission from execution
  - dependence between suites via new suite run databases
  - polling and killing of real task jobs
  - polling as task communications option.

- **cylc-6**

  - specification of all date-times and cycling workflows via the ISO8601
    date-times, durations, and recurrence expressions
  - integer cycling
  - a multi-process pool to execute job submissions, event handlers, and poll
    and kill commands.

- **cylc-7**

  - Replaced the Pyro communications layer with RESTful HTTPS
  - Removed deprecated pre cylc-6 syntax and features.
