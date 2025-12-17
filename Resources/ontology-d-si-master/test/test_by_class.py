from test.util.util import get_file_pairs, normalize_uuids, extract_signature_normalized, pretty_diff
import pytest

from shacl import validate_shacl
from dsi2dsio.DSI2DSIO import create_ontology_instances
from rdflib import Graph

"""
    Tests if the mapping function from XML to the ontology
    creates the expected instances of the classes
"""

xml_ttl_file_pairs = get_file_pairs("test/XML", "test/TTL")


@pytest.mark.parametrize("file_pair", xml_ttl_file_pairs, ids=[f"Test-{pair[0]}" for pair in xml_ttl_file_pairs])
def test_xml2ttl(file_pair):
    with (open(file_pair[0], "r", encoding="utf8") as xml_file,
          open(file_pair[1], "r", encoding="utf8") as ttl_file):
        instances_graph_from_xml = create_ontology_instances(xml_file.read())
        instances_graph_from_ttl = Graph()
        instances_graph_from_ttl.parse(data=ttl_file.read(), format="turtle")

        uuid_pattern = r"http://example\.org/[0-9a-fA-F\-]+"

        # Normalize both graphs
        normalized_graph1 = normalize_uuids(instances_graph_from_xml, uuid_pattern)
        normalized_graph2 = normalize_uuids(instances_graph_from_ttl, uuid_pattern)

        # Extract simplified signature of graphs
        sig1 = extract_signature_normalized(normalized_graph1)
        sig2 = extract_signature_normalized(normalized_graph2)

        debug_output = f"""
        Transformed XML element:
        {normalized_graph1.serialize(format="turtle")}
        Expected instance of the ontology class:
        {normalized_graph2.serialize(format="turtle")}
            """

        # Check if normalized graphs are isomorphic
        assert normalized_graph1.isomorphic(normalized_graph2), \
            (f"The element in {file_pair[0]} has not been transformed"
             f"correctly to an instance of the ontology class.\n{debug_output}")
        # Compare normalized signatures
        if sig1 != sig2:
            diff = pretty_diff(sig1, sig2)
            debug = (
                f"Transformed:\n{normalized_graph1.serialize(format='turtle')}\n\n"
                f"Expected:\n{normalized_graph2.serialize(format='turtle')}\n\n"
                f"Normalized diff:\n{diff}"
            )
            pytest.fail(f"Signature mismatch:\n{debug}")
        # Check if graph adheres to shacl shapes
        assert validate_shacl(instances_graph_from_xml, "shacl/shapes.ttl"), \
            f"The following instance does not conform to the SHACL constraints:\n{debug_output}"
