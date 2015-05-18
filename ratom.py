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


class ConnectError(Error):
    """Raised when error occurs during connection setup with remote atom."""


class OpenError(Error):
    """Raised when error occurs using remote atom to open files."""


class HandleError(Error):
    """Raised when error occurs saving or closing remotely opened files."""


def __config_logging(verbose):
    """Basic configurations for the logging module."""
    log_level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(format='[%(levelname)s] %(message)s', level=log_level)


def __check_path(path, force):
    """Checks if |path| is valid and writable.

    Args:
        path: The path to check.
        force: Whether to force open if the file is not writable.

    Returns:
        True if path is valid and writable, and False otherwise.
    """
    if os.path.isdir(path):
        # TODO (vastri): Support directory.
        logging.error('%s is a directory!', path)
        return False

    if os.path.isfile(path) and not os.access(path, os.W_OK):
        if force:
            logging.warning('File %s is not writable. Opening anyway.', path)
            return True
        logging.error(
                'File %s is not writable! Use -f/--force to open anyway.', path)
        return False

    if not os.path.isfile(path):
        dir_path = os.path.dirname(path)
        if not os.path.isdir(dir_path):
            logging.error('Directory %s does not exist! Cannot create file %s',
                          dir_path, path)
            return False
        if not os.access(dir_path, os.W_OK):
            logging.error('Directory %s is not writable! Cannot create file %s',
                          dir_path, path)
            return False

    return True


def __parse_line(line):
    """Parses |line| into a key:value pair."""
    return [item.strip() for item in line.strip().split(':', 2)]


def connect_atom(host, port):
    """Connects to atom on a remote machine.

    Args:
        host: The hostname of the atom server.
        port: The port number of the atom server.

    Returns:
        A tuple of a socket object and a file object used for communication with
        remote atom.

    Raises:
        ConnectError when error occurs during the connection.
    """
    try:
        socket.setdefaulttimeout(DEFAULT_TIMEOUT)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        sock.setblocking(True)

        atom = sock.makefile('rw')
        info = atom.readline().strip()  # pylint: disable=no-member
        if not info:
            raise ConnectError('Unable to get remote atom info.')
        logging.info('Connected and using: %s', info)

        return (sock, atom)
    except (IOError, socket.error) as e:
        raise ConnectError(e)


def open_atom(atom, path):
    """Opens |path| in the remote |atom|.

    Args:
        atom: The file object used for communication with remote atom.
        path: The path to open in remote atom.

    Raises:
        OpenError when error occurs opening the path.
    """
    cmd = {
            DISPLAY_NAME_KEY: '%s:%s' % (socket.gethostname(), path),
            REAL_PATH_KEY: os.path.abspath(path), DATA_ON_SAVE_KEY: 'yes',
            RE_ACTIVATE_KEY: 'yes', PATH_KEY: path,
    }
    if os.path.isfile(path):
        try:
            with open(path, 'r') as file:
                cmd[DATA_CONTENT_KEY] = file.read()
                cmd[DATA_SIZE_KEY] = file.tell()
        except IOError as e:
            raise OpenError(e)

    try:
        atom.write('%s\n' % OPEN_CMD)
        for key, val in cmd.items():
            if key not in (DATA_CONTENT_KEY, DATA_SIZE_KEY):
                atom.write('%s: %s\n' % (key, val))
        atom.write('%s: %d\n%s\n.\n' % (DATA_SIZE_KEY,
                                        cmd.get(DATA_SIZE_KEY, 0),
                                        cmd.get(DATA_CONTENT_KEY, '')))
        atom.flush()  # pylint: disable=no-member
    except (IOError, socket.error) as e:
        raise OpenError('Unable to send data to remote atom: %s' % e)

    logging.info('Opening %s', path)


def handle_atom(atom):
    """Handles the remote |atom|'s response.

    Args:
        atom: The file object used for communication with remote atom.

    Raises:
        HandleError when error occurs handling the response.
    """
    try:
        while True:
            line = atom.readline().strip()
            if not line:
                line = atom.readline().strip()
                if not line:
                    return
            if line != SAVE_CMD:
                break

            path_key, path = __parse_line(atom.readline())
            data_size_key, data_size = __parse_line(atom.readline())
            if path_key != PATH_KEY or not path or \
                    data_size_key != DATA_SIZE_KEY or not data_size:
                raise ValueError(
                        'Invalid response from remote atom:\n%s: %s\n%s: %s' %
                        (path_key, path, data_size_key, data_size))

            logging.info('Saving %s', path)

            try:
                tmp_path = '%s~' % path
                while os.path.isfile(tmp_path):
                    tmp_path = '%s~' % tmp_path
                if os.path.isfile(path):
                    shutil.copy2(path, tmp_path)
                with open(path, 'w') as file:
                    file.write(atom.read(int(data_size)))
                if os.path.isfile(tmp_path):
                    os.remove(tmp_path)
            finally:
                if os.path.isfile(tmp_path):
                    shutil.copy2(tmp_path, path)
                    os.remove(tmp_path)
    except (IOError, ValueError, socket.error) as e:
        raise HandleError(e)


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
    # pylint: disable=broad-except
    try:
        args = __parse_args()

        __config_logging(args.verbose)

        path = os.path.abspath(args.path)
        if not __check_path(path, args.force):
            exit(1)

        sock, atom = None, None
        try:
            (sock, atom) = connect_atom(args.host, args.port)
            open_atom(atom, path)
            handle_atom(atom)
        except ConnectError as e:
            logging.error('Failed to connect to remote atom: %s', e)
            exit(1)
        except OpenError as e:
            logging.error('Failed to open "%s" in remote atom: %s', path, e)
            exit(1)
        except HandleError as e:
            logging.error('Failed to save "%s": %s', path, e)
            exit(1)
        finally:
            if sock:
                sock.close()
            if atom:
                atom.close()
    except KeyboardInterrupt:
        logging.error('Aborted.')
        exit(1)
    except Exception as e:
        logging.error('Unexpected error: %s', e)
        exit(1)


if __name__ == '__main__':
    main()
