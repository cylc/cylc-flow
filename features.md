---
layout: default
title: features
---

## Features

* Comprehensive *command line* and *graphical* user interfaces.
* *Distributed suites* - run tasks on remote hosts.
* Can handle *several thousand tasks* in a single workflow.
* Submits jobs to many *batch schedulers* (PBS, slurm, etc.).
* Remote *job poll* and *kill*. 
* *Edit Run* - edit job scripts on the fly just before submission.
* ISO 8601 compliant *date-time cycling* workflows.
* Integer cycling workflows.
* Broadcast information to tasks (including inter-task communication).
* Special behaviour at start-up, shut-down, and anywhere between.
* *Inter-suite dependence* - triggering tasks off tasks in other suites.
* *Restarts* - even handles jobs orphaned when the suite was down.
* *Reload* modified suite configurations at run time.
* Group tasks into *families* for triggering, and inheritance of settings.
* *Failure recovery* by automatic task retries or alternate workflows.
* *Task and suite event hooks and timeouts*.
* *Simulation and dummy modes* - get the scheduling right without running real tasks.
* Supports the *Jinja2 Template Processor* in suite definitions.
* *Internal Queues* to limit the number of simultaneously active tasks.
* *Conditional triggers*.
* Generate tasks by *parameter expansion*.
* *Clock-triggers* - trigger off the clock as well as off other tasks.
* *Event triggers* - trigger off external events as well as other tasks.
* *Expiring tasks* - optionally skip tasks that are too far behind the clock.
* *Validation* - catch many errors prior to run time.
* Written in [Python](https://www.python.org).
