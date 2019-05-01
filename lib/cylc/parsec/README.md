# Parsec Config File Parser

A framework for constructing nested-INI-style config file formats with
automatic parsing, validation, default values, on-the-fly item
obsoletion, deprecation and upgrade, and site/user-style file override
(e.g. User's ``global.rc`` overrides site's overrides spec default values).

###  Used in Cylc for:

   * suite definition files
   * site/user config files


## Design & Implementation

### Parsing: ``lib/parsec/fileparse.py``

Parses any nested-INI format file into a corresponding nested dict
structure, after ``%include``-inlining, Jinja2 processing, and line
continuation joining. Also: trailing comments are stripped; single-,
double-, or un-quoted values; and triple-quoted multiline string values.
string-internal comments are retained.

### Validation: ``lib/parsec/validate.py``

Validates a config structure (from the parser) against a file spec that
defines the "file format" (next).

### File spec

**E.g. ``lib/parsec/test_spec.py`` for ``lib/parsec/test.rc`` and Cylc file
specs in ``lib/cylc/cfgspec/``.**

A nested dict that contains all legal items in their proper place, and
"values" that are *validator* objects prescribing the type of the value
(string, integer, etc.), other requirements, and default values. There
are pre-defined validators for string, integer, float; list (of strings,
integers, floats, and lists with multipliers as for Cylc "retry
delays"); and Cylc times. Other validators can be defined.

### Deprecation & automatic upgrade: ``lib/parsec/upgrade.py``

Allows the file spec module to specify mapping between deprecated items
and their new counterparts, along with an upgrader object to do any
value transformation required.  If affected items are found in the
config file, a deprecation warning will be emitted and the item upgraded
on-the-fly for compatibility with the current file spec.

### High-level "interface"(?): ``lib/parsec/loadcfg.py``

Defines functions that combine parsing and validation for (presumably)
common use cases. Includes combine two config files with precedence order.

## Testing

  * **``lib/parsec/test.rc``**
    An example config file that does (or should/will) contain all types of
    config item that parsec is supposed to support.

  * **``lib/parsec/test_spec.py``**
    Defines a spec for ``test.rc``, and a unit test to parse, validate, and
    print the config file. Does not test deprecation/upgrade at this stage.

  * **``lib/cylc/parsec/upgrade.py``**
    Contains a unit test to test on-the-fly upgrade of deprecated items.

## Note on use of ordered dicts

Files are parsed into ordered dicts, in case order is important. In Cylc
it is important in at least two places: variables defined in
``[[[environment]]]`` sections under ``[runtime]`` may depend on other variables
previously defined in the same section; and in site/user config files,
parsed host sections need to remain ordered in case of an ordered hierarchy
(specific to general) of hostname match patterns.

This generally only matters for items parsed from config files, not for
the default values defined in file spec modules - so there is no need to
use ordered dicts in file specs unless the order of defaults matters.
