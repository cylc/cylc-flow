# Functional Tests

This directory contains Cylc functional tests.

## How To Run These Tests

```console
$ etc/bin/run-functional-tests tests/f

# 4 tests in parallel
$ etc/bin/run-functional-tests tests/f

# split the tests into 4 "chunks" and run the first chunk
$ CHUNK='1/4' etc/bin/run-functional-tests tests/f
```

## What Are Functional Tests?

These tests ensure end-to-end functionality is as expected.

With Cylc this typically involves building workflow configurations which
cause many parts of the system (and other systems) to be activated.

This includes interaction with other systems (e.g. batch schedulers),
command line interfaces / outputs, etc.

## How To Run "Non-Generic" Tests?

Some tests require batch systems (e.g. at, slurm, pbs) or remote platforms.

To run these tests you must configure remote platforms, your options are:

1. Use a swarm of docker containers.

   $ etc/bin/swarm configure
   $ etc/bin/swarm build
   $ etc/bin/swarm run

2. By configuring your own remote platforms in your Cylc config.

   Platforms are named using a convention, see /etc/bin/swarm --help for
   details.

Once you have defined your remote platforms provide them with the `-p` arg:

```console
# run ONLY tests compatible with the _remote_background_indep_tcp platform
$ etc/bin/run-functional-tests -p _remote_background_indep_tcp tests/f

# run tests on the first compatible platform configured 
$ etc/bin/run-functional-tests -p '*' tests/f
```

## Guidelines

Don't write functional tests when you can write integration tests:

* If a test requires a workflow to be put in an "exotic" state, consider if
  this can be achieved artificially.
* If a test can be broken down into smaller more targeted sub-tests then
  integration testing might be more appropriate.

