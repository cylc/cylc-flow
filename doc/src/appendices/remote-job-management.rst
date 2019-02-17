Remote Job Management
=====================

Managing tasks in a workflow requires more than just job execution: Cylc
performs additional actions with ``rsync`` for file transfer, and
direct execution of ``cylc`` sub-commands over non-interactive
SSH [4]_.

SSH-free Job Management?
------------------------

Some sites may want to restrict access to job hosts by whitelisting SSH
connections to allow only ``rsync`` for file transfer, and allowing job
execution only via a local batch system that sees the job hosts [5]_ .
We are investigating the feasibility of SSH-free job management when a local
batch system is available, but this is not yet possible unless your suite
and job hosts also share a filesystem, which allows Cylc to treat jobs as
entirely local [6]_ .

SSH-based Job Management
------------------------

Cylc does not have persistent agent processes running on job hosts to act on
instructions received over the network [7]_ so instead we execute job
management commands directly on job hosts over SSH. Reasons for this include:

- it works equally for batch system and background jobs
- SSH is *required* for background jobs, and for batch jobs if the
  batch system is not available on the suite host
- *querying the batch system alone is not sufficient for full job
  polling functionality* because jobs can complete (and then be forgotten by
  the batch system) while the network, suite host, or suite server program is
  down (e.g. between suite shutdown and restart)

  - to handle this we get the automatic job wrapper code to write
    job messages and exit status to *job status files* that are
    interrogated by suite server programs during job polling operations
  - job status files reside on the job host, so the interrogation
    is done over SSH

- job status files also hold batch system name and job ID; this is
  written by the job submit command, and read by job poll and kill commands
  (all over SSH)

A Concrete Example
------------------

The following suite, registered as ``suitex``, is used to illustrate
our current SSH-based remote job management. It submits two jobs to a remote,
and a local task views a remote job log then polls and kills the remote jobs.

.. code-block:: cylc

   # suite.rc
   [scheduling]
      [[dependencies]]
             graph = "delayer => master & REMOTES"
   [runtime]
      [[REMOTES]]
         script = "sleep 30"
          [[[remote]]]
              host = wizard
              owner = hobo
      [[remote-a, remote-b]]
          inherit = REMOTES
      [[delayer]]
         script = "sleep 10"
      [[master]]
          script = """
    sleep 5
    cylc cat-log -m c -f o $CYLC_SUITE_NAME remote-a.1
    sleep 2
    cylc poll $CYLC_SUITE_NAME REMOTES.1
    sleep 2
    cylc kill $CYLC_SUITE_NAME REMOTES.1
    sleep 2
    cylc remove $CYLC_SUITE_NAME REMOTES.1"""


The *delayer* task just separates suite start-up from remote job
submission, for clarity when watching the job host (e.g. with
``watch -n 1 find ~/cylc-run/suitex``).

Global config specifies the path to the remote Cylc executable, says
to retrieve job logs, and not to use a remote login shell:

.. code-block:: cylc

   # global.rc
   [hosts]
      [[wizard]]
          cylc executable = /opt/bin/cylc
          retrieve job logs = True
          use login shell = False

On running the suite, remote job host actions were captured in the transcripts
below by wrapping the ``ssh``, ``scp``, and ``rsync``
executables in scripts that log their command lines before taking action.

Create suite run directory and install source files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Done by ``rose suite-run`` before suite start-up (the command will be
migrated to Cylc soon though).

- with ``--new`` it invokes bash over SSH and a raw shell
  expression, to delete previous-run files
- it invokes itself over SSH to create top level suite directories
  and install source files

  - skips installation if server UUID file is found on the job host
    (indicates a shared filesystem)

- uses ``rsync`` for suite source file installation

.. note::

   The same directory structure is used on suite and job hosts, for
   consistency and simplicity, and because the suite host can also be a job
   host.

.. code-block:: bash

   # rose suite-run --new only: initial clean-out
   ssh -oBatchMode=yes -oConnectTimeout=10 hobo@wizard bash -l -O extglob -c 'cd; echo '"'"'673d7a0d-7816-42a4-8132-4b1ab394349c'"'"'; ls -d -r cylc-run/suitex/work cylc-run/suitex/share/cycle cylc-run/suitex/share cylc-run/suitex; rm -fr cylc-run/suitex/work cylc-run/suitex/share/cycle cylc-run/suitex/share cylc-run/suitex; (cd ; rmdir -p cylc-run/suitex/work cylc-run/suitex/share/cycle cylc-run/suitex/share cylc-run 2>/dev/null || true)'

   # rose suite-run: test for shared filesystem and create share/cycle directories
   ssh -oBatchMode=yes -oConnectTimeout=10 -n hobo@wizard env ROSE_VERSION=2018.02.0 CYLC_VERSION=7.6.x bash -l -c '"$0" "$@"' rose suite-run -vv -n suitex --run=run --remote=uuid=231cd6a1-6d61-476d-96e1-4325ef9216fc,now-str=20180416T042319Z

   # rose suite-run: install suite source directory to job host
   rsync -a --exclude=.* --timeout=1800 --rsh=ssh -oBatchMode=yes -oConnectTimeout=10 --exclude=231cd6a1-6d61-476d-96e1-4325ef9216fc --exclude=log/231cd6a1-6d61-476d-96e1-4325ef9216fc --exclude=share/231cd6a1-6d61-476d-96e1-4325ef9216fc --exclude=share/cycle/231cd6a1-6d61-476d-96e1-4325ef9216fc --exclude=work/231cd6a1-6d61-476d-96e1-4325ef9216fc --exclude=/.* --exclude=/cylc-suite.db --exclude=/log --exclude=/log.* --exclude=/state --exclude=/share --exclude=/work ./ hobo@wizard:cylc-run/suitex
      # (internal rsync)
      ssh -oBatchMode=yes -oConnectTimeout=10 -l hobo wizard rsync --server -logDtpre.iLsfx --timeout=1800 . cylc-run/suitex
      # (internal rsync, back from hobo@wizard)
      rsync --server -logDtpre.iLsfx --timeout=1800 . cylc-run/suitex

