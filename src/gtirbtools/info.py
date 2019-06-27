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
