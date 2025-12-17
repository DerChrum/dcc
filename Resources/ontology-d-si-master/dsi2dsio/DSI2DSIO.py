from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF
from uuid import uuid4

import xml.etree.ElementTree as ET

from dsi2dsio.src import prefixes, elt_is_in_namespace, create_uri_ref
from dsi2dsio.src import (parse_dsi_unit,
                          parse_qudt_quantitykind,
                          update_prefixes,
                          get_si_unit_expression)
from dsi2dsio.src.sis import SIS

Sis = SIS()


# Map XML element to instance of ontology class
def process_elt(g, elt, instance_iri, class_iri, parent_class):
    # Add instance of class
    if class_iri == create_uri_ref("sis", "Complex"):
        # Look ahead if element contains cartesian or polar coordinates
        if elt.find("{https://ptb.de/si}valueImag") is not None:
            parent_class = Sis.elt2class("complexCartesian")
            class_iri = create_uri_ref("sis", "ComplexCartesian")
        elif elt.find("{https://ptb.de/si}valueMagnitude") is not None:
            parent_class = Sis.elt2class("complexPolar")
            class_iri = create_uri_ref("sis", "ComplexPolar")
    g.add((instance_iri, RDF.type, class_iri))
    index = 0
    for child in elt:
        instance_id = uuid4()
        child_class = parent_class.get('elements').get(child.tag.split('}')[-1])
        child_instance_iri = create_uri_ref("ex", str(instance_id))
        if child_class is not None:
            property_type = child_class.get('propertyType')
            property_iri = create_uri_ref("sis", child_class.get('propertyName'))
            child_class_iri = URIRef(f"{child_class.get('type')}")
            if property_type == 'object':
                g.add((instance_iri, property_iri, child_instance_iri))
                elt_class = Sis.elt2class(child_class.get('type'))
                process_elt(g, elt, child_instance_iri, child_class_iri, elt_class)
            elif property_type == 'newobject':
                # Add object property with class that does not exist as an element in the xml
                g.add((instance_iri, property_iri, child_instance_iri))
                if elt.tag.split('}')[-1] == 'realList' and child.tag.split('}')[-1] == 'real':
                    g.add((child_instance_iri,
                           create_uri_ref("sis", "hasListIndex"),
                           Literal(index, datatype=f"{Namespace(prefixes['xsd'])}integer")))
                    g.add((child_instance_iri,
                           create_uri_ref("sis", "isInRealList"),
                           instance_iri))
                    index += 1
                elt_class = Sis.elt2class(child_class.get('type'))
                process_elt(g, child, child_instance_iri, child_class_iri, elt_class)
            elif property_type == 'superclass':
                # Add object property with abstract superclass
                for grandchild in child:
                    grandchild_class = Sis.elt2class(grandchild.tag)
                    grandchild_class_iri = URIRef(f"{grandchild_class.get('type')}")
                    g.add((instance_iri, property_iri, child_instance_iri))
                    process_elt(g, grandchild, child_instance_iri, grandchild_class_iri, grandchild_class)
            elif property_type == 'covarianceMatrix':
                create_covariance_matrix(g, child, instance_iri, property_iri, child_instance_iri)
            elif property_type == 'qudtQuantitykind':
                qudt_quantitykind_iri = parse_qudt_quantitykind(child.text)
                g.add((instance_iri, property_iri, URIRef(qudt_quantitykind_iri)))
            elif property_type == 'unit':
                create_unit(g, child, child_class, instance_iri, property_iri)
            else:
                # Add data property
                g.add((instance_iri, property_iri, Literal(child.text, datatype=child_class.get('type'))))


def create_unit(g, child, child_class, instance_iri, property_iri):
    # Add unitIdentifier data property
    unit_identifier_type = child_class.get('type')
    g.add((instance_iri, property_iri, Literal(child.text, datatype=unit_identifier_type)))
    # Add sirp:MeasurementUnit
    si_unit_pid = parse_dsi_unit(child.text)
    # Try to get compound unit from SIRP API and add to graph
    # (SIRP does not support "one" or "percent")
    if "one" not in si_unit_pid and "percent" not in si_unit_pid:
        unit_instance = get_si_unit_expression(si_unit_pid)
        if unit_instance is not None:
            unit_graph = Graph()
            unit_graph.parse(data=unit_instance, format="turtle")
            g += unit_graph
        g.add((instance_iri,
               create_uri_ref("sis", "hasSIMeasurementUnit"),
               URIRef(si_unit_pid)))


def create_covariance_matrix(g, child, instance_iri, property_iri, child_instance_iri):
    g.add((instance_iri, property_iri, child_instance_iri))
    g.add((child_instance_iri, RDF.type, URIRef(f"{Namespace(prefixes['sis'])}CovarianceMatrix")))
    covariance_class = Sis.elt2class("covariance")
    row_index = 1
    for column in child.findall("{https://ptb.de/si}column"):
        column_index = 1
        for covariance in column.findall("{https://ptb.de/si}covariance"):
            covariance_id = uuid4()
            covariance_iri = create_uri_ref("ex", str(covariance_id))
            g.add((child_instance_iri,
                   create_uri_ref("sis", "hasCovariance"),
                   covariance_iri))
            g.add((covariance_iri, RDF.type, create_uri_ref("sis", "Covariance")))
            g.add((covariance_iri,
                   create_uri_ref("sis", "hasColumnIndex"),
                   Literal(column_index, datatype=f"{Namespace(prefixes['xsd'])}positiveInteger")))
            column_index += 1
            g.add((covariance_iri,
                   create_uri_ref("sis","hasRowIndex"),
                   Literal(row_index, datatype=f"{Namespace(prefixes['xsd'])}positiveInteger")))
            g.add((covariance_iri,
                   create_uri_ref("sis", "hasValue"),
                   Literal(covariance.find("{https://ptb.de/si}value").text,
                           datatype=f"{Namespace(prefixes['xsd'])}double")))
            create_unit(g, covariance.find("{https://ptb.de/si}unit"), covariance_class.get("elements").get("unit"),
                        covariance_iri,
                        create_uri_ref("sis", covariance_class.get('elements').get('unit').get('propertyName')))
        row_index += 1


def find_dsi_elements(elements, g):
    for elt in elements:
        if elt.tag is not None and elt_is_in_namespace(elt.tag, 'si'):
            child_class = Sis.elt2class(elt.tag)
            if child_class is not None:
                instance_id = uuid4()
                class_iri = URIRef(f"{child_class.get('type')}")
                instance_iri = create_uri_ref("ex", str(instance_id))
                process_elt(g, elt, instance_iri, class_iri, child_class)
        else:
            find_dsi_elements(elt, g)


def create_ontology_instances(xml_file):
    # Parse the XML file
    root = ET.fromstring(xml_file)

    # Create new instances graph
    instances_graph = update_prefixes(Graph())

    find_dsi_elements(root, instances_graph)

    # Extract D-SI elements from XML

    return instances_graph
