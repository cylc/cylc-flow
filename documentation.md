---
layout: default
title: documentation
---

# Table of Contents
{:.no_toc}

* replace-me
{:toc}

---

## Documentation And Information Links

### Frequently Asked Questions
See [FAQ](./faq.html).

### The Cylc User Guide

If you have access to cylc already, type `cylc doc` or use the GUI "Help" menu
to view the User Guide.  Otherwise, an online copy is available here:

* [Cylc User Guide - PDF ~3MB](doc/cylc-user-guide.pdf)
* [Cylc User Guide - HTML single page](html/single/cug-html.html)
* [Cylc User Guide - HTML multi page](html/multi/cug-html.html)

### Presentations

Format HTML5 with embedded .webm videos (plays natively in Firefox or Chrome).
Hit the "Home" and "End" keys to skip to the beginning and end of the
presentation, and the 'o' key for a multi-slide summary. This is the
[dzslides](https://github.com/paulrouget/dzslides) framework by Paul Roget.

* [Cylc Keynote](cylc-keynote-lisbon-Sept2016/index.html) - from
  the IS-ENES2 Workshop on Workflow in Earth Systems Modeling, Lisbon,
  September 2016

### Publications, Citations, and References

The Cylc developers plan to write a reference paper in 2017.

In the meantime Cylc releases have a citable DOI:
[![DOI](https://zenodo.org/badge/1836229.svg)](https://zenodo.org/badge/latestdoi/1836229) 

#### Cylc Response to "Assessment Report on Autosubmit, Cylc and ecFlow"

*The Cylc developers would like to respond to a recent comparison paper,
__Assessment report on Autosubmit, Cylc and ecFlow (2016, Domingo Manubens-Gil
et. al.)__ and another that references it, __Seamless Management of Ensemble
Climate Prediction Experiments on HPC Platforms (2016, Domingo Manubens-Gil et.
al.)__. Two of us are listed as contributors to the first paper but it should be
noted that this contribution was limited by time and workload constraints to
correction of any major misunderstandings of Cylc.*

*The lead author of both papers is also the lead developer of Autosubmit so it
is perhaps inevitable that the comparison plays to Autosubmit’s strengths.
However this was not made clear in the comparison paper, and we would like to
address several points that we believe convey a misleading impression to
readers.*

...[CLICK HERE FOR THE FULL 2-PAGE
RESPONSE](doc/cylc-response-to-autosubmit-comparison-report.pdf) (PDF)

---

## A Cycling Workflow Example

The following example is intended to convey something of cylc's basic
functionality.  However, it barely scratches the surface; to understand more,
read the User Guide!

### Create A New Suite

    $ mkdir -p /home/bob/suites/test/
    $ vim /home/bob/suites/test/suite.rc

    [cylc]
        cycle point format = %Y

    [scheduling]
       initial cycle point = 2021
       final cycle point = 2023
       [[dependencies]]
          [[[R1]]]  # Initial cycle point.
             graph = prep => model
          [[[R//P1Y]]]  # Yearly cycling.
             graph = model[-P1D] => model => post
          [[[R1/P0Y]]]  # Final cycle point.
             graph = post => stop

    [runtime]
       [[root]]  # Inherited by all tasks.
          script = sleep 10
       [[model]]
          script = echo "my FOOD is $FOOD"; sleep 10
          [[[environment]]]
             FOOD = icecream

    [visualization]
        default node attributes = "style=filled", "shape=ellipse"
        [[node attributes]]
            prep = "fillcolor=#00c798"
            stop = "fillcolor=#ffcc00"
            model = "fillcolor=#00b4fd"
            post = "fillcolor=#ff5966"

### Register It

    $ cylc register my.suite /home/bob/suites/test
    REGISTER my.suite: /home/bob/suites/test

    $ cylc db print my.suite
    my.suite | No title provided | ~/suites/test

    $ cylc edit my.suite  # Open the suite in your editor again.

    $ cylc help  # See other commands!

### Validate It

    $ cylc validate my.suite
    Valid for cylc-6.10.1


### Visualize It

    $ cylc graph my.suite &

![img/cylc-graph.png](img/cylc-graph.png)


### Run It

    $ cylc run my.suite
        # OR
    $ gcylc my.suite &  # (and run it from the GUI)

![img/gcylc-example.png](img/gcylc-example.png)

### View Task Job Output

    $ cylc log -o my.suite model.2021

    JOB SCRIPT STARTING
    cylc Suite and Task Identity:
    Suite Name  : my.suite
    Suite Host  : niwa-34403.niwa.local
    Suite Port  : 7766
    Suite Owner : oliverh
    Task ID     : model.2021
    Task Host   : niwa-34403.niwa.local
    Task Owner  : oliverh
    Task Submit No.: 1
    Task Try No.: 1

    my FOOD is icecream

    cylc (scheduler - 2016-05-18T17:25:18+12): started at 2016-05-18T17:25:18+12
    cylc (scheduler - 2016-05-18T17:25:28+12): succeeded at 2016-05-18T17:25:28+12
    JOB SCRIPT EXITING (TASK SUCCEEDED)
