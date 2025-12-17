from rdflib import URIRef, BNode, Graph, RDF, Literal
import re
import os

from dsi2dsio.src import update_prefixes


def split_iri(iri_str):
    """Return (namespace, local) for an IRI string. Keeps the separator (# or /) in namespace."""
    s = str(iri_str)
    if "#" in s:
        ns, local = s.split("#", 1)
        return ns + "#", local
    parts = s.rstrip("/").rsplit("/", 1)
    if len(parts) == 2:
        return parts[0] + "/", parts[1]
    # fallback: no separator
    return s, ""


def normalize_local(local):
    """Case-insensitive normalization for comparison. Use .casefold() for robust folding."""
    return local.casefold() if local is not None else local


def extract_signature_normalized(graph: Graph):
    """
    Produce a normalized signature:
      - classes: set of (namespace, normalized_local)
      - properties: set of (namespace, normalized_local)
      - objects: set of (namespace, normalized_local)
      - literals: set of (value, datatype_str_or_None)
    """
    classes = set()
    properties = set()
    objects = set()
    literals = set()

    for s, p, o in graph:
        # properties: normalize property IRI local-name (keep ns + normalized local)
        p_ns, p_local = split_iri(p)
        properties.add((p_ns, normalize_local(p_local)))

        # classes: rdf:type objects that are URIs
        if p == RDF.type and isinstance(o, URIRef):
            o_ns, o_local = split_iri(o)
            classes.add((o_ns, normalize_local(o_local)))

        # object URIs (excluding rdf:type) normalized
        if isinstance(o, URIRef) and p != RDF.type:
            o_ns, o_local = split_iri(o)
            objects.add((o_ns, normalize_local(o_local)))

        # literals (value, datatype)
        if isinstance(o, Literal):
            literals.add((str(o), str(o.datatype) if o.datatype else None))

    return {
        "classes": classes,
        "properties": properties,
        "objects": objects,
        "literals": literals,
    }


def pretty_diff(sig1, sig2):
    """Return string describing differences for each section."""
    out_lines = []
    for key in ("classes", "properties", "objects", "literals"):
        a = sig1[key]
        b = sig2[key]
        only_a = a - b
        only_b = b - a
        if only_a or only_b:
            out_lines.append(f"--- {key} ---")
            if only_a:
                out_lines.append("Only in graph A (transformed):")
                for item in sorted(only_a):
                    out_lines.append(f"  {item}")
            if only_b:
                out_lines.append("Only in graph B (expected):")
                for item in sorted(only_b):
                    out_lines.append(f"  {item}")
    return "\n".join(out_lines)


# Function to normalize UUIDs in an RDF graph
def normalize_uuids(graph, uuid_pattern):
    """Replace UUIDs with consistent placeholders."""
    uuid_mapping = {}
    new_graph = update_prefixes(Graph())
    for subj, pred, obj in graph:
        if isinstance(subj, URIRef) and re.match(uuid_pattern, str(subj)):
            if str(subj) not in uuid_mapping:
                uuid_mapping[str(subj)] = BNode()
            subj = uuid_mapping[str(subj)]
        if isinstance(obj, URIRef) and re.match(uuid_pattern, str(obj)):
            if str(obj) not in uuid_mapping:
                uuid_mapping[str(obj)] = BNode()
            obj = uuid_mapping[str(obj)]
        new_graph.add((subj, pred, obj))
    return new_graph


# Get all files in the directory
def get_files_from_directory(directory):
    return [
        os.path.join(directory, file)
        for file in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, file))
    ]


# Helper function to collect input and output file pairs
def get_file_pairs(input_dir, output_dir):
    input_files = [
        f for f in os.listdir(input_dir)
        if f.endswith(".xml") and os.path.isfile(os.path.join(input_dir, f))
    ]
    file_pairs = []
    for input_file in input_files:
        input_path = os.path.join(input_dir, input_file)
        # Replace the .xml extension with .ttl for the output file
        output_file = input_file.replace(".xml", ".ttl")
        output_path = os.path.join(output_dir, output_file)
        if os.path.isfile(output_path):  # Ensure a matching output file exists
            file_pairs.append((input_path, output_path))
    return file_pairs
