import argparse
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
import xml.etree.ElementTree as ET

from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, SKOS, XSD
from rdflib.compare import graph_diff, to_isomorphic

# Column order mirrors dcc_tabular_template.md
COLUMNS = [
    "id",
    "label",
    "entity_type",
    "dccx_alignment",
    "status",
    "replaced_by",
    "definition",
    "comment",
    "example",
    "source",
    "subclass_of",
    "equivalent_to",
    "disjoint_with",
    "on_property",
    "restriction_type",
    "restriction_filler",
    "cardinality_value",
    "property_domain",
    "property_range",
    "property_characteristic",
    "inverse_of",
    "annotation_predicate",
    "annotation_value",
]

CHARACTERISTIC_TYPES = {
    OWL.FunctionalProperty: "functional",
    OWL.InverseFunctionalProperty: "inverseFunctional",
    OWL.SymmetricProperty: "symmetric",
    OWL.AsymmetricProperty: "asymmetric",
    OWL.ReflexiveProperty: "reflexive",
    OWL.IrreflexiveProperty: "irreflexive",
    OWL.TransitiveProperty: "transitive",
}

PREFERRED_PREFIXES: Dict[str, str] = {
    "dcc": "https://ptb.de/dcc/ont/",
    "dccx": "https://ptb.de/dcc/",
    "sis": "https://ptb.de/sis/",
    "six": "https://ptb.de/si/",
    "omt": "http://www.nmdc.com/ontology/OMT#",
    "skos": str(SKOS),
    "owl": str(OWL),
    "rdfs": str(RDFS),
    "rdf": str(RDF),
    "xsd": str(XSD),
    "dcterms": "http://purl.org/dc/terms/",
    "prov": "http://www.w3.org/ns/prov#",
    "schema": "https://schema.org/",
    "vann": "http://purl.org/vocab/vann/",
}

DCTERMS_SOURCE = URIRef("http://purl.org/dc/terms/source")

ANNOTATION_COLUMN_MAP: Dict[URIRef, str] = {
    SKOS.prefLabel: "label",
    RDFS.label: "label",
    SKOS.definition: "definition",
    RDFS.comment: "comment",
    SKOS.example: "example",
    DCTERMS_SOURCE: "source",
}

FORCE_LITERAL_PREDICATES: Set[URIRef] = {
    URIRef("http://purl.org/vocab/vann/preferredNamespaceUri"),
}


def _bind_prefixes(graph: Graph) -> None:
    for prefix, uri in PREFERRED_PREFIXES.items():
        graph.bind(prefix, Namespace(uri))


def _preferred_literal(graph: Graph, subject: URIRef, predicate: URIRef) -> Tuple[Optional[Literal], List[Literal]]:
    values = [v for v in graph.objects(subject, predicate) if isinstance(v, Literal)]
    if not values:
        return None, []
    preferred: Optional[Literal] = None
    leftovers: List[Literal] = []
    # prefer English label if present
    for lit in values:
        if lit.language == "en":
            preferred = lit
            leftovers = [l for l in values if l != lit]
            break
    if preferred is None:
        preferred = values[0]
        leftovers = [l for l in values[1:]]
    return preferred, leftovers


def _literal_to_text(value: Literal) -> str:
    if value.language:
        return f"{value}@{value.language}"
    if value.datatype:
        return f"{value}^^{value.datatype}"
    return str(value)


def _serialize_list(graph: Graph, node) -> Optional[str]:
    try:
        items = list(graph.items(node))
    except Exception:
        return None
    if not items:
        return None
    serialized_items: List[str] = []
    for item in items:
        if isinstance(item, Literal):
            serialized_items.append(_literal_to_text(item))
        else:
            serialized_items.append(str(item))
    return "|".join(serialized_items)


def _serialize_class_expression(graph: Graph, expr) -> Optional[str]:
    if isinstance(expr, URIRef):
        return str(expr)
    one_of = graph.value(expr, OWL.oneOf)
    if one_of:
        serialized = _serialize_list(graph, one_of)
        if serialized:
            return f"oneOf({serialized})"
    union = graph.value(expr, OWL.unionOf)
    if union:
        serialized = _serialize_list(graph, union)
        if serialized:
            return f"union({serialized})"
    return None


def _collect_from_expression(graph: Graph, expr) -> List:
    collected: List = []
    if (expr, RDF.type, OWL.Restriction) in graph:
        collected.append(expr)
    for lst in graph.objects(expr, OWL.intersectionOf):
        collected.extend(_collect_from_list(graph, lst))
    for lst in graph.objects(expr, OWL.unionOf):
        collected.extend(_collect_from_list(graph, lst))
    return collected


