# Selected Cylc Changes

For the full list of all changes for each release see [closed
milestones](https://github.com/cylc/cylc/milestones?state=closed).

-------------------------------------------------------------------------------

## __cylc-6.10.0 (2016-05-04)__

### Highlighted Changes

[#1769](https://github.com/cylc/cylc/pull/1769),
[#1809](https://github.com/cylc/cylc/pull/1809),
[#1810](https://github.com/cylc/cylc/pull/1810),
[#1811](https://github.com/cylc/cylc/pull/1811),
[#1812](https://github.com/cylc/cylc/pull/1812),
[#1813](https://github.com/cylc/cylc/pull/1813),
[#1819](https://github.com/cylc/cylc/pull/1819): Big efficiency
and memory footprint improvements.

[#1777](https://github.com/cylc/cylc/pull/1777): Much faster validation of
suites with large inter-dependent families.  See also
[#1791](https://github.com/cylc/cylc/pull/1791).

[#1743](https://github.com/cylc/cylc/pull/1743): Improved event handling:
flexible handlers, built-in email handlers, execute event handlers
asynchronously, general suite event handlers.

[#1729](https://github.com/cylc/cylc/pull/1729): `gcylc` - The *File -> Open*
dialog can now connect to suites running on other scanned hosts.

[#1821](https://github.com/cylc/cylc/pull/1821): Right-click on a cycle-point
in the `gcylc` text tree view to operate on all tasks at that cycle point.

### Other Changes

[#1714](https://github.com/cylc/cylc/pull/1714): Further improvements to Jinja2
error reporting.

[#1755](https://github.com/cylc/cylc/pull/1755): Pyro-3.16 is now packaged with
with cylc and has been modified to reduce the overhead of repeated calls to
`socket.gethost*`. We will eventually replace it with a new client/server
communications layer.

[#1807](https://github.com/cylc/cylc/pull/1807): Dropped support for
_detaching_ (or _manual completion_) tasks.

[#1805](https://github.com/cylc/cylc/pull/1805): `gcylc` - corrected the suite
hold/release button state during  active suite reloads.

[#1802](https://github.com/cylc/cylc/pull/1802): Do not unregister running
suites or assume that the argument of `cylc unregister` is a pattern.

[#1800](https://github.com/cylc/cylc/pull/1800): Print a sensible error message
for a suite graph section with a zero-width cycling interval.

[#1791](https://github.com/cylc/cylc/pull/1791): Documented how to write suites
with efficient inter-family triggering.

[#1789](https://github.com/cylc/cylc/pull/1789): Fixed a bug causing high CPU
load in large suites with `queued` tasks present.

[#1788](https://github.com/cylc/cylc/pull/1788): Fixed a bug that could
occasionally result in missing entries in suite run databases.

[#1784](https://github.com/cylc/cylc/pull/1784): Corrected and improved the
advice printed at start-up on how to see if a suite is still running.

[#1781](https://github.com/cylc/cylc/pull/1781): Fixed a bug that could disable
the right-click menu for some tasks after enabling a filter.

[#1768](https://github.com/cylc/cylc/pull/1768): Client commands like `cylc
broadcast` can now be invoked by tasks on remote hosts that do not share a
filesystem with the suite host.

[#1763](https://github.com/cylc/cylc/pull/1763): Remote tasks now load 
the right suite passphrase even if a locally registered suite has
the same name.

[#1762](https://github.com/cylc/cylc/pull/1762): Fixed polling of jobs
submitted to loadleveler (broken since 6.8.1).

[#1816](https://github.com/cylc/cylc/pull/1819),
[#1779](https://github.com/cylc/cylc/pull/1779): Allow task names that contain
family names after a hyphen.

-------------------------------------------------------------------------------

For highlighted changes prior to cylc-6.10.0 see doc/changes.html.
