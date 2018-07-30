---
layout: frontpage
title: a workflow engine
---

**Cylc (*"silk"*) is a workflow engine for cycling systems** - it orchestrates
distributed **suites** of interdependent **cycling tasks** that may continue to
run indefinitely.

There are several reasons why tasks might need to be cycled:

 * To run successive cycles of an environmental forecasting system (where in
   real time operation new forecasts are initiated at regular intervals; but in
   catch-up or historical mode dependencies may allow concurrent cycles).

 * To split long model runs into a sequence of smaller runs, with associated
   processing tasks for each chunk.

 * To run successive steps in some multi-task iterative process, such as for
   optimizing model parameters.

 * To process a series of datasets (potentially concurrently, to the extent
   possible) as they are generated or received.

Cylc was originally developed for operational environmental forecasting at
[NIWA](http://www.niwa.co.nz) by [Dr Hilary
Oliver](mailto:hilary.oliver@niwa.co.nz). It is now an Open
Source collaboration involving NIWA, [Met Office](http://www.metoffice.gov.uk),
and
[others](https://github.com/cylc/cylc/blob/master/CONTRIBUTING.md#code-contributors).
It is [available under the GPL v3 license](./license.html).

{% include feature.html content="Suites are defined in a human-readable config
file format - so you can use software development power tools for suite
development." %}

{% include feature.html content="Configure scheduling with an efficient graph
description notation, and task runtime properties in an efficient inheritance
hierarchy (to factor out all commonality)." %}

{% include feature.html content="Cylc dynamically generates new workflow
without being constrained by a global cycle loop. Cycles interleave
naturally, suites flow around failed or delayed tasks, and they adapt to
insertion and removal of tasks." %}

{% include feature.html content="Cylc has low admin overhead and a small
security footprint, because - as a distributed system - there is no central
server process to manage workflows for all users." %}

{% include feature.html content="Plus <a href='features.html'>many other
features</a> to support both clock-triggered real time and free-flow
metascheduling in research and operational environments." %}

Please [let us know](mailto:hilary.oliver@niwa.co.nz) if your organization
should be included in the **[list of Cylc users](./users.html)**.

Here's the DOI to use when citing Cylc: [![DOI](https://zenodo.org/badge/1836229.svg)](https://zenodo.org/badge/latestdoi/1836229)

See also [publications and citations](./documentation.html#publications-and-citations)
