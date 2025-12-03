import typer
from repo_graph.cli.build import app as build_app
from repo_graph.cli.query import app as query_app

app=typer.Typer()
app.add_typer(build_app, name="build")
app.add_typer(query_app, name="query")

if __name__=='__main__':
    app()