Result:

.. todo::

   Nicer dirtree display via sphinx or custom extension?

.. code-block:: bash

    ~/cylc-run/suitex
   |__log->log.20180418T025047Z  # LOG DIRECTORIES
   |__log.20180418T025047Z  # log directory for current suite run
   |__suiter.rc
   |__xxx  # any suite source sub-dirs or file
   |__work  # JOB WORK DIRECTORIES
   |__share  #  SUITE SHARE DIRECTORY
      |__cycle


Server installs service directory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- server address and credentials, so that clients such as
  ``cylc message`` executed by jobs can connect
- done just before the first job is submitted to a remote, and at
  suite restart for the remotes of jobs running when the suite went
  down (server host, port, etc. may change at restart)
- uses SSH to invoke ``cylc remote-init`` on job hosts. If the remote command
  does not find a server-side UUID file (which would indicate a shared
  filesystem) it reads a tar archive of the service directory from stdin, and
  unpacks it to install.

.. code-block:: bash

   # cylc remote-init: install suite service directory
   ssh -oBatchMode=yes -oConnectTimeout=10 hobo@wizard env CYLC_VERSION=7.6.x /opt/bin/cylc remote-init '066592b1-4525-48b5-b86e-da06eb2380d9' '$HOME/cylc-run/suitex'

Result:

.. todo::

   Nicer dirtree display via sphinx or custom extension?

.. code-block:: bash

    ~/cylc-run/suitex
   |__.service  # SUITE SERVICE DIRECTORY
   |  |__contact  # server address information
   |  |__passphrase  # suite passphrase
   |  |__ssl.cert  # suite SSL certificate
   |__log->log.20180418T025047Z  # LOG DIRECTORIES
   |__log.20180418T025047Z  # log directory for current suite run
   |__suiter.rc
   |__xxx  # any suite source sub-dirs or file
   |__work  # JOB WORK DIRECTORIES
   |__share  #  SUITE SHARE DIRECTORY
      |__cycle


Server submits jobs
^^^^^^^^^^^^^^^^^^^

- done when tasks are ready to run, for multiple jobs at once
- uses SSH to invoke ``cylc jobs-submit`` on the remote - to read job
  scripts from stdin, write them to disk, and submit them to run

.. code-block:: bash

   # cylc jobs-submit: submit two jobs
   ssh -oBatchMode=yes -oConnectTimeout=10 hobo@wizard env CYLC_VERSION=7.6.x /opt/bin/cylc jobs-submit '--remote-mode' '--' '$HOME/cylc-run/suitex/log/job' '1/remote-a/01' '1/remote-b/01'

Result:

.. todo::

   Nicer dirtree display via sphinx or custom extension?

.. code-block:: bash

    ~/cylc-run/suitex
   |__.service  # SUITE SERVICE DIRECTORY
   |  |__contact  # server address information
   |  |__passphrase  # suite passphrase
   |  |__ssl.cert  # suite SSL certificate
   |__log->log.20180418T025047Z  # LOG DIRECTORIES
   |__log.20180418T025047Z  # log directory for current suite run
   |  |__ job  # job logs (to be distinguished from log/suite/ on the suite host)
   |     |__1  # cycle point
   |        |__remote-a  # task name
   |        |  |__01  # job submit number
   |        |  |  |__job  # job script
   |        |  |  |__job.out  # job stdout
   |        |  |  |__job.err  # job stderr
   |        |  |  |__job.status  # job status
   |        |  |__NN->0l  # symlink to latest submit number
   |        |__remote-b  # task name
   |           |__01  # job submit number
   |           |  |__job  # job script
   |           |  |__job.out  # job stdout
   |           |  |__job.err  # job stderr
   |           |  |__job.status  # job status
   |           |__NN->0l  # symlink to latest submit number
   |__suiter.rc
   |__xxx  # any suite source sub-dirs or file
   |__work  # JOB WORK DIRECTORIES
   |  |__1  # cycle point
   |     |__remote-a  # task name
   |     |  |__xxx  # (any files written by job to PWD)
   |     |__remote-b  # task name
   |        |__xxx  # (any files written by job to PWD)
   |__share  #  SUITE SHARE DIRECTORY
      |__cycle
      |__xxx  # (any job-created sub-dirs and files)


