# Unit Tests

This directory contains Cylc unit tests.

## How To Run These Tests

```console
$ pytest tests/u
$ pytest tests/u -n 5  # run up to 5 tests in parallel
$ pytest tests/u --dist=no -n0  # turn off xdist (allows --pdb etc)
```

## What Are Unit Tests

Unit tests test the smallest possible units of functionality, typically
methods or functions.

The interaction of components is mitigated by mocking input objects.

## Guidelines

Don't write integration tests here:

* If your test requires any of the fixtures in the integration tests
  then it is an integration test.
* If your test sees logic flow through multiple modules it's not a unit test.
* If you are constructing computationally expensive objects it's unlikely
  to be a unit test.
