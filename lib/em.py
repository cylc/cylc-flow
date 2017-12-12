#!/usr/bin/env python
#
# $Id: em.py 5656 2017-02-13 01:41:55Z max $ $Date: 2017-02-12 17:41:55 -0800 (Sun, 12 Feb 2017) $

"""
A system for processing Python as markup embedded in text.
"""


__program__ = 'empy'
__version__ = '3.3.3'
__url__ = 'http://www.alcyone.com/software/empy/'
__author__ = 'Erik Max Francis <max@alcyone.com>'
__copyright__ = 'Copyright (C) 2002-2017 Erik Max Francis'
__license__ = 'LGPL'


import copy
import getopt
import inspect
import os
import re
import sys
import types

# 2.x/3.0 compatbility
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

try:
    _unicode = unicode # bytes will be undefined in 3.x releases
    _str = str
    _unichr = unichr
    _input = raw_input
    def _exec(code, globals, locals=None):
        if globals is None:
            exec("""exec code""")
        else:
            if locals is None:
                exec("""exec code in globals""")
            else:
                exec("""exec code in globals, locals""")
except NameError:
    _unicode = str
    _str = bytes
    _unichr = chr
    _input = input
    try:
        _exec = __builtins__.__dict__['exec']
    except AttributeError:
        _exec = __builtins__['exec']

# Some basic defaults.
FAILURE_CODE = 1
DEFAULT_PREFIX = '@'
DEFAULT_PSEUDOMODULE_NAME = 'empy'
DEFAULT_SCRIPT_NAME = '?'
SIGNIFICATOR_RE_SUFFIX = r"%(\S+)\s*(.*)\s*$"
SIGNIFICATOR_RE_STRING = DEFAULT_PREFIX + SIGNIFICATOR_RE_SUFFIX
BANGPATH = '#!'
DEFAULT_CHUNK_SIZE = 8192
DEFAULT_ERRORS = 'strict'

# Character information.
IDENTIFIER_FIRST_CHARS = '_abcdefghijklmnopqrstuvwxyz' \
                         'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
IDENTIFIER_CHARS = IDENTIFIER_FIRST_CHARS + '0123456789.'
ENDING_CHARS = {'(': ')', '[': ']', '{': '}'}

# Environment variable names.
OPTIONS_ENV = 'EMPY_OPTIONS'
PREFIX_ENV = 'EMPY_PREFIX'
PSEUDO_ENV = 'EMPY_PSEUDO'
FLATTEN_ENV = 'EMPY_FLATTEN'
RAW_ENV = 'EMPY_RAW_ERRORS'
INTERACTIVE_ENV = 'EMPY_INTERACTIVE'
BUFFERED_ENV = 'EMPY_BUFFERED_OUTPUT'
NO_OVERRIDE_ENV = 'EMPY_NO_OVERRIDE'
UNICODE_ENV = 'EMPY_UNICODE'
INPUT_ENCODING_ENV = 'EMPY_UNICODE_INPUT_ENCODING'
OUTPUT_ENCODING_ENV = 'EMPY_UNICODE_OUTPUT_ENCODING'
INPUT_ERRORS_ENV = 'EMPY_UNICODE_INPUT_ERRORS'
OUTPUT_ERRORS_ENV = 'EMPY_UNICODE_OUTPUT_ERRORS'

# Interpreter options.
BANGPATH_OPT = 'processBangpaths' # process bangpaths as comments?
BUFFERED_OPT = 'bufferedOutput' # fully buffered output?
RAW_OPT = 'rawErrors' # raw errors?
EXIT_OPT = 'exitOnError' # exit on error?
FLATTEN_OPT = 'flatten' # flatten pseudomodule namespace?
OVERRIDE_OPT = 'override' # override sys.stdout with proxy?
CALLBACK_OPT = 'noCallbackError' # is no custom callback an error?

# Usage info.
OPTION_INFO = [
("-V --version", "Print version and exit"),
("-h --help", "Print usage and exit"),
("-H --extended-help", "Print extended usage and exit"),
("-k --suppress-errors", "Do not exit on errors; go interactive"),
("-p --prefix=<char>", "Change prefix to something other than @"),
("   --no-prefix", "Do not do any markup processing at all"),
("-m --module=<name>", "Change the internal pseudomodule name"),
("-f --flatten", "Flatten the members of pseudmodule to start"),
("-r --raw-errors", "Show raw Python errors"),
("-i --interactive", "Go into interactive mode after processing"),
("-n --no-override-stdout", "Do not override sys.stdout with proxy"),
("-o --output=<filename>", "Specify file for output as write"),
("-a --append=<filename>", "Specify file for output as append"),
("-b --buffered-output", "Fully buffer output including open"),
("   --binary", "Treat the file as a binary"),
("   --chunk-size=<chunk>", "Use this chunk size for reading binaries"),
("-P --preprocess=<filename>", "Interpret EmPy file before main processing"),
("-I --import=<modules>", "Import Python modules before processing"),
("-D --define=<definition>", "Execute Python assignment statement"),
("-E --execute=<statement>", "Execute Python statement before processing"),
("-F --execute-file=<filename>", "Execute Python file before processing"),
("   --pause-at-end", "Prompt at the ending of processing"),
("   --relative-path", "Add path of EmPy script to sys.path"),
("   --no-callback-error", "Custom markup without callback is error"),
("   --no-bangpath-processing", "Suppress bangpaths as comments"),
("-u --unicode", "Enable Unicode subsystem (Python 2+ only)"),
("   --unicode-encoding=<e>", "Set both input and output encodings"),
("   --unicode-input-encoding=<e>", "Set input encoding"),
("   --unicode-output-encoding=<e>", "Set output encoding"),
("   --unicode-errors=<E>", "Set both input and output error handler"),
("   --unicode-input-errors=<E>", "Set input error handler"),
("   --unicode-output-errors=<E>", "Set output error handler"),
]

USAGE_NOTES = """\
Notes: Whitespace immediately inside parentheses of @(...) are
ignored.  Whitespace immediately inside braces of @{...} are ignored,
unless ... spans multiple lines.  Use @{ ... }@ to suppress newline
following expansion.  Simple expressions ignore trailing dots; `@x.'
means `@(x).'.  A #! at the start of a file is treated as a @#
comment."""

MARKUP_INFO = [
("@# ... NL", "Comment; remove everything up to newline"),
("@? NAME NL", "Set the current context name"),
("@! INTEGER NL", "Set the current context line number"),
("@ WHITESPACE", "Remove following whitespace; line continuation"),
("@\\ ESCAPE_CODE", "A C-style escape sequence"),
("@@", "Literal @; @ is escaped (duplicated prefix)"),
("@), @], @}", "Literal close parenthesis, bracket, brace"),
("@ STRING_LITERAL", "Replace with string literal contents"),
("@( EXPRESSION )", "Evaluate expression and substitute with str"),
("@( TEST [? THEN [! ELSE]] )", "If test is true, evaluate then, otherwise else"),
("@( TRY $ CATCH )", "Expand try expression, or catch if it raises"),
("@ SIMPLE_EXPRESSION", "Evaluate simple expression and substitute;\n"
                        "e.g., @x, @x.y, @f(a, b), @l[i], etc."),
("@` EXPRESSION `", "Evaluate expression and substitute with repr"),
("@: EXPRESSION : [DUMMY] :", "Evaluates to @:...:expansion:"),
("@{ STATEMENTS }", "Statements are executed for side effects"),
("@[ CONTROL ]", "Control markups: if E; elif E; for N in E;\n"
                 "while E; try; except E, N; finally; continue;\n"
                 "break; end X"),
("@%% KEY WHITESPACE VALUE NL", "Significator form of __KEY__ = VALUE"),
("@< CONTENTS >", "Custom markup; meaning provided by user"),
]

ESCAPE_INFO = [
("@\\0", "NUL, null"),
("@\\a", "BEL, bell"),
("@\\b", "BS, backspace"),
("@\\dDDD", "three-digit decimal code DDD"),
("@\\e", "ESC, escape"),
("@\\f", "FF, form feed"),
("@\\h", "DEL, delete"),
("@\\n", "LF, linefeed, newline"),
("@\\N{NAME}", "Unicode character named NAME"),
("@\\oOOO", "three-digit octal code OOO"),
("@\\qQQQQ", "four-digit quaternary code QQQQ"),
("@\\r", "CR, carriage return"),
("@\\s", "SP, space"),
("@\\t", "HT, horizontal tab"),
("@\\uHHHH", "16-bit hexadecimal Unicode HHHH"),
("@\\UHHHHHHHH", "32-bit hexadecimal Unicode HHHHHHHH"),
("@\\v", "VT, vertical tab"),
("@\\xHH", "two-digit hexadecimal code HH"),
("@\\z", "EOT, end of transmission"),
]

PSEUDOMODULE_INFO = [
("VERSION", "String representing EmPy version"),
("SIGNIFICATOR_RE_STRING", "Regular expression matching significators"),
("SIGNIFICATOR_RE_SUFFIX", "The above stub, lacking the prefix"),
("interpreter", "Currently-executing interpreter instance"),
("argv", "The EmPy script name and command line arguments"),
("args", "The command line arguments only"),
("identify()", "Identify top context as name, line"),
("setContextName(name)", "Set the name of the current context"),
("setContextLine(line)", "Set the line number of the current context"),
("atExit(callable)", "Invoke no-argument function at shutdown"),
("getGlobals()", "Retrieve this interpreter's globals"),
("setGlobals(dict)", "Set this interpreter's globals"),
("updateGlobals(dict)", "Merge dictionary into interpreter's globals"),
("clearGlobals()", "Start globals over anew"),
("saveGlobals([deep])", "Save a copy of the globals"),
("restoreGlobals([pop])", "Restore the most recently saved globals"),
("defined(name, [loc])", "Find if the name is defined"),
("evaluate(expression, [loc])", "Evaluate the expression"),
("serialize(expression, [loc])", "Evaluate and serialize the expression"),
("execute(statements, [loc])", "Execute the statements"),
("single(source, [loc])", "Execute the 'single' object"),
("atomic(name, value, [loc])", "Perform an atomic assignment"),
("assign(name, value, [loc])", "Perform an arbitrary assignment"),
("significate(key, [value])", "Significate the given key, value pair"),
("include(file, [loc])", "Include filename or file-like object"),
("expand(string, [loc])", "Explicitly expand string and return"),
("string(data, [name], [loc])", "Process string-like object"),
("quote(string)", "Quote prefixes in provided string and return"),
("flatten([keys])", "Flatten module contents into globals namespace"),
("getPrefix()", "Get current prefix"),
("setPrefix(char)", "Set new prefix"),
("stopDiverting()", "Stop diverting; data sent directly to output"),
("createDiversion(name)", "Create a diversion but do not divert to it"),
("retrieveDiversion(name)", "Retrieve the actual named diversion object"),
("startDiversion(name)", "Start diverting to given diversion"),
("playDiversion(name)", "Recall diversion and then eliminate it"),
("replayDiversion(name)", "Recall diversion but retain it"),
("purgeDiversion(name)", "Erase diversion"),
("playAllDiversions()", "Stop diverting and play all diversions in order"),
("replayAllDiversions()", "Stop diverting and replay all diversions"),
("purgeAllDiversions()", "Stop diverting and purge all diversions"),
("getFilter()", "Get current filter"),
("resetFilter()", "Reset filter; no filtering"),
("nullFilter()", "Install null filter"),
("setFilter(shortcut)", "Install new filter or filter chain"),
("attachFilter(shortcut)", "Attach single filter to end of current chain"),
("areHooksEnabled()", "Return whether or not hooks are enabled"),
("enableHooks()", "Enable hooks (default)"),
("disableHooks()", "Disable hook invocation"),
("getHooks()", "Get all the hooks"),
("clearHooks()", "Clear all hooks"),
("addHook(hook, [i])", "Register the hook (optionally insert)"),
("removeHook(hook)", "Remove an already-registered hook from name"),
("invokeHook(name_, ...)", "Manually invoke hook"),
("getCallback()", "Get interpreter callback"),
("registerCallback(callback)", "Register callback with interpreter"),
("deregisterCallback()", "Deregister callback from interpreter"),
("invokeCallback(contents)", "Invoke the callback directly"),
("Interpreter", "The interpreter class"),
]

