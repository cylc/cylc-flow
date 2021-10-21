# Functional Tests

This directory contains Cylc functional tests.

## How To Run These Tests

```console
$ etc/bin/run-functional-tests tests/f

# 4 tests in parallel
$ etc/bin/run-functional-tests tests/f

# split the tests into 4 "chunks" and run the first chunk
$ CHUNK='1/4' etc/bin/run-functional-tests tests/f

# measure code coverage
# (coverage files are not automatically transferred from remote platforms)
$ export CYLC_COVERAGE=1
$ etc/bin/run-functional-tests tests/f
$ coverage combine
```

## What Are Functional Tests?

These tests ensure end-to-end functionality is as expected.

With Cylc this typically involves building workflow configurations which
cause many parts of the system (and other systems) to be activated.

This includes interaction with other systems (e.g. batch schedulers/job runners),
command line interfaces / outputs, etc.

## How To Run "Non-Generic" Tests?

Some tests require job runners (e.g. at, slurm, pbs), remote platforms or
specific configurations.

To run these tests you must configure remote platforms, your options are:

1. Use a swarm of docker containers

   (currently does not cover all platform types)

   $ etc/bin/swarm configure
   $ etc/bin/swarm build
   $ etc/bin/swarm run

2. Configure your own remote platforms in your Cylc config.

   See the next section for the platform matrix and naming conventions.

Once you have defined your remote platforms provide them with the `-p` arg:

```console
# run ONLY tests compatible with the _remote_background_indep_tcp platform
$ etc/bin/run-functional-tests -p _remote_background_indep_tcp tests/f

# run tests on the first compatible platform with the "at" job runner
$ etc/bin/run-functional-tests -p '_*at*' tests/f

# run tests on the first compatible platform configured
$ etc/bin/run-functional-tests -p '*' tests/f
```

## Test Platform Names

Each platform is named using this convention:

    _<submission_locality>_<job_runner>_<filesystem>_<comms_method>

`loc` "submission locality" - `{local, remote}`:
  Where do jobs get submitted?

  * Locally (on the scheduler host).
  * Remotely (on a remote host).

`runner` "job runner" - `{background, at, slurm, ...}`:
  The name of the job runner the container is configured to use.

`fs` "filesystem" - `{indep, shared}`:
  What is the relationship between the filesystem in the container to
  the filesystem on the host?

  * Independent (indep) - it is a completely different filesystem.
  * Shared (shared) - the cylc-run directory is shared.

  warning: For shared filesystems cylc-run is shared, however, the
  absolute path to cylc-run on the host system may be different
  to that on the container, use ~/cylc-run for safety.

`comms` "task communication method" - `{tcp, ssh, poll}`
  The task communication method to use.

Define any test platforms in your global config e.g:

```
# ~/.cylc/global.cylc
[platforms]
    [[_remote_background_indep_tcp]]
        hosts = my_remote_host
```

## Test Global Config

Cylc supports a `global-tests.cylc` file which can be used to define some
top-level configurations to run tests with.

Do not use this file to define test platforms, put them in your regular global
config where they can also be used for interactive work.

## How To Configure "Non-Generic" Tests?

By default tests require the platform `_local_background_indep_tcp`.

If you want your test to run on any other platform export an environment
variable called `REQUIRE_PLATFORM` *before* the `test_header` is sourced.

This variable should define a test's requirements of a platform e.g:

```bash
# require a remote platform with a shared filesystem and tcp task comms
export REQUIRE_PLATFORM='loc:remote fs:shared comms:tcp'
```

Bash extglob pattern matching can be provided
(https://www.gnu.org/software/bash/manual/html_node/Pattern-Matching.html)
e.g:

```bash
# run for all job runners with tcp comms on remote platforms
export REQUIRE_PLATFORM='loc:remote runner:* comms:tcp'
# run for tcp and ssh comms on remote platform
export REQUIRE_PLATFORM='loc:remote comms:?(tcp|ssh)'
```

If a field is not provided it defaults to `*` with the exception of
`loc` which defaults to `local` i.e:

```bash
# run for all job runners on local platforms
export REQUIRE_PLATFORM='runner:*'
# run for all job runners on remote platforms
export REQUIRE_PLATFORM='loc:remote runner:*'
```

## Guidelines

Don't write functional tests when you can write integration tests:

* If a test requires a workflow to be put in an "exotic" state, consider if
  this can be achieved artificially.
* If a test can be broken down into smaller more targeted sub-tests then
  integration testing might be more appropriate.

