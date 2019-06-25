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

from search.DDDeleter import DDBlocks, DDFunctions
from search.linear import LinearBlocks, LinearFunctions
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

    # dd = DDBlocks(infile=args.in_file,
    #               trampoline=args.tramp,
    #               workdir=args.workdir,
    #               save_files=args.save)
    # blocks = set(dd.ddmin(dd.blocklist))
    # deleted_blocks = [b for b in dd.blocklist if b not in blocks]
    tester = GrepTest(limit_bin='/development/src/testing/limit',
                      tests_dir='/development/grep-generated-tests',
                      flag='c')
    start = datetime.now()
    dd = DDFunctions(infile=args.in_file,
                     trampoline=args.tramp,
                     workdir=args.workdir,
                     save_files=args.save,
                     tester=tester)
    functions = dd.ddmin(dd.functions)
    log.info(f"Functions to delete:\n"
             f"{' '.join(functions)}")
    finish = datetime.now()
    runtime = finish - start
    log.info(f"Finish time: {finish}")
    log.info(f"Runtime: {runtime}")

    # start = datetime.now()
    # log.info(f"Start time: {start}")
    # linear = LinearBlocks(infile=args.in_file,
    #                       trampoline=args.tramp,
    #                       workdir=args.workdir,
    #                       save_files=args.save)
    # functions = linear.run()

    # ir_loader = IRLoader()
    # ir = ir_loader.IRLoadFromProtobufFileName(args.in_file)
    # factory = ir_loader._factory
    # block_deleter.remove_blocks(ir, factory, block_addresses=deleted_blocks)
    # ir_out = ir.toProtobuf()

    # log.info(f"Functions to delete:\n"
    #          f"{' '.join(functions)}")
    # finish = datetime.now()
    # runtime = finish - start
    # log.info(f"Finish time: {finish}")
    # log.info(f"Runtime: {runtime}")

    # with open(args.out, 'wb') as outfile:
    #     outfile.write(ir_out.SerializeToString())


if __name__ == '__main__':
    main()
