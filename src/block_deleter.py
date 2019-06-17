# Large parts copied from block_remove.py in the rewriting/gtirb-reduce repo

import argparse
import logging
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


def remove_node(graph, target_node):
    out_edges = list()
    connections = graph.get(target_node)
    if connections is None:
        return out_edges

    def delete_edges(direction, out_edges):
        for node, edges in connections[direction].items():
            out_edges += edges
            try:
                del graph[node][direction][target_node]
            except Exception:
                pass
        return out_edges

    for direction in ['to', 'from']:
        out_edges += delete_edges(direction, out_edges)

    del graph[target_node]
    return out_edges


def remove_blocks(ir, factory, block_addresses=list()):
    for module in ir._modules:
        blocks_by_addr = dict()
        cfg = module._cfg
        extern_trampoline = Symbol(factory=factory,
                                   name='__gtirb_trampoline',
                                   storage_kind=StorageKind.Extern)
        module._symbols.append(extern_trampoline)

        graph = dict()
        for block in module._blocks:
            if hasattr(block, '_address'):
                blocks_by_addr[block._address] = block

        # Add CFG edges to graph
        logging.debug("Building graph")
        for edge in cfg._edges:
            add_edge(graph, edge.source(), edge.target(), edge)

        # Using sets instead of a lists here greatly speeds up the
        # `if x in` checks
        edges_removed = set()
        blocks_removed = set()
        logging.debug("Removing blocks "
                      f"{' '.join([f'{b:x}' for b in block_addresses])}")

        # Remove nodes from the graph, returned list of edges correspond to the
        # edges that must be deleted from the IR
        for b in block_addresses:
            if b not in blocks_by_addr:
                logging.warning(f"No block with address {b:x} found")
                continue
            blocks_removed.add(blocks_by_addr[b])
            edges_removed.update(set(remove_node(graph, blocks_by_addr[b])))

        # if logging.getLogger().isEnabledFor(logging.DEBUG):
        #     for edge_removed in edges_removed:
        #         source = edge_removed.source()
        #         s_addr = source._address
        #         target = edge_removed.target()
        #         if isinstance(target, ProxyBlock):
        #             continue
        #         t_addr = target._address
        #         if (target in blocks_removed and source not in blocks_removed):
        #             logging.debug(f"{t_addr:x} removed,"
        #                           f" but {s_addr:x} references it")
        #         logging.debug(f"removed edge {s_addr:x} -> {t_addr:x}")

        # Collects the symbols that refer to removed blocks so the symbols can
        # also be removed
        logging.debug("Collecting symbols to remove")
        symbols_to_remove = list()
        for symbol in module.symbols():
            block = symbol.referent()
            if isinstance(block, Block) and block in blocks_removed:
                symbols_to_remove.append(symbol)

        logging.debug("Removing symbols")
        for symbol in symbols_to_remove:
            module._symbols.remove(symbol)

        # Remove symbol references to the block addresses and replace them with
        # a call to the trampoline symbol
        logging.debug("Pointing stale references to trampoline")
        for op in module._symbolic_operands.values():
            try:
                if (isinstance(op, SymAddrConst)
                    and op.symbol().referent() in blocks_removed):
                    op.setSymbol(extern_trampoline)
                elif (isinstance(op, SymAddrAddr)
                      and op._symbol1.referent() in blocks_removed):
                    op.setSymbol1(extern_trampoline)
            except Exception:
                pass
        logging.debug("Deleting blocks from GTIRB")
        module.removeBlocks(blocks_removed)
        logging.debug("Deleting edges from GTIRB CFG")
        cfg.removeEdges(edges_removed)
        logging.debug("Deleting functionBlock info from AuxData")
        function_blocks = module.auxData('functionBlocks')
        for value in function_blocks.values():
            for block in blocks_removed:
                value.discard(block._uuid)
        logging.debug("Deleting functionEntries info from AuxData")
        function_entries = module.auxData('functionEntries')
        keys_to_delete = set()
        for key, value in function_entries.items():
            for block in blocks_removed:
                value.discard(block._uuid)
            if len(value) == 0:
                keys_to_delete.add(key)

        for key in keys_to_delete:
            del function_entries[key]
            del function_blocks[key]


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


def block_addresses(ir):
    blocks = list()
    for module in ir._modules:
        blocks += [b._address for b in module._blocks
                   if hasattr(b, '_address')]
    return blocks
