# Flaky Functional Tests

This directory contains tests that are sensitive to timing, server load, etc.

## How To Run These Tests

```console
$ etc/bin/run-functional-tests tests/k

# 4 tests in parallel
$ etc/bin/run-functional-tests tests/k

# split the tests into 4 "chunks" and run the first chunk
$ CHUNK='1/4' etc/bin/run-functional-tests tests/k
```

## Why Are There Flaky Tests?

A lot of the functional tests are highly timing dependent which can cause
them to become flaky, especially on heavily loaded systems or slow
file systems.

We put especially sensitive functional tests into the `flakyfunctional`
directory so that we can easily test them separately with fewer tests
running in parallel to give them a chance of passing.

## See Also

* ../functional/README.md
* [cylc/cylc-flow#2894](https://github.com/cylc/cylc-flow/issues/2894).
