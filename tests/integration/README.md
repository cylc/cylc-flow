# Integration Tests

This directory contains Cylc integration tests.

## How To Run These Tests

```console
$ pytest tests/i
$ pytest tests/i -n 5  # run up to 5 tests in parallel
$ pytest tests/i --dist=no -n0  # turn off xdist (allows --pdb etc)
```

## What Are Integration Tests

Integration tests aren't end-to-end tests. They focus on targeted interactions
of multiple modules and may do a bit of monkeypatching to achieve that result.

With Cylc this typically involves running workflows.

The general approach is:

1) Start a workflow.
2) Put it in a funny state.
3) Test how components interract to handle this state.

I.e., the integration test framework runs the scheduler. The only thing it's
really cutting out is the CLI.

You can do everything, up to and including reference tests with it if so
inclined, although that would really be a functional test implemented in Python:

async with run(schd) as log:
    # run the workflow with a timeout of 60 seconds
    await asyncio.sleep(60)
assert reftest(log) == '''
1/b triggered off [1/a]
1/c triggered off [1/b]
'''

For a more integration'y approach to reftests we can do something like this
which is essentially just another way of getting the "triggered off" information
without having to run the main loop and bring race conditions into play:

async with start(schd):
    assert set(schd.pool.get_tasks()) == {'1/a'}

    # setting a:succeeded should spawn b
    schd.command_reset('1/a', 'succeeded')
    assert set(schd.pool.get_tasks()) == {'1/b'}
    
    # setting b:x should spawn c
    schd.command_reset('1/b', 'x')
    assert set(schd.pool.get_tasks()) == {'1/b', '1/c'}

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
