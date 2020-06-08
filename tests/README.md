# Functional Tests

This directory contains Cylc functional tests.

## How To Run These Tests

```console
$ etc/bin/run-functional-tests tests/ flakytests/
$ etc/bin/run-functional-tests tests/ flakytests/ -j 4  # 4 tests in parallel
```

## What Are Functional Tests

These tests ensure end-to-end functionality is as expected.

With Cylc this typically involves building workflow configurations which
cause many parts of the system (and other systems) to be activated.

This includes interaction with other systems (e.g. batch schedulers),
command line interfaces / outputs, etc.

# Guidelines

Don't write functional tests when you can write integration tests:

* If a test requires a workflow to be put in an "exotic" state, consider if
  this can be achieved artificially.
* If a test can be broken down into smaller more targeted sub-tests then
  integration testing might be more appropriate.