def _collect_from_list(graph: Graph, head) -> List:
    items: List = []
    try:
        for item in graph.items(head):
            items.extend(_collect_from_expression(graph, item))
    except Exception:
        return []
    return items


def _as_uri(value: str, graph: Graph) -> Optional[Union[URIRef, BNode]]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("_:"):
        return BNode(text[2:])
    if "@" in text or "^^" in text:
        return None
    if any(ch.isspace() for ch in text) and not (text.startswith("<") and text.endswith(">")):
        return None
    if text.startswith("<") and text.endswith(">"):
        return URIRef(text[1:-1])
    if "://" in text:
        return URIRef(text)
    if ":" in text:
        try:
            expanded = graph.namespace_manager.expand_curie(text, False, True)
        except Exception:
            expanded = None
        if isinstance(expanded, URIRef):
            return expanded
        return None
    return None


def _split_multivalue(cell: str) -> List[str]:
    if cell is None or str(cell).strip() == "":
        return []
    text = str(cell).strip()
    if text.startswith(("union(", "oneOf(")) and text.endswith(")"):
        return [text]
    delimiter = "|" if "|" in text else ","
    return [part.strip() for part in text.split(delimiter) if part.strip()]


def _entity_type(graph: Graph, entity: URIRef) -> str:
    types = set(graph.objects(entity, RDF.type))
    if OWL.Class in types:
        return "Class"
    if OWL.ObjectProperty in types:
        return "ObjectProperty"
    if OWL.DatatypeProperty in types:
        return "DataProperty"
    if OWL.AnnotationProperty in types:
        return "AnnotationProperty"
    if types:
        return "Individual"
    return "Individual"


