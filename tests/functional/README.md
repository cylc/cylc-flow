# Functional Tests

This directory contains Cylc functional tests.


## How To Run These Tests

```console
# run all tests in this directory
$ etc/bin/run-functional-tests tests/f

# run a specified test
$ etc/bin/run-functional-tests tests/f/cylc-cat-log/00-local.t

# run a specified test in debug mode
$ etc/bin/run-functional-tests -v tests/f/cylc-cat-log/00-local.t

# run tests with 5x parallelism
$ etc/bin/run-functional-tests -j 5 tests/f

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


## How Are Tests Implemented

Tests are written in files with the `.t` extension. These are Bash scripts
(despite the file extension). The tests are run with a tool called `prove`
which is invoked via the `etc/bin/run-functional-tests` command.

Each test file starts by sourcing the file `lib/bash/test_header`, this
contains various Bash functions which provide assertion functions, e.g.
`run_ok` (which asserts that the provided command succeeds).

Assertions run a command, then write either `ok` or `not ok` to stdout, prove
then scrapes this output to determine test outcome.

Each assertion (or subtest) needs a name, this is usually the first argument
to the function. You should use the prefix `$TEST_NAME_BASE`, e.g, this
assertion tests that the command `sleep 10` succeeds
`run_ok "${TEST_NAME_BASE}-sleep" sleep 10`. Note, some assertions infer the
test name for you from the arguments.

For the list of available assertions, and usage info, see the comments at the
top of `lib/bash/test_header`.

Each test file needs to declare the number of subtests within it, this is
done with the function `set_test_number` which must be run at the start of the
test.

Many tests install workflows for testing. These are installed into cylc-run as
usual under the prefix `cylctb`.


## recording tests that fail

When running many tests you can record the tests that fail using
`--state=save`. You can then re-run the only the failed tests using
`--state=failed`.

For more details see `man prove`.


## Debugging

When a test fails, it may print some directories to the screen which contain
the stderr of the failed tests, or the workflow logs.

Tips:

* Run the test using the `-v` argument, this will reveal which subtest(s)
  failed.
* Some tests reveal extra debug info when you set `CYLC_TEST_DEBUG=true`.
* If the test fails, any workflows installed into the `~/cylc-run/cylctb???`
  directory will not be deleted, you can inspect the workflow logs there.
* In GitHub actions, the `~/cylc-run` directory is uploaded as an "artifact"
  where it can be downloaded for debugging.
* Any text that gets written to stdout will be swallowed by the test framework,
  redirect to stderr in order to use `echo` statements for debugging, e.g,
  `echo "DEBUG: platform=$CYLC_PLATFORM_NAME" >&2`.


### Python Debuggers

"Normal" Python debuggers (e.g, `pdb`) will not work from within the functional
test framework because the Python code maybe run non-interactively.

However, you can use remote debuggers
(e.g. [`remote_pdb`](https://pypi.org/project/remote-pdb/)).

Remote PDB is probably the simplest remote debugger, here's a simple example
to get started:

Open two terminal tabs and run this code in both of them:

```shell
PYTHONBREAKPOINT=remote_pdb.set_trace
REMOTE_PDB_HOST=0.0.0.0
REMOTE_PDB_PORT=${-4444}
export PYTHONBREAKPOINT REMOTE_PDB_HOST REMOTE_PDB_PORT
```

Run the test in the first tab, then run this command in the second:

```shell
nc -C "$REMOTE_PDB_HOST" "$REMOTE_PDB_PORT"
```


### Traps for the unwary

#### `grep_ok` vs `comp_ok`

Tests that use `comp_ok` generally compare `${TEST_NAME}.stdout` or
`${TEST_NAME}.stderr` against either a reference or against `/dev/null`.
They expect the entire output to be **exactly** the same as the
reference and are therefore very unforgiving.

`grep_ok` is much less sensitive only requiring the reference output to
be present **somewhere** in the test output.


### Further Reading

#### Heredocs

If you see code that looks like this:

```bash
cat >'hello.py' <<'__HELLO_PY__'
print("Hello World")
__HELLO_PY__
```

You are looking at an "heredoc" and you may wish to read about heredocs:
[A modern looking bloggy guide](https://linuxize.com/post/bash-heredoc/)
[A web 1.0 manual](http://tldp.org/LDP/abs/html/here-docs.html)


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

