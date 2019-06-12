#!/usr/bin/env python3
import argparse
import sys
import os
import pprint
from gtirb import *


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input",
                        help="The input GTIRB file",
                        action='store',
                        required=True)
    parser.add_argument("-o", "--out",
                        help="The output GTIRB file",
                        action='store',
                        default='out.ir')
    args = parser.parse_args()

    infile = args.input
    if not os.path.exists(infile):
        print(f"Error: Input file {infile} does not exist.", file=sys.stderr)
        return -1

    ir_loader = IRLoader()
    ir = ir_loader.IRLoadFromProtobufFileName(infile)
    factory = ir_loader._factory
    IRPrintString(infile)

if __name__ == '__main__':
    main()
