from rdflib import Graph
from pyshacl import validate


def validate_shacl(data_graph, shacl_file):
    # Load the OWL ontology instances file
    ontology_graph = Graph()
    ontology_graph.parse("SI_Format.ttl", format="turtle")

    # Combine the graphs
    combined_graph = Graph()
    combined_graph += ontology_graph
    combined_graph += data_graph

    # Load the SHACL constraints file
    shacl_graph = Graph()
    shacl_graph.parse(shacl_file, format="turtle")  # Adjust format if necessary

    # Validate the ontology instances against the SHACL constraints
    conforms, results_graph, results_text = validate(
        combined_graph,
        shacl_graph=shacl_graph,
        inference='rdfs',  # Optionally add inference, e.g., 'rdfs' or 'owlrl' for OWL reasoning
        abort_on_first=False,
        meta_shacl=False,
        debug=False
    )

    # Output the results
    print("Conforms:", conforms)
    print("Results Text:")
    print(results_text)

    return conforms
