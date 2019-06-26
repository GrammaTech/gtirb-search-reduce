#!/usr/bin/env python3

import argparse
import logging as log
import tempfile
from datetime import datetime
import shutil
import subprocess
import sys
import os
from gtirb import *

from search.delta import DeltaBlocks, DeltaFunctions
from search.simple import BisectBlocks, BisectFunctions
from search.simple import LinearBlocks, LinearFunctions
from testing.grep import GrepTest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--in",
                        help="input GTIRB file",
                        metavar="FILE",
                        dest='in_file',
                        required=True)
    parser.add_argument("-o", "--out",
                        help="output GTIRB file",
                        metavar="FILE",
                        default='out.ir')
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
                        choices=['all', 'passing'])

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
    search = LinearFunctions(infile=args.in_file,
                             trampoline=args.tramp,
                             workdir=args.workdir,
                             save_files=args.save,
                             tester=tester)
    start = datetime.now()
    functions = search.run()
    log.info(f"Functions to delete:\n"
             f"{' '.join(functions)}")
    finish = datetime.now()
    runtime = finish - start
    log.info(f"Finish time: {finish}")
    log.info(f"Runtime: {runtime}")


if __name__ == '__main__':
    main()
