#!/usr/bin/python3

import argparse
import asyncio
import os
import subprocess
import sys

from contextlib import suppress
from platform import system as get_system

# Constants
PROGRAM_NAME = 'PanMK'
VERSION = '0.1a'


def get_platform():
    ''' Guess the platform the user is using.

        Naturally, this will fail miserably if you invoke the Windows version from Cywgin/WSL.
    '''
    platforms = ['windows', 'cygin', 'darwin']
    platform = get_system().lower()

    for plat in platforms:
        if plat in platform:
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

    skip_timestamp_flag = parser.add_mutually_exclusive_group()
    skip_timestamp_flag.add_argument('-g', dest='g', action='store_true',
                                     help='process regardless of file timestamps')
    skip_timestamp_flag.add_argument('-g-', dest='g', action='store_false', default=False,
                                     help='Turn off -g')

    viewer_flag = parser.add_mutually_exclusive_group()
    viewer_flag.add_argument('--new-viewer', dest='new-viewer', action='store_true',
                             help='in -pvc mode, always start a new viewer')
    viewer_flag.add_argument('--no-new-viewer', dest='new-viewer', action='store_false', default=False,
                             help='in -pvc mode, start a new viewer only if needed')

    parser.add_argument('--norc', dest='norc', action='store_true',
                        help='omit automatic reading of system, user, and project rc files')

    preview_flag = parser.add_mutually_exclusive_group()
    preview_flag.add_argument('-p', dest='action', action='store_const', const='p', default='p',
                              help='compile document.')
    preview_flag.add_argument('-pc', dest='action', action='store_const', const='pc', default='p',
                              help='continuously compile document.')
    preview_flag.add_argument('-pv', dest='action', action='store_const', const='pv', default='p',
                              help='preview document.')
    preview_flag.add_argument('-pvc', dest='action', action='store_const', const='pvc', default='p',
                              help='preview document and continuously update.')

    parser.add_argument('--rc', help='Read custom RC file')

    parser.add_argument('-v', '--version', action='version', version='%s %s' % (PROGRAM_NAME, VERSION))

    parser.add_argument('-o', '--output', required=True,
                        help='The name of the output file.'
                             '{filename} will automatically be replaced with the input file\'s base name.')

    parser.add_argument('filename', help='the root filename of the document(s) to compile')

    return parser.parse_known_args()


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

    args.update(config)


def load_default_rc(platform, args):
    '''Loads the default rc, based on what platform you are own.'''

    if platform == 'windows':
        sysdrive = os.environ['systemdrive']

        path = os.path.join(sysdrive, 'panmk', 'panmkrc')
        load_rc(path, args)

        path = os.path.expanduser(os.path.join('~user', '.panmkrc'))
        load_rc(path, args)

    else:
        # This won't work if you execute this using the Windows Python binary
        paths = ['/opt/local/share/panmk', '/usr/local/share/panmk',
                 '/usr/local/lib/panmk', '~']

        for path in paths:
            load_rc(os.path.join(path, '.panmk'), args)


def call_pandoc(path, output, args):
    '''Call pandoc to compile `path`, with arguments `args`'''

    basename = os.path.splitext(os.path.basename(path))[0]
    output_file = output.format(filename=basename)
    proc = subprocess.run(['pandoc', path, '-o', output_file] + args, capture_output=True)
    if proc.stderr:
        print('%s' % proc.stderr)
    return output_file


def get_loader_cmd(platform):
    ''' Returns a lambda that gives the command to view the file on the given platform. 

       Since the platform will not change under normal circumstances, we can avoid using a comparison.
       This should speed up the loading and reloading functions.
    '''

    if platform == 'windows':
        cmd = lambda x: ['start', x]
    elif platform == 'cygin':
        cmd = lambda x: ['cmd', '/c', 'start', x]
    elif platform == 'darwin':
        cmd = lambda x: ['open', x]
    else:
        # Please work please work please work
        # cmd = lambda x: ['xdg-open', x]

        # TODO: REMOVE THIS DEBUG CODE
        cmd = lambda x: ['evince', x]

    return cmd


def get_file_loader(platform):
    '''Returns a function that opens files for viewing on the given platform.'''

    cmd = get_loader_cmd(platform)
    return lambda x: subprocess.run(cmd(x))


def get_reloadable(path, platform):
    '''Returns a Popen object so it can be reloaded'''

    return subprocess.Popen(get_loader_cmd(platform)(path))


def get_file_reloader(platform):
    ''' Returns a function that reloads the file for viewing on the given platform.'''

    return (lambda x: x)


def continuous(platform, args, pandoc_args, reload_file):
    '''Continuous mode: continually compile the file until ^C is sent.'''

    pre = None
    output = call_pandoc(args['filename'], args['output'], pandoc_args)
    proc = get_reloadable(output, platform)
    while True:
        try:
            cur = os.stat(args['filename'])
            if cur != pre:
                pre = cur
                try:
                    call_pandoc(args['filename'], args['output'], pandoc_args)
                    reload_file(proc)
                except KeyboardInterrupt:
                    pass
        except KeyboardInterrupt:
            break


def main():
    '''Main function. 'nough said.'''

    # Get panmk and pandoc arguements
    args, pandoc_args = get_cmd_args()
    args = vars(args)

    platform = get_platform()

    # Execute the user's code
    if args.get('exec') is not None:
        try:
            exec(args.exec)
        except Exception as e:
            print(e, file=sys.stderr)

    # Load the rc file
    if args.get('rc'):
        load_rc(args.get('rc'), args)
    elif not args.get('norc'):
        load_default_rc(platform, args)

    # There is a possibility that [re]loading a file is non-trivial
    # *COUGH* acroread *COUGH*
    # So we allow the user to specify a different reload function
    if args.get('load_file'):
        load_file = eval(args.get('load_file'))
    else:
        load_file = get_file_loader(platform)

    if args['new-viewer']:
        reload_file = load_file
    else:
        if args.get('reload_file'):
            reload_file = eval(args.get('reload_file'))
        else:
            reload_file = get_file_reloader(platform)


    # Test with trivial case for now
    if args['action'] == 'p':
        output = call_pandoc(args['filename'], args['output'], pandoc_args)
    elif args['action'] == 'pv':
        output = call_pandoc(args['filename'], args['output'], pandoc_args)
        load_file(output)
    elif args['action'] == 'pvc':
        continuous(platform, args, pandoc_args, reload_file)

    return 0


if __name__ == '__main__':
    sys.exit(main())
