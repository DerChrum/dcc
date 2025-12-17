import rdflib
from rdflib.namespace import RDF, RDFS, OWL
from rdflib import BNode
from rdflib.collection import Collection
from pathlib import Path
import os
import json

# Configure your ontology base IRI
BASE_IRI = "https://ptb.de/sis/"


# Load prefixes from config file
def load_prefixes(config_file="config/prefixes.json"):
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


prefixes = load_prefixes()


def is_local_term(uri):
    """Return True if uri is a named IRI in the ontology namespace."""
    return isinstance(uri, rdflib.URIRef) and str(uri).startswith(BASE_IRI)


def get_prefix(url):
    match = max(
        ((p, u) for p, u in prefixes.items() if url.startswith(u)),
        key=lambda x: len(x[1]),
        default=(None, None)
    )
    return match[0]  # just return the prefix


def is_uri(s: str) -> bool:
    return s.startswith(("http://", "https://"))


def get_identifier(iri: str) -> str:
    if "#" in iri:
        return iri.split("#")[-1]
    else:
        return iri.split("/")[-1]


def shorten_IRI(iri):
    identifier = get_identifier(iri)
    prefix = get_prefix(iri)
    return f'{prefix}:{identifier}'


def linkify(uri):
    """Make HTML link for local or external IRI."""
    short_IRI = shorten_IRI(uri)
    if is_local_term(uri):
        return f'<a href="{os.path.basename(str(uri))}">{short_IRI}</a>'
    else:
        return f'<a href="{uri}">{short_IRI}</a>'


def get_restrictions(graph, cls):
    """Return property restrictions (with cardinalities) for a given class."""
    restrictions = []
    for _, _, restriction in graph.triples((cls, RDFS.subClassOf, None)):
        if (restriction, RDF.type, OWL.Restriction) in graph:
            prop = graph.value(restriction, OWL.onProperty)
            minc = graph.value(restriction, OWL.minQualifiedCardinality)
            maxc = graph.value(restriction, OWL.maxQualifiedCardinality)
            card = graph.value(restriction, OWL.cardinality)
            qcard = graph.value(restriction, OWL.qualifiedCardinality)
            onclass = graph.value(restriction, OWL.onClass)
            ondata = graph.value(restriction, OWL.onDataRange)

            restrictions.append({
                "property": prop,
                "min": minc,
                "max": maxc,
                "card": card,
                "qcard": qcard,
                "onclass": onclass,
                "ondata": ondata
            })
    return restrictions


def get_domains(graph, prop):
    domains = []
    for d in graph.objects(prop, RDFS.domain):
        if isinstance(d, BNode):
            # check if it's an owl:unionOf
            for union_list in graph.objects(d, OWL.unionOf):
                collection = Collection(graph, union_list)
                domains.extend(collection)  # add all members of union
        else:
            domains.append(d)
    return list(domains)


def get_type(graph, term):
    if (term, RDF.type, OWL.ObjectProperty) in graph:
        return OWL.ObjectProperty
    elif (term, RDF.type, OWL.DatatypeProperty) in graph:
        return OWL.DatatypeProperty
    elif (term, RDF.type, OWL.Class) in graph:
        return OWL.Class
    else:
        return None


def generate_WIDOCO_IRI(iri):
    if '#' in iri:
        return iri
    else:
        return f"index.html#{iri.rpartition('/')[2]}"


