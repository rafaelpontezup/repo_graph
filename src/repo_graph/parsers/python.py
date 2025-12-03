from tree_sitter import Language, Parser
import networkx as nx
from pathlib import Path
import os

LANG_PATH = os.environ.get('TREE_SITTER_LANG_SO', str(Path.cwd() / 'build' / 'my-languages.so'))
PY_LANG = Language(LANG_PATH, 'python')

class PythonParser:
    def __init__(self):
        self.parser = Parser()
        self.parser.set_language(PY_LANG)

    def parse_file(self, path):
        code = Path(path).read_bytes()
        tree = self.parser.parse(code)
        root = tree.root_node
        g = nx.DiGraph()
        file_node = f"file:{Path(path)}"
        g.add_node(file_node, type='file', path=str(path))

        # collect imports, classes, functions, and calls (naive)
        cursor = root.walk()
        stack = [root]
        while stack:
            node = stack.pop()
            for child in reversed(node.children):
                stack.append(child)
            # imports
            if node.type == 'import_statement' or node.type == 'import_from_statement':
                # extract dotted names
                text = code[node.start_byte:node.end_byte].decode('utf8')
                # naive splitting
                for line in text.split('\n'):
                    line = line.strip()
                    if line.startswith('import '):
                        parts = line[len('import '):].split(',')
                        for p in parts:
                            name = p.strip().split(' as ')[0]
                            if name:
                                mod_node = f"module:{name}"
                                g.add_node(mod_node, type='module', name=name)
                                g.add_edge(file_node, mod_node, type='imports')
                    if line.startswith('from '):
                        # from X import Y
                        parts = line.split()
                        if len(parts) >= 4 and parts[2] == 'import':
                            mod = parts[1]
                            mod_node = f"module:{mod}"
                            g.add_node(mod_node, type='module', name=mod)
                            g.add_edge(file_node, mod_node, type='imports')
            # class
            if node.type == 'class_definition':
                # identifier child
                name = None
                for c in node.children:
                    if c.type == 'identifier':
                        name = code[c.start_byte:c.end_byte].decode('utf8')
                        break
                if name:
                    class_node = f"{Path(path).stem}.{name}"
                    g.add_node(class_node, type='class', name=name, file=str(path))
                    g.add_edge(file_node, class_node, type='defines')
                    # methods inside
                    for member in node.children:
                        if member.type == 'block':
                            for stmt in member.children:
                                if stmt.type == 'function_definition':
                                    mname = None
                                    for cc in stmt.children:
                                        if cc.type == 'identifier':
                                            mname = code[cc.start_byte:cc.end_byte].decode('utf8')
                                            break
                                    if mname:
                                        method_node = f"{class_node}.{mname}"
                                        g.add_node(method_node, type='method', name=mname, file=str(path))
                                        g.add_edge(class_node, method_node, type='has_method')
                                        # search calls inside method
                                        for inner in stmt.walk():
                                            if inner.node.type == 'call':
                                                fn = inner.node.child_by_field_name('function')
                                                if fn is not None:
                                                    called = code[fn.start_byte:fn.end_byte].decode('utf8')
                                                    g.add_edge(method_node, f"call:{called}", type='calls')
            # free functions
            if node.type == 'function_definition' and node.parent.type != 'class_definition':
                name = None
                for c in node.children:
                    if c.type == 'identifier':
                        name = code[c.start_byte:c.end_byte].decode('utf8')
                        break
                if name:
                    func_node = f"{Path(path).stem}.{name}"
                    g.add_node(func_node, type='function', name=name, file=str(path))
                    g.add_edge(file_node, func_node, type='defines')
                    for inner in node.walk():
                        if inner.node.type == 'call':
                            fn = inner.node.child_by_field_name('function')
                            if fn is not None:
                                called = code[fn.start_byte:fn.end_byte].decode('utf8')
                                g.add_edge(func_node, f"call:{called}", type='calls')
        return g
