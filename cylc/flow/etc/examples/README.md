# Examples

These examples are intended to illustrate the major patterns for implementing
Cylc workflows. The hope is that users can find a workflow which fits their
pattern, make a copy and fill in the details. Keep the examples minimal and
abstract. We aren't trying to document every Cylc feature here, just the
major design patterns.

These examples are auto-documented in cylc-doc which looks for an `index.rst`
file in each example.

Users can extract them using `cylc get-resources` which will put them into the
configured Cylc source directory (`~/cylc-src` by default). They can then be
run using the directory name, e.g. `cylc vip hello-world`.

Files:

* `index.rst`
  This file is used to generate a page in the documentation for the example.
  This file is excluded when the user extracts the example.
* `.validate`
  This is a test file, it gets detected and run automatically.
  This file is excluded when the user extracts the example.
* `README.rst`
  Examples can include a README file, to save duplication, you can
  `.. include::` this in the `index.rst` file (hence using ReStructuredText
  rather than Markdown).
