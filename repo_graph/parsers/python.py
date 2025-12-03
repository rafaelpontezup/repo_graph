from tree_sitter import Language, Parser
import networkx as nx
import os

# NOTE: user must build language lib manually
# LANG_PATH = 'build/my-languages.so'
import tree_sitter_python as tspython
LANG = Language(tspython.language())

class PythonParser:
    def __init__(self):
        self.parser=Parser(LANG)
        # self.parser.set_language(LANG)

    def parse_file(self,path):
        code=open(path,'rb').read()
        tree=self.parser.parse(code)
        g=nx.DiGraph()
        root=tree.root_node
        # Simplest: collect function defs
        for n in root.children:
            if n.type=='function_definition':
                name=code[n.child_by_field_name('name').start_byte:n.child_by_field_name('name').end_byte].decode()
                g.add_node(name, type='function')
        return g
