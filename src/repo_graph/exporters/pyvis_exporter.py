from pyvis.network import Network
def export_to_pyvis(g, out_html: str):
    net = Network(directed=True, notebook=False, height='800px', width='100%')
    for n, data in g.nodes(data=True):
        label = n
        title = str(data)
        net.add_node(n, label=label, title=title)
    for u, v, data in g.edges(data=True):
        title = data.get('type')
        net.add_edge(u, v, title=title)
    net.show(out_html)
