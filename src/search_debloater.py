#!/usr/bin/env python3

import argparse
import sys
import os
from gtirb import *

import block_deleter

verbosity = 0


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

    infile = args.input
    verbosity = args.verbose
    if not os.path.exists(infile):
        print(f"Error: Input file {infile} does not exist.", file=sys.stderr)
        return -1

    ir_loader = IRLoader()
    ir = ir_loader.IRLoadFromProtobufFileName(infile)
    factory = ir_loader._factory

    # IRPrintString(infile)
    block_deleter.remove_blocks(ir, factory,
                                block_addresses=[0x3476], verbosity=verbosity)

    ir_out = ir.toProtobuf()
    with open(args.out, 'wb') as outfile:
        outfile.write(ir_out.SerializeToString())


if __name__ == '__main__':
    main()
