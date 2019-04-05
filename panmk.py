#!/usr/bin/python3
import argparse
import os
import platform
import sys


# Constants
PROGRAM_NAME = 'PanMK'
VERSION = '0.1'


def get_platform():
    ''' Guess the platform the user is using.

        Naturally, this will fail miserably if you invoke the Windows version from Cywgin/WSL.
    '''
    platforms = ['windows', 'cygin', 'darwin']
    _platform = platform.system().lower()

    for plat in platforms:
        if plat in _platform:
            return plat
    else:
        # Assume that all other system are posix-like enough that this is fine
        return 'posix'

def get_cmd_args():
    '''Parses the command line arguments and returns them.'''

    parser = argparse.ArgumentParser(prog='%s' % (PROGRAM_NAME.lower()),
                                     description='%s %s: Automatic pandoc compiler routine' % (PROGRAM_NAME, VERSION))

    cd_flag = parser.add_mutually_exclusive_group()
    cd_flag.add_argument('--cd', dest='cd', action='store_true',
                         help='Change to directory of source file when processing it')
    cd_flag.add_argument('--no-cd', dest='cd', action='store_false', default=False,
                        help='Do NOT change to directory of source file when processing it')

    parser.add_argument('-e', dest='exec', metavar='<code>',
                        help='Execute specified Python code (as part of panmk start-up code)')

    # skip_timestamp_flag = parser.add_mutually_exclusive_group()
    # skip_timestamp_flag.add_argument('-g', dest='g', action='store_true',
    #                                  help='process regardless of file timestamps')
    # skip_timestamp_flag.add_argument('-g-', dest='g', action='store_false', default=False,
    #                                  help='Turn off -g')

    viewer_flag = parser.add_mutually_exclusive_group()
    viewer_flag.add_argument('--new-viewer', dest='new-viewer', action='store_true',
                             help='in -pvc mode, always start a new viewer')
    viewer_flag.add_argument('--no-new-viewer', dest='new-viewer', action='store_false',
                             help='in -pvc mode, start a new viewer only if needed')

    parser.add_argument('--norc', dest='norc', action='store_true',
                        help='omit automatic reading of system, user, and project rc files')

    preview_flag = parser.add_mutually_exclusive_group()
    preview_flag.add_argument('-pv', dest='action', action='store_const', const='pv', default='p',
                              help='preview document.')
    preview_flag.add_argument('-pvc', dest='action', action='store_const', const='pvc', default='p',
                              help='preview document and continuously update.')

    parser.add_argument(['--rc'], dest='rc', help='Read custom RC file')

    parser.add_argument(['-v', '--version'], action='version', version='%s %s' % (PROGRAM_NAME, VERSION))

    parser.add_argument('filename', help='file to compile with pandoc')

    return parser.parse_args()


def normalize_path(path):
    '''Converts `path` to an absolute path, expanding all variables along the way.'''
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def read_config(path):
    ''' Reads the config specified by path.'''

    with open(path) as f:
        props = {line.strip().split('=', 1) for line in f}

    return props


def load_rc(rc, args):
    ''' Loads the rc file `rc` if it exists.
    
        `rc` should be written in an `ini` format.
    '''

    # Convert `rc` to an absolute path and expand all variables
    rc = normalize_path(rc)

    if not os.path.isfile(rc):
        return

    config = read_config(rc)

    for key, value in config:
        setattr(args, key, value)

    return args


def load_default_rc(platform, args):
    '''Loads the default rc, based on what platform you are own.'''

    if platform == 'windows':
        sysdrive = os.environ['systemdrive']

        path = os.path.join(sysdrive, 'panmk', 'panmkrc')
        args = load_rc(path, args)

        path = os.path.expanduser(os.path.join('~user', '.panmkrc'))
        args = load_rc(path, args)

    elif platform == 'cygin':
        # This won't work if you execute this using the Windows Python binary
        paths = ['/opt/local/share/panmk/', '/usr/local/share/panmk',
                 '/usr/local/lib/panmk']



def main():
    args = get_cmd_args()

    platform = get_platform()

    # Execute the user's code
    if args.exec is not None:
        try:
            exec(args.exec)
        except Exception as e:
            print(e, file=sys.stderr)

    # Load the rc file
    if args.rc:
        args = load_rc(args.rc, args)
    elif not args.norc:
        args = load_default_rc(platform, args)

    # There is a possibility that reloading a file is non-trivial
    # *COUGH* acroread *COUGH*
    # So we allow the user to specify a different reload function
    if args.reload_file:
        reload_file = eval(args.reload_file)

    return 0


if __name__ == '__main__':
    sys.exit(main())