ENVIRONMENT_INFO = [
(OPTIONS_ENV, "Specified options will be included"),
(PREFIX_ENV, "Specify the default prefix: -p <value>"),
(PSEUDO_ENV, "Specify name of pseudomodule: -m <value>"),
(FLATTEN_ENV, "Flatten empy pseudomodule if defined: -f"),
(RAW_ENV, "Show raw errors if defined: -r"),
(INTERACTIVE_ENV, "Enter interactive mode if defined: -i"),
(BUFFERED_ENV, "Fully buffered output if defined: -b"),
(NO_OVERRIDE_ENV, "Do not override sys.stdout if defined: -n"),
(UNICODE_ENV, "Enable Unicode subsystem: -n"),
(INPUT_ENCODING_ENV, "Unicode input encoding"),
(OUTPUT_ENCODING_ENV, "Unicode output encoding"),
(INPUT_ERRORS_ENV, "Unicode input error handler"),
(OUTPUT_ERRORS_ENV, "Unicode output error handler"),
]

class Error(Exception):
    """The base class for all EmPy errors."""
    pass

EmpyError = EmPyError = Error # DEPRECATED

class DiversionError(Error):
    """An error related to diversions."""
    pass

class FilterError(Error):
    """An error related to filters."""
    pass

class StackUnderflowError(Error):
    """A stack underflow."""
    pass

class SubsystemError(Error):
    """An error associated with the Unicode subsystem."""
    pass

class FlowError(Error):
    """An exception related to control flow."""
    pass

class ContinueFlow(FlowError):
    """A continue control flow."""
    pass

class BreakFlow(FlowError):
    """A break control flow."""
    pass

class ParseError(Error):
    """A parse error occurred."""
    pass

class TransientParseError(ParseError):
    """A parse error occurred which may be resolved by feeding more data.
    Such an error reaching the toplevel is an unexpected EOF error."""
    pass


class MetaError(Exception):

    """A wrapper around a real Python exception for including a copy of
    the context."""
    
    def __init__(self, contexts, exc):
        Exception.__init__(self, exc)
        self.contexts = contexts
        self.exc = exc

    def __str__(self):
        backtrace = [str(x) for x in self.contexts]
        return "%s: %s (%s)" % (self.exc.__class__, self.exc, 
                                (', '.join(backtrace)))


class Subsystem:

    """The subsystem class defers file creation so that it can create
    Unicode-wrapped files if desired (and possible)."""

    def __init__(self):
        self.useUnicode = False
        self.inputEncoding = None
        self.outputEncoding = None
        self.errors = None

    def initialize(self, inputEncoding=None, outputEncoding=None, 
                   inputErrors=None, outputErrors=None):
        self.useUnicode = True
        defaultEncoding = sys.getdefaultencoding()
        if inputEncoding is None:
            inputEncoding = defaultEncoding
        self.inputEncoding = inputEncoding
        if outputEncoding is None:
            outputEncoding = defaultEncoding
        self.outputEncoding = outputEncoding
        if inputErrors is None:
            inputErrors = DEFAULT_ERRORS
        self.inputErrors = inputErrors
        if outputErrors is None:
            outputErrors = DEFAULT_ERRORS
        self.outputErrors = outputErrors

    def assertUnicode(self):
        if not self.useUnicode:
            raise SubsystemError("Unicode subsystem unavailable")

    def open(self, name, mode=None):
        if self.useUnicode:
            return self.unicodeOpen(name, mode)
        else:
            return self.defaultOpen(name, mode)

    def defaultOpen(self, name, mode=None):
        if mode is None:
            mode = 'r'
        return open(name, mode)

    def unicodeOpen(self, name, mode=None):
        import codecs
        if mode is None:
            mode = 'rb'
        if mode.find('w') >= 0 or mode.find('a') >= 0:
            encoding = self.outputEncoding
            errors = self.outputErrors
        else:
            encoding = self.inputEncoding
            errors = self.inputErrors
        return codecs.open(name, mode, encoding, errors)

theSubsystem = Subsystem()


class Stack:
    
    """A simple stack that behaves as a sequence (with 0 being the top
    of the stack, not the bottom)."""

    def __init__(self, seq=None):
        if seq is None:
            seq = []
        self.data = seq

    def top(self):
        """Access the top element on the stack."""
        try:
            return self.data[-1]
        except IndexError:
            raise StackUnderflowError("stack is empty for top")
        
    def pop(self):
        """Pop the top element off the stack and return it."""
        try:
            return self.data.pop()
        except IndexError:
            raise StackUnderflowError("stack is empty for pop")
        
    def push(self, object):
        """Push an element onto the top of the stack."""
        self.data.append(object)

    def filter(self, function):
        """Filter the elements of the stack through the function."""
        self.data = list(filter(function, self.data))

    def purge(self):
        """Purge the stack."""
        self.data = []

    def clone(self):
        """Create a duplicate of this stack."""
        return self.__class__(self.data[:])

    def __nonzero__(self): return len(self.data) != 0 # 2.x
    def __bool__(self): return len(self.data) != 0 # 3.x
    def __len__(self): return len(self.data)
    def __getitem__(self, index): return self.data[-(index + 1)]

    def __repr__(self):
        return ('<%s instance at 0x%x [%s]>' % 
                (self.__class__, id(self), 
                 ', '.join(repr(x) for x in self.data)))


class AbstractFile:
    
    """An abstracted file that, when buffered, will totally buffer the
    file, including even the file open."""

    def __init__(self, filename, mode='w', buffered=False):
        # The calls below might throw, so start off by marking this
        # file as "done."  This way destruction of a not-completely-
        # initialized AbstractFile will generate no further errors.
        self.done = True
        self.filename = filename
        self.mode = mode
        self.buffered = buffered
        if buffered:
            self.bufferFile = StringIO()
        else:
            self.bufferFile = theSubsystem.open(filename, mode)
        # Okay, we got this far, so the AbstractFile is initialized.
        # Flag it as "not done."
        self.done = False

    def __del__(self):
        self.close()

    def write(self, data):
        self.bufferFile.write(data)

    def writelines(self, data):
        self.bufferFile.writelines(data)

    def flush(self):
        self.bufferFile.flush()

    def close(self):
        if not self.done:
            self.commit()
            self.done = True

    def commit(self):
        if self.buffered:
            file = theSubsystem.open(self.filename, self.mode)
            file.write(self.bufferFile.getvalue())
            file.close()
        else:
            self.bufferFile.close()

    def abort(self):
        if self.buffered:
            self.bufferFile = None
        else:
            self.bufferFile.close()
            self.bufferFile = None
        self.done = True


class Diversion:

    """The representation of an active diversion.  Diversions act as
    (writable) file objects, and then can be recalled either as pure
    strings or (readable) file objects."""

    def __init__(self):
        self.file = StringIO()

    # These methods define the writable file-like interface for the
    # diversion.

    def write(self, data):
        self.file.write(data)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self):
        self.file.flush()

    def close(self):
        self.file.close()

    # These methods are specific to diversions.

    def asString(self):
        """Return the diversion as a string."""
        return self.file.getvalue()

    def asFile(self):
        """Return the diversion as a file."""
        return StringIO(self.file.getvalue())


class Stream:
    
    """A wrapper around an (output) file object which supports
    diversions and filtering."""
    
    def __init__(self, file):
        self.file = file
        self.currentDiversion = None
        self.diversions = {}
        self.filter = file
        self.done = False

    def write(self, data):
        if self.currentDiversion is None:
            self.filter.write(data)
        else:
            self.diversions[self.currentDiversion].write(data)
    
    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self):
        self.filter.flush()

    def close(self):
        if not self.done:
            self.undivertAll(True)
            self.filter.close()
            self.done = True

    def shortcut(self, shortcut):
        """Take a filter shortcut and translate it into a filter, returning
        it.  Sequences don't count here; these should be detected
        independently."""
        if shortcut == 0:
            return NullFilter()
        elif (isinstance(shortcut, types.FunctionType) or 
              inspect.ismethoddescriptor(shortcut) or 
              isinstance(shortcut, types.BuiltinFunctionType) or 
              isinstance(shortcut, types.BuiltinMethodType) or 
              isinstance(shortcut, types.LambdaType)):
            return FunctionFilter(shortcut)
        elif isinstance(shortcut, _str) or isinstance(shortcut, _unicode):
            return StringFilter(filter)
        elif isinstance(shortcut, dict):
            raise NotImplementedError("mapping filters not yet supported")
        else:
            # Presume it's a plain old filter.
            return shortcut

    def last(self):
        """Find the last filter in the current filter chain, or None if
        there are no filters installed."""
        if self.filter is None:
            return None
        thisFilter, lastFilter = self.filter, None
        while thisFilter is not None and thisFilter is not self.file:
            lastFilter = thisFilter
            thisFilter = thisFilter.next()
        return lastFilter

    def install(self, shortcut=None):
        """Install a new filter; None means no filter.  Handle all the
        special shortcuts for filters here."""
        # Before starting, execute a flush.
        self.filter.flush()
        if shortcut is None or shortcut == [] or shortcut == ():
            # Shortcuts for "no filter."
            self.filter = self.file
        else:
            if isinstance(shortcut, list) or isinstance(shortcut, tuple):
                shortcuts = list(shortcut)
            else:
                shortcuts = [shortcut]
            # Run through the shortcut filter names, replacing them with
            # full-fledged instances of Filter.
            filters = []
            for shortcut in shortcuts:
                filters.append(self.shortcut(shortcut))
            if len(filters) > 1:
                # If there's more than one filter provided, chain them
                # together.
                lastFilter = None
                for filter in filters:
                    if lastFilter is not None:
                        lastFilter.attach(filter)
                    lastFilter = filter
                lastFilter.attach(self.file)
                self.filter = filters[0]
            else:
                # If there's only one filter, assume that it's alone or it's
                # part of a chain that has already been manually chained;
                # just find the end.
                filter = filters[0]
                lastFilter = filter.last()
                lastFilter.attach(self.file)
                self.filter = filter

    def attach(self, shortcut):
        """Attached a solitary filter (no sequences allowed here) at the
        end of the current filter chain."""
        lastFilter = self.last()
        if lastFilter is None:
            # Just install it from scratch if there is no active filter.
            self.install(shortcut)
        else:
            # Attach the last filter to this one, and this one to the file.
            filter = self.shortcut(shortcut)
            lastFilter.attach(filter)
            filter.attach(self.file)

    def revert(self):
        """Reset any current diversions."""
        self.currentDiversion = None

    def create(self, name):
        """Create a diversion if one does not already exist, but do not
        divert to it yet."""
        if name is None:
            raise DiversionError("diversion name must be non-None")
        if name not in self.diversions:
            self.diversions[name] = Diversion()

    def retrieve(self, name):
        """Retrieve the given diversion."""
        if name is None:
            raise DiversionError("diversion name must be non-None")
        if name in self.diversions:
            return self.diversions[name]
        else:
            raise DiversionError("nonexistent diversion: %s" % name)

    def divert(self, name):
        """Start diverting."""
        if name is None:
            raise DiversionError("diversion name must be non-None")
        self.create(name)
        self.currentDiversion = name

    def undivert(self, name, purgeAfterwards=False):
        """Undivert a particular diversion."""
        if name is None:
            raise DiversionError("diversion name must be non-None")
        if name in self.diversions:
            diversion = self.diversions[name]
            self.filter.write(diversion.asString())
            if purgeAfterwards:
                self.purge(name)
        else:
            raise DiversionError("nonexistent diversion: %s" % name)

    def purge(self, name):
        """Purge the specified diversion."""
        if name is None:
            raise DiversionError("diversion name must be non-None")
        if name in self.diversions:
            del self.diversions[name]
            if self.currentDiversion == name:
                self.currentDiversion = None

    def undivertAll(self, purgeAfterwards=True):
        """Undivert all pending diversions."""
        if self.diversions:
            self.revert() # revert before undiverting!
            names = sorted(self.diversions.keys())
            for name in names:
                self.undivert(name)
                if purgeAfterwards:
                    self.purge(name)
            
    def purgeAll(self):
        """Eliminate all existing diversions."""
        if self.diversions:
            self.diversions = {}
        self.currentDiversion = None


class NullFile:

    """A simple class that supports all the file-like object methods
    but simply does nothing at all."""

    def __init__(self): pass
    def write(self, data): pass
    def writelines(self, lines): pass
    def flush(self): pass
    def close(self): pass


class UncloseableFile:

    """A simple class which wraps around a delegate file-like object
    and lets everything through except close calls."""

    def __init__(self, delegate):
        self.delegate = delegate

    def write(self, data):
        self.delegate.write(data)

    def writelines(self, lines):
        self.delegate.writelines(data)

    def flush(self):
        self.delegate.flush()

    def close(self):
        """Eat this one."""
        pass


