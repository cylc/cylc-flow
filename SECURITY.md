# Security Policies and Procedures

This document outlines security procedures and general policies for the Cylc
project.

  * [Reporting a Bug](#reporting-a-bug)
  * [Disclosure Policy](#disclosure-policy)
  * [Comments on this Policy](#comments-on-this-policy)
  * [Current Alerts](#current-alerts)

## Reporting a Bug

The Cylc team take security bugs seriously. Thank you for improving the
security of Cylc. We appreciate your efforts and responsible disclosure and
will make every effort to acknowledge your contributions.

Report security bugs by sending an email to the [Cylc
Forum](mailto:cylc@googlegroups.com) or by posting a [Cylc repository
Issue](https://github.com/cylc/cylc-flow/issues). Project maintainers will
endeavor to respond within 48 hours. Progress toward a fix will be recorded on
the Issue page, and resulting new releases will be announced on the mail forum. 

Report security bugs in third-party modules to the person or team maintaining
the module.

## Disclosure Policy

When the team receives a security bug report, they will assign it to a primary
handler. This person will coordinate the fix and release process as follows:

  * Confirm the problem and determine the affected versions.
  * Audit code to find any potential similar problems.
  * Prepare fixes for all releases still under maintenance. These fixes will be
    released as fast as possible.

## Comments on this Policy

If you have suggestions on how this process could be improved please submit a
pull request.

## Current Alerts

*[Jinja2 CVE-2019-8341 (High)](https://nvd.nist.gov/vuln/detail/CVE-2019-8341)
An issue was discovered in Jinja2 2.10. The `from_string` function is prone to
Server Side Template Injection (SSTI) where it takes the "source" parameter as
a template object, renders it, and then returns it. The attacker can exploit it
with `{{INJECTION COMMANDS}}` in a URI*

- cylc-7 (7.8.x branch, written in Python 2) has a bundled copy of Jinja2 2.10
that cannot be updated because the new Jinja2 requires Python 3. However **this
CVE does not impact cylc-7 because Cylc workflow definitions are not web
pages**.
- cylc-8 (master branch, written in Python 3) does not bundle Jinja2.
