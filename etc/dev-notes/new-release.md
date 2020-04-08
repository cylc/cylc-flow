
# Cylc-7 release process

(Updated April 2020 without testing - HJO)

## Make the release

If all Issues assigned to the milestone are done:
- check out the 7.8.x branch locally
- make sure the test battery passes (Travis CI, and locally at NIWA and Met Office)
- update `CHANGES.md` for the release and commit (to the 7.8.x branch)
- tag the new release: `git tag -a x.y.z "Release x.y.z"`
- push (new commit and tag) to the 7.8.x branch of `cylc/cylc-flow`
- use the GH release page to make a release from the new tag

## Update online User Guide

First check out the release tag and generate new docs: `make documentation`
- (Note on Centos 7 I was unable to do this because the default Python 2.7
  version of Sphinx was too old, and the upgraded one was only for Python 3,
  some pfutzing about may be required to get this working...)

Then go to your clone of `cylc.github.io`
- check out a new branch for a doc update PR
- remove the old docs
- copy in the new docs from your cylc-flow 7.8.x branch
- commit any new files added by copying the docs in 
- (note the web site docs page does not currently refer to the cylc version, so
  no updates needed there at the moment)
- push to your cylc.github.io for and make a PR
