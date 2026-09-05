#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Find unicode control characters in source files

By default the script takes one or more files or directories and looks for
unicode control characters in all text files.  To narrow down the files, provide
a config file with the -c command line, defining a scan_exclude list, which
should be a list of regular expressions matching paths to exclude from the scan.

There is a second mode enabled with -p which when set to 'all', prints all
control characters and when set to 'bidi', prints only the 9 bidirectional
control characters.
"""
from __future__ import print_function

import sys, os, argparse, re, unicodedata, subprocess
import importlib
import io
import threading
from stat import *

try:
    import magic
except ImportError:
    magic = None

def _unicode(line, encoding):
    if isinstance(line, str):
        return line
    return line.decode(encoding)

import platform
if platform.python_version()[0] == '2':
    _chr = unichr
    do_unicode = unicode
else:
    _chr = chr
    do_unicode = _unicode

if platform.python_version_tuple() < ('3','04','0'):
    import imp

# .git and .hg will get excluded when they're part of a directory tree being
# scanned but not when they're explicitly specified as targets.  That is:
#
# find_unicode_control.py foo
#
# will skip foo/.git but
#
# cd foo && find_unicode_control.py .git
#
# will read into .git.  I've left it like this on purpose in case someone ever
# needs to scan inside these directories even though I don't see any reason to
# do that at the moment.  Also,
#
# find_unicode_control.py foo/.git
#
# will skip .git and I don't really care much about fixing it myself since you
# could just pushd/popd your way out of that.  Send a PR if you wish to see that
# work :)
scan_exclude = [r'/\.git/', r'/\.hg/', r'\.desktop$', r'ChangeLog$', r'NEWS$',
                r'\.ppd$', r'\.txt$', r'\.directory$']
scan_exclude_mime = [r'text/x-po$', r'text/x-tex$', r'text/x-troff$',
                     r'text/html$']
verbose_mode = False
detailed_mode = False
jobs = 1

# Analysis threads buffer their output, so that a parallel scan still reports
# files in the order in which they were found.
_thread_output = threading.local()

def _stream(name):
    buf = getattr(_thread_output, name, None)
    if buf is not None:
        return buf
    return sys.stdout if name == 'out' else sys.stderr

# Print a finding to stdout.
def wprint(*args, **kwargs):
    print(*args, file=_stream('out'), **kwargs)

# Print to stderr in verbose mode.
def eprint(*args, **kwargs):
    if verbose_mode:
        print(*args, file=_stream('err'), **kwargs)

# Decode a single latin1 line.
def decodeline(inf):
    return do_unicode(inf, 'utf-8')

# Make a text string from an already open file, attempting to decode from
# latin1 if necessary.  Other non-utf-8 locales are not supported at the
# moment.  The caller passes the binary file object it used to detect the mime
# type, so that the file is opened only once.
def getfiletext(filename, fobj):
    text = None
    infile = io.TextIOWrapper(fobj, encoding='utf-8')
    try:
        try:
            if detailed_mode:
                return [inf for inf in infile]
        except Exception as e:
            eprint('%s: %s' % (filename, e))
            return None

        try:
            text = ''.join(infile)
        except UnicodeDecodeError:
            eprint('%s: Retrying with latin1' % filename)
            try:
                infile.detach()
                fobj.seek(0)
                infile = io.TextIOWrapper(fobj, encoding='latin-1')
                text = ''.join(infile)
            except Exception as e:
                eprint('%s: %s' % (filename, e))
    finally:
        # Leave closing the file to the caller.
        try:
            infile.detach()
        except ValueError:
            pass
    if text:
        return set(text)
    else:
        return None

def analyze_text_detailed(filename, text, disallowed, msg):
    line = 0
    warned = False
    for t in text:
        line = line + 1
        subset = [c for c in t if _chr(ord(c)) in disallowed]
        if subset:
            wprint('%s:%d %s: %s' % (filename, line, msg, subset))
            warned = True
    if not warned:
        eprint('%s: OK' % filename)

    return warned

# Look for disallowed characters in the text.  We reduce all characters into a
# set to speed up analysis.  FIXME: Add a slow mode to get line numbers in files
# that have these disallowed chars.
def analyze_text(filename, text, disallowed, msg):
    if detailed_mode:
        return analyze_text_detailed(filename, text, disallowed, msg)

    if not text.isdisjoint(disallowed):
        wprint('%s: %s: %s' % (filename, msg, text & disallowed))
        return True
    else:
        eprint('%s: OK' % filename)

    return False

# Detect the mime type, preferably from the descriptor the caller is about to
# read, so that the file does not have to be opened a second time.
def get_mime(f, fobj=None):
    if magic:
        if fobj is not None:
            return magic.detect_from_fobj(fobj).mime_type
        return magic.detect_from_filename(f).mime_type
    args = ['file', '--mime-type', f]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    m = [decodeline(x[:-1]) for x in proc.stdout][0].split(':')[1].strip()
    return m

# Fast check, just the file name.
def excluded_by_name(f):
    return bool([e for e in scan_exclude if re.search(e, f)])

# Slower check, mime type.
def excluded_by_mime(m):
    return not 'text/' in m \
            or bool([e for e in scan_exclude_mime if re.search(e, m)])

def should_read(f):
    return not excluded_by_name(f) and not excluded_by_mime(get_mime(f))

# Get file text and feed into analyze_text.  The file is opened once: the same
# descriptor serves the mime type detection and the read of the contents.
def analyze_file(f, disallowed, msg):
    eprint('%s: Reading file' % f)
    if excluded_by_name(f):
        eprint('%s: SKIPPED' % f)
        return False

    # Symbolic links carry no text of their own and empty files carry no text
    # at all; libmagic reports inode/symlink and inode/x-empty for them, so
    # deciding from the metadata keeps the outcome and saves the open().
    try:
        lstat_res = os.lstat(f)
        if S_ISLNK(lstat_res.st_mode) or lstat_res.st_size == 0:
            eprint('%s: SKIPPED' % f)
            return False
    except Exception as e:
        eprint('%s: %s' % (f, e))
        return False

    try:
        fobj = open(f, 'rb')
    except Exception as e:
        eprint('%s: %s' % (f, e))
        return False

    with fobj:
        if excluded_by_mime(get_mime(f, fobj)):
            eprint('%s: SKIPPED' % f)
            return False

        fobj.seek(0)
        text = getfiletext(f, fobj)

    if text:
        return analyze_text(f, text, disallowed, msg)

    return False

# Actual implementation of the recursive descent into directories.  Files are
# collected first and analyzed afterwards, so that the analysis can run in
# parallel while the report keeps the order of the descent.
def collect_any(p, dirs_seen, files):
    try:
        stat_res = os.stat(p)
    except Exception as e:
        eprint('%s: %s' % (p, e))
        return

    mode = stat_res.st_mode
    if S_ISDIR(mode):
        # avoid analyzing the same dir twice
        inode = stat_res.st_ino
        if inode:
            if inode in dirs_seen:
                return
            dirs_seen.add(inode)

        collect_dir(p, dirs_seen, files)
    elif S_ISREG(mode):
        files.append(p)
    else:
        eprint('%s: UNREADABLE' % p)

# Recursively collect files in the directory.
def collect_dir(d, dirs_seen, files):
    for f in os.listdir(d):
        collect_any(os.path.join(d, f), dirs_seen, files)

# Analyze one file with its output kept in per-thread buffers, so that the
# caller can print the results in order.
def analyze_file_buffered(args):
    f, disallowed, msg = args
    _thread_output.out = io.StringIO()
    _thread_output.err = io.StringIO()
    try:
        warned = analyze_file(f, disallowed, msg)
        return warned, _thread_output.out.getvalue(), _thread_output.err.getvalue()
    finally:
        _thread_output.out = None
        _thread_output.err = None

def analyze_files(files, disallowed, msg):
    warned = False

    if jobs > 1:
        try:
            from concurrent.futures import ThreadPoolExecutor
        except ImportError:
            ThreadPoolExecutor = None

        if ThreadPoolExecutor:
            # The scan spends most of its time waiting for file I/O, so threads
            # overlap that wait even though they share the interpreter lock.
            work = [(f, disallowed, msg) for f in files]
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                for w, out, err in pool.map(analyze_file_buffered, work):
                    sys.stdout.write(out)
                    sys.stderr.write(err)
                    warned = warned or w
            return warned

        eprint('Parallel analysis is unavailable, falling back to one job')

    for f in files:
        w = analyze_file(f, disallowed, msg)
        warned = warned or w

    return warned

def analyze_paths(paths, disallowed, msg, dirs_seen):
    files = []

    for p in paths:
        collect_any(p, dirs_seen, files)

    return analyze_files(files, disallowed, msg)

# All control characters.  We omit the ascii control characters.
def nonprint_unicode(c):
    cat = unicodedata.category(c)
    if cat.startswith('C') and cat != 'Cc':
        return True
    return False

# Entry point for the analysis.  Arguments are passed in cli.py.
def start_unicode_analysis(args):
    global verbose_mode, detailed_mode
    global jobs
    verbose_mode = args.verbose
    detailed_mode = args.detailed
    jobs = max(1, getattr(args, 'jobs', 1))

    if not args.nonprint:
        # Formatting control characters in the unicode space.  This includes the
        # bidi control characters.
        disallowed = set(_chr(c) for c in range(sys.maxunicode) if \
                                 unicodedata.category(_chr(c)) == 'Cf')

        msg = 'unicode control characters'
    elif args.nonprint == 'all':
        # All control characters.
        disallowed = set(_chr(c) for c in range(sys.maxunicode) if \
                         nonprint_unicode(_chr(c)))

        msg = 'disallowed characters'
    else:
        # Only bidi control characters.
        disallowed = set([
            _chr(0x202a), _chr(0x202b), _chr(0x202c), _chr(0x202d), _chr(0x202e),
            _chr(0x2066), _chr(0x2067), _chr(0x2068), _chr(0x2069)])
        msg = 'bidirectional control characters'

    if args.config:
        if platform.python_version_tuple() >= ('3','04','0'):
            # load settings file, method for Python >= 3.4
            spec = importlib.util.spec_from_file_location("settings", args.config)
            settings = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(settings)
        else:
            # load settings file, method for Python < 3.4
            settings = imp.load_source("settings", args.config)

        if hasattr(settings, 'scan_exclude'):
            scan_exclude = scan_exclude + settings.scan_exclude
        if hasattr(settings, 'scan_exclude_mime'):
            scan_exclude_mime = scan_exclude_mime + settings.scan_exclude_mime

    if args.notests:
        scan_exclude = scan_exclude + [r'/test[^/]+/']

    dirs_seen = set()

    warned = analyze_paths(args.path, disallowed, msg, dirs_seen)

    if warned:
        exit(1)