class ProxyFile:

    """The proxy file object that is intended to take the place of
    sys.stdout.  The proxy can manage a stack of file objects it is
    writing to, and an underlying raw file object."""

    def __init__(self, bottom):
        self.stack = Stack()
        self.bottom = bottom

    def current(self):
        """Get the current stream to write to."""
        if self.stack:
            return self.stack[-1][1]
        else:
            return self.bottom

    def push(self, interpreter):
        self.stack.push((interpreter, interpreter.stream()))

    def pop(self, interpreter):
        result = self.stack.pop()
        assert interpreter is result[0]

    def clear(self, interpreter):
        self.stack.filter(lambda x, i=interpreter: x[0] is not i)

    def write(self, data):
        self.current().write(data)

    def writelines(self, lines):
        self.current().writelines(lines)

    def flush(self):
        self.current().flush()

    def close(self):
        """Close the current file.  If the current file is the bottom, then
        close it and dispose of it."""
        current = self.current()
        if current is self.bottom:
            self.bottom = None
        current.close()

    def _testProxy(self): pass


class Filter:

    """An abstract filter."""

    def __init__(self):
        if self.__class__ is Filter:
            raise NotImplementedError
        self.sink = None

    def next(self):
        """Return the next filter/file-like object in the sequence, or None."""
        return self.sink

    def __next__(self): return self.next()

    def write(self, data):
        """The standard write method; this must be overridden in subclasses."""
        raise NotImplementedError

    def writelines(self, lines):
        """Standard writelines wrapper."""
        for line in lines:
            self.write(line)

    def _flush(self):
        """The _flush method should always flush the sink and should not
        be overridden."""
        self.sink.flush()

    def flush(self):
        """The flush method can be overridden."""
        self._flush()

    def close(self):
        """Close the filter.  Do an explicit flush first, then close the
        sink."""
        self.flush()
        self.sink.close()

    def attach(self, filter):
        """Attach a filter to this one."""
        if self.sink is not None:
            # If it's already attached, detach it first.
            self.detach()
        self.sink = filter

    def detach(self):
        """Detach a filter from its sink."""
        self.flush()
        self._flush() # do a guaranteed flush to just to be safe
        self.sink = None

    def last(self):
        """Find the last filter in this chain."""
        this, last = self, self
        while this is not None:
            last = this
            this = this.next()
        return last

class NullFilter(Filter):

    """A filter that never sends any output to its sink."""

    def write(self, data): pass

class FunctionFilter(Filter):

    """A filter that works simply by pumping its input through a
    function which maps strings into strings."""
    
    def __init__(self, function):
        Filter.__init__(self)
        self.function = function

    def write(self, data):
        self.sink.write(self.function(data))

class StringFilter(Filter):

    """A filter that takes a translation string (256 characters) and
    filters any incoming data through it."""

    def __init__(self, table):
        if not ((isinstance(table, _str) or isinstance(table, _unicode))
                and len(table) == 256):
            raise FilterError("table must be 256-character string")
        Filter.__init__(self)
        self.table = table

    def write(self, data):
        self.sink.write(data.translate(self.table))

class BufferedFilter(Filter):

    """A buffered filter is one that doesn't modify the source data
    sent to the sink, but instead holds it for a time.  The standard
    variety only sends the data along when it receives a flush
    command."""

    def __init__(self):
        Filter.__init__(self)
        self.buffer = ''

    def write(self, data):
        self.buffer += data

    def flush(self):
        if self.buffer:
            self.sink.write(self.buffer)
        self._flush()

class SizeBufferedFilter(BufferedFilter):

    """A size-buffered filter only in fixed size chunks (excepting the
    final chunk)."""

    def __init__(self, bufferSize):
        BufferedFilter.__init__(self)
        self.bufferSize = bufferSize

    def write(self, data):
        BufferedFilter.write(self, data)
        while len(self.buffer) > self.bufferSize:
            chunk, self.buffer = self.buffer[:self.bufferSize], self.buffer[self.bufferSize:]
            self.sink.write(chunk)

class LineBufferedFilter(BufferedFilter):

    """A line-buffered filter only lets data through when it sees
    whole lines."""

    def __init__(self):
        BufferedFilter.__init__(self)

    def write(self, data):
        BufferedFilter.write(self, data)
        chunks = self.buffer.split('\n')
        for chunk in chunks[:-1]:
            self.sink.write(chunk + '\n')
        self.buffer = chunks[-1]

class MaximallyBufferedFilter(BufferedFilter):

    """A maximally-buffered filter only lets its data through on the final
    close.  It ignores flushes."""

    def __init__(self):
        BufferedFilter.__init__(self)

    def flush(self): pass

    def close(self):
        if self.buffer:
            BufferedFilter.flush(self)
            self.sink.close()


class Context:
    
    """An interpreter context, which encapsulates a name, an input
    file object, and a parser object."""

    DEFAULT_UNIT = 'lines'

    def __init__(self, name, line=0, units=DEFAULT_UNIT):
        self.name = name
        self.line = line
        self.units = units
        self.pause = False

    def bump(self, quantity=1):
        if self.pause:
            self.pause = False
        else:
            self.line += quantity

    def identify(self):
        return self.name, self.line

    def __str__(self):
        if self.units == self.DEFAULT_UNIT:
            return "%s:%s" % (self.name, self.line)
        else:
            return "%s:%s[%s]" % (self.name, self.line, self.units)


class Hook:

    """The base class for implementing hooks."""

    def __init__(self):
        self.interpreter = None

    def register(self, interpreter):
        self.interpreter = interpreter

    def deregister(self, interpreter):
        if interpreter is not self.interpreter:
            raise Error("hook not associated with this interpreter")
        self.interpreter = None

    def push(self):
        self.interpreter.push()

    def pop(self):
        self.interpreter.pop()

    def null(self): pass

    def atStartup(self): pass
    def atReady(self): pass
    def atFinalize(self): pass
    def atShutdown(self): pass
    def atParse(self, scanner, locals): pass
    def atToken(self, token): pass
    def atHandle(self, meta): pass
    def atInteract(self): pass

    def beforeInclude(self, name, file, locals): pass
    def afterInclude(self): pass

    def beforeExpand(self, string, locals): pass
    def afterExpand(self, result): pass

    def beforeFile(self, name, file, locals): pass
    def afterFile(self): pass

    def beforeBinary(self, name, file, chunkSize, locals): pass
    def afterBinary(self): pass

    def beforeString(self, name, string, locals): pass
    def afterString(self): pass

    def beforeQuote(self, string): pass
    def afterQuote(self, result): pass

    def beforeEscape(self, string, more): pass
    def afterEscape(self, result): pass

    def beforeControl(self, type, rest, locals): pass
    def afterControl(self): pass

    def beforeSignificate(self, key, value, locals): pass
    def afterSignificate(self): pass

    def beforeAtomic(self, name, value, locals): pass
    def afterAtomic(self): pass

    def beforeMulti(self, name, values, locals): pass
    def afterMulti(self): pass

    def beforeImport(self, name, locals): pass
    def afterImport(self): pass

    def beforeClause(self, catch, locals): pass
    def afterClause(self, exception, variable): pass

    def beforeSerialize(self, expression, locals): pass
    def afterSerialize(self): pass

    def beforeDefined(self, name, locals): pass
    def afterDefined(self, result): pass

    def beforeLiteral(self, text): pass
    def afterLiteral(self): pass

    def beforeEvaluate(self, expression, locals): pass
    def afterEvaluate(self, result): pass

    def beforeExecute(self, statements, locals): pass
    def afterExecute(self): pass

    def beforeSingle(self, source, locals): pass
    def afterSingle(self): pass

class VerboseHook(Hook):

    """A verbose hook that reports all information received by the
    hook interface.  This class dynamically scans the Hook base class
    to ensure that all hook methods are properly represented."""

    EXEMPT_ATTRIBUTES = ['register', 'deregister', 'push', 'pop']

    def __init__(self, output=sys.stderr):
        Hook.__init__(self)
        self.output = output
        self.indent = 0

        class FakeMethod:
            """This is a proxy method-like object."""
            def __init__(self, hook, name):
                self.hook = hook
                self.name = name

            def __call__(self, **keywords):
                self.hook.output.write("%s%s: %s\n" % 
                                       (' ' * self.hook.indent, 
                                        self.name, repr(keywords)))

        for attribute in dir(Hook):
            if (attribute[:1] != '_' and 
                attribute not in self.EXEMPT_ATTRIBUTES):
                self.__dict__[attribute] = FakeMethod(self, attribute)
        

class Token:

    """An element of expansion."""

    def run(self, interpreter, locals):
        raise NotImplementedError

    def string(self):
        raise NotImplementedError

    def __str__(self): return self.string()

class NullToken(Token):
    """A chunk of data not containing markups."""
    def __init__(self, data):
        self.data = data

    def run(self, interpreter, locals):
        interpreter.write(self.data)

    def string(self):
        return self.data

class ExpansionToken(Token):
    """A token that involves an expansion."""
    def __init__(self, prefix, first):
        self.prefix = prefix
        self.first = first

    def scan(self, scanner):
        pass

    def run(self, interpreter, locals):
        pass

class WhitespaceToken(ExpansionToken):
    """A whitespace markup."""
    def string(self):
        return '%s%s' % (self.prefix, self.first)

class LiteralToken(ExpansionToken):
    """A literal markup."""
    def run(self, interpreter, locals):
        interpreter.write(self.first)

    def string(self):
        return '%s%s' % (self.prefix, self.first)

class PrefixToken(ExpansionToken):
    """A prefix markup."""
    def run(self, interpreter, locals):
        interpreter.write(interpreter.prefix)

    def string(self):
        return self.prefix * 2
        
class CommentToken(ExpansionToken):
    """A comment markup."""
    def scan(self, scanner):
        loc = scanner.find('\n')
        if loc >= 0:
            self.comment = scanner.chop(loc, 1)
        else:
            raise TransientParseError("comment expects newline")

    def string(self):
        return '%s#%s\n' % (self.prefix, self.comment)

class ContextNameToken(ExpansionToken):
    """A context name change markup."""
    def scan(self, scanner):
        loc = scanner.find('\n')
        if loc >= 0:
            self.name = scanner.chop(loc, 1).strip()
        else:
            raise TransientParseError("context name expects newline")

    def run(self, interpreter, locals):
        context = interpreter.context()
        context.name = self.name

class ContextLineToken(ExpansionToken):
    """A context line change markup."""
    def scan(self, scanner):
        loc = scanner.find('\n')
        if loc >= 0:
            try:
                self.line = int(scanner.chop(loc, 1))
            except ValueError:
                raise ParseError("context line requires integer")
        else:
            raise TransientParseError("context line expects newline")

    def run(self, interpreter, locals):
        context = interpreter.context()
        context.line = self.line
        context.pause = True

class EscapeToken(ExpansionToken):
    """An escape markup."""
    def scan(self, scanner):
        try:
            code = scanner.chop(1)
            result = None
            if code in '()[]{}\'\"\\': # literals
                result = code
            elif code == '0': # NUL
                result = '\x00'
            elif code == 'a': # BEL
                result = '\x07'
            elif code == 'b': # BS
                result = '\x08'
            elif code == 'd': # decimal code
                decimalCode = scanner.chop(3)
                result = chr(int(decimalCode, 10))
            elif code == 'e': # ESC
                result = '\x1b'
            elif code == 'f': # FF
                result = '\x0c'
            elif code == 'h': # DEL
                result = '\x7f'
            elif code == 'n': # LF (newline)
                result = '\x0a'
            elif code == 'N': # Unicode character name
                theSubsystem.assertUnicode()
                import unicodedata
                if scanner.chop(1) != '{':
                    raise ParseError("Unicode name escape should be \\N{...}")
                i = scanner.find('}')
                name = scanner.chop(i, 1)
                try:
                    result = unicodedata.lookup(name)
                except KeyError:
                    raise SubsystemError("unknown Unicode character name: %s" % name)
            elif code == 'o': # octal code
                octalCode = scanner.chop(3)
                result = chr(int(octalCode, 8))
            elif code == 'q': # quaternary code
                quaternaryCode = scanner.chop(4)
                result = chr(int(quaternaryCode, 4))
            elif code == 'r': # CR
                result = '\x0d'
            elif code in 's ': # SP
                result = ' '
            elif code == 't': # HT
                result = '\x09'
            elif code in 'u': # Unicode 16-bit hex literal
                theSubsystem.assertUnicode()
                hexCode = scanner.chop(4)
                result = _unichr(int(hexCode, 16))
            elif code in 'U': # Unicode 32-bit hex literal
                theSubsystem.assertUnicode()
                hexCode = scanner.chop(8)
                result = _unichr(int(hexCode, 16))
            elif code == 'v': # VT
                result = '\x0b'
            elif code == 'x': # hexadecimal code
                hexCode = scanner.chop(2)
                result = chr(int(hexCode, 16))
            elif code == 'z': # EOT
                result = '\x04'
            elif code == '^': # control character
                controlCode = scanner.chop(1).upper()
                if controlCode >= '@' and controlCode <= '`':
                    result = chr(ord(controlCode) - ord('@'))
                elif controlCode == '?':
                    result = '\x7f'
                else:
                    raise ParseError("invalid escape control code")
            else:
                raise ParseError("unrecognized escape code")
            assert result is not None
            self.code = result
        except ValueError:
            raise ParseError("invalid numeric escape code")

    def run(self, interpreter, locals):
        interpreter.write(self.code)

    def string(self):
        return '%s\\x%02x' % (self.prefix, ord(self.code))