def _restriction_rows(graph: Graph, restriction_nodes: List, base_row: Dict[str, str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for node in restriction_nodes:
        if (node, RDF.type, OWL.Restriction) not in graph:
            continue
        on_property = graph.value(node, OWL.onProperty)
        filler = graph.value(node, OWL.someValuesFrom) or graph.value(node, OWL.allValuesFrom)
        restriction_type = None
        if (node, OWL.someValuesFrom, filler) in graph:
            restriction_type = "some"
        elif (node, OWL.allValuesFrom, filler) in graph:
            restriction_type = "only"
        cardinality_value = None
        min_card = graph.value(node, OWL.minQualifiedCardinality)
        if min_card is None:
            min_card = graph.value(node, OWL.minCardinality)
        if min_card is not None:
            restriction_type = "min"
            cardinality_value = min_card
        max_card = graph.value(node, OWL.maxQualifiedCardinality)
        if max_card is None:
            max_card = graph.value(node, OWL.maxCardinality)
        if max_card is not None:
            restriction_type = "max"
            cardinality_value = max_card
        exact_card = graph.value(node, OWL.qualifiedCardinality)
        if exact_card is None:
            exact_card = graph.value(node, OWL.cardinality)
        if exact_card is not None:
            restriction_type = "exact"
            cardinality_value = exact_card
        if cardinality_value is not None and isinstance(cardinality_value, Literal):
            cardinality_value = _literal_to_text(cardinality_value)
        filler = filler or graph.value(node, OWL.onClass) or graph.value(node, OWL.onDataRange)
        restriction_row = base_row.copy()
        restriction_row.update(
            {
                "on_property": str(on_property) if on_property else "",
                "restriction_type": restriction_type or "",
                "restriction_filler": str(filler) if filler else "",
                "cardinality_value": cardinality_value or "",
            }
        )
        rows.append(restriction_row)
    return rows


def graph_to_table(graph: Graph) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    _bind_prefixes(graph)

    entities: Set = set()
    entities.update(s for s in graph.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef))
    entities.update(s for s in graph.subjects(RDF.type, OWL.ObjectProperty) if isinstance(s, URIRef))
    entities.update(s for s in graph.subjects(RDF.type, OWL.DatatypeProperty) if isinstance(s, URIRef))
    entities.update(s for s in graph.subjects(RDF.type, OWL.AnnotationProperty) if isinstance(s, URIRef))
    entities.update(s for s in graph.subjects(RDF.type, OWL.AllDisjointClasses))
    # include individuals and skolemized blank nodes that have outgoing triples
    for s in graph.subjects():
        if isinstance(s, URIRef) and s not in entities:
            entities.add(s)

    for entity in sorted(entities, key=lambda e: str(e)):
        base_row = {col: "" for col in COLUMNS}
        if isinstance(entity, BNode):
            base_row["id"] = f"_:{entity}"
        else:
            base_row["id"] = str(entity)
        entity_id = base_row["id"]
        base_row["entity_type"] = _entity_type(graph, entity)

        consumed_preds: Set[URIRef] = set()

        label_pred = None
        label, label_leftover = _preferred_literal(graph, entity, SKOS.prefLabel)
        if label or label_leftover:
            label_pred = SKOS.prefLabel
        else:
            label, label_leftover = _preferred_literal(graph, entity, RDFS.label)
            if label or label_leftover:
                label_pred = RDFS.label
        if label:
            base_row["label"] = _literal_to_text(label)
        if label_pred:
            consumed_preds.add(label_pred)

        dccx_alignment = graph.value(entity, SKOS.exactMatch)
        extra_alignments = [o for o in graph.objects(entity, SKOS.exactMatch) if o != dccx_alignment]
        if dccx_alignment:
            base_row["dccx_alignment"] = str(dccx_alignment)
            consumed_preds.add(SKOS.exactMatch)
        if extra_alignments:
            consumed_preds.add(SKOS.exactMatch)

        definition, def_leftover = _preferred_literal(graph, entity, SKOS.definition)
        if definition:
            base_row["definition"] = _literal_to_text(definition)
        if definition or def_leftover:
            consumed_preds.add(SKOS.definition)

        comment, comment_leftover = _preferred_literal(graph, entity, RDFS.comment)
        if comment:
            base_row["comment"] = _literal_to_text(comment)
        if comment or comment_leftover:
            consumed_preds.add(RDFS.comment)

        example, example_leftover = _preferred_literal(graph, entity, SKOS.example)
        if example:
            base_row["example"] = _literal_to_text(example)
        if example or example_leftover:
            consumed_preds.add(SKOS.example)

        source_objects = list(graph.objects(entity, DCTERMS_SOURCE))
        source, source_leftover = _preferred_literal(graph, entity, DCTERMS_SOURCE)
        if source:
            base_row["source"] = _literal_to_text(source)
        if source or source_leftover or source_objects:
            consumed_preds.add(DCTERMS_SOURCE)

        if base_row["entity_type"] == "Class":
            subclasses = [o for o in graph.objects(entity, RDFS.subClassOf) if isinstance(o, URIRef)]
            equivalents = [o for o in graph.objects(entity, OWL.equivalentClass) if isinstance(o, URIRef)]
            disjoints = [o for o in graph.objects(entity, OWL.disjointWith) if isinstance(o, URIRef)]
            restriction_nodes = []
            for expr in graph.objects(entity, RDFS.subClassOf):
                restriction_nodes.extend(_collect_from_expression(graph, expr))
            for expr in graph.objects(entity, OWL.equivalentClass):
                restriction_nodes.extend(_collect_from_expression(graph, expr))
            restriction_nodes = list(dict.fromkeys(restriction_nodes))
            if subclasses:
                base_row["subclass_of"] = "|".join(sorted(str(o) for o in subclasses))
            if equivalents:
                base_row["equivalent_to"] = "|".join(sorted(str(o) for o in equivalents))
            if disjoints:
                base_row["disjoint_with"] = "|".join(sorted(str(o) for o in disjoints))
            rows.append(base_row)
            rows.extend(_restriction_rows(graph, restriction_nodes, base_row))
        elif base_row["entity_type"] in {"ObjectProperty", "DataProperty"}:
            domains = [
                val
                for val in (
                    _serialize_class_expression(graph, o)
                    for o in graph.objects(entity, RDFS.domain)
                )
                if val
            ]
            ranges = [
                val
                for val in (
                    _serialize_class_expression(graph, o)
                    for o in graph.objects(entity, RDFS.range)
                )
                if val
            ]
            if domains:
                base_row["property_domain"] = "|".join(sorted(domains))
            if ranges:
                base_row["property_range"] = "|".join(sorted(ranges))
            chars: List[str] = []
            for t in graph.objects(entity, RDF.type):
                if t in CHARACTERISTIC_TYPES:
                    chars.append(CHARACTERISTIC_TYPES[t])
            if chars:
                base_row["property_characteristic"] = "|".join(sorted(set(chars)))
            inverse = graph.value(entity, OWL.inverseOf)
            if inverse:
                base_row["inverse_of"] = str(inverse)
            rows.append(base_row)
        else:
            rows.append(base_row)

        handled_preds = set(consumed_preds)
        structural_types = {
            OWL.Class,
            OWL.ObjectProperty,
            OWL.DatatypeProperty,
            OWL.AnnotationProperty,
            OWL.Restriction,
        }
        for lit in label_leftover:
            pred = label_pred or SKOS.prefLabel
            rows.append({**{col: "" for col in COLUMNS}, "id": entity_id, "annotation_predicate": str(pred), "annotation_value": _literal_to_text(lit)})
        for lit in def_leftover:
            rows.append({**{col: "" for col in COLUMNS}, "id": entity_id, "annotation_predicate": str(SKOS.definition), "annotation_value": _literal_to_text(lit)})
        for lit in comment_leftover:
            rows.append({**{col: "" for col in COLUMNS}, "id": entity_id, "annotation_predicate": str(RDFS.comment), "annotation_value": _literal_to_text(lit)})
        for lit in example_leftover:
            rows.append({**{col: "" for col in COLUMNS}, "id": entity_id, "annotation_predicate": str(SKOS.example), "annotation_value": _literal_to_text(lit)})
        for lit in source_leftover:
            rows.append({**{col: "" for col in COLUMNS}, "id": entity_id, "annotation_predicate": str(DCTERMS_SOURCE), "annotation_value": _literal_to_text(lit)})
        for aln in extra_alignments:
            value = _literal_to_text(aln) if isinstance(aln, Literal) else str(aln)
            rows.append({**{col: "" for col in COLUMNS}, "id": entity_id, "annotation_predicate": str(SKOS.exactMatch), "annotation_value": value})
        for obj in source_objects:
            if isinstance(obj, Literal):
                continue
            rows.append({**{col: "" for col in COLUMNS}, "id": entity_id, "annotation_predicate": str(DCTERMS_SOURCE), "annotation_value": str(obj)})

        for pred, obj in graph.predicate_objects(entity):
            if pred in handled_preds:
                continue
            if (entity, RDF.type, OWL.Restriction) in graph:
                continue
            if pred in {RDFS.subClassOf, OWL.equivalentClass, OWL.disjointWith, RDFS.domain, RDFS.range, OWL.inverseOf}:
                continue
            if pred == RDF.type and obj in structural_types:
                continue
            if pred in {OWL.unionOf, OWL.intersectionOf, OWL.members}:
                serialized = _serialize_list(graph, obj)
                if serialized is not None:
                    value = serialized
                else:
                    value = _literal_to_text(obj) if isinstance(obj, Literal) else str(obj)
            else:
                value = _literal_to_text(obj) if isinstance(obj, Literal) else str(obj)
            rows.append({**{col: "" for col in COLUMNS}, "id": entity_id, "annotation_predicate": str(pred), "annotation_value": value})

    return rows


def _literal_from_value(value: str) -> Literal:
    if value is None:
        return Literal("")
    text = str(value)
    if "^^" in text:
        lexical, datatype = text.rsplit("^^", 1)
        return Literal(lexical, datatype=URIRef(datatype))
    if "@" in text and not text.startswith("http"):
        lexical, lang = text.rsplit("@", 1)
        return Literal(lexical, lang=lang)
    return Literal(text)


def _expand_class_expression(value: str, graph: Graph, datatype_context: bool = False):
    if value is None:
        return None
    text = str(value).strip()
    if text.startswith("union(") and text.endswith(")"):
        members = _split_multivalue(text[len("union(") : -1])
        uris = []
        for part in members:
            uri_val = _as_uri(part, graph)
            uris.append(uri_val or _literal_from_value(part))
        if uris:
            node = BNode()
            graph.add((node, RDF.type, RDFS.Datatype if datatype_context else OWL.Class))
            head = BNode()
            Collection(graph, head, uris)
            graph.add((node, OWL.unionOf, head))
            return node
        return None
    if text.startswith("oneOf(") and text.endswith(")"):
        members = _split_multivalue(text[len("oneOf(") : -1])
        values = []
        for part in members:
            uri_val = _as_uri(part, graph)
            values.append(uri_val or _literal_from_value(part))
        if values:
            node = BNode()
            head = BNode()
            Collection(graph, head, values)
            graph.add((node, RDF.type, RDFS.Datatype if datatype_context else OWL.Class))
            graph.add((node, OWL.oneOf, head))
            return node
        return None
    return _as_uri(text, graph)


def table_to_graph(rows: List[Dict[str, str]]) -> Graph:
    graph = Graph()
    _bind_prefixes(graph)
    property_types: Dict[str, str] = {}
    for row in rows:
        subj = _as_uri(row.get("id"), graph)
        if subj:
            entity_type = (row.get("entity_type") or "").strip()
            if entity_type:
                property_types[str(subj)] = entity_type
    for row in rows:
        subj = _as_uri(row.get("id"), graph)
        if subj is None:
            continue
        entity_type = row.get("entity_type") or ""
        label = row.get("label")
        if label:
            label_predicate = (
                SKOS.prefLabel
                if entity_type in {"Class", "ObjectProperty", "DataProperty", "AnnotationProperty"}
                else RDFS.label
            )
            graph.add((subj, label_predicate, _literal_from_value(label)))
        dccx_alignment = row.get("dccx_alignment")
        if dccx_alignment:
            obj = _as_uri(dccx_alignment, graph)
            if obj:
                graph.add((subj, SKOS.exactMatch, obj))
        if row.get("definition"):
            graph.add((subj, SKOS.definition, _literal_from_value(row.get("definition"))))
        if row.get("comment"):
            graph.add((subj, RDFS.comment, _literal_from_value(row.get("comment"))))
        if row.get("example"):
            graph.add((subj, SKOS.example, _literal_from_value(row.get("example"))))
        if row.get("source"):
            graph.add((subj, DCTERMS_SOURCE, _literal_from_value(row.get("source"))))

        if row.get("annotation_predicate"):
            pred = _as_uri(row.get("annotation_predicate"), graph)
            if pred:
                val = row.get("annotation_value")
                if pred == OWL.members and val:
                    members = []
                    for part in _split_multivalue(val):
                        uri_val = _as_uri(part, graph)
                        members.append(uri_val or _literal_from_value(part))
                    if members:
                        head = BNode()
                        Collection(graph, head, members)
                        graph.add((subj, pred, head))
                    continue
                if pred in {OWL.unionOf, OWL.intersectionOf} and val:
                    members = []
                    for part in _split_multivalue(val):
                        uri_val = _as_uri(part, graph)
                        members.append(uri_val or _literal_from_value(part))
                    if members:
                        head = BNode()
                        Collection(graph, head, members)
                        graph.add((subj, pred, head))
                    continue
                obj_uri = _as_uri(val, graph) if pred not in FORCE_LITERAL_PREDICATES else None
                if obj_uri:
                    graph.add((subj, pred, obj_uri))
                else:
                    graph.add((subj, pred, _literal_from_value(val)))

        if entity_type == "Class":
            graph.add((subj, RDF.type, OWL.Class))
            for parent in _split_multivalue(row.get("subclass_of")):
                parent_uri = _as_uri(parent, graph)
                if parent_uri:
                    graph.add((subj, RDFS.subClassOf, parent_uri))
            for equiv in _split_multivalue(row.get("equivalent_to")):
                equiv_uri = _as_uri(equiv, graph)
                if equiv_uri:
                    graph.add((subj, OWL.equivalentClass, equiv_uri))
            for disjoint in _split_multivalue(row.get("disjoint_with")):
                disjoint_uri = _as_uri(disjoint, graph)
                if disjoint_uri:
                    graph.add((subj, OWL.disjointWith, disjoint_uri))
            if row.get("on_property"):
                restr = BNode()
                graph.add((restr, RDF.type, OWL.Restriction))
                on_prop = _as_uri(row.get("on_property"), graph)
                if on_prop:
                    graph.add((restr, OWL.onProperty, on_prop))
                prop_type = property_types.get(str(on_prop), "")
                restriction_type = (row.get("restriction_type") or "").strip()
                filler_value = _as_uri(row.get("restriction_filler"), graph)
                cardinality = row.get("cardinality_value")
                if restriction_type == "some" and filler_value:
                    predicate = OWL.someValuesFrom
                    if prop_type == "DataProperty":
                        predicate = OWL.someValuesFrom
                    graph.add((restr, predicate, filler_value))
                elif restriction_type == "only" and filler_value:
                    predicate = OWL.allValuesFrom
                    graph.add((restr, predicate, filler_value))
                elif restriction_type in {"min", "max", "exact"}:
                    card_literal = _literal_from_value(cardinality)
                    if restriction_type == "min":
                        graph.add((restr, OWL.minQualifiedCardinality, card_literal))
                    elif restriction_type == "max":
                        graph.add((restr, OWL.maxQualifiedCardinality, card_literal))
                    else:
                        graph.add((restr, OWL.qualifiedCardinality, card_literal))
                    if filler_value:
                        if prop_type == "DataProperty":
                            graph.add((restr, OWL.onDataRange, filler_value))
                        else:
                            graph.add((restr, OWL.onClass, filler_value))
                graph.add((subj, RDFS.subClassOf, restr))
        elif entity_type == "ObjectProperty":
            graph.add((subj, RDF.type, OWL.ObjectProperty))
        elif entity_type == "DataProperty":
            graph.add((subj, RDF.type, OWL.DatatypeProperty))
        elif entity_type == "AnnotationProperty":
            graph.add((subj, RDF.type, OWL.AnnotationProperty))

        if entity_type in {"ObjectProperty", "DataProperty"}:
            for domain in _split_multivalue(row.get("property_domain")):
                domain_uri = _expand_class_expression(domain, graph, datatype_context=entity_type == "DataProperty")
                if domain_uri:
                    graph.add((subj, RDFS.domain, domain_uri))
            for rng in _split_multivalue(row.get("property_range")):
                rng_uri = _expand_class_expression(rng, graph, datatype_context=entity_type == "DataProperty")
                if rng_uri:
                    graph.add((subj, RDFS.range, rng_uri))
            for char in _split_multivalue(row.get("property_characteristic")):
                for owl_type, label in CHARACTERISTIC_TYPES.items():
                    if label == char:
                        graph.add((subj, RDF.type, owl_type))
            if row.get("inverse_of"):
                inv = _as_uri(row.get("inverse_of"), graph)
                if inv:
                    graph.add((subj, OWL.inverseOf, inv))
    return graph


def _load_schema_terms(schema_path: Optional[Path]) -> Set[str]:
    if not schema_path:
        return set()
    schema_terms: Set[str] = set()
    try:
        tree = ET.parse(schema_path)
    except Exception:
        return set()
    root = tree.getroot()
    target_ns = root.attrib.get("targetNamespace", "").strip()
    if not target_ns:
        return set()
    base = target_ns if target_ns.endswith(("/", "#")) else f"{target_ns}/"
    for elem in root.iter():
        name = elem.attrib.get("name")
        if name:
            schema_terms.add(f"{base}{name}")
    return schema_terms


def _alignment_coverage(graph: Graph, schema_terms: Set[str]) -> Tuple[int, int, int]:
    if not schema_terms:
        return 0, 0, 0
    aligned_values = {str(obj) for obj in graph.objects(None, SKOS.exactMatch) if isinstance(obj, URIRef)}
    matched = {uri for uri in aligned_values if uri in schema_terms}
    missing = aligned_values - schema_terms
    return len(aligned_values), len(matched), len(missing)


def _entity_category(graph: Graph, subj: URIRef) -> str:
    if (subj, RDF.type, OWL.Class) in graph:
        return "Class"
    if (subj, RDF.type, OWL.ObjectProperty) in graph:
        return "ObjectProperty"
    if (subj, RDF.type, OWL.DatatypeProperty) in graph:
        return "DataProperty"
    if (subj, RDF.type, OWL.AnnotationProperty) in graph:
        return "AnnotationProperty"
    return "Unknown"


def _as_display(value: Union[URIRef, BNode], graph: Graph) -> str:
    try:
        return graph.namespace_manager.normalizeUri(value)
    except Exception:
        return str(value)


def _sample_list(items: List[str], limit: int = 10) -> List[str]:
    if len(items) <= limit:
        return items
    return items[:limit]


@dataclass
class RoundTripReport:
    source_triples: int
    reconstructed_triples: int
    overlap_triples: int
    missing_from_roundtrip: int
    extra_in_roundtrip: int
    source_alignments: int = 0
    source_alignments_in_schema: int = 0
    source_alignments_missing_schema: int = 0
    roundtrip_alignments: int = 0
    roundtrip_alignments_in_schema: int = 0
    roundtrip_alignments_missing_schema: int = 0
    identical: bool = field(init=False)

    def __post_init__(self) -> None:
        self.identical = self.missing_from_roundtrip == 0 and self.extra_in_roundtrip == 0


@dataclass
class AlignmentReport:
    total_alignments: int
    alignments_in_schema: int
    alignments_missing_schema: int
    schema_without_alignment: int
    per_type: Dict[str, int]
    per_type_in_schema: Dict[str, int]
    missing_examples: List[str] = field(default_factory=list)
    schema_without_examples: List[str] = field(default_factory=list)


@dataclass
class LabelLanguageReport:
    total_with_labels: int
    english_pref_missing: List[str]
    german_pref: List[str]
    german_pref_without_alt: List[str]
    other_non_english_pref: List[str]


def _alignment_report(graph: Graph, schema_terms: Set[str], sample_limit: int = 10) -> AlignmentReport:
    alignments: List[Tuple[URIRef, URIRef, str]] = []
    for subj, obj in graph.subject_objects(SKOS.exactMatch):
        if not isinstance(obj, URIRef):
            continue
        alignments.append((subj, obj, _entity_category(graph, subj)))

    target_values = {str(obj) for _, obj, _ in alignments}
    matched = target_values & schema_terms
    missing = target_values - schema_terms
    schema_without_alignment = schema_terms - target_values if schema_terms else set()

    per_type: Dict[str, int] = {}
    per_type_in_schema: Dict[str, int] = {}
    for _, obj, entity_type in alignments:
        per_type[entity_type] = per_type.get(entity_type, 0) + 1
        if str(obj) in schema_terms:
            per_type_in_schema[entity_type] = per_type_in_schema.get(entity_type, 0) + 1

    missing_examples = _sample_list(sorted(missing), sample_limit)
    schema_without_examples = _sample_list(sorted(schema_without_alignment), sample_limit)

    return AlignmentReport(
        total_alignments=len(alignments),
        alignments_in_schema=len(matched),
        alignments_missing_schema=len(missing),
        schema_without_alignment=len(schema_without_alignment),
        per_type=per_type,
        per_type_in_schema=per_type_in_schema,
        missing_examples=missing_examples,
        schema_without_examples=schema_without_examples,
    )


def _label_language_report(graph: Graph, sample_limit: int = 10) -> LabelLanguageReport:
    english_pref_missing: List[str] = []
    german_pref: List[str] = []
    german_pref_without_alt: List[str] = []
    other_non_english_pref: List[str] = []
    seen_subjects: Set[URIRef] = set()

    for predicate in (SKOS.prefLabel, RDFS.label):
        seen_subjects.update({s for s in graph.subjects(predicate=predicate) if isinstance(s, (URIRef, BNode))})

    for subj in seen_subjects:
        prefs = [
            lit
            for predicate in (SKOS.prefLabel, RDFS.label)
            for lit in graph.objects(subj, predicate)
            if isinstance(lit, Literal)
        ]
        if not prefs:
            continue

        en_pref = [lit for lit in prefs if lit.language == "en"]
        if not en_pref:
            english_pref_missing.append(_as_display(subj, graph))

        german_pref_labels = [lit for lit in prefs if lit.language == "de"]
        if german_pref_labels:
            german_pref.append(_as_display(subj, graph))
            alt_german = [
                lit
                for lit in graph.objects(subj, SKOS.altLabel)
                if isinstance(lit, Literal) and lit.language == "de"
            ]
            if not alt_german:
                german_pref_without_alt.append(_as_display(subj, graph))

        other_non_en = [lit for lit in prefs if lit.language not in {None, "en", "de"}]
        if other_non_en:
            other_non_english_pref.append(_as_display(subj, graph))

    return LabelLanguageReport(
        total_with_labels=len(seen_subjects),
        english_pref_missing=_sample_list(sorted(set(english_pref_missing)), sample_limit),
        german_pref=_sample_list(sorted(set(german_pref)), sample_limit),
        german_pref_without_alt=_sample_list(sorted(set(german_pref_without_alt)), sample_limit),
        other_non_english_pref=_sample_list(sorted(set(other_non_english_pref)), sample_limit),
    )

def run_roundtrip(
    ttl_path: Path,
    csv_path: Path,
    roundtrip_ttl: Path,
    schema_terms: Optional[Set[str]] = None,
) -> RoundTripReport:
    original = Graph()
    original.parse(ttl_path)

    rows = graph_to_table(original)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        writer.writerows(rows)

    reconstructed = table_to_graph(rows)
    reconstructed.serialize(roundtrip_ttl, format="turtle")

    # Use isomorphic graphs so blank nodes (restrictions, anonymous expressions) are aligned
    iso_original = to_isomorphic(original)
    iso_reconstructed = to_isomorphic(reconstructed)
    both, original_only, reconstructed_only = graph_diff(iso_original, iso_reconstructed)
    source_alignments = (0, 0, 0)
    roundtrip_alignments = (0, 0, 0)
    if schema_terms:
        source_alignments = _alignment_coverage(original, schema_terms)
        roundtrip_alignments = _alignment_coverage(reconstructed, schema_terms)

    return RoundTripReport(
        source_triples=len(original),
        reconstructed_triples=len(reconstructed),
        overlap_triples=len(both),
        missing_from_roundtrip=len(original_only),
        extra_in_roundtrip=len(reconstructed_only),
        source_alignments=source_alignments[0],
        source_alignments_in_schema=source_alignments[1],
        source_alignments_missing_schema=source_alignments[2],
        roundtrip_alignments=roundtrip_alignments[0],
        roundtrip_alignments_in_schema=roundtrip_alignments[1],
        roundtrip_alignments_missing_schema=roundtrip_alignments[2],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Export/import DCC ontology to tabular CSV format.")
    parser.add_argument("--mode", choices=["export", "import", "roundtrip", "validate"], default="export")
    parser.add_argument("--input-ttl", type=Path, help="Path to TTL ontology to export")
    parser.add_argument("--input-csv", type=Path, help="Path to tabular CSV to import")
    parser.add_argument("--output-csv", type=Path, help="Where to write CSV table")
    parser.add_argument("--output-ttl", type=Path, help="Where to write TTL when importing")
    parser.add_argument("--roundtrip-ttl", type=Path, help="Where to write reconstructed TTL")
    parser.add_argument(
        "--schema-xsd",
        type=Path,
        help="Path to the DCC schema XSD (used to validate dccx_alignment targets)",
    )
    args = parser.parse_args()

    schema_terms: Set[str] = _load_schema_terms(args.schema_xsd) if args.schema_xsd else set()

    if args.mode == "export":
        if not args.input_ttl or not args.output_csv:
            parser.error("--input-ttl and --output-csv are required for export")
        graph = Graph()
        graph.parse(args.input_ttl)
        rows = graph_to_table(graph)
        with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS, quoting=csv.QUOTE_NONNUMERIC)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Exported {len(rows)} rows from {args.input_ttl} to {args.output_csv}")
        if schema_terms:
            total, matched, missing = _alignment_coverage(graph, schema_terms)
            if total:
                print(
                    f"Schema alignment coverage (source TTL): {matched}/{total} in XSD namespace; {missing} missing"
                )
    elif args.mode == "import":
        if not args.input_csv or not args.output_ttl:
            parser.error("--input-csv and --output-ttl are required for import")
        with args.input_csv.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        graph = table_to_graph(rows)
        graph.serialize(args.output_ttl, format="turtle")
        print(f"Wrote {len(graph)} triples to {args.output_ttl}")
        if schema_terms:
            total, matched, missing = _alignment_coverage(graph, schema_terms)
            if total:
                print(
                    f"Schema alignment coverage (imported TTL): {matched}/{total} in XSD namespace; {missing} missing"
                )
    elif args.mode == "validate":
        if not args.input_ttl:
            parser.error("--input-ttl is required for validate")
        graph = Graph()
        graph.parse(args.input_ttl)
        print(f"Loaded {len(graph)} triples from {args.input_ttl}")

        if schema_terms:
            alignment_report = _alignment_report(graph, schema_terms)
            print("Schema alignment against XSD:")
            print(
                f"  Alignments in schema namespace: {alignment_report.alignments_in_schema}/"
                f"{alignment_report.total_alignments}"
            )
            print(f"  Alignment targets missing from schema: {alignment_report.alignments_missing_schema}")
            if alignment_report.missing_examples:
                print("    Examples (alignment targets not in schema):")
                for example in alignment_report.missing_examples:
                    print(f"      - {example}")
            print(f"  Schema terms without ontology alignment: {alignment_report.schema_without_alignment}")
            if alignment_report.schema_without_examples:
                print("    Examples (schema names without alignment):")
                for example in alignment_report.schema_without_examples:
                    print(f"      - {example}")
            if alignment_report.per_type:
                print("  Alignment coverage by entity type:")
                for entity_type, total in sorted(alignment_report.per_type.items()):
                    in_schema = alignment_report.per_type_in_schema.get(entity_type, 0)
                    print(f"    {entity_type}: {in_schema}/{total} targets in schema")
        else:
            print("No schema provided; skipping XSD alignment checks.")

        label_report = _label_language_report(graph)
        print("Label language checks:")
        print(f"  Entities with labels: {label_report.total_with_labels}")
        print(f"  Missing English prefLabel/RDFS label: {len(label_report.english_pref_missing)}")
        if label_report.english_pref_missing:
            print("    Examples:")
            for example in label_report.english_pref_missing:
                print(f"      - {example}")
        print(f"  German used as preferred label: {len(label_report.german_pref)}")
        if label_report.german_pref:
            print("    Examples:")
            for example in label_report.german_pref:
                print(f"      - {example}")
        print(f"  German preferred labels lacking altLabel@de: {len(label_report.german_pref_without_alt)}")
        if label_report.german_pref_without_alt:
            print("    Examples:")
            for example in label_report.german_pref_without_alt:
                print(f"      - {example}")
        print(f"  Other non-English preferred labels: {len(label_report.other_non_english_pref)}")
        if label_report.other_non_english_pref:
            print("    Examples:")
            for example in label_report.other_non_english_pref:
                print(f"      - {example}")
    else:  # roundtrip
        if not args.input_ttl or not args.output_csv or not args.roundtrip_ttl:
            parser.error("--input-ttl, --output-csv and --roundtrip-ttl are required for roundtrip")
        report = run_roundtrip(args.input_ttl, args.output_csv, args.roundtrip_ttl, schema_terms)
        print("Round-trip summary:")
        print(f"  Source triples:       {report.source_triples}")
        print(f"  Reconstructed triples:{report.reconstructed_triples}")
        print(f"  Overlap triples:      {report.overlap_triples}")
        print(f"  Missing in roundtrip: {report.missing_from_roundtrip}")
        print(f"  Extra in roundtrip:   {report.extra_in_roundtrip}")
        print(f"  Graphs identical:     {report.identical}")
        if schema_terms:
            print(
                "  Alignment coverage (source):        "
                f"{report.source_alignments_in_schema}/{report.source_alignments} in XSD; "
                f"{report.source_alignments_missing_schema} missing"
            )
            print(
                "  Alignment coverage (round-tripped): "
                f"{report.roundtrip_alignments_in_schema}/{report.roundtrip_alignments} in XSD; "
                f"{report.roundtrip_alignments_missing_schema} missing"
            )


if __name__ == "__main__":
    main()