def generate_html_for_term(graph, term, output_dir):
    labels = list(graph.objects(term, RDFS.label))
    annotations = [(p, o) for p, o in graph.predicate_objects(term)
                   if p not in (RDFS.subClassOf, RDFS.subPropertyOf, RDF.type,
                                RDFS.domain, RDFS.range, OWL.equivalentClass)]

    superclasses = list(graph.objects(term, RDFS.subClassOf))
    subclasses = list(graph.subjects(RDFS.subClassOf, term))
    superproperties = list(graph.objects(term, RDFS.subPropertyOf))
    subproperties = list(graph.subjects(RDFS.subPropertyOf, term))
    type = get_type(graph, term)

    # Object property and datatype property connections
    object_property_links = []
    datatype_property_links = []
    if (term, RDF.type, OWL.Class) in graph:
        for p, domain in graph.subject_objects(RDFS.domain):
            # Case 1: direct domain match
            if domain == term:
                if (p, RDF.type, OWL.ObjectProperty) in graph:
                    ranges = list(graph.objects(p, RDFS.range))
                    object_property_links.append((p, ranges))
                if (p, RDF.type, OWL.DatatypeProperty) in graph:
                    ranges = list(graph.objects(p, RDFS.range))
                    datatype_property_links.append((p, ranges))

            # Case 2: union domain
            elif (domain, RDF.type, OWL.Class) in graph:
                union = list(graph.objects(domain, OWL.unionOf))
                if union:
                    members = list(Collection(graph, union[0]))
                    if term in members:
                        if (p, RDF.type, OWL.ObjectProperty) in graph:
                            ranges = list(graph.objects(p, RDFS.range))
                            object_property_links.append((p, ranges))
                        if (p, RDF.type, OWL.DatatypeProperty) in graph:
                            ranges = list(graph.objects(p, RDFS.range))
                            datatype_property_links.append((p, ranges))

    domains = []
    ranges = []
    if (term, RDF.type, OWL.ObjectProperty) in graph or (term, RDF.type, OWL.DatatypeProperty) in graph:
        domains.extend(get_domains(graph, term))
        ranges.extend(list(graph.objects(term, RDFS.range)))

    # Restrictions (cardinality info)
    restrictions = get_restrictions(graph, term)

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{shorten_IRI(term)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 900px; margin: auto; }}
    h1 {{ border-bottom: 1px solid #ccc; padding-bottom: 0.2em; }}
    ul {{ list-style: none; padding-left: 0; }}
    li {{ margin: 0.2em 0; }}
    td {{ padding: 0px; }}
    a {{ text-decoration: none; color: blue; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>{shorten_IRI(term)}</h1>
  <table style='width: 100%;'><tr><td><strong>IRI:</strong> <a href="{term}">{term}</a></td>
  """
    if type:
        html += f"<td style='float: right;'><strong>Type:</strong> {linkify(type)}</td>"
    html += "</table>"

    if annotations:
        html += "<h3>Annotations</h3><table>"
        for p, o in annotations:
            html += (f"<tr><td style='vertical-align: top;'><div style='margin-bottom:10px;'>{linkify(p)}</div>"
                     f"</td><td><div style='margin-left:50px; margin-bottom:10px;'>{o}</div></td></tr>")
        html += "</table>"

    if domains:
        html += "<h3>Domain</h3><ul>"
        for domain in domains:
            html += f"<li>{linkify(domain)}</li>"
        html += "</ul>"

    if ranges:
        html += "<h3>Range</h3><ul>"
        for r in ranges:
            html += f"<li>{linkify(r)}</li>"
        html += "</ul>"

    if subclasses:
        html += "<h3>Subclasses</h3><ul>"
        for sc in subclasses:
            html += f"<li>{linkify(sc)}</li>"
        html += "</ul>"

    if superclasses:
        html += "<h3>Superclasses</h3><ul>"
        for sc in superclasses:
            if is_local_term(sc):
                html += f"<li>{linkify(sc)}</li>"
        html += "</ul>"

    if subproperties:
        html += "<h3>Subproperties</h3><ul>"
        for sp in subproperties:
            html += f"<li>{linkify(sp)}</li>"
        html += "</ul>"

    if superproperties:
        html += "<h3>Superproperties</h3><ul>"
        for sp in superproperties:
            html += f"<li>{linkify(sp)}</li>"
        html += "</ul>"

    if object_property_links:
        html += "<h3>Object Properties</h3><ul>"
        for prop, ranges in object_property_links:
            html += f"<li>{linkify(prop)}"
            if ranges:
                html += " → " + ", ".join(linkify(r) for r in ranges)
            html += "</li>"
        html += "</ul>"

    if datatype_property_links:
        html += "<h3>Datatype Properties</h3><ul>"
        for prop, ranges in datatype_property_links:
            html += f"<li>{linkify(prop)}"
            if ranges:
                html += " → " + ", ".join(linkify(r) for r in ranges)
            html += "</li>"
        html += "</ul>"

    if restrictions:
        html += "<h3>Property Restrictions</h3><ul>"
        for r in restrictions:
            prop = linkify(r["property"])
            if r["onclass"]:
                target = linkify(r["onclass"])
            elif r["ondata"]:
                target = linkify(r["ondata"])
            else:
                target = ""
            cardinfo = []
            if r["min"]:
                cardinfo.append(f"min {r['min']}")
            if r["max"]:
                cardinfo.append(f"max {r['max']}")
            if r["card"]:
                cardinfo.append(f"exactly {r['card']}")
            if r["qcard"]:
                cardinfo.append(f"qualified exactly {r['qcard']}")
            cardtext = ", ".join(cardinfo) if cardinfo else ""
            html += f"<li>`{prop}`  <span style='font-family: monospace;'>{cardtext}</span>  `{target}`</li>"
        html += "</ul>"

    html += "<div style='border-top: 1px solid #ccc; padding-top: 1em; padding-bottom: 1em;'>"
    html += "<table style='width: 100%;'><tr>"
    html += f"<td>Explore term in <a href='{generate_WIDOCO_IRI(term)}'>WIDOCO</a></td>"
    html += f"<td style='float: right'>View as: <a href='{get_identifier(term)}.ttl'>TURTLE</a></td>"
    html += "</tr></table></div>"

    html += "</body></html>"

    # Save to file
    filename = os.path.basename(str(term)) + ".html"
    (output_dir / filename).write_text(html, encoding="utf-8")


def generate_docs(ontology_file, output_dir="terms"):
    g = rdflib.Graph()
    g.parse(ontology_file, format="turtle")

    out_path = Path(output_dir)
    out_path.mkdir(exist_ok=True)

    for term in set(g.subjects()) | set(g.objects()):
        if is_local_term(term):
            generate_html_for_term(g, term, out_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("ontology", help="Ontology Turtle file")
    parser.add_argument("--out", default="terms", help="Output directory")
    args = parser.parse_args()

    generate_docs(args.ontology, args.out)