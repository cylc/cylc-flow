---
layout: frontpage
title: a workflow engine
---

**Cylc (*"silk"*) is a workflow engine for cycling systems** - it orchestrates
complex distributed **suites** of interdependent **cycling tasks**.
There are several reasons why jobs might need to be cycled:

 * In real time environmental forecasting systems, a new forecast may be
 initiated at regular intervals as new real time data comes in.

 * Batch scheduler queue limits may require that single long jobs be split into
 many smaller runs with incremental processing of associated inputs and
 outputs.

Cylc was originally developed for operational environmental forecasting at
[NIWA](http://www.niwa.co.nz) by [Dr Hilary
Oliver](mailto:hilary.oliver@niwa.co.nz), and is now an Open
Source collaboration involving NIWA, [Met Office](http://www.metoffice.gov.uk),
and [others](./users.html). It is [available under the GPL v3
license](./license.html).

{% include feature.html content="Suites are defined in a human-readable text
format - so you can use standard software development power tools for suite
development (see <a
href='./faq.html#how-do-i-version-control-my-suites'>here</a> for why this is a
good thing)." %}

{% include feature.html content="Configure scheduling with an efficient graph
notation, and task runtime properties in an efficient inheritance hierarchy
(to factor out all commonality)." %}

{% include feature.html content="Scheduling of cycling systems is not restricted
by a global time loop (cycles can interleave as dependencies allow); suites
flow around failed or delayed tasks; and they adapt to insertion and removal of
tasks." %}

{% include feature.html content="Cylc has low admin overhead and a small
security footprint, because there is no central server process to manage
workflows for all users." %}

{% include feature.html content="Plus <a href='features.html'>many other
features</a> to support both clock-triggered real time and free-flow
metascheduling in research and operational environments." %}

Please [let us know](mailto:hilary.oliver@niwa.co.nz) if your organization
should be included in the **[list of cylc users](./users.html)**.