class SignificatorToken(ExpansionToken):
    """A significator markup."""
    def scan(self, scanner):
        loc = scanner.find('\n')
        if loc >= 0:
            line = scanner.chop(loc, 1)
            if not line:
                raise ParseError("significator must have nonblank key")
            if line[0] in ' \t\v\n':
                raise ParseError("no whitespace between % and key")
            # Work around a subtle CPython-Jython difference by stripping
            # the string before splitting it: 'a '.split(None, 1) has two
            # elements in Jython 2.1).
            fields = line.strip().split(None, 1)
            if len(fields) == 2 and fields[1] == '':
                fields.pop()
            self.key = fields[0]
            if len(fields) < 2:
                fields.append(None)
            self.key, self.valueCode = fields
        else:
            raise TransientParseError("significator expects newline")

    def run(self, interpreter, locals):
        value = self.valueCode
        if value is not None:
            value = interpreter.evaluate(value.strip(), locals)
        interpreter.significate(self.key, value)

    def string(self):
        if self.valueCode is None:
            return '%s%%%s\n' % (self.prefix, self.key)
        else:
            return '%s%%%s %s\n' % (self.prefix, self.key, self.valueCode)

class ExpressionToken(ExpansionToken):
    """An expression markup."""
    def scan(self, scanner):
        z = scanner.complex('(', ')', 0)
        try:
            q = scanner.next('$', 0, z, True)
        except ParseError:
            q = z
        try:
            i = scanner.next('?', 0, q, True)
            try:
                j = scanner.next('!', i, q, True)
            except ParseError:
                try:
                    j = scanner.next(':', i, q, True) # DEPRECATED
                except ParseError:
                    j = q
        except ParseError:
            i = j = q
        code = scanner.chop(z, 1)
        self.testCode = code[:i]
        self.thenCode = code[i + 1:j]
        self.elseCode = code[j + 1:q]
        self.exceptCode = code[q + 1:z]

    def run(self, interpreter, locals):
        try:
            result = interpreter.evaluate(self.testCode, locals)
            if self.thenCode:
                if result:
                    result = interpreter.evaluate(self.thenCode, locals)
                else:
                    if self.elseCode:
                        result = interpreter.evaluate(self.elseCode, locals)
                    else:
                        result = None
        except SyntaxError:
            # Don't catch syntax errors; let them through.
            raise
        except:
            if self.exceptCode:
                result = interpreter.evaluate(self.exceptCode, locals)
            else:
                raise
        if result is not None:
            interpreter.write(str(result))

    def string(self):
        result = self.testCode
        if self.thenCode:
            result += '?' + self.thenCode
        if self.elseCode:
            result += '!' + self.elseCode
        if self.exceptCode:
            result += '$' + self.exceptCode
        return '%s(%s)' % (self.prefix, result)

class StringLiteralToken(ExpansionToken):
    """A string token markup."""
    def scan(self, scanner):
        scanner.retreat()
        assert scanner[0] == self.first
        i = scanner.quote()
        self.literal = scanner.chop(i)

    def run(self, interpreter, locals):
        interpreter.literal(self.literal)

    def string(self):
        return '%s%s' % (self.prefix, self.literal)

class SimpleExpressionToken(ExpansionToken):
    """A simple expression markup."""
    def scan(self, scanner):
        i = scanner.simple()
        self.code = self.first + scanner.chop(i)

    def run(self, interpreter, locals):
        interpreter.serialize(self.code, locals)

    def string(self):
        return '%s%s' % (self.prefix, self.code)

class ReprToken(ExpansionToken):
    """A repr markup."""
    def scan(self, scanner):
        i = scanner.next('`', 0)
        self.code = scanner.chop(i, 1)

    def run(self, interpreter, locals):
        interpreter.write(repr(interpreter.evaluate(self.code, locals)))

    def string(self):
        return '%s`%s`' % (self.prefix, self.code)
    
class InPlaceToken(ExpansionToken):
    """An in-place markup."""
    def scan(self, scanner):
        i = scanner.next(':', 0)
        j = scanner.next(':', i + 1)
        self.code = scanner.chop(i, j - i + 1)

    def run(self, interpreter, locals):
        interpreter.write("%s:%s:" % (interpreter.prefix, self.code))
        try:
            interpreter.serialize(self.code, locals)
        finally:
            interpreter.write(":")

    def string(self):
        return '%s:%s::' % (self.prefix, self.code)

class StatementToken(ExpansionToken):
    """A statement markup."""
    def scan(self, scanner):
        i = scanner.complex('{', '}', 0)
        self.code = scanner.chop(i, 1)

    def run(self, interpreter, locals):
        interpreter.execute(self.code, locals)

    def string(self):
        return '%s{%s}' % (self.prefix, self.code)

class CustomToken(ExpansionToken):
    """A custom markup."""
    def scan(self, scanner):
        i = scanner.complex('<', '>', 0)
        self.contents = scanner.chop(i, 1)

    def run(self, interpreter, locals):
        interpreter.invokeCallback(self.contents)

    def string(self):
        return '%s<%s>' % (self.prefix, self.contents)

class ControlToken(ExpansionToken):

    """A control token."""

    PRIMARY_TYPES = ['if', 'for', 'while', 'try', 'def']
    SECONDARY_TYPES = ['elif', 'else', 'except', 'finally']
    TERTIARY_TYPES = ['continue', 'break']
    GREEDY_TYPES = ['if', 'elif', 'for', 'while', 'def', 'end']
    END_TYPES = ['end']

    IN_RE = re.compile(r"\bin\b")
    
    def scan(self, scanner):
        scanner.acquire()
        i = scanner.complex('[', ']', 0)
        self.contents = scanner.chop(i, 1)
        fields = self.contents.strip().split(' ', 1)
        if len(fields) > 1:
            self.type, self.rest = fields
        else:
            self.type = fields[0]
            self.rest = None
        self.subtokens = []
        if self.type in self.GREEDY_TYPES and self.rest is None:
            raise ParseError("control '%s' needs arguments" % self.type)
        if self.type in self.PRIMARY_TYPES:
            self.subscan(scanner, self.type)
            self.kind = 'primary'
        elif self.type in self.SECONDARY_TYPES:
            self.kind = 'secondary'
        elif self.type in self.TERTIARY_TYPES:
            self.kind = 'tertiary'
        elif self.type in self.END_TYPES:
            self.kind = 'end'
        else:
            raise ParseError("unknown control markup: '%s'" % self.type)
        scanner.release()

    def subscan(self, scanner, primary):
        """Do a subscan for contained tokens."""
        while True:
            token = scanner.one()
            if token is None:
                raise TransientParseError("control '%s' needs more tokens" % primary)
            if (isinstance(token, ControlToken) and 
                token.type in self.END_TYPES):
                if token.rest != primary:
                    raise ParseError("control must end with 'end %s'" % primary)
                break
            self.subtokens.append(token)

    def build(self, allowed=None):
        """Process the list of subtokens and divide it into a list of
        2-tuples, consisting of the dividing tokens and the list of
        subtokens that follow them.  If allowed is specified, it will
        represent the list of the only secondary markup types which
        are allowed."""
        if allowed is None:
            allowed = SECONDARY_TYPES
        result = []
        latest = []
        result.append((self, latest))
        for subtoken in self.subtokens:
            if (isinstance(subtoken, ControlToken) and 
                subtoken.kind == 'secondary'):
                if subtoken.type not in allowed:
                    raise ParseError("control unexpected secondary: '%s'" % subtoken.type)
                latest = []
                result.append((subtoken, latest))
            else:
                latest.append(subtoken)
        return result

    def run(self, interpreter, locals):
        interpreter.invoke('beforeControl', type=self.type, rest=self.rest, 
                           locals=locals)
        if self.type == 'if':
            info = self.build(['elif', 'else'])
            elseTokens = None
            if info[-1][0].type == 'else':
                elseTokens = info.pop()[1]
            for secondary, subtokens in info:
                if secondary.type not in ('if', 'elif'):
                    raise ParseError("control 'if' unexpected secondary: '%s'" % secondary.type)
                if interpreter.evaluate(secondary.rest, locals):
                    self.subrun(subtokens, interpreter, locals)
                    break
            else:
                if elseTokens:
                    self.subrun(elseTokens, interpreter, locals)
        elif self.type == 'for':
            sides = self.IN_RE.split(self.rest, 1)
            if len(sides) != 2:
                raise ParseError("control expected 'for x in seq'")
            iterator, sequenceCode = sides
            info = self.build(['else'])
            elseTokens = None
            if info[-1][0].type == 'else':
                elseTokens = info.pop()[1]
            if len(info) != 1:
                raise ParseError("control 'for' expects at most one 'else'")
            sequence = interpreter.evaluate(sequenceCode, locals)
            for element in sequence:
                try:
                    interpreter.assign(iterator, element, locals)
                    self.subrun(info[0][1], interpreter, locals)
                except ContinueFlow:
                    continue
                except BreakFlow:
                    break
            else:
                if elseTokens:
                    self.subrun(elseTokens, interpreter, locals)
        elif self.type == 'while':
            testCode = self.rest
            info = self.build(['else'])
            elseTokens = None
            if info[-1][0].type == 'else':
                elseTokens = info.pop()[1]
            if len(info) != 1:
                raise ParseError("control 'while' expects at most one 'else'")
            atLeastOnce = False
            while True:
                try:
                    if not interpreter.evaluate(testCode, locals):
                        break
                    atLeastOnce = True
                    self.subrun(info[0][1], interpreter, locals)
                except ContinueFlow:
                    continue
                except BreakFlow:
                    break
            if not atLeastOnce and elseTokens:
                self.subrun(elseTokens, interpreter, locals)
        elif self.type == 'try':
            info = self.build(['except', 'finally'])
            if len(info) == 1:
                raise ParseError("control 'try' needs 'except' or 'finally'")
            type = info[-1][0].type
            if type == 'except':
                for secondary, _tokens in info[1:]:
                    if secondary.type != 'except':
                        raise ParseError("control 'try' cannot have 'except' and 'finally'")
            else:
                assert type == 'finally'
                if len(info) != 2:
                    raise ParseError("control 'try' can only have one 'finally'")
            if type == 'except':
                try:
                    self.subrun(info[0][1], interpreter, locals)
                except FlowError:
                    raise
                except Exception:
                    e = sys.exc_info()[1]
                    for secondary, tokens in info[1:]:
                        exception, variable = interpreter.clause(secondary.rest)
                        if variable is not None:
                            interpreter.assign(variable, e)
                        if isinstance(e, exception):
                            self.subrun(tokens, interpreter, locals)
                            break
                    else:
                        raise
            else:
                try:
                    self.subrun(info[0][1], interpreter, locals)
                finally:
                    self.subrun(info[1][1], interpreter, locals)
        elif self.type == 'continue':
            raise ContinueFlow("control 'continue' without 'for', 'while'")
        elif self.type == 'break':
            raise BreakFlow("control 'break' without 'for', 'while'")
        elif self.type == 'def':
            signature = self.rest
            definition = self.substring()
            code = ('def %s:\n' 
                    ' r"""%s"""\n' 
                    ' return %s.expand(r"""%s""", locals())\n' % 
                    (signature, definition, interpreter.pseudo, definition))
            interpreter.execute(code, locals)
        elif self.type == 'end':
            raise ParseError("control 'end' requires primary markup")
        else:
            raise ParseError("control '%s' cannot be at this level" % self.type)
        interpreter.invoke('afterControl')

    def subrun(self, tokens, interpreter, locals):
        """Execute a sequence of tokens."""
        for token in tokens:
            token.run(interpreter, locals)

    def substring(self):
        return ''.join(str(x) for x in self.subtokens)

    def string(self):
        if self.kind == 'primary':
            return ('%s[%s]%s%s[end %s]' % 
                    (self.prefix, self.contents, self.substring(), 
                     self.prefix, self.type))
        else:
            return '%s[%s]' % (self.prefix, self.contents)


