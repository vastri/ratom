#!/usr/bin/env python3

"""The main module for ratom."""

import argparse


DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 52698


def parse_args():
    """Parses the command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('file-path', help='edit specified file')
    parser.add_argument('-H', '--host', default=DEFAULT_HOST,
                        help='Connect to HOST. Use \'auto\' to detect the host '
                        'from SSH. Defaults to %s.' % DEFAULT_HOST)
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                        help='Port number to use for connetion. Defaults to '
                        '%d.' % DEFAULT_PORT)
    parser.add_argument('-w', '--wait', default=False, action='store_true',
                        help='Wait for file to be closed by Atom.')
    parser.add_argument('-l', '--line', type=int,
                        help='Place caret on the line number after loading '
                        'file.')
    parser.add_argument('-m', '--name', help='The display name shown in Atom.')
    parser.add_argument('-t', '--type',
                        help='Treat file as having specified type.')
    parser.add_argument('-f', '--force', default=False, action='store_true',
                        help='Open even if file is not writable.')
    parser.add_argument('-v', '--verbose', default=False, action='store_true',
                        help='Verbose logging messages.')
    parser.add_argument('--version', default=False, action='store_true',
                        help='Show version and exit.')
    return parser.parse_args()


def main():
    """The main function of this module."""
    parse_args()
    print('This script is not yet functional.')


if __name__ == '__main__':
    main()
