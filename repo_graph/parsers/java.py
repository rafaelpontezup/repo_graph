from tree_sitter import Language, Parser
import networkx as nx
import tree_sitter_java as tsjava
# LANG_PATH='build/my-languages.so'
LANG=Language(tsjava.language())

class JavaParser:
    def __init__(self):
        self.parser=Parser(LANG)
        # self.parser.set_language(LANG)

    def parse_file(self,path):
        code=open(path,'rb').read()
        tree=self.parser.parse(code)
        g=nx.DiGraph()
        # placeholder
        return g
