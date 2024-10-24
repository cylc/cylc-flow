# Cylc: How to Contribute

Thanks for you interest in the Cylc project!

Contributions are welcome, please open an issue to discuss changes before
raising a pull request.

You can also get in touch via:

* The developers chat: [![chat](https://img.shields.io/matrix/cylc-general:matrix.org)](https://matrix.to/#/#cylc-general:matrix.org)
* The forum: [![forum](https://img.shields.io/discourse/https/cylc.discourse.group/posts.svg)](https://cylc.discourse.group/)


## New Contributors

Please read the [CLA](#contributor-licence-agreement-and-certificate-of-origin).

Please add your name to the
[Code Contributors](#code-contributors) section of this file as part of your
first Pull Request (for each Cylc repository you contribute to).


## Contribute Code

We use [semver](https://semver.org/) to separate riskier changes (e.g. new features
& code refactors) from bugfixes to provide more stable releases for production environments.

**Enhancements** are made on the `master` branch and released in the next minor version
(e.g. 8.1, 8.2, 8.3)

**Bugfixes** and minor usability enhancements are made on bugfix branches and
released as the next maintainance version (e.g. 8.0.1, 8.0.2, 8.0.3). E.G. if the issue is on the `8.0.x` milestone, branch off of `8.0.x` to
develop your bugfix, then raise the pull request against the `8.0.x` branch. We will later merge the `8.0.x` branch into `master`.

Feel free to ask questions on the issue or
[developers chat](https://matrix.to/#/#cylc-general:matrix.org) if unsure about
anything.

We use [towncrier](https://towncrier.readthedocs.io/en/stable/index.html) for
generating the changelog. Changelog entries are added by running
```
towncrier create <PR-number>.<break|feat|fix>.md --content "Short description"
```

## Code Contributors

The following people have contributed to this code under the terms of
the Contributor Licence Agreement and Certificate of Origin detailed
below (_except for the parenthesised names, which represent contributions
from outside of NIWA and the Met Office that predate the explicit introduction
of this Agreement in July 2018; they must be un-parenthesised in future pull
requests_).

<!-- start-shortlog -->
 - Hilary Oliver
 - Matt Shin
 - Ben Fitzpatrick
 - Andrew Clark
 - Oliver Sanders
 - Declan Valters
 - Sadie Bartholomew
 - (Luis Kornblueh)
 - Kerry Day
 - Prasanna Challuri
 - David Matthews
 - Tim Whitcomb
 - Scott Wales
 - Tomek Trzeciak
 - Thomas Coleman
 - Bruno Kinoshita
 - (Annette Osprey)
 - (Jonathan Thomas)
 - Rosalyn Hatcher
 - (Domingo Manubens Gil)
 - Jonny Williams
 - (Milton Woods)
 - (Alex Reinecke)
 - (Chandin Wilson)
 - (Kevin Pulo)
 - Lois Huggett
 - (Martin Dix)
 - (Ivor Blockley)
 - Alexander Paulsell
 - David Sutherland
 - Martin Ryan
 - Tim Pillinger
 - Samuel Gaist
 - Dima Veselov
 - Gilliano Menezes
 - Mel Hall
 - Ronnie Dutta
 - John Haiducek
 - (Andrew Huang)
 - Cheng Da
 - Mark Dawson
 - Diquan Jabbour
 - Shixian Sheng
 - Utheri Wagura
 - Maxime Rio
<!-- end-shortlog -->

(All contributors are identifiable with email addresses in the git version
control logs or otherwise.)


## Contributor Licence Agreement and Certificate of Origin

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I have
    the right to submit it, either on my behalf or on behalf of my
    employer, under the terms and conditions as described by this file;
    or

(b) The contribution is based upon previous work that, to the best of
    my knowledge, is covered under an appropriate licence and I have
    the right or permission from the copyright owner under that licence
    to submit that work with modifications, whether created in whole or
    in part by me, under the terms and conditions as described by
    this file; or

(c) The contribution was provided directly to me by some other person
    who certified (a) or (b) and I have not modified it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including my
    name and email address) is retained for the full term of
    the copyright and may be redistributed consistent with this project
    or the licence(s) involved.

(e) I, or my employer, grant to NIWA and all recipients of
    this software a perpetual, worldwide, non-exclusive, no-charge,
    royalty-free, irrevocable copyright licence to reproduce, modify,
    prepare derivative works of, publicly display, publicly perform,
    sub-licence, and distribute this contribution and such modifications
    and derivative works consistent with this project or the licence(s)
    involved or other appropriate open source licence(s) specified by
    the project and approved by the
    [Open Source Initiative (OSI)](http://www.opensource.org/).

(f) If I become aware of anything that would make any of the above
    inaccurate, in any way, I will let NIWA know as soon as
    I become aware.

(The Cylc Contributor Licence Agreement and Certificate of Origin is
inspired that of [Rose](https://github.com/metomi/rose), which in turn was
inspired by the Certificate of Origin used by Enyo and the Linux Kernel.)