Server tracks job progress
^^^^^^^^^^^^^^^^^^^^^^^^^^

- jobs send messages back to the server program on the suite host

  - directly: client-server HTTPS over the network (requires service
    files installed - see above)
  - indirectly: re-invoke clients on the suite host (requires reverse SSH)

- OR server polls jobs at intervals (requires job polling - see below)


User views job logs
^^^^^^^^^^^^^^^^^^^

- command ``cylc cat-log`` via CLI or GUI, invokes itself over SSH to the
  remote
- suites will serve job logs in future, but this will still be needed
  (e.g. if the suite is down)

.. code-block:: bash

   # cylc cat-log: view a job log
   ssh -oBatchMode=yes -oConnectTimeout=10 -n hobo@wizard env CYLC_VERSION=7.6.x /opt/bin/cylc cat-log --remote-arg='$HOME/cylc-run/suitex/log/job/1/remote-a/NN/job.out' --remote-arg=cat --remote-arg='tail -n +1 -F %(filename)s' suitex


Server cancels or kills jobs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- done automatically or via user command ``cylc kill``, for
  multiple jobs at once
- uses SSH to invoke ``cylc jobs-kill`` on the
  remote, with job log paths on the command line. Reads job ID from the
  job status file.

.. code-block:: bash

   # cylc jobs-kill: kill two jobs
   ssh -oBatchMode=yes -oConnectTimeout=10 hobo@wizard env CYLC_VERSION=7.6.x /opt/bin/cylc jobs-kill '--' '$HOME/cylc-run/suitex/log/job' '1/remote-a/01' '1/remote-b/01'


Server polls jobs
^^^^^^^^^^^^^^^^^

- done automatically or via user command ``cylc poll``, for
  multiple jobs at once
- uses SSH to invoke ``cylc jobs-poll`` on the
  remote, with job log paths on the command line. Reads job ID from the
  job status file.

.. code-block:: bash

   # cylc jobs-poll: poll two jobs
   ssh -oBatchMode=yes -oConnectTimeout=10 hobo@wizard env CYLC_VERSION=7.6.x /opt/bin/cylc jobs-poll '--' '$HOME/cylc-run/suitex/log/job' '1/remote-a/01' '1/remote-b/01'


Server retrieves jobs logs
^^^^^^^^^^^^^^^^^^^^^^^^^^

- done at job completion, according to global config
- uses ``rsync``

.. code-block:: bash

   # rsync: retrieve two job logs
   rsync -a --rsh=ssh -oBatchMode=yes -oConnectTimeout=10 --include=/1 --include=/1/remote-a --include=/1/remote-a/01 --include=/1/remote-a/01/** --include=/1/remote-b --include=/1/remote-b/01 --include=/1/remote-b/01/** --exclude=/** hobo@wizard:$HOME/cylc-run/suitex/log/job/ /home/vagrant/cylc-run/suitex/log/job/
      # (internal rsync)
      ssh -oBatchMode=yes -oConnectTimeout=10 -l hobo wizard rsync --server --sender -logDtpre.iLsfx . $HOME/cylc-run/suitex/log/job/
      # (internal rsync, back from hobo@wizard)
      rsync --server --sender -logDtpre.iLsfx . /home/hobo/cylc-run/suitex/log/job/


Server tidies job remote at shutdown
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- removes ``.service/contact`` so that clients won't repeatedly
  try to connect

.. code-block:: bash

   # cylc remote-tidy: remove the remote suite contact file
   ssh -oBatchMode=yes -oConnectTimeout=10 hobo@wizard env CYLC_VERSION=7.6.x /opt/bin/cylc remote-tidy '$HOME/cylc-run/suitex'


Other Use of SSH in Cylc
------------------------

- see if a suite is running on another host with a shared
  filesystem - see ``detect_old_contact_file()`` in
  ``lib/cylc/suite_srv_files_mgr.py``
- cat content of a remote service file over SSH, if possible, for
  clients on that do not have suite credentials installed - see
  ``_load_remote_item()`` in ``suite_srv_files_mgr.py``


.. [4] Cylc used to run bare shell expressions over SSH, which required
       a bash shell and made whitelisting difficult.
.. [5] A malicious script could be ``rsync``'d and run from a batch
       job, but batch jobs are considered easier to audit.
.. [6] The job ID must also be valid to query and kill the job via the local
       batch system. This is not the case for Slurm, unless the ``--cluster``
       option is explicitly used in job query and kill commands, otherwise
       the job ID is not recognized by the local Slurm instance.
.. [7] This would be a more complex solution, in terms of implementation,
       administration, and security.
