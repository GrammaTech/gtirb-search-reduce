#!/usr/bin/env python3

import argparse
import copy
import logging
import tempfile
import subprocess
import sys
import os
from gtirb import *

import block_deleter
from search.DD import DD, Result


class DDBlocks(DD):
    def __init__(self, infile, keep_passing=False):
        DD.__init__(self)
        self.infile = infile
        self._read_ir()
        self.blocklist = block_deleter.block_addresses(self._ir)
        self.keep_passing = keep_passing

    def _read_ir(self):
        if not os.path.exists(self.infile):
            sys.exit(f"Error: Input file {infile} does not exist.")
        self._ir_loader = IRLoader()
        self._ir = self._ir_loader.IRLoadFromProtobufFileName(self.infile)
        self._factory = self._ir_loader._factory

    def _test(self, delete_blocks):
        logging.info(f"Processing: \n"
                     f"{' '.join([str(b) for b in delete_blocks])}")
        # Re-read IR every time
        logging.info("Reading IR")
        self._read_ir()
        # Generate new IR
        logging.info("Deleting blocks")
        block_deleter.remove_blocks(self._ir, self._factory,
                                    block_addresses=delete_blocks)
        # Output to a GTIRB file
        with tempfile.NamedTemporaryFile(mode='w+b') as temp:
            temp.write(self._ir.toProtobuf().SerializeToString())
            asm_file = temp.name + '.S'
            exe_file = temp.name + '.exe'
            # Dump assembly
            logging.info("Dumping assembly")
            pprinter_command = ['gtirb-pprinter',
                                '-i', temp.name,
                                '-o', asm_file]
            try:
                result = subprocess.run(pprinter_command)
                if result.returncode != 0:
                    logging.error("gtirb-pprinter failed to assemble "
                                  f"{asm_file}")
                    return Result.FAIL
            except Exception:
                logging.error("Exception while running gtirb-pprinter")
                return Result.FAIL

            # Compile
            logging.info("Compiling")
            build_command = ['gcc', asm_file, '-o', exe_file]
            try:
                result = subprocess.run(build_command)
                if result.returncode != 0:
                    logging.error(f"gcc failed to build {exe_file}")
                    return Result.FAIL
            except Exception:
                logging.error("exception while running gcc")
                return Result.FAIL
            # Run tests
            logging.info("Testing")
            # FIXME
            return Result.PASS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input",
                        help="input GTIRB file",
                        action='store',
                        required=True)
    parser.add_argument("-o", "--out",
                        help="output GTIRB file",
                        action='store',
                        default='out.ir')
    parser.add_argument("--log-level",
                        help="logging level",
                        action='store',
                        default=logging.INFO)
    parser.add_argument("--log-file",
                        help="log file",
                        action='store')

    args = parser.parse_args()

    format = '[%(levelname)s] %(asctime)s - %(module)s: %(message)s'
    datefmt = '%m/%d %H:%M:%S'
    if args.log_file:
        logging.basicConfig(filename=args.log_file, format=format,
                            datefmt=datefmt, level=args.log_level)
    else:
        logging.basicConfig(level=args.log_level, format=format,
                            datefmt=datefmt)

    dd = DDBlocks(args.input)
    blocks = dd.ddmax(dd.blocklist)

    ir_out = ir.toProtobuf()
    with open(args.out, 'wb') as outfile:
        outfile.write(ir_out.SerializeToString())


if __name__ == '__main__':
    main()
