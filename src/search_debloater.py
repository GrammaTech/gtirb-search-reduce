#!/usr/bin/env python3
# Large parts copied from block_remove.py in the rewriting/gtirb-reduce repo

import argparse
import sys
import os
import pprint
from gtirb import *


def print_graph(graph):
    for entry, value in graph.items():
        def print_edges(direction):
            for node, edges in value[direction].items():
                edges = str([(hex(e._source_block._address),
                              hex(e._target_block._address))
                             for e in edges])
                print(f"\t{direction.upper()}: {node._address} | "
                      f"EDGES: {edges}")
        try:
            print(f"NODE: {entry._address}")
            for direction in ['to', 'from']:
                print_edges(direction)
        except Exception as e:
            pass
        print()


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
    # IRPrintString(infile)

    ir_out = ir.toProtobuf()
    with open(args.out, 'wb') as outfile:
        outfile.write(ir_out.SerializeToString())


if __name__ == '__main__':
    main()
