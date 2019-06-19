#!/usr/bin/env python3

import argparse
import logging as log
import tempfile
import shutil
import subprocess
import sys
import os
from gtirb import *

import block_deleter
from search.DDDeleter import DDBlocks, DDFunctions


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
                        default=None)
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

    dd = DDBlocks(infile=args.in_file,
                  trampoline=args.tramp,
                  workdir=args.workdir,
                  save_files=args.save)
    blocks = set(dd.ddmin(dd.blocklist))
    deleted_blocks = [b for b in dd.blocklist if b not in blocks]

    ir_loader = IRLoader()
    ir = ir_loader.IRLoadFromProtobufFileName(args.in_file)
    factory = ir_loader._factory
    block_deleter.remove_blocks(ir, factory, block_addresses=deleted_blocks)
    ir_out = ir.toProtobuf()

    log.info(f"Blocks to delete:\n"
             f"{' '.join([str(b) for b in deleted_blocks])}")
    with open(args.out, 'wb') as outfile:
        outfile.write(ir_out.SerializeToString())


if __name__ == '__main__':
    main()
