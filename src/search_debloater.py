#!/usr/bin/env python3

import argparse
import copy
import tempfile
import subprocess
import sys
import os
from gtirb import *

import block_deleter
from search.DD import DD, Result

verbosity = 0


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
        print(' '.join([str(b) for b in delete_blocks]))
        # Re-read IR every time
        if verbosity > 0:
            print("SEARCH: Reading IR")
        self._read_ir()
        # Generate new IR
        if verbosity > 0:
            print("SEARCH: Deleting blocks")
        block_deleter.remove_blocks(self._ir, self._factory,
                                    block_addresses=delete_blocks,
                                    verbosity=verbosity)
        # Output to a GTIRB file
        with tempfile.NamedTemporaryFile(mode='w+b') as temp:
            temp.write(self._ir.toProtobuf().SerializeToString())
            asm_file = temp.name + '.S'
            exe_file = temp.name + '.exe'
            # Dump assembly
            if verbosity > 0:
                print("SEARCH: Dumping assembly")
            pprinter_command = ['gtirb-pprinter',
                                '-i', temp.name,
                                '-o', asm_file]
            try:
                result = subprocess.run(pprinter_command)
                if result.returncode != 0:
                    print("ERROR: gtirb-pprinter failed to assemble "
                          f"{asm_file}", file=sys.stderr)
                    return Result.FAIL
            except Exception:
                print("ERROR: exception while running gtirb-pprinter",
                      file=sys.stderr)
                return Result.FAIL

            # Compile
            if verbosity > 0:
                print("SEARCH: Compiling")
            build_command = ['gcc', asm_file, '-o', exe_file]
            try:
                result = subprocess.run(build_command)
                if result.returncode != 0:
                    print(f"ERROR: gcc failed to build {exe_file}",
                          file=sys.stderr)
                    return Result.FAIL
            except Exception:
                print("ERROR: exception while running gcc", file=sys.stderr)
                return Result.FAIL
            # Run tests
            if verbosity > 0:
                print("SEARCH: Testing")
            # FIXME
            return Result.PASS


def main():
    global verbosity
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input",
                        help="input GTIRB file",
                        action='store',
                        required=True)
    parser.add_argument("-o", "--out",
                        help="output GTIRB file",
                        action='store',
                        default='out.ir')
    parser.add_argument("-v", "--verbose",
                        help="verbosity level",
                        action='count',
                        default=0)
    args = parser.parse_args()

    verbosity = args.verbose

    dd = DDBlocks(args.input)
    blocks = dd.ddmax(dd.blocklist)

    ir_out = ir.toProtobuf()
    with open(args.out, 'wb') as outfile:
        outfile.write(ir_out.SerializeToString())


if __name__ == '__main__':
    main()
