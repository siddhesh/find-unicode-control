# find-unicode-control

This script looks for non-printable unicode characters in all text files in a source tree.

```
usage: find_unicode_control2.py [-h] [-p {all,bidi}] [-v] [-c CONFIG] path [path ...]

Look for Unicode control characters

positional arguments:
  path                  Sources to analyze

optional arguments:
  -h, --help            show this help message and exit
  -p {all,bidi}, --nonprint {all,bidi}
                        Look for either all non-printable unicode characters or bidirectional control characters.
  -v, --verbose         Verbose mode.
  -d, --detailed        Print line numbers where characters occur.
  -t, --notests         Exclude tests (basically test.* as a component of path).
  -c CONFIG, --config CONFIG
                        Configuration file to read settings from.
```

`find_unicode_control2.py` should work with both python2 as well as python3.

If unicode BIDI control characters or non-printable characters are found in a
file, it will print output as follows:

```
$ python3 find_unicode_control2.py -p bidi *.c
commenting-out.c: bidirectional control characters: {'\u202e', '\u2066', '\u2069'}
early-return.c: bidirectional control characters: {'\u2067'}
stretched-string.c: bidirectional control characters: {'\u202e', '\u2066', '\u2069'}
```

Using the `-d` flag, the output is more detailed, showing line numbers in
files, but this mode is also slower:

```
find_unicode_control2.py -p bidi -d .
./commenting-out.c:4 bidirectional control characters: ['\u202e', '\u2066', '\u2069', '\u2066']
./commenting-out.c:6 bidirectional control characters: ['\u202e', '\u2066']
./early-return.c:4 bidirectional control characters: ['\u2067']
./stretched-string.c:6 bidirectional control characters: ['\u202e', '\u2066', '\u2069', '\u2066']
```

The optimal workflow would be to do a quick scan through a source tree and if
any issues are found, do a detailed scan on only those files.

## Configuration file

If files need to be excluded from the scan, make a configuration file and
define a `scan_exclude` variable to a list of regular expressions that match
the files or paths to exclude.  Alternatively, add a `scan_exclude_mime` list
with the list of mime types to ignore; this can again be a regular expression.
Here is an example configuration that glibc uses:

```
scan_exclude = [
        # Iconv test data
        r'/iconvdata/testdata/',
        # Test case data
        r'libio/tst-widetext.input$',
        # Test script.  This is to silence the warning:
        # 'utf-8' codec can't decode byte 0xe9 in position 2118: invalid continuation byte
        # since the script tests mixed encoding characters.
        r'localedata/tst-langinfo.sh$']
```

