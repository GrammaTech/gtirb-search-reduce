# Large parts copied from block_remove.py in the rewriting/gtirb-reduce repo

import argparse
import logging as log
import sys
import os
import pprint
from gtirb import *


def block_addresses(ir):
    blocks = list()
    for module in ir._modules:
        blocks += [b._address for b in module._blocks
                   if hasattr(b, '_address')]
    return blocks


def get_function_map(ir):
    """Returns a mapping from function (symbol) names to function UUIDs"""
    # Symbol Name -> Function UUID
    functions = dict()
    for module in ir.modules():
        # Function UUID -> set of entry block UUIDs
        function_entries = module.auxData('functionEntries')
        # Symbol Name -> Block UUID
        block_symbols = {s.name(): s.referent().uuid()
                          for s in module.symbols()
                          if isinstance(s.referent(), Block)}
        for symbol_name, block_uuid in block_symbols.items():
            for function_uuid, entry_block_uuids in function_entries.items():
                if block_uuid in entry_block_uuids:
                    functions[symbol_name] = function_uuid
                    break
    return functions


def get_function_block_addresses(function_name, functions, ir):
    """Returns the set of block addresses corresponding to the function
    with name function_name, given a mapping from function (symbol) names
    to function UUIDs"""
    log.debug(f"Getting blocks for function {function_name}")
    function_uuid = functions[function_name]
    # Block UUID -> Block Address
    block_uuid_map = dict()
    for module in ir.modules():
        block_uuid_map.update({b.uuid(): b.address() for b in module.blocks()
                               if hasattr(b, '_address')})

    function_block_uuids = set()
    for module in ir.modules():
        # Function UUID -> set of block UUIDs in the function
        function_blocks = module.auxData('functionBlocks')
        function_block_uuids.update(function_blocks.get(function_uuid))
    return {block_uuid_map[uuid] for uuid in function_block_uuids}


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
        log.debug("Building graph")
        for edge in cfg._edges:
            add_edge(graph, edge.source(), edge.target(), edge)

        # Using sets instead of a lists here greatly speeds up the
        # `if x in` checks
        edges_removed = set()
        blocks_removed = set()
        log.debug("Removing blocks "
                  f"{' '.join([f'{b:x}' for b in block_addresses])}")

        # Remove nodes from the graph, returned list of edges correspond to the
        # edges that must be deleted from the IR
        for b in block_addresses:
            if b not in blocks_by_addr:
                log.warning(f"No block with address {b:x} found")
                continue
            blocks_removed.add(blocks_by_addr[b])
            edges_removed.update(set(remove_node(graph, blocks_by_addr[b])))

        # if log.getLogger().isEnabledFor(log.DEBUG):
        #     for edge_removed in edges_removed:
        #         source = edge_removed.source()
        #         s_addr = source._address
        #         target = edge_removed.target()
        #         if isinstance(target, ProxyBlock):
        #             continue
        #         t_addr = target._address
        #         if (target in blocks_removed and source not in blocks_removed):
        #             log.debug(f"{t_addr:x} removed,"
        #                       f" but {s_addr:x} references it")
        #         log.debug(f"removed edge {s_addr:x} -> {t_addr:x}")

        # Collects the symbols that refer to removed blocks so the symbols can
        # also be removed
        log.debug("Collecting symbols to remove")
        symbols_to_remove = list()
        for symbol in module.symbols():
            block = symbol.referent()
            if isinstance(block, Block) and block in blocks_removed:
                symbols_to_remove.append(symbol)

        log.debug("Removing symbols")
        for symbol in symbols_to_remove:
            module._symbols.remove(symbol)

        # Remove symbol references to the block addresses and replace them with
        # a call to the trampoline symbol
        log.debug("Pointing stale references to trampoline")
        keys_to_delete = set()
        for key, op in module._symbolic_operands.items():
            try:
                if (isinstance(op, SymAddrConst) and
                    op.symbol().referent() in blocks_removed):
                    op.setSymbol(extern_trampoline)
                elif (isinstance(op, SymAddrAddr) and
                      (op._symbol1.referent() in blocks_removed or
                       op._symbol2.referent() in blocks_removed)):
                    keys_to_delete.add(key)
            except Exception:
                pass
        for key in keys_to_delete:
            del module._symbolic_operands[key]

        log.debug("Deleting blocks from GTIRB")
        module.removeBlocks(blocks_removed)
        log.debug("Deleting edges from GTIRB CFG")
        cfg.removeEdges(edges_removed)
        log.debug("Deleting functionBlock info from AuxData")
        uuids = {b._uuid for b in blocks_removed}
        function_blocks = module.auxData('functionBlocks')
        for value in function_blocks.values():
            value.difference_update(uuids)
        log.debug("Deleting functionEntries info from AuxData")
        function_entries = module.auxData('functionEntries')
        keys_to_delete = set()
        for key, value in function_entries.items():
            value.difference_update(uuids)
            if len(value) == 0:
                keys_to_delete.add(key)

        for key in keys_to_delete:
            del function_entries[key]
            del function_blocks[key]


def remove_functions(ir, factory, function_names=list()):
    """Takes a list of function names and deletes them"""
    delete_blocks = set()
    functions = get_function_map(ir)
    for f in function_names:
        delete_blocks.update(
            get_function_block_addresses(
                function_name=f,
                functions=functions,
                ir=ir
            )
        )
    remove_blocks(ir, factory, delete_blocks)
