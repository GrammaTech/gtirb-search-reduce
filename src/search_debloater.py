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
    def __init__(self, infile, trampoline, keep_passing=False):
        DD.__init__(self)
        self.infile = infile
        self.trampoline = trampoline
        self._read_ir()
        self.blocklist = block_deleter.block_addresses(self._ir)
        self.keep_passing = keep_passing
        self.test_count = 0

    def _read_ir(self):
        if not os.path.exists(self.infile):
            sys.exit(f"Error: Input file {infile} does not exist.")
        self._ir_loader = IRLoader()
        self._ir = self._ir_loader.IRLoadFromProtobufFileName(self.infile)
        self._factory = self._ir_loader._factory

    def _test(self, blocks):
        blocks = set(blocks)
        delete_blocks = [x for x in self.blocklist if x not in blocks]
        self.test_count += 1
        logging.info(f"Test #{self.test_count}")
        logging.debug(f"Processing: \n"
                      f"{' '.join([str(b) for b in delete_blocks])}")
        # Re-read IR every time
        logging.info("Reading IR")
        self._read_ir()
        # Generate new IR
        logging.info("Deleting blocks")
        block_deleter.remove_blocks(self._ir, self._factory,
                                    block_addresses=delete_blocks)
        # Output to a GTIRB file
        with tempfile.NamedTemporaryFile(prefix=str(self.test_count) + '-',
                                         suffix='.ir') as ir_file, \
             tempfile.NamedTemporaryFile(prefix=str(self.test_count) + '-',
                                         suffix='.S') as asm:
            ir_file.write(self._ir.toProtobuf().SerializeToString())
            ir_file.flush()
            # Dump assembly
            logging.info("Dumping assembly")
            pprinter_command = ['gtirb-pprinter',
                                '-i', ir_file.name,
                                '-o', asm.name]
            try:
                result = subprocess.run(pprinter_command,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
                if result.returncode != 0:
                    logging.error("gtirb-pprinter failed to assemble "
                                  f"{asm.name}")
                    logging.info("FAIL")
                    return Result.PASS
            except Exception:
                logging.error("Exception while running gtirb-pprinter")
                logging.info("FAIL")
                return Result.PASS

            # Compile
            with tempfile.NamedTemporaryFile(prefix=str(self.test_count) + '-',
                                             suffix='.exe',
                                             delete=False) as exe:
                logging.info("Compiling")
                build_command = ['gcc', '-no-pie',
                                 asm.name, self.trampoline,
                                 '-o', exe.name]
                try:
                    res = subprocess.run(build_command,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
                    if res.returncode != 0:
                        logging.info(f"gcc failed to build with error:\n"
                                     f"{res.stderr.decode('utf-8').strip()}")
                        logging.info("FAIL")
                        return Result.PASS
                except Exception:
                    logging.error("exception while running gcc")
                    logging.info("FAIL")
                    return Result.PASS
            # Run tests
            logging.info("Testing")
            test_command = ['tests/test.py', exe.name]
            result = subprocess.run(test_command)
            if result.returncode == 0:
                logging.info("PASS")
                return Result.FAIL
            else:
                os.remove(exe.name)
                logging.info("FAIL")
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
    parser.add_argument("-t", "--trampoline",
                        help="trampoline file",
                        action='store',
                        default='etc/__gtirb_trampoline.S')
    parser.add_argument("--log-level",
                        help="logging level",
                        action='store',
                        default=logging.INFO)
    parser.add_argument("--log-file",
                        help="log file",
                        action='store')

    args = parser.parse_args()
    if not os.path.exists(args.input):
        sys.exit(f"Error: Input file {args.infile} does not exist.")
    if not os.path.exists(args.trampoline):
        sys.exit(f"Error: Trampoline file {args.trampoline} does not exist")

    format = '[%(levelname)-5s %(asctime)s] - %(module)s: %(message)s'
    datefmt = '%m/%d %H:%M:%S'
    if args.log_file:
        logging.basicConfig(filename=args.log_file, format=format,
                            datefmt=datefmt, level=args.log_level)
    else:
        logging.basicConfig(level=args.log_level, format=format,
                            datefmt=datefmt)

    dd = DDBlocks(args.input, args.trampoline)
    blocks = set(dd.ddmin(dd.blocklist))

    print([x for x in dd.blocklist if x not in blocks])
    ir_out = ir.toProtobuf()
    with open(args.out, 'wb') as outfile:
        outfile.write(ir_out.SerializeToString())


if __name__ == '__main__':
    main()
