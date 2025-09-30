# SPDX-License-Identifier: BSD-3-Clause

from .find_unicode_control import *


def main():
    parser = argparse.ArgumentParser(description="Look for Unicode control characters")
    parser.add_argument('path', metavar='path', nargs='+',
            help='Sources to analyze')
    parser.add_argument('-p', '--nonprint', required=False,
            type=str, choices=['all', 'bidi'],
            help='Look for either all non-printable unicode characters or bidirectional control characters.')
    parser.add_argument('-v', '--verbose', required=False, action='store_true',
            help='Verbose mode.')
    parser.add_argument('-d', '--detailed', required=False, action='store_true',
            help='Print line numbers where characters occur.')
    parser.add_argument('-t', '--notests', required=False,
            action='store_true', help='Exclude tests (basically test.* as a component of path).')
    parser.add_argument('-c', '--config', required=False, type=str,
            help='Configuration file to read settings from.')

    start_unicode_analysis(parser.parse_args())


if __name__ == '__main__':
    main()

