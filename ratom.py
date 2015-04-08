#!/usr/bin/env python3

"""The main module for ratom."""

from __future__ import print_function

import argparse
import logging
import os
import shutil
import socket


DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 52698
DEFAULT_TIMEOUT = 5

OPEN_CMD = 'open'
SAVE_CMD = 'save'
CLOSE_CMD = 'close'

DATA_SIZE_KEY = 'data'
DATA_CONTENT_KEY = 'content'
DATA_ON_SAVE_KEY = 'data-on-save'
DISPLAY_NAME_KEY = 'display-name'
PATH_KEY = 'token'
REAL_PATH_KEY = 'real-path'
RE_ACTIVATE_KEY = 're-activate'


class Error(Exception):
    """Base exception for this module."""


def __config_logging(verbose):
    """Basic configurations for the logging module."""
    log_level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(format='%[levelname]s %(message)s', level=log_level)


def open_atom(atom, path):
    """Opens |path| in the remote |atom|."""
    cmd = {
            DISPLAY_NAME_KEY: '%s:%s' % (socket.gethostname(), path),
            REAL_PATH_KEY: os.path.abspath(path), DATA_ON_SAVE_KEY: 'yes',
            RE_ACTIVATE_KEY: 'yes', PATH_KEY: path,
    }
    if os.path.isfile(path):
        with open(path, 'r') as file:
            cmd[DATA_CONTENT_KEY] = file.read()
            cmd[DATA_SIZE_KEY] = file.tell()

    atom.write('%s\n' % OPEN_CMD)
    for key, val in cmd.items():
        if key not in (DATA_CONTENT_KEY, DATA_SIZE_KEY):
            atom.write('%s: %s\n' % (key, val))
    if cmd.get(DATA_SIZE_KEY, 0) and cmd.get(DATA_CONTENT_KEY, ''):
        atom.write('%s: %d\n%s\n' % (DATA_SIZE_KEY, cmd[DATA_SIZE_KEY],
                                     cmd[DATA_CONTENT_KEY]))
    atom.write('.\n')

    logging.info('Opening %s', path)


def handle_atom(atom):
    """Handles the remote |atom|'s command."""
    cmd = None
    for line in atom:
        line = line.strip()

        if not line:
            if DATA_SIZE_KEY in cmd and cmd.get(PATH_KEY, ''):
                path = cmd[PATH_KEY]
                logging.info('Saving %s', path)

                backup_path = '%s~' % path
                while os.path.isfile(backup_path):
                    backup_path = '%s~' % backup_path
                if os.path.isfile(path):
                    shutil.copy2(path, backup_path)

                file = open(path, 'w')
                file.write(cmd[DATA_CONTENT_KEY])
                if os.path.isfile(backup_path):
                    os.remove(backup_path)

            cmd = None

        if cmd == None:
            if line == SAVE_CMD:
                cmd = {DATA_CONTENT_KEY: ''}
        else:
            items = [item.strip() for item in line.split(':', 2)]
            cmd[items[0]] = items[1]
            if items[0] == DATA_SIZE_KEY:
                cmd[DATA_CONTENT_KEY] += atom.read(int(items[1]))


def __parse_args():
    """Parses the command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('path', help='edit specified file')
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
    try:
        args = __parse_args()
        __config_logging(args.verbose)

        if os.path.isdir(args.path):
            raise Error('%s is a directory!' % args.path)
        elif os.path.isfile(args.path) and not os.access(args.path, os.W_OK):
            if args.force:
                logging.warning(
                        'File %s is not writable. Opening anyway.', args.path)
            else:
                raise Error('File %s is not writable! Use -f/--force to open '
                            'anyway.' % args.path)

        sock = None
        atom = None

        try:
            socket.setdefaulttimeout(DEFAULT_TIMEOUT)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((args.host, args.port))
            sock.setblocking(True)

            atom = sock.makefile('rw')
            info = atom.readline().strip()  # pylint: disable=no-member
            if not info:
                raise Error()
            logging.info('Connected and using: %s', info)

            open_atom(atom, args.path)
            atom.flush()  # pylint: disable=no-member
            handle_atom(atom)
        except (Error, socket.error):
            raise Error('Unable to connect to Atom on %s:%s' %
                        (args.host, args.port))
        finally:
            if sock:
                sock.close()
            if atom:
                atom.close()
    except Error as e:
        logging.error(e)
        exit(1)


if __name__ == '__main__':
    main()