class Scanner:

    """A scanner holds a buffer for lookahead parsing and has the
    ability to scan for special symbols and indicators in that
    buffer."""

    # This is the token mapping table that maps first characters to
    # token classes.
    TOKEN_MAP = [
        (None,                   PrefixToken),
        (' \t\v\r\n',            WhitespaceToken),
        (')]}',                  LiteralToken),
        ('\\',                   EscapeToken),
        ('#',                    CommentToken),
        ('?',                    ContextNameToken),
        ('!',                    ContextLineToken),
        ('%',                    SignificatorToken),
        ('(',                    ExpressionToken),
        (IDENTIFIER_FIRST_CHARS, SimpleExpressionToken),
        ('\'\"',                 StringLiteralToken),
        ('`',                    ReprToken),
        (':',                    InPlaceToken),
        ('[',                    ControlToken),
        ('{',                    StatementToken),
        ('<',                    CustomToken),
    ]

    def __init__(self, prefix, data=''):
        self.prefix = prefix
        self.pointer = 0
        self.buffer = data
        self.lock = 0

    def __nonzero__(self): return self.pointer < len(self.buffer) # 2.x
    def __bool__(self): return self.pointer < len(self.buffer) # 3.x
    def __len__(self): return len(self.buffer) - self.pointer

    def __getitem__(self, index):
        if isinstance(index, slice):
            assert index.step is None or index.step == 1
            return self.__getslice__(index.start, index.stop)
        else:
            return self.buffer[self.pointer + index]

    def __getslice__(self, start, stop):
        if start is None:
            start = 0
        if stop is None:
            stop = len(self)
        if stop > len(self):
            stop = len(self)
        return self.buffer[self.pointer + start:self.pointer + stop]

    def advance(self, count=1):
        """Advance the pointer count characters."""
        self.pointer += count

    def retreat(self, count=1):
        self.pointer = self.pointer - count
        if self.pointer < 0:
            raise ParseError("can't retreat back over synced out chars")

    def set(self, data):
        """Start the scanner digesting a new batch of data; start the pointer
        over from scratch."""
        self.pointer = 0
        self.buffer = data

    def feed(self, data):
        """Feed some more data to the scanner."""
        self.buffer += data

    def chop(self, count=None, slop=0):
        """Chop the first count + slop characters off the front, and return
        the first count.  If count is not specified, then return
        everything."""
        if count is None:
            assert slop == 0
            count = len(self)
        if count > len(self):
            raise TransientParseError("not enough data to read")
        result = self[:count]
        self.advance(count + slop)
        return result

    def acquire(self):
        """Lock the scanner so it doesn't destroy data on sync."""
        self.lock += 1

    def release(self):
        """Unlock the scanner."""
        self.lock -= 1

    def sync(self):
        """Sync up the buffer with the read head."""
        if self.lock == 0 and self.pointer != 0:
            self.buffer = self.buffer[self.pointer:]
            self.pointer = 0

    def unsync(self):
        """Undo changes; reset the read head."""
        if self.pointer != 0:
            self.lock = 0
            self.pointer = 0

    def rest(self):
        """Get the remainder of the buffer."""
        return self[:]

    def read(self, i=0, count=1):
        """Read count chars starting from i; raise a transient error if
        there aren't enough characters remaining."""
        if len(self) < i + count:
            raise TransientParseError("need more data to read")
        else:
            return self[i:i + count]

    def check(self, i, archetype=None):
        """Scan for the next single or triple quote, with the specified
        archetype.  Return the found quote or None."""
        quote = None
        if self[i] in '\'\"':
            quote = self[i]
            if len(self) - i < 3:
                for j in range(i, len(self)):
                    if self[i] == quote:
                        return quote
                else:
                    raise TransientParseError("need to scan for rest of quote")
            if self[i + 1] == self[i + 2] == quote:
                quote = quote * 3
        if quote is not None:
            if archetype is None:
                return quote
            else:
                if archetype == quote:
                    return quote
                elif len(archetype) < len(quote) and archetype[0] == quote[0]:
                    return archetype
                else:
                    return None
        else:
            return None

    def find(self, sub, start=0, end=None):
        """Find the next occurrence of the character, or return -1."""
        if end is not None:
            return self.rest().find(sub, start, end)
        else:
            return self.rest().find(sub, start)

    def last(self, char, start=0, end=None):
        """Find the first character that is _not_ the specified character."""
        if end is None:
            end = len(self)
        i = start
        while i < end:
            if self[i] != char:
                return i
            i += 1
        else:
            raise TransientParseError("expecting other than %s" % char)

    def next(self, target, start=0, end=None, mandatory=False):
        """Scan for the next occurrence of one of the characters in
        the target string; optionally, make the scan mandatory."""
        if mandatory:
            assert end is not None
        quote = None
        if end is None:
            end = len(self)
        i = start
        while i < end:
            newQuote = self.check(i, quote)
            if newQuote:
                if newQuote == quote:
                    quote = None
                else:
                    quote = newQuote
                i += len(newQuote)
            else:
                c = self[i]
                if quote:
                    if c == '\\':
                        i += 1
                else:
                    if c in target:
                        return i
                i += 1
        else:
            if mandatory:
                raise ParseError("expecting %s, not found" % target)
            else:
                raise TransientParseError("expecting ending character")

    def quote(self, start=0, end=None, mandatory=False):
        """Scan for the end of the next quote."""
        assert self[start] in '\'\"'
        quote = self.check(start)
        if end is None:
            end = len(self)
        i = start + len(quote)
        while i < end:
            newQuote = self.check(i, quote)
            if newQuote:
                i += len(newQuote)
                if newQuote == quote:
                    return i
            else:
                c = self[i]
                if c == '\\':
                    i += 1
                i += 1
        else:
            if mandatory:
                raise ParseError("expecting end of string literal")
            else:
                raise TransientParseError("expecting end of string literal")

    def nested(self, enter, exit, start=0, end=None):
        """Scan from i for an ending sequence, respecting entries and exits
        only."""
        depth = 0
        if end is None:
            end = len(self)
        i = start
        while i < end:
            c = self[i]
            if c == enter:
                depth += 1
            elif c == exit:
                depth -= 1
                if depth < 0:
                    return i
            i += 1
        else:
            raise TransientParseError("expecting end of complex expression")

    def complex(self, enter, exit, start=0, end=None, skip=None):
        """Scan from i for an ending sequence, respecting quotes,
        entries and exits."""
        quote = None
        depth = 0
        if end is None:
            end = len(self)
        last = None
        i = start
        while i < end:
            newQuote = self.check(i, quote)
            if newQuote:
                if newQuote == quote:
                    quote = None
                else:
                    quote = newQuote
                i += len(newQuote)
            else:
                c = self[i]
                if quote:
                    if c == '\\':
                        i += 1
                else:
                    if skip is None or last != skip:
                        if c == enter:
                            depth += 1
                        elif c == exit:
                            depth -= 1
                            if depth < 0:
                                return i
                last = c
                i += 1
        else:
            raise TransientParseError("expecting end of complex expression")

    def word(self, start=0):
        """Scan from i for a simple word."""
        length = len(self)
        i = start
        while i < length:
            if not self[i] in IDENTIFIER_CHARS:
                return i
            i += 1
        else:
            raise TransientParseError("expecting end of word")

    def phrase(self, start=0):
        """Scan from i for a phrase (e.g., 'word', 'f(a, b, c)', 'a[i]', or
        combinations like 'x[i](a)'."""
        # Find the word.
        i = self.word(start)
        while i < len(self) and self[i] in '([{':
            enter = self[i]
            if enter == '{':
                raise ParseError("curly braces can't open simple expressions")
            exit = ENDING_CHARS[enter]
            i = self.complex(enter, exit, i + 1) + 1
        return i
    
    def simple(self, start=0):
        """Scan from i for a simple expression, which consists of one 
        more phrases separated by dots."""
        i = self.phrase(start)
        length = len(self)
        while i < length and self[i] == '.':
            i = self.phrase(i)
        # Make sure we don't end with a trailing dot.
        while i > 0 and self[i - 1] == '.':
            i -= 1
        return i

    def one(self):
        """Parse and return one token, or None if the scanner is empty."""
        if not self:
            return None
        if not self.prefix:
            loc = -1
        else:
            loc = self.find(self.prefix)
        if loc < 0:
            # If there's no prefix in the buffer, then set the location to
            # the end so the whole thing gets processed.
            loc = len(self)
        if loc == 0:
            # If there's a prefix at the beginning of the buffer, process
            # an expansion.
            prefix = self.chop(1)
            assert prefix == self.prefix
            first = self.chop(1)
            if first == self.prefix:
                first = None
            for firsts, factory in self.TOKEN_MAP:
                if firsts is None:
                    if first is None:
                        break
                elif first in firsts:
                    break
            else:
                raise ParseError("unknown markup: %s%s" % (self.prefix, first))
            token = factory(self.prefix, first)
            try:
                token.scan(self)
            except TransientParseError:
                # If a transient parse error occurs, reset the buffer pointer
                # so we can (conceivably) try again later.
                self.unsync()
                raise
        else:
            # Process everything up to loc as a null token.
            data = self.chop(loc)
            token = NullToken(data)
        self.sync()
        return token


