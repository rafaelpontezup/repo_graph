import networkx as nx
import pickle
import os

class GraphStore:
    def __init__(self):
        self.g=nx.DiGraph()

    def merge(self,other):
        self.g.update(other)

    def save(self,path):
        with open(path,'wb') as f: pickle.dump(self.g,f)

    @staticmethod
    def load(path):
        gs=GraphStore()
        gs.g=pickle.load(open(path,'rb'))
        return gs

    def depends(self,node):
        return list(self.g.successors(node))

    def used_by(self,node):
        return list(self.g.predecessors(node))
