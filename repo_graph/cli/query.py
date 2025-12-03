import typer
from repo_graph.graph.store import GraphStore

app=typer.Typer()

@app.command()
def depends(node: str):
    g=GraphStore.load('graph.pkl')
    for d in g.depends(node):
        print(d)

@app.command()
def used_by(node: str):
    g=GraphStore.load('graph.pkl')
    for u in g.used_by(node):
        print(u)
