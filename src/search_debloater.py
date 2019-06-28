#!/usr/bin/env python3

import argparse
import logging as log
import tempfile
import shutil
import subprocess
import sys
import os
from gtirb import *

from gtirbtools.deleter import BlockDeleter, FunctionDeleter
from search.delta import Delta
from search.simple import Bisect, Linear
from testing.grep import GrepTest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--in",
                        help="input GTIRB file",
                        metavar="FILE",
                        dest='in_file',
                        required=True)
    parser.add_argument("-t", "--tramp",
                        help="trampoline file",
                        metavar="FILE",
                        action='store',
                        default='etc/__gtirb_trampoline.S')
    parser.add_argument("--log-file",
                        help="log file")
    parser.add_argument("--log-level",
                        help="log level",
                        metavar="LEVEL",
                        choices=[log.getLevelName(l) for l in
                                 [log.ERROR, log.INFO, log.DEBUG]],
                        default=log.INFO)
    parser.add_argument("-w", "--workdir",
                        help="working directory",
                        metavar="DIR",
                        required=True)
    parser.add_argument("-s", "--save",
                        help="save files generated during the search",
                        choices=['all', 'passing'],
                        default='passing')

    args = parser.parse_args()
    if not os.path.exists(args.in_file):
        sys.exit(f"Error: Input file {args.in_file} does not exist.")
    if not os.path.exists(args.tramp):
        sys.exit(f"Error: Trampoline file {args.tramp} does not exist")

    format = '[%(levelname)-5s %(asctime)s] - %(module)s: %(message)s'
    datefmt = '%m/%d %H:%M:%S'
    log.basicConfig(level=args.log_level, format=format, datefmt=datefmt)

    if args.log_file:
        fh = log.FileHandler(args.log_file)
        fh.setFormatter(log.Formatter(format))
        log.getLogger().addHandler(fh)

    tester = GrepTest(limit_bin='/development/src/testing/limit',
                      tests_dir='/development/grep-generated-tests',
                      flag='c')
    deleter = FunctionDeleter(infile=args.in_file,
                              trampoline=args.tramp,
                              workdir=args.workdir,
                              binary_name='grep',
                              build_flags = ['-lm', '-lresolv'])
    search = Bisect(save_files=args.save, tester=tester, deleter=deleter)
    results = search.run()

if __name__ == '__main__':
    main()
