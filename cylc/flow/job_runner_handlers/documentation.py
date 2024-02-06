# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This file is used to auto-generate some reference documentation for the
job runner plugin interface.

Note the class contained here is just for documentation purposes and is
not intended to be subclassed.
"""

from typing import (
    Iterable,
    List,
    Tuple,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    import re


class ExampleHandler():
    """Documentation for writing job runner handlers.

    Cylc can submit jobs to a number of different job runners
    (aka batch systems) e.g. Slurm and PBS. For a list of built-in integrations
    see :ref:`AvailableMethods`.

    If the job runner you require is not on this list, Cylc provides a generic
    interface for writing your own integration.

    Defining a new job runner handler requires a little Python programming. Use
    the built-in handlers
    (e.g. :py:mod:`cylc.flow.job_runner_handlers.background`) as examples.

    .. _where to put job runner handler modules:

    .. rubric:: Installation

    Custom job runner handlers must be installed on workflow and job
    hosts in one of these locations:

    - under ``WORKFLOW-RUN-DIR/lib/python/``
    - under ``CYLC-PATH/cylc/flow/job_runner_handlers/``
    - or anywhere in ``$PYTHONPATH``

    Each module should export the symbol ``JOB_RUNNER_HANDLER`` for the
    singleton instance that implements the job system handler logic e.g:

    .. code-block:: python
       :caption: my_handler.py

       class MyHandler():
           pass

       JOB_RUNNER_HANDLER = MyHandler()

    Each job runner handler class should instantiate with no argument.


    .. rubric:: Usage

    You can then define a Cylc platform using the handler:

    .. code-block:: cylc
       :caption: global.cylc

       [platforms]
           [[my_platform]]
               job runner = my_handler  # note matches Python module name
               hosts = localhost

    And configure tasks to submit to it:

    .. code-block:: cylc
       :caption: flow.cylc

       [runtime]
           [[my_task]]
               script = echo "Hello World!"
               platform = my_platform


    .. rubric:: Common Arguments

    ``job_conf: dict``
       The Cylc job configuration as a dictionary with the following fields:

       * ``dependencies``
       * ``directives``
       * ``env-script``
       * ``environment``
       * ``err-script``
       * ``execution_time_limit``
       * ``exit-script``
       * ``flow_nums``
       * ``init-script``
       * ``job_d``
       * ``job_file_path``
       * ``job_runner_command_template``
       * ``job_runner_name``
       * ``namespace_hierarchy``
       * ``param_var``
       * ``platform``
       * ``post-script``
       * ``pre-script``
       * ``script``
       * ``submit_num``
       * ``task_id``
       * ``try_num``
       * ``uuid_str``
       * ``work_d``
       * ``workflow_name``

    ``submit_opts: dict``
       The Cylc job submission options as a dictionary which may contain
       the following fields:

       * ``env``
       * ``execution_time_limit``
       * ``execution_time_limit``
       * ``job_runner_cmd_tmpl``
       * ``job_runner_cmd_tmpl``


    .. rubric:: An Example

    The following ``qsub.py`` module overrides the built-in *pbs*
    job runner handler to change the directive prefix from ``#PBS`` to
    ``#QSUB``:

    .. TODO - double check that this still works, it's been a while

    .. code-block:: python

       #!/usr/bin/env python3

       from cylc.flow.job_runner_handlers.pbs import PBSHandler

       class QSUBHandler(PBSHandler):
           DIRECTIVE_PREFIX = "#QSUB "

       JOB_RUNNER_HANDLER = QSUBHandler()

    If this is in the Python search path (see
    :ref:`Where To Put Job Runner Handler Modules` above) you can use it by
    name in your global configuration:

    .. code-block:: cylc

       [platforms]
           [[my_platform]]
               hosts = myhostA, myhostB
               job runner = qsub  # <---!

    Then in your ``flow.cylc`` file you can use this platform:

    .. code-block:: cylc

       # Note, this workflow will fail at run time because we only changed the
       # directive format, and PBS does not accept ``#QSUB`` directives in
       # reality.

       [scheduling]
           [[graph]]
               R1 = "a"
       [runtime]
           [[root]]
               execution time limit = PT1M
               platform = my_platform
               [[[directives]]]
                   -l nodes = 1
                   -q = long
                   -V =

    .. note::

       Don't subclass this class as it provides optional interfaces which
       you may not want to inherit.

    """

    FAIL_SIGNALS: Tuple[str]
    """A tuple containing the names of signals to trap for reporting errors.

    The default is ``("EXIT", "ERR", "TERM", "XCPU")``.

    ``ERR`` and ``EXIT`` are always recommended.
    ``EXIT`` is used to report premature stopping of the job
    script, and its trap is unset at the end of the script.
    """

    KILL_CMD_TMPL: str
    """Command template for killing a job submission.

    A Python string template for getting the job runner command to remove
    and terminate a job ID. The command is formed using the logic:
    ``job_runner.KILL_CMD_TMPL % {"job_id": job_id}``.

    For info on Python string template format see:
    https://docs.python.org/3/library/stdtypes.html#printf-style-string-formatting

    """

    POLL_CMD: str
    """Command for checking job submissions.

    A list of job IDs to poll will be provided as arguments.

    The command should write valid submitted/running job IDs to stdout.

    * To filter out invalid/failed jobs use
      :py:meth:`ExampleHandler.filter_poll_many_output`.
    * To build a more advanced command than is possible with this configuration
      use :py:meth:`ExampleHandler.get_poll_many_cmd`.

    """

    POLL_CANT_CONNECT_ERR: str
    """String for detecting communication errors in poll command output.

    A string containing an error message. If this is defined, when a poll
    command returns a non-zero return code and its STDERR contains this
    string, then the poll result will not be trusted, because it is assumed
    that the job runner is currently unavailable. Jobs submitted to the
    job runner will be assumed OK until we are able to connect to the
    job runner again.

    """

    SHOULD_KILL_PROC_GROUP: bool
    """Kill jobs by killing the process group.

     A boolean to indicate whether it is necessary to kill a job by sending
     a signal to its Unix process group. This boolean also indicates that
     a job submitted via this job runner will physically run on the same
     host it is submitted to.

    """

    SHOULD_POLL_PROC_GROUP: bool
    """Poll jobs by PID.

    A boolean to indicate whether it is necessary to poll a job by its PID
    as well as the job ID.

    """

    REC_ID_FROM_SUBMIT_OUT: 're.Pattern'
    """Regular expression to extract job IDs from submission stderr.

    A regular expression (compiled) to extract the job "id" from the standard
    output or standard error of the job submission command.

    """

    REC_ID_FROM_SUBMIT_ERR: 're.Pattern'
    """Regular expression to extract job IDs from submission stderr.

    See :py:attr:`ExampleHandler.REC_ID_FROM_SUBMIT_OUT`.

    """

    SUBMIT_CMD_ENV: Iterable[str]
    """Extra environment variables for the job runner command.

       A Python dict (or an iterable that can be used to update a dict)
       containing extra environment variables for getting the job runner
       command to submit a job file.

    """

    SUBMIT_CMD_TMPL: str
    """Command template for job submission.

    A Python string template for getting the job runner command to submit a
    job file. The command is formed using the logic:
    ``job_runner.SUBMIT_CMD_TMPL % {"job": job_file_path}``

    For info on Python string template format see:
    https://docs.python.org/3/library/stdtypes.html#printf-style-string-formatting

    """

    def filter_poll_many_output(self, out: str) -> List[str]:
        """Filter job ides out of poll output.

        Called after the job runner's poll command. The method should read
        the output and return a list of job IDs that are still in the
        job runner.

        Args:
            out: Job poll stdout.

        Returns:
            List of job IDs

        """
        raise NotImplementedError()

    def filter_submit_output(self, out: str, err: str) -> Tuple[str, str]:
        """Filter job submission stdout/err.

        Filter the standard output and standard error of the job submission
        command. This is useful if the job submission command returns
        information that should just be ignored.

        See also :py:meth:`ExampleHandler.SUBMIT_CMD_TMPL`.

        Args:
            out: Job submit stdout.
            err: Job submit stderr.

        Returns:
            (new_out, new_err)
        """
        raise NotImplementedError()

    def format_directives(self, job_conf: dict) -> List[str]:
        """Returns lines to be appended to the job script.

        This method formats the job directives for a job file, if
        job file directives are relevant for the job runner. The argument
        "job_conf" is a dict containing the job configuration.

        Args:
            job_conf: The Cylc configuration.

        Returns:
            lines

        """
        raise NotImplementedError()

    def get_poll_many_cmd(self, job_id_list: List[str]) -> List[str]:
        """Return a command to poll the specified jobs.

        If specified, this will be called instead of
        :py:attr:`ExampleHandler.POLL_CMD`.

        Args:
            job_id_list: The list of job IDs to poll.

        Returns:
            command e.g. ['foo', '--bar', 'baz']

        """
        raise NotImplementedError()

    def get_submit_stdin(self, job_file_path: str, submit_opts: dict) -> Tuple:
        """

        Return a 2-element tuple ``(proc_stdin_arg, proc_stdin_value)``.

        * Element 1 is suitable for the ``stdin=...`` argument of
          ``subprocess.Popen`` so it can be a file handle, ``subprocess.PIPE``
          or ``None``.
        * Element 2 is the string content to pipe to stdin of the submit
          command (relevant only if ``proc_stdin_arg`` is ``subprocess.PIPE``.

        Args:
            job_file_path: The path to the job file for this submission.
            submit_opts: Job submission options.

        Returns:
            (proc_stdin_arg, proc_stdin_value)

        """
        raise NotImplementedError()

    def get_vacation_signal(self, job_conf: dict) -> str:
        """Return the vacation signal.

        If relevant, return a string containing the name of the signal that
        indicates the job has been vacated by the job runner.

        Args:
            job_conf: The Cylc configuration.

        Returns:
            signal

        """
        raise NotImplementedError()

    def submit(
        self,
        job_file_path: str,
        submit_opts: dict,
    ) -> Tuple[int, str, str]:
        """Submit a job.

        Submit a job and return an instance of the Popen object for the
        submission. This method is useful if the job submission requires logic
        beyond just running a system or shell command.

        See also :py:attr:`ExampleHandler.SUBMIT_CMD_TMPL`.

        You must pass "env=submit_opts.get('env')" to Popen - see
        :py:mod:`cylc.flow.job_runner_handlers.background`
        for an example.

        Args:
            job_file_path: The job file for this submission.
            submit_opts: Job submission options.

        Returns:
            (ret_code, out, err)

        """
        raise NotImplementedError()

    def manip_job_id(self, job_id: str) -> str:
        """Modify the job ID that is returned by the job submit command.

        Args:
            job_id: The job ID returned by the submit command.

        Returns:
            job_id

        """
        raise NotImplementedError()
