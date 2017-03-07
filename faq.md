---
layout: default
title: FAQ
---

*See the Cylc User Guide for full documentation.*

## Frequently Asked Questions
{:.no_toc}

*This FAQ is new as of 2016, and is not yet very comprehensive.*

If you have a question that you think should be added to the FAQ,
please [email the cylc forum](mailto:cylc@google-groups.com).

## Table of Contents
{:.no_toc}

* replace-me
{:toc}

---

## Installation

### How do I install cylc?

See [INSTALL.md]({{site.github.repository_url}}/blob/master/INSTALL.md).

You can download the latest release from the [main page](./index.html) of this site.

#### What other software is required?

See [INSTALL.md#external-software-packages]({{site.github.repository_url}}/blob/master/INSTALL.md#external-software-packages).

### Does cylc run on Microsoft Windows?

No, only Linux and Unix-variants, including Apple Mac OSX.  Cylc is largely
written in Python so a Windows port should not be too difficult - but to date
there has not been any call for that in the HPC community that cylc rose out
of.

## Graphical User Interfaces (GUIs)

### Is there a web interface to cylc suites?

Not yet, but we plan to develop one.  The [current GUI](./screenshots.html) is based
on the PyGTK toolkit.

### How can I view all my running suites?

Use the [`cylc gscan`](screenshots/gscan.png) GUI

## Task Implementation

### How can I convert my job into a cylc task?

Simply call your job script or executable in the `script` item of a task definition, e.g.:

    [runtime]
       [[my-task]]
            script = my-job.sh

or embed it in inlined scripting:

    [runtime]
       [[my-task]]
            script = """
                echo 'Running my-job now'
                my-job.sh
                     """

Cylc will automatically supply the boilerplate code to handle job start-up,
completion, and error detection.

## Suite Output Files

### Where's My Task Output?

Cylc stores the job standard output and error from each task. The default location is,

    $HOME/cylc-run/<SUITE-NAME>/log/job/<CYCLE-POINT>/<TASK-NAME>/<JOB-SUBMIT-NUMBER>/

## Suite Management

### How do I store and version control my suites?

Collaborative development of complex workflow definitions requires proper
branch-and-merge version control, just like program source code. Cylc does
not have built-in version control or suite databases for the same reason that
programming languages do not have built-in version control or program
databases. Version control is the job of specialist power tools
like git and subversion, and storage and discovery requirements are very much
user, project, site, or collaboration dependent.


The [Rose](https://github.com/metomi/rose) suite management framework provides
a nice solution for suite storage, discovery, and version control (via Subversion).

### How do I install task scripts etc. to task hosts?

TBD.

### Does cylc pipeline data automatically?

TBD.