class Interpreter:
    
    """An interpreter can process chunks of EmPy code."""

    # Constants.

    VERSION = __version__
    SIGNIFICATOR_RE_SUFFIX = SIGNIFICATOR_RE_SUFFIX
    SIGNIFICATOR_RE_STRING = None

    # Types.

    Interpreter = None # define this below to prevent a circular reference
    Hook = Hook # DEPRECATED
    Filter = Filter # DEPRECATED
    NullFilter = NullFilter # DEPRECATED
    FunctionFilter = FunctionFilter # DEPRECATED
    StringFilter = StringFilter # DEPRECATED
    BufferedFilter = BufferedFilter # DEPRECATED
    SizeBufferedFilter = SizeBufferedFilter # DEPRECATED
    LineBufferedFilter = LineBufferedFilter # DEPRECATED
    MaximallyBufferedFilter = MaximallyBufferedFilter # DEPRECATED

    # Tables.

    ESCAPE_CODES = {0x00: '0', 0x07: 'a', 0x08: 'b', 0x1b: 'e', 0x0c: 'f', 
                    0x7f: 'h', 0x0a: 'n', 0x0d: 'r', 0x09: 't', 0x0b: 'v', 
                    0x04: 'z'}

    ASSIGN_TOKEN_RE = re.compile(r"[_a-zA-Z][_a-zA-Z0-9]*|\(|\)|,")

    DEFAULT_OPTIONS = {BANGPATH_OPT: True,
                       BUFFERED_OPT: False,
                       RAW_OPT: False,
                       EXIT_OPT: True,
                       FLATTEN_OPT: False,
                       OVERRIDE_OPT: True,
                       CALLBACK_OPT: False}

    _wasProxyInstalled = False # was a proxy installed?

    # Construction, initialization, destruction.

    def __init__(self, output=None, argv=None, prefix=DEFAULT_PREFIX, 
                 pseudo=None, options=None, globals=None, hooks=None):
        self.interpreter = self # DEPRECATED
        # Set up the stream.
        if output is None:
            output = UncloseableFile(sys.__stdout__)
        self.output = output
        self.prefix = prefix
        if pseudo is None:
            pseudo = DEFAULT_PSEUDOMODULE_NAME
        self.pseudo = pseudo
        if argv is None:
            argv = [DEFAULT_SCRIPT_NAME]
        self.argv = argv
        self.args = argv[1:]
        if options is None:
            options = {}
        self.options = options
        # Initialize any hooks.
        self.hooksEnabled = None # special sentinel meaning "false until added"
        self.hooks = []
        if hooks is None:
            hooks = []
        for hook in hooks:
            self.register(hook)
        # Initialize callback.
        self.callback = None
        # Finalizers.
        self.finals = []
        # The interpreter stacks.
        self.contexts = Stack()
        self.streams = Stack()
        # Now set up the globals.
        self.globals = globals
        self.fix()
        self.history = Stack()
        # Install a proxy stdout if one hasn't been already.
        self.installProxy()
        # Finally, reset the state of all the stacks.
        self.reset()
        # Okay, now flatten the namespaces if that option has been set.
        if self.options.get(FLATTEN_OPT, False):
            self.flatten()
        # Set up old pseudomodule attributes.
        if prefix is None:
            self.SIGNIFICATOR_RE_STRING = None
        else:
            self.SIGNIFICATOR_RE_STRING = prefix + self.SIGNIFICATOR_RE_SUFFIX
        self.Interpreter = self.__class__
        # Done.  Now declare that we've started up.
        self.invoke('atStartup')

    def __del__(self):
        self.shutdown()

    def __repr__(self):
        return ('<%s pseudomodule/interpreter at 0x%x>' % 
                (self.pseudo, id(self)))

    def ready(self):
        """Declare the interpreter ready for normal operations."""
        self.invoke('atReady')

    def fix(self):
        """Reset the globals, stamping in the pseudomodule."""
        if self.globals is None:
            self.globals = {}
        # Make sure that there is no collision between two interpreters'
        # globals.
        if self.pseudo in self.globals:
            if self.globals[self.pseudo] is not self:
                raise Error("interpreter globals collision")
        self.globals[self.pseudo] = self

    def unfix(self):
        """Remove the pseudomodule (if present) from the globals."""
        UNWANTED_KEYS = [self.pseudo, '__builtins__']
        for unwantedKey in UNWANTED_KEYS:
            if unwantedKey in self.globals:
                del self.globals[unwantedKey]

    def update(self, other):
        """Update the current globals dictionary with another dictionary."""
        self.globals.update(other)
        self.fix()

    def clear(self):
        """Clear out the globals dictionary with a brand new one."""
        self.globals = {}
        self.fix()

    def save(self, deep=True):
        if deep:
            copyMethod = copy.deepcopy
        else:
            copyMethod = copy.copy
        """Save a copy of the current globals on the history stack."""
        self.unfix()
        self.history.push(copyMethod(self.globals))
        self.fix()

    def restore(self, destructive=True):
        """Restore the topmost historic globals."""
        if destructive:
            fetchMethod = self.history.pop
        else:
            fetchMethod = self.history.top
        self.unfix()
        self.globals = fetchMethod()
        self.fix()

    def shutdown(self):
        """Declare this interpreting session over; close the stream file
        object.  This method is idempotent."""
        if self.streams is not None:
            try:
                self.finalize()
                self.invoke('atShutdown')
                while self.streams:
                    stream = self.streams.pop()
                    stream.close()
            finally:
                self.streams = None

    def ok(self):
        """Is the interpreter still active?"""
        return self.streams is not None

    # Writeable file-like methods.

    def write(self, data):
        self.stream().write(data)

    def writelines(self, stuff):
        self.stream().writelines(stuff)

    def flush(self):
        self.stream().flush()

    def close(self):
        self.shutdown()

    # Stack-related activity.

    def context(self):
        return self.contexts.top()

    def stream(self):
        return self.streams.top()

    def reset(self):
        self.contexts.purge()
        self.streams.purge()
        self.streams.push(Stream(self.output))
        if self.options.get(OVERRIDE_OPT, True):
            sys.stdout.clear(self)

    def push(self):
        if self.options.get(OVERRIDE_OPT, True):
            sys.stdout.push(self)

    def pop(self):
        if self.options.get(OVERRIDE_OPT, True):
            sys.stdout.pop(self)

    # Higher-level operations.

    def include(self, fileOrFilename, locals=None):
        """Do an include pass on a file or filename."""
        if isinstance(fileOrFilename, _str):
            # Either it's a string representing a filename ...
            filename = fileOrFilename
            name = filename
            file = theSubsystem.open(filename, 'r')
        else:
            # ... or a file object.
            file = fileOrFilename
            name = "<%s>" % str(file.__class__)
        self.invoke('beforeInclude', name=name, file=file, locals=locals)
        self.file(file, name, locals)
        self.invoke('afterInclude')

    def expand(self, data, locals=None):
        """Do an explicit expansion on a subordinate stream."""
        outFile = StringIO()
        stream = Stream(outFile)
        self.invoke('beforeExpand', string=data, locals=locals)
        self.streams.push(stream)
        try:
            self.string(data, '<expand>', locals)
            stream.flush()
            expansion = outFile.getvalue()
            self.invoke('afterExpand', result=expansion)
            return expansion
        finally:
            self.streams.pop()

    def quote(self, data):
        """Quote the given string so that if it were expanded it would
        evaluate to the original."""
        self.invoke('beforeQuote', string=data)
        scanner = Scanner(self.prefix, data)
        result = []
        i = 0
        try:
            j = scanner.next(self.prefix, i)
            result.append(data[i:j])
            result.append(self.prefix * 2)
            i = j + 1
        except TransientParseError:
            pass
        result.append(data[i:])
        result = ''.join(result)
        self.invoke('afterQuote', result=result)
        return result

    def escape(self, data, more=''):
        """Escape a string so that nonprintable characters are replaced
        with compatible EmPy expansions."""
        self.invoke('beforeEscape', string=data, more=more)
        result = []
        for char in data:
            if char < ' ' or char > '~':
                charOrd = ord(char)
                if charOrd in Interpreter.ESCAPE_CODES:
                    result.append(self.prefix + '\\' + 
                                  Interpreter.ESCAPE_CODES[charOrd])
                else:
                    result.append(self.prefix + '\\x%02x' % charOrd)
            elif char in more:
                result.append(self.prefix + '\\' + char)
            else:
                result.append(char)
        result = ''.join(result)
        self.invoke('afterEscape', result=result)
        return result

    # Processing.

    def wrap(self, callable, args):
        """Wrap around an application of a callable and handle errors.
        Return whether no error occurred."""
        try:
            callable(*args)
            self.reset()
            return True
        except KeyboardInterrupt:
            # Handle keyboard interrupts specially: we should always exit
            # from these.
            e = sys.exc_info()[1]
            self.fail(e, True)
        except Exception:
            # A standard exception (other than a keyboard interrupt).
            e = sys.exc_info()[1]
            self.fail(e)
        except:
            # If we get here, then either it's an exception not derived from
            # Exception or it's a string exception, so get the error type
            # from the sys module.
            e = sys.exc_info()[1]
            self.fail(e)
        # An error occurred if we leak through to here, so do cleanup.
        self.reset()
        return False

    def interact(self):
        """Perform interaction."""
        self.invoke('atInteract')
        done = False
        while not done:
            result = self.wrap(self.file, (sys.stdin, '<interact>'))
            if self.options.get(EXIT_OPT, True):
                done = True
            else:
                if result:
                    done = True
                else:
                    self.reset()

    def fail(self, error, fatal=False):
        """Handle an actual error that occurred."""
        if self.options.get(BUFFERED_OPT, False):
            try:
                self.output.abort()
            except AttributeError:
                # If the output file object doesn't have an abort method,
                # something got mismatched, but it's too late to do
                # anything about it now anyway, so just ignore it.
                pass
        meta = self.meta(error)
        self.handle(meta)
        if self.options.get(RAW_OPT, False):
            raise
        if fatal or self.options.get(EXIT_OPT, True):
            sys.exit(FAILURE_CODE)

    def file(self, file, name='<file>', locals=None):
        """Parse the entire contents of a file-like object, line by line."""
        context = Context(name)
        self.contexts.push(context)
        self.invoke('beforeFile', name=name, file=file, locals=locals)
        scanner = Scanner(self.prefix)
        first = True
        done = False
        while not done:
            self.context().bump()
            line = file.readline()
            if first:
                if self.options.get(BANGPATH_OPT, True) and self.prefix:
                    # Replace a bangpath at the beginning of the first line
                    # with an EmPy comment.
                    if line.startswith(BANGPATH):
                        line = self.prefix + '#' + line[2:]
                first = False
            if line:
                scanner.feed(line)
            else:
                done = True
            self.safe(scanner, done, locals)
        self.invoke('afterFile')
        self.contexts.pop()

    def binary(self, file, name='<binary>', chunkSize=0, locals=None):
        """Parse the entire contents of a file-like object, in chunks."""
        if chunkSize <= 0:
            chunkSize = DEFAULT_CHUNK_SIZE
        context = Context(name, units='bytes')
        self.contexts.push(context)
        self.invoke('beforeBinary', name=name, file=file, 
                    chunkSize=chunkSize, locals=locals)
        scanner = Scanner(self.prefix)
        done = False
        while not done:
            chunk = file.read(chunkSize)
            if chunk:
                scanner.feed(chunk)
            else:
                done = True
            self.safe(scanner, done, locals)
            self.context().bump(len(chunk))
        self.invoke('afterBinary')
        self.contexts.pop()

    def string(self, data, name='<string>', locals=None):
        """Parse a string."""
        context = Context(name)
        self.contexts.push(context)
        self.invoke('beforeString', name=name, string=data, locals=locals)
        context.bump()
        scanner = Scanner(self.prefix, data)
        self.safe(scanner, True, locals)
        self.invoke('afterString')
        self.contexts.pop()

    def safe(self, scanner, final=False, locals=None):
        """Do a protected parse.  Catch transient parse errors; if
        final is true, then make a final pass with a terminator,
        otherwise ignore the transient parse error (more data is
        pending)."""
        try:
            self.parse(scanner, locals)
        except TransientParseError:
            if final:
                # If the buffer doesn't end with a newline, try tacking on
                # a dummy terminator.
                buffer = scanner.rest()
                if buffer and buffer[-1] != '\n':
                    scanner.feed(self.prefix + '\n')
                # A TransientParseError thrown from here is a real parse
                # error.
                self.parse(scanner, locals)

    def parse(self, scanner, locals=None):
        """Parse and run as much from this scanner as possible."""
        self.invoke('atParse', scanner=scanner, locals=locals)
        while True:
            token = scanner.one()
            if token is None:
                break
            self.invoke('atToken', token=token)
            token.run(self, locals)

    # Medium-level evaluation and execution.

    def tokenize(self, name):
        """Take an lvalue string and return a name or a (possibly recursive)
        list of names."""
        result = []
        stack = [result]
        for garbage in self.ASSIGN_TOKEN_RE.split(name):
            garbage = garbage.strip()
            if garbage:
                raise ParseError("unexpected assignment token: '%s'" % garbage)
        tokens = self.ASSIGN_TOKEN_RE.findall(name)
        # While processing, put a None token at the start of any list in which
        # commas actually appear.
        for token in tokens:
            if token == '(':
                stack.append([])
            elif token == ')':
                top = stack.pop()
                if len(top) == 1:
                    top = top[0] # no None token means that it's not a 1-tuple
                elif top[0] is None:
                    del top[0] # remove the None token for real tuples
                stack[-1].append(top)
            elif token == ',':
                if len(stack[-1]) == 1:
                    stack[-1].insert(0, None)
            else:
                stack[-1].append(token)
        # If it's a 1-tuple at the top level, turn it into a real subsequence.
        if result and result[0] is None:
            result = [result[1:]]
        if len(result) == 1:
            return result[0]
        else:
            return result

    def significate(self, key, value=None, locals=None):
        """Declare a significator."""
        self.invoke('beforeSignificate', key=key, value=value, locals=locals)
        name = '__%s__' % key
        self.atomic(name, value, locals)
        self.invoke('afterSignificate')

    def atomic(self, name, value, locals=None):
        """Do an atomic assignment."""
        self.invoke('beforeAtomic', name=name, value=value, locals=locals)
        if locals is None:
            self.globals[name] = value
        else:
            locals[name] = value
        self.invoke('afterAtomic')

    def multi(self, names, values, locals=None):
        """Do a (potentially recursive) assignment."""
        self.invoke('beforeMulti', names=names, values=values, locals=locals)
        # No zip in 1.5, so we have to do it manually.
        i = 0
        try:
            values = tuple(values)
        except TypeError:
            raise TypeError("unpack non-sequence")
        if len(names) != len(values):
            raise ValueError("unpack tuple of wrong size")
        for i in range(len(names)):
            name = names[i]
            if isinstance(name, _str) or isinstance(name, _unicode):
                self.atomic(name, values[i], locals)
            else:
                self.multi(name, values[i], locals)
        self.invoke('afterMulti')

    def assign(self, name, value, locals=None):
        """Do a potentially complex (including tuple unpacking) assignment."""
        left = self.tokenize(name)
        # The return value of tokenize can either be a string or a list of
        # (lists of) strings.
        if isinstance(left, _str) or isinstance(left, _unicode):
            self.atomic(left, value, locals)
        else:
            self.multi(left, value, locals)

    def import_(self, name, locals=None):
        """Do an import."""
        self.invoke('beforeImport', name=name, locals=locals)
        self.execute('import %s' % name, locals)
        self.invoke('afterImport')

    def clause(self, catch, locals=None):
        """Given the string representation of an except clause, turn it into
        a 2-tuple consisting of the class name, and either a variable name
        or None."""
        self.invoke('beforeClause', catch=catch, locals=locals)
        if catch is None:
            exceptionCode, variable = None, None
        elif catch.find(',') >= 0:
            exceptionCode, variable = catch.strip().split(',', 1)
            variable = variable.strip()
        else:
            exceptionCode, variable = catch.strip(), None
        if not exceptionCode:
            exception = Exception
        else:
            exception = self.evaluate(exceptionCode, locals)
        self.invoke('afterClause', exception=exception, variable=variable)
        return exception, variable

    def serialize(self, expression, locals=None):
        """Do an expansion, involving evaluating an expression, then
        converting it to a string and writing that string to the
        output if the evaluation is not None."""
        self.invoke('beforeSerialize', expression=expression, locals=locals)
        result = self.evaluate(expression, locals)
        if result is not None:
            self.write(str(result))
        self.invoke('afterSerialize')

    def defined(self, name, locals=None):
        """Return a Boolean indicating whether or not the name is
        defined either in the locals or the globals."""
        self.invoke('beforeDefined', name=name, locals=locals)
        if locals is not None:
            if name in locals:
                result = True
            else:
                result = False
        elif name in self.globals:
            result = True
        else:
            result = False
        self.invoke('afterDefined', result=result)
        return result

    def literal(self, text):
        """Process a string literal."""
        self.invoke('beforeLiteral', text=text)
        self.serialize(text)
        self.invoke('afterLiteral')

    # Low-level evaluation and execution.

    def evaluate(self, expression, locals=None):
        """Evaluate an expression."""
        if expression in ('1', 'True'): return True
        if expression in ('0', 'False'): return False
        self.push()
        try:
            self.invoke('beforeEvaluate', 
                        expression=expression, locals=locals)
            if locals is not None:
                result = eval(expression, self.globals, locals)
            else:
                result = eval(expression, self.globals)
            self.invoke('afterEvaluate', result=result)
            return result
        finally:
            self.pop()

    def execute(self, statements, locals=None):
        """Execute a statement."""
        # If there are any carriage returns (as opposed to linefeeds/newlines)
        # in the statements code, then remove them.  Even on DOS/Windows
        # platforms, 
        if statements.find('\r') >= 0:
            statements = statements.replace('\r', '')
        # If there are no newlines in the statements code, then strip any
        # leading or trailing whitespace.
        if statements.find('\n') < 0:
            statements = statements.strip()
        self.push()
        try:
            self.invoke('beforeExecute', 
                        statements=statements, locals=locals)
            _exec(statements, self.globals, locals)
            self.invoke('afterExecute')
        finally:
            self.pop()

    def single(self, source, locals=None):
        """Execute an expression or statement, just as if it were
        entered into the Python interactive interpreter."""
        self.push()
        try:
            self.invoke('beforeSingle', 
                        source=source, locals=locals)
            code = compile(source, '<single>', 'single')
            _exec(code, self.globals, locals)
            self.invoke('afterSingle')
        finally:
            self.pop()

    # Hooks.

    def register(self, hook, prepend=False):
        """Register the provided hook."""
        hook.register(self)
        if self.hooksEnabled is None:
            # A special optimization so that hooks can be effectively
            # disabled until one is added or they are explicitly turned on.
            self.hooksEnabled = True
        if prepend:
            self.hooks.insert(0, hook)
        else:
            self.hooks.append(hook)

    def deregister(self, hook):
        """Remove an already registered hook."""
        hook.deregister(self)
        self.hooks.remove(hook)

    def invoke(self, _name, **keywords):
        """Invoke the hook(s) associated with the hook name, should they
        exist."""
        if self.hooksEnabled:
            for hook in self.hooks:
                hook.push()
                try:
                    method = getattr(hook, _name)
                    method(*(), **keywords)
                finally:
                    hook.pop()

    def finalize(self):
        """Execute any remaining final routines."""
        self.push()
        self.invoke('atFinalize')
        try:
            # Pop them off one at a time so they get executed in reverse
            # order and we remove them as they're executed in case something
            # bad happens.
            while self.finals:
                final = self.finals.pop()
                final()
        finally:
            self.pop()

    # Error handling.

    def meta(self, exc=None):
        """Construct a MetaError for the interpreter's current state."""
        return MetaError(self.contexts.clone(), exc)

    def handle(self, meta):
        """Handle a MetaError."""
        first = True
        self.invoke('atHandle', meta=meta)
        for context in meta.contexts:
            if first:
                if meta.exc is not None:
                    desc = "error: %s: %s" % (meta.exc.__class__, meta.exc)
                else:
                    desc = "error"
            else:
                desc = "from this context"
            first = False
            sys.stderr.write('%s: %s\n' % (context, desc))

    def installProxy(self):
        """Install a proxy if necessary."""
        # Unfortunately, there's no surefire way to make sure that installing
        # a sys.stdout proxy is idempotent, what with different interpreters
        # running from different modules.  The best we can do here is to try
        # manipulating the proxy's test function ...
        try:
            sys.stdout._testProxy()
        except AttributeError:
            # ... if the current stdout object doesn't have one, then check
            # to see if we think _this_ particularly Interpreter class has
            # installed it before ...
            if Interpreter._wasProxyInstalled:
                # ... and if so, we have a proxy problem.
                raise Error("interpreter stdout proxy lost")
            else:
                # Otherwise, install the proxy and set the flag.
                sys.stdout = ProxyFile(sys.stdout)
                Interpreter._wasProxyInstalled = True

    #
    # Pseudomodule routines.
    #

    # Identification.

    def identify(self):
        """Identify the topmost context with a 2-tuple of the name and
        line number."""
        return self.context().identify()

    def atExit(self, callable):
        """Register a function to be called at exit."""
        self.finals.append(callable)

    # Context manipulation.

    def pushContext(self, name='<unnamed>', line=0):
        """Create a new context and push it."""
        self.contexts.push(Context(name, line))

    def popContext(self):
        """Pop the top context."""
        self.contexts.pop()

    def setContextName(self, name):
        """Set the name of the topmost context."""
        context = self.context()
        context.name = name
        
    def setContextLine(self, line):
        """Set the name of the topmost context."""
        context = self.context()
        context.line = line

    setName = setContextName # DEPRECATED
    setLine = setContextLine # DEPRECATED

    # Globals manipulation.

    def getGlobals(self):
        """Retrieve the globals."""
        return self.globals

    def setGlobals(self, globals):
        """Set the globals to the specified dictionary."""
        self.globals = globals
        self.fix()

    def updateGlobals(self, otherGlobals):
        """Merge another mapping object into this interpreter's globals."""
        self.update(otherGlobals)

    def clearGlobals(self):
        """Clear out the globals with a brand new dictionary."""
        self.clear()

    def saveGlobals(self, deep=True):
        """Save a copy of the globals off onto the history stack."""
        self.save(deep)

    def restoreGlobals(self, destructive=True):
        """Restore the most recently saved copy of the globals."""
        self.restore(destructive)
        
    # Hook support.

    def areHooksEnabled(self):
        """Return whether or not hooks are presently enabled."""
        if self.hooksEnabled is None:
            return True
        else:
            return self.hooksEnabled

    def enableHooks(self):
        """Enable hooks."""
        self.hooksEnabled = True

    def disableHooks(self):
        """Disable hooks."""
        self.hooksEnabled = False

    def getHooks(self):
        """Get the current hooks."""
        return self.hooks[:]

    def clearHooks(self):
        """Clear all hooks."""
        self.hooks = []

    def addHook(self, hook, prepend=False):
        """Add a new hook; optionally insert it rather than appending it."""
        self.register(hook, prepend)

    def removeHook(self, hook):
        """Remove a preexisting hook."""
        self.deregister(hook)

    def invokeHook(self, _name, **keywords):
        """Manually invoke a hook."""
        self.invoke(*(_name,), **keywords)

    # Callbacks.

    def getCallback(self):
        """Get the callback registered with this interpreter, or None."""
        return self.callback

    def registerCallback(self, callback):
        """Register a custom markup callback with this interpreter."""
        self.callback = callback

    def deregisterCallback(self):
        """Remove any previously registered callback with this interpreter."""
        self.callback = None

    def invokeCallback(self, contents):
        """Invoke the callback."""
        if self.callback is None:
            if self.options.get(CALLBACK_OPT, False):
                raise Error("custom markup invoked with no defined callback")
        else:
            self.callback(contents)

    # Pseudomodule manipulation.

    def flatten(self, keys=None):
        """Flatten the contents of the pseudo-module into the globals
        namespace."""
        if keys is None:
            keys = list(self.__dict__.keys()) + list(self.__class__.__dict__.keys())
        dict = {}
        for key in keys:
            # The pseudomodule is really a class instance, so we need to
            # fumble use getattr instead of simply fumbling through the
            # instance's __dict__.
            dict[key] = getattr(self, key)
        # Stomp everything into the globals namespace.
        self.globals.update(dict)

    # Prefix.

    def getPrefix(self):
        """Get the current prefix."""
        return self.prefix

    def setPrefix(self, prefix):
        """Set the prefix."""
        self.prefix = prefix

    # Diversions.

    def stopDiverting(self):
        """Stop any diverting."""
        self.stream().revert()

    def createDiversion(self, name):
        """Create a diversion (but do not divert to it) if it does not
        already exist."""
        self.stream().create(name)

    def retrieveDiversion(self, name):
        """Retrieve the diversion object associated with the name."""
        return self.stream().retrieve(name)

    def startDiversion(self, name):
        """Start diverting to the given diversion name."""
        self.stream().divert(name)

    def playDiversion(self, name):
        """Play the given diversion and then purge it."""
        self.stream().undivert(name, True)

    def replayDiversion(self, name):
        """Replay the diversion without purging it."""
        self.stream().undivert(name, False)

    def purgeDiversion(self, name):
        """Eliminate the given diversion."""
        self.stream().purge(name)

    def playAllDiversions(self):
        """Play all existing diversions and then purge them."""
        self.stream().undivertAll(True)

    def replayAllDiversions(self):
        """Replay all existing diversions without purging them."""
        self.stream().undivertAll(False)

    def purgeAllDiversions(self):
        """Purge all existing diversions."""
        self.stream().purgeAll()

    def getCurrentDiversion(self):
        """Get the name of the current diversion."""
        return self.stream().currentDiversion

    def getAllDiversions(self):
        """Get the names of all existing diversions."""
        names = sorted(self.stream().diversions.keys())
        return names
    
    # Filter.

    def resetFilter(self):
        """Reset the filter so that it does no filtering."""
        self.stream().install(None)

    def nullFilter(self):
        """Install a filter that will consume all text."""
        self.stream().install(0)

    def getFilter(self):
        """Get the current filter."""
        filter = self.stream().filter
        if filter is self.stream().file:
            return None
        else:
            return filter

    def setFilter(self, shortcut):
        """Set the filter."""
        self.stream().install(shortcut)

    def attachFilter(self, shortcut):
        """Attach a single filter to the end of the current filter chain."""
        self.stream().attach(shortcut)


