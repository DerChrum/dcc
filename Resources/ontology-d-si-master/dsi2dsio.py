import argparse

from dsi2dsio import create_ontology_instances


def dsi2dsio(xml_file, instances_file):
    # Generate instances graph
    with open(xml_file, "r", encoding="utf8") as f:
        instances_graph = create_ontology_instances(f.read())
        print(instances_graph.serialize(format="turtle"))

    # Save the updated ontology
    with open(instances_file, "w", encoding="utf8") as f:
        f.write(instances_graph.serialize(format="turtle"))


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Convert XML data to ontology instances.")
    parser.add_argument(
        "--xml", type=str, required=True, help="Path to the input XML file."
    )
    parser.add_argument(
        "--output", type=str, required=True, help="Path to save the output TTL file."
    )
    args = parser.parse_args()

    # Run the conversion
    dsi2dsio(args.xml, args.output)
