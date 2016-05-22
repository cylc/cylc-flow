---
layout: default
title: features
---

## Features

* Comprehensive *command line* and *graphical* user interfaces.
* *Distributed suites* - run tasks on remote hosts.
* Submits jobs to many *batch schedulers* (PBS, slurm, etc.).
* Remote *job poll* and *kill*. 
* Handles *thousands of tasks* in a single suite.
* *Edit Run* - edit job scripts on the fly, just before execution.
* One-off (non-cycling) workflows.
* Integer cycling workflows.
* ISO 8601 compliant *date-time cycling* workflows.
* Broadcast information to tasks (including inter-task communication).
* Special behaviour at start-up, shut-down, and anywhere between.
* *Inter-suite dependence* - triggering tasks off tasks in other suites.
* *Restarts* - even handles jobs orphaned when the suite was down.
* *Reload* modified suite configurations at run time.
* Group tasks into *families* for triggering, and inheritance of settings.
* *Failure recovery* by automatic task retries or alternate workflows.
* *Task and suite event hooks and timeouts*.
* *Simulation mode* - get the scheduling right without running real tasks.
* Use the *Jinja2 Template Processor* for programming suite definitions.
* *Internal Queues* to limit the number of simultaneously active tasks.
* *Conditional triggers*.
* *Clock-triggers* - trigger off the clock as well as off other tasks.
* *Event triggers* - trigger off external events as well as other tasks.
* *Expiring tasks* - optionally skip tasks that are too far behind the clock.
* *Validation* - catch many errors prior to run time.
* Handles *thousands of tasks* in a single workflow.
* Written in [Python](https://www.python.org).
