.. _Introduction Label:

Introduction
============

This document provides guidance on making complex Cylc + Rose workflows that
are clear, maintainable, and portable. Note that best practice advice may
evolve over time with the capabilities of Rose and Cylc.

Content is drawn from the Rose and Cylc user guides, earlier Met Office suite
design and operational suite review documents, experience with real suites
across the Unified Model Consortium, and discussion among members of the UM
TISD (Technical Infrastructure Suite Design) working group.

We start with the most general topics (coding style, general principles),
move on to more advanced topics (efficiency and maintainability, portable
suites), and end with some pointers to future developments.

.. note::

   A good working knowledge of Cylc and Rose is assumed. For further details,
   please consult the:
 
   - `Cylc documentation <http://cylc.github.io/documentation.html>`_
   - `Rose documentation <http://metomi.github.io/rose>`_

.. note::

   For non-Rose users: this document comes out of the Unified Model
   Consortium wherein Cylc is used within the Rose *suite management
   framework*. However, the bulk of the information in this guide is about
   Cylc suite design; which parts are Rose-specific should be clear from
   context.
