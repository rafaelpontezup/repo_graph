import typer
import os
from repo_graph.parsers.python import PythonParser
from repo_graph.parsers.java import JavaParser
from repo_graph.graph.store import GraphStore

app=typer.Typer()

@app.command()
def repo(path: str):
    g=GraphStore()
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith('.py'):
                g.merge(PythonParser().parse_file(os.path.join(root,f)))
            elif f.endswith('.java'):
                g.merge(JavaParser().parse_file(os.path.join(root,f)))
    g.save('graph.pkl')
    typer.echo('Graph built: graph.pkl')
