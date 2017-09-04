---
layout: default
title: features
---

## Features

* *Distributed suites* - run tasks on remote hosts.
* *Validation* - catch many errors prior to run time.
* Comprehensive *command line* and *graphical* user interfaces.
* Submits jobs to many common *batch schedulers* (PBS, slurm, etc.).
* Remote *job poll* and *job kill*. 
* *Edit Run* - edit job scripts on the fly just before submission.
* ISO 8601 compliant *date-time cycling* workflows.
* Integer cycling workflows.
* *Broadcast* information to tasks (including inter-task communication).
* Run special tasks at start-up, shut-down, and anywhere between.
* *Inter-suite dependence* - robust triggering off tasks in other suites.
* *Restart* from previous state - even recovers orphaned jobs.
* *Reload* modified suite configurations at run time.
* Group tasks into *families* for triggering, and inheritance of settings.
* *Failure recovery* by automatic task retries or alternate workflows.
* Flexible *event handling* - task and suite event hooks and timeouts.
* *Simulation mode* and *dummy mode* with proportional run length.
* Use the *Jinja2 Template Processor* for programming suite definitions.
* *Internal Queues* to limit the number of simultaneously active tasks.
* *Conditional triggering*.
* Generate similar tasks efficiently by *parameter expansion*.
* *Clock-triggers* - trigger off the clock as well as off other tasks.
* *Event triggers* - trigger off external events as well as other tasks.
* *Expiring tasks* - optionally skip tasks that are too far behind the clock.
* Handles *several thousand cycling tasks* in a single ongoing workflow.
* Written in [Python](https://www.python.org).
