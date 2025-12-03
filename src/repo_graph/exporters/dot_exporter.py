def export_to_dot(g, out_path: str):
    try:
        from networkx.drawing.nx_agraph import write_dot
    except Exception as e:
        raise RuntimeError('pygraphviz/agraph required to export dot') from e
    write_dot(g, out_path)