class Document:

    """A representation of an individual EmPy document, as used by a
    processor."""

    def __init__(self, ID, filename):
        self.ID = ID
        self.filename = filename
        self.significators = {}


class Processor:

    """An entity which is capable of processing a hierarchy of EmPy
    files and building a dictionary of document objects associated
    with them describing their significator contents."""

    DEFAULT_EMPY_EXTENSIONS = ('.em',)
    SIGNIFICATOR_RE = re.compile(SIGNIFICATOR_RE_STRING)

    def __init__(self, factory=Document):
        self.factory = factory
        self.documents = {}

    def identifier(self, pathname, filename): return filename

    def clear(self):
        self.documents = {}

    def scan(self, basename, extensions=DEFAULT_EMPY_EXTENSIONS):
        if isinstance(extensions, _str):
            extensions = (extensions,)
        def _noCriteria(x):
            return True
        def _extensionsCriteria(pathname, extensions=extensions):
            if extensions:
                for extension in extensions:
                    if pathname[-len(extension):] == extension:
                        return True
                return False
            else:
                return True
        self.directory(basename, _noCriteria, _extensionsCriteria, None)
        self.postprocess()

    def postprocess(self):
        pass

    def directory(self, basename, dirCriteria, fileCriteria, depth=None):
        if depth is not None:
            if depth <= 0:
                return
            else:
                depth -= 1
        filenames = os.listdir(basename)
        for filename in filenames:
            pathname = os.path.join(basename, filename)
            if os.path.isdir(pathname):
                if dirCriteria(pathname):
                    self.directory(pathname, dirCriteria, fileCriteria, depth)
            elif os.path.isfile(pathname):
                if fileCriteria(pathname):
                    documentID = self.identifier(pathname, filename)
                    document = self.factory(documentID, pathname)
                    self.file(document, open(pathname))
                    self.documents[documentID] = document

    def file(self, document, file):
        while True:
            line = file.readline()
            if not line:
                break
            self.line(document, line)

    def line(self, document, line):
        match = self.SIGNIFICATOR_RE.search(line)
        if match:
            key, valueS = match.groups()
            valueS = valueS.strip()
            if valueS:
                value = eval(valueS)
            else:
                value = None
            document.significators[key] = value


