---
title: 'Cylc: A Workflow Engine for Cycling Systems'
authors:
- affiliation: 1
  name: Hilary J Oliver
  orcid: 0000-0002-5715-5279
- affiliation: 2
  name: Matthew Shin
  orcid: TODO
- affiliation: 3
  name: Oliver Sanders
  orcid: TODO
date: "10 Arpil 2018"
output:
  html_document: default
  pdf_document: default
bibliography: paper.bib
tags:
- forecasting
- weather
- meteorology
- climate
- hydrology
- ocean
- Python
- workflow
affiliations:
- index: 1
  name: National Institute of Water and Atmospheric Research (NIWA), New Zealand
- index: 2
  name: Met Office, UK
- index: 3
  name: Met Office, UK
---

# Summary

Cylc (http://cylc.github.io/cylc/) is a workflow engine for orchestrating
complex distributed systems of cycling (repeating) tasks, as well as ordinary
non-cycling workflows. It has been widely adopted for weather, climate, and
related forecasting applications in research and production HPC environments,
and it is now part of the official software infrastructure for the Unified
Model atmospheric model. Cylc is written in Python and developed primarily by
NIWA (NZ) and Met Office (UK). It has strong support for large production
systems but is not in any way specialized to environmental forecasting, and
ease of use for individuals with smaller workflow automation requirements
remains a key priority.

In cycling workflows tasks repeat on sequences that may represent forecast
cycles, or successive chunks of a simulation that is too long for a single run,
or steps in some multi-program iterative process (e.g. for optimizing model
parameters), or successive datasets to be processed as they are generated or
received, and so forth. Dependence across cycles creates ongoing, potentially
never-ending, workflows. Cylc can uniquely manage these without imposing a
global cycle loop: one cycle does not have to complete before the next can
start. Instead, Cylc's novel meta-scheduling algorithm runs tasks from many
cycles at once, to the full extent allowed by individual dependencies and
external constraints such as compute resource and data availability. So, for
example, on restarting after extended downtime, a workflow that processes
real-time data can clear its backlog and catch up very quickly by interleaving
cycles.

As a distributed system, Cylc scales sideways: each workflow is managed by its
own lightweight ad-hoc server program. Existing scripts or programs can by used
by Cylc without modification: they are automatically wrapped in code to trap
errors and report run status via authenticated HTTPS messages. Cylc workflows
(or *suites*) are defined with a graph notation that efficiently expresses
dependence between tasks; and task runtime properties are defined in an
inheritance hierarchy for efficient sharing of common settings. Tasks can
depend on the wall clock and arbitrary external events, as well as other tasks.
Dependence between workflows is also supported, so for coupled systems you can
choose between a large suite that controls all tasks, and many smaller suites
that depend on each other.

Cycling is controlled by ISO 8601 date-time recurrence expressions (e.g. for
environmental forecasting), or integer recurrence expressions (e.g. for
iterative processes).

# References
(not sure if there are any at this point...)
