#!/usr/bin/env python3
# Large parts copied from block_remove.py in the rewriting/gtirb-reduce repo

import argparse
import sys
import os
import pprint
from gtirb import *


def add_edge(graph, source, target, edge):
    source_entry = graph.get(source)
    if source_entry is not None:
        if target in source_entry['to']:
            source_entry['to'][target].add(edge)
        else:
            source_entry['to'][target] = set([edge])
    else:
        graph[source] = {
            'from': dict(),
            'to': {target: set([edge])}
        }
    target_entry = graph.get(target)
    if target_entry is not None:
        if source in target_entry['from']:
            target_entry['from'][source].add(edge)
        else:
            target_entry['from'][source] = set([edge])
    else:
        graph[target] = {
            'from': {source: set([edge])},
            'to': dict()
        }


def print_graph(graph):
    for entry, value in graph.items():
        def print_edges(direction):
            for node, edges in value[direction].items():
                edges = [f"({e._source_block._address:x},"
                         f" {e._target_block._address:x})"
                         for e in edges]
                print(f"\t{direction.upper()}: {node._address:x} | "
                      f"EDGES: {edges}")
        try:
            print(f"NODE: {entry._address:x}")
            for direction in ['to', 'from']:
                print_edges(direction)
        except Exception as e:
            pass
        print()


def print_CFG(ir, factory):
    for module in ir._modules:
        cfg = module._cfg
        graph = dict()
        for edge in cfg._edges:
            add_edge(graph, edge.source(), edge.target(), edge)
        print_graph(graph)

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
    print_CFG(ir, factory)
    # IRPrintString(infile)

    ir_out = ir.toProtobuf()
    with open(args.out, 'wb') as outfile:
        outfile.write(ir_out.SerializeToString())


if __name__ == '__main__':
    main()