def expand(_data, _globals=None, 
           _argv=None, _prefix=DEFAULT_PREFIX, _pseudo=None, _options=None, \
           **_locals):
    """Do an atomic expansion of the given source data, creating and
    shutting down an interpreter dedicated to the task.  The sys.stdout
    object is saved off and then replaced before this function
    returns."""
    if len(_locals) == 0:
        # If there were no keyword arguments specified, don't use a locals
        # dictionary at all.
        _locals = None
    output = NullFile()
    interpreter = Interpreter(output, argv=_argv, prefix=_prefix, 
                              pseudo=_pseudo, options=_options, 
                              globals=_globals)
    if interpreter.options.get(OVERRIDE_OPT, True):
        oldStdout = sys.stdout
    try:
        result = interpreter.expand(_data, _locals)
    finally:
        interpreter.shutdown()
        if _globals is not None:
            interpreter.unfix() # remove pseudomodule to prevent clashes
        if interpreter.options.get(OVERRIDE_OPT, True):
            sys.stdout = oldStdout
    return result

def environment(name, default=None):
    """Get data from the current environment.  If the default is True
    or False, then presume that we're only interested in the existence
    or non-existence of the environment variable."""
    if name in os.environ:
        # Do the True/False test by value for future compatibility.
        if default == False or default == True:
            return True
        else:
            return os.environ[name]
    else:
        return default

def info(table):
    DEFAULT_LEFT = 28
    maxLeft = 0
    maxRight = 0
    for left, right in table:
        if len(left) > maxLeft:
            maxLeft = len(left)
        if len(right) > maxRight:
            maxRight = len(right)
    FORMAT = '  %%-%ds  %%s\n' % max(maxLeft, DEFAULT_LEFT)
    for left, right in table:
        if right.find('\n') >= 0:
            for right in right.split('\n'):
                sys.stderr.write(FORMAT % (left, right))
                left = ''
        else:
            sys.stderr.write(FORMAT % (left, right))

def usage(verbose=True):
    """Print usage information."""
    programName = sys.argv[0]
    def warn(line=''):
        sys.stderr.write("%s\n" % line)
    warn("""\
Usage: %s [options] [<filename, or '-' for stdin> [<argument>...]]
Welcome to EmPy version %s.""" % (programName, __version__))
    warn()
    warn("Valid options:")
    info(OPTION_INFO)
    if verbose:
        warn()
        warn("The following markups are supported:")
        info(MARKUP_INFO)
        warn()
        warn("Valid escape sequences are:")
        info(ESCAPE_INFO)
        warn()
        warn("The %s pseudomodule contains the following attributes:" % DEFAULT_PSEUDOMODULE_NAME)
        info(PSEUDOMODULE_INFO)
        warn()
        warn("The following environment variables are recognized:")
        info(ENVIRONMENT_INFO)
        warn()
        warn(USAGE_NOTES)
    else:
        warn()
        warn("Type %s -H for more extensive help." % programName)

def invoke(args):
    """Run a standalone instance of an EmPy interpeter."""
    # Initialize the options.
    _output = None
    _options = {BUFFERED_OPT: environment(BUFFERED_ENV, False),
                RAW_OPT: environment(RAW_ENV, False),
                EXIT_OPT: True,
                FLATTEN_OPT: environment(FLATTEN_ENV, False),
                OVERRIDE_OPT: not environment(NO_OVERRIDE_ENV, False),
                CALLBACK_OPT: False}
    _preprocessing = []
    _prefix = environment(PREFIX_ENV, DEFAULT_PREFIX)
    _pseudo = environment(PSEUDO_ENV, None)
    _interactive = environment(INTERACTIVE_ENV, False)
    _extraArguments = environment(OPTIONS_ENV)
    _binary = -1 # negative for not, 0 for default size, positive for size
    _unicode = environment(UNICODE_ENV, False)
    _unicodeInputEncoding = environment(INPUT_ENCODING_ENV, None)
    _unicodeOutputEncoding = environment(OUTPUT_ENCODING_ENV, None)
    _unicodeInputErrors = environment(INPUT_ERRORS_ENV, None)
    _unicodeOutputErrors = environment(OUTPUT_ERRORS_ENV, None)
    _hooks = []
    _pauseAtEnd = False
    _relativePath = False
    if _extraArguments is not None:
        _extraArguments = _extraArguments.split()
        args = _extraArguments + args
    # Parse the arguments.
    pairs, remainder = getopt.getopt(args, 'VhHvkp:m:frino:a:buBP:I:D:E:F:', ['version', 'help', 'extended-help', 'verbose', 'null-hook', 'suppress-errors', 'prefix=', 'no-prefix', 'module=', 'flatten', 'raw-errors', 'interactive', 'no-override-stdout', 'binary', 'chunk-size=', 'output=' 'append=', 'preprocess=', 'import=', 'define=', 'execute=', 'execute-file=', 'buffered-output', 'pause-at-end', 'relative-path', 'no-callback-error', 'no-bangpath-processing', 'unicode', 'unicode-encoding=', 'unicode-input-encoding=', 'unicode-output-encoding=', 'unicode-errors=', 'unicode-input-errors=', 'unicode-output-errors='])
    for option, argument in pairs:
        if option in ('-V', '--version'):
            sys.stderr.write("%s version %s\n" % (__program__, __version__))
            return
        elif option in ('-h', '--help'):
            usage(False)
            return
        elif option in ('-H', '--extended-help'):
            usage(True)
            return
        elif option in ('-v', '--verbose'):
            _hooks.append(VerboseHook())
        elif option in ('--null-hook',):
            _hooks.append(Hook())
        elif option in ('-k', '--suppress-errors'):
            _options[EXIT_OPT] = False
            _interactive = True # suppress errors implies interactive mode
        elif option in ('-m', '--module'):
            _pseudo = argument
        elif option in ('-f', '--flatten'):
            _options[FLATTEN_OPT] = True
        elif option in ('-p', '--prefix'):
            _prefix = argument
        elif option in ('--no-prefix',):
            _prefix = None
        elif option in ('-r', '--raw-errors'):
            _options[RAW_OPT] = True
        elif option in ('-i', '--interactive'):
            _interactive = True
        elif option in ('-n', '--no-override-stdout'):
            _options[OVERRIDE_OPT] = False
        elif option in ('-o', '--output'):
            _output = argument, 'w', _options[BUFFERED_OPT]
        elif option in ('-a', '--append'):
            _output = argument, 'a', _options[BUFFERED_OPT]
        elif option in ('-b', '--buffered-output'):
            _options[BUFFERED_OPT] = True
        elif option in ('-B',): # DEPRECATED
            _options[BUFFERED_OPT] = True
        elif option in ('--binary',):
            _binary = 0
        elif option in ('--chunk-size',):
            _binary = int(argument)
        elif option in ('-P', '--preprocess'):
            _preprocessing.append(('pre', argument))
        elif option in ('-I', '--import'):
            for module in argument.split(','):
                module = module.strip()
                _preprocessing.append(('import', module))
        elif option in ('-D', '--define'):
            _preprocessing.append(('define', argument))
        elif option in ('-E', '--execute'):
            _preprocessing.append(('exec', argument))
        elif option in ('-F', '--execute-file'):
            _preprocessing.append(('file', argument))
        elif option in ('-u', '--unicode'):
            _unicode = True
        elif option in ('--pause-at-end',):
            _pauseAtEnd = True
        elif option in ('--relative-path',):
            _relativePath = True
        elif option in ('--no-callback-error',):
            _options[CALLBACK_OPT] = True
        elif option in ('--no-bangpath-processing',):
            _options[BANGPATH_OPT] = False
        elif option in ('--unicode-encoding',):
            _unicodeInputEncoding = _unicodeOutputEncoding = argument
        elif option in ('--unicode-input-encoding',):
            _unicodeInputEncoding = argument
        elif option in ('--unicode-output-encoding',):
            _unicodeOutputEncoding = argument
        elif option in ('--unicode-errors',):
            _unicodeInputErrors = _unicodeOutputErrors = argument
        elif option in ('--unicode-input-errors',):
            _unicodeInputErrors = argument
        elif option in ('--unicode-output-errors',):
            _unicodeOutputErrors = argument
    # Set up the Unicode subsystem if required.
    if (_unicode or 
        _unicodeInputEncoding or _unicodeOutputEncoding or 
        _unicodeInputErrors or _unicodeOutputErrors):
        theSubsystem.initialize(_unicodeInputEncoding, 
                                _unicodeOutputEncoding, 
                                _unicodeInputErrors, _unicodeOutputErrors)
    # Now initialize the output file if something has already been selected.
    if _output is not None:
        _output = AbstractFile(*_output)
    # Set up the main filename and the argument.
    if not remainder:
        remainder.append('-')
    filename, arguments = remainder[0], remainder[1:]
    # Set up the interpreter.
    if _options[BUFFERED_OPT] and _output is None:
        raise ValueError("-b only makes sense with -o or -a arguments")
    if _prefix == 'None':
        _prefix = None
    if (_prefix and isinstance(_prefix, _str) and len(_prefix) != 1):
        raise Error("prefix must be single-character string")
    interpreter = Interpreter(output=_output, 
                              argv=remainder, 
                              prefix=_prefix, 
                              pseudo=_pseudo, 
                              options=_options, 
                              hooks=_hooks)
    try:
        # Execute command-line statements.
        i = 0
        for which, thing in _preprocessing:
            if which == 'pre':
                command = interpreter.file
                target = theSubsystem.open(thing, 'r')
                name = thing
            elif which == 'define':
                command = interpreter.string
                if thing.find('=') >= 0:
                    target = '%s{%s}' % (_prefix, thing)
                else:
                    target = '%s{%s = None}' % (_prefix, thing)
                name = '<define:%d>' % i
            elif which == 'exec':
                command = interpreter.string
                target = '%s{%s}' % (_prefix, thing)
                name = '<exec:%d>' % i
            elif which == 'file':
                command = interpreter.string
                name = '<file:%d (%s)>' % (i, thing)
                target = '%s{exec(open("""%s""").read())}' % (_prefix, thing)
            elif which == 'import':
                command = interpreter.string
                name = '<import:%d>' % i
                target = '%s{import %s}' % (_prefix, thing)
            else:
                assert 0
            interpreter.wrap(command, (target, name))
            i += 1
        # Now process the primary file.
        interpreter.ready()
        if filename == '-':
            if not _interactive:
                name = '<stdin>'
                path = ''
                file = sys.stdin
            else:
                name, file = None, None
        else:
            name = filename
            file = theSubsystem.open(filename, 'r')
            path = os.path.split(filename)[0]
            if _relativePath:
                sys.path.insert(0, path)
        if file is not None:
            if _binary < 0:
                interpreter.wrap(interpreter.file, (file, name))
            else:
                chunkSize = _binary
                interpreter.wrap(interpreter.binary, (file, name, chunkSize))
        # If we're supposed to go interactive afterwards, do it.
        if _interactive:
            interpreter.interact()
    finally:
        interpreter.shutdown()
    # Finally, if we should pause at the end, do it.
    if _pauseAtEnd:
        try:
            _input()
        except EOFError:
            pass

def main():
    invoke(sys.argv[1:])

if __name__ == '__main__': main()
