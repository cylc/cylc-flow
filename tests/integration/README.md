# Integration Tests

This directory contains Cylc integration tests.

## How To Run These Tests

```console
$ pytest tests/i
$ pytest tests/i -n 5  # run up to 5 tests in parallel
$ pytest tests/i --dist=no -n0  # turn off xdist (allows --pdb etc)
```

## What Are Integration Tests

These tests are intended to test the interaction of different modules.
With Cylc this typically involves running workflows.

The general approach is:

1) Start a workflow.
2) Put it in a funny state.
3) Test how components interract to handle this state.

Integration tests aren't end-to-end tests, they focus on targeted interactions
and behaviour and may do a bit of monkeypatching to achieve that result.

## Guidelines

Don't write functional tests here:

* No sleep statements!
* Avoid interaction with the command line.
* Avoid testing interaction with other systems.
* Don't get workflows to call out to executables.
* Put workflows into funny states via artificial means rather than by
  getting the workflow to actually run to the desired state.
* Avoid testing specific log messages or output formats where more general
  testing is possible.

Don't write unit tests here:

* No testing of odd methods and functions.
* If it runs *really* quickly, it's likely a unit test.

## How To Write Integation Tests

Common test patterns are documented in `test_examples.py`.

Workflows can be run in two ways:

```
with start(schd):
    # starts the Scheduler but does not start the main loop
    # (always the better option if its possible)
    ...

with run(schd):
    # starts the Scheduler and sets the main loop running
    await asyncio.sleep(0)  # yield control to the main loop
    ...
```

These methods both shut down the workflow / clean up after themselves.

It is necessary to shut down workflows correctly to clean up resorces and
running tasks.
