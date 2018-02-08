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

* [Cylc User Guide - PDF ~3.5MB](doc/cylc-user-guide.pdf)
* [Cylc User Guide - HTML single page](doc/html/single/cug-html.html)
* [Cylc User Guide - HTML multi page](doc/html/multi/cug-html.html)

### Suite Design Guide

* [Suite Design Guide - PDF ~0.5MB](doc/suite-design-guide.pdf)

### Presentations

Format HTML5 with embedded .webm videos (plays natively in Firefox or Chrome).
Hit the "Home" and "End" keys to skip to the beginning and end of the
presentation, and the 'o' key for a multi-slide summary. This is the
[dzslides](https://github.com/paulrouget/dzslides) framework by Paul Roget.

* [Cylc Keynote](cylc-keynote-lisbon-Sept2016/index.html) - from
  the IS-ENES2 Workshop on Workflow in Earth Systems Modeling, Lisbon,
  September 2016

* [Cylc High Level Introduction](BoM-Feb-2017/index.html) - Bureau of
  Meteorology, Melbourne, February 2017

### Publications, Citations, and References

The Cylc developers plan to write a reference paper in 2017.

In the meantime Cylc releases have a citable DOI:
[![DOI](https://zenodo.org/badge/1836229.svg)](https://zenodo.org/badge/latestdoi/1836229) 

#### Cylc Response to "Assessment Report on Autosubmit, Cylc and ecFlow"

*The Cylc developers would like to respond to a recent comparison paper,
__Assessment report on Autosubmit, Cylc and ecFlow__ (2016, Domingo Manubens-Gil
et. al.) and another that references it, __Seamless Management of Ensemble
Climate Prediction Experiments on HPC Platforms__ (2016, Domingo Manubens-Gil
et. al.).  Two of us are listed as contributors to the first paper but it should
be noted that the contribution was limited by time and workload constraints to
major corrections relating to Cylc (all of which were addressed by the lead
author).*

*The lead author of both papers is also the lead developer of Autosubmit.
Perhaps inevitably as the developers of Cylc we have a rather different view on
the strengths and weaknesses of the different systems.  In particular we would
like to address the following points.*

...[CLICK HERE FOR THE FULL RESPONSE](doc/cylc-autosub-response.pdf) (PDF)

---

## A Cycling Workflow Example

The following example is intended to convey something of cylc's basic
functionality.  However, it barely scratches the surface; to understand more,
read the User Guide!

### Create A New Suite

    $ mkdir -p ~/suites/test/
    $ vim ~/suites/test/suite.rc

    title = A first Cylc suite.

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

    $ cylc register my.suite ~/suites/test
    REGISTER my.suite: /home/bob/suites/test

    $ cylc print my.suite
    my.suite | A first test suite | ~/suites/test

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

    Suite    : my.suite
    Task Job : 2021/model/01 (try 1)
    User@Host: bob@hpc-1.niwa.co.nz

    my FOOD is icecream

    2017-03-20T19:37:49Z NORMAL - started
    2017-03-20T19:37:59Z NORMAL - succeeded
