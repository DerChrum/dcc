from rdflib import Graph, URIRef
import os
import sys
from urllib.parse import urlparse

def iri_to_filename(iri: str) -> str:
    """
    Convert an IRI to a safe filename.
    Works with slash- or hash-separated ontologies.
    """
    parsed = urlparse(iri)

    # Handle hash IRIs (e.g., ...#QuantityValue)
    if "#" in iri:
        filename = iri.split("#")[-1]
    else:
        filename = os.path.basename(parsed.path)

    if not filename:
        filename = "ontology"

    filename = filename.replace(":", "_")
    return filename

def split_ttl(input_file, output_dir, base_uri="https://ptb.de/sis/"):
    g = Graph()
    g.parse(input_file, format="turtle", encoding="utf-8")

    os.makedirs(output_dir, exist_ok=True)

    # Collect only terms inside the ontology base URI
    terms = set()
    for s, p, o in g:
        if isinstance(s, URIRef) and str(s).startswith(base_uri):
            terms.add(s)
        if isinstance(o, URIRef) and str(o).startswith(base_uri):
            terms.add(o)

    print(f"Found {len(terms)} terms in namespace {base_uri}")

    for term in terms:
        subg = Graph()

        # Add all triples where the term is subject or object
        for s, p, o in g.triples((term, None, None)):
            subg.add((s, p, o))
        for s, p, o in g.triples((None, None, term)):
            subg.add((s, p, o))

        if len(subg) == 0:
            continue

        filename = iri_to_filename(str(term))
        outfile = os.path.join(output_dir, f"{filename}.ttl")
        subg.serialize(outfile, format="turtle")
        print(f"✅ Wrote {outfile} with {len(subg)} triples")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_per_term_ttls.py ontology.ttl output_dir")
        sys.exit(1)

    split_ttl(sys.argv[1], sys.argv[2])