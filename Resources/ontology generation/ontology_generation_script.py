"""
Project: Lab of the Future - Oligonucleotide synthesis process flow and instrument modelling

This script generates RDF Turtle files from Excel mapping sheets.

It processes 5 main sheets from Mapping_SOSASSN.xlsx:
  - BaseModel_TBox: Core ontology definitions (T-box)
  - MappingDCAT: DCAT catalog metadata
  - PlatformSynthesis_ABox: Synthesis platform instances
  - PlatformAnalysis_ABox: Analysis platform instances
  - AFOAlignment: AAlignment with the allotrope foundation ontologies

Example:
    Before running, adjust:
    1. PROJECT_FOLDER: Point to your project directory
    2. MAPPING_FILE: Path to the Mapping_SOSASSN.xlsx file
    3. ONTOLOGY_METADATA: Update creator, publisher, descriptions

To run:
    python ontology_generator.py

Requirements:
    - Python 3.12
    - pandas
    - rdflib

Author: MC
Date: 4/10/2025
Version: 0.9
Internal review: -
Disclaimers: This code has been enhanced through the use of CoPilot. (Code and documentation.) 
The original design and structure is based on historical work by Priyanka Bharti and Michael Chrubasik and has been adjusted for this project.
"""

import os
import pandas as pd
from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS, OWL, XSD, BNode
from rdflib.namespace import DCTERMS, FOAF, SKOS
from datetime import datetime, date
import re
from typing import Dict, Set, Optional, Tuple, List



# Config Paths

PROJECT_FOLDER = os.environ.get('PROJECT_FOLDER', os.getcwd())
#INPUT_DIR = os.environ.get('INPUT_DIR', os.path.join(PROJECT_FOLDER, "input"))
INPUT_DIR = r'C:\Users\mc29\OneDrive - National Physical Laboratory\Data Science Department (Internal) - 2025-26\Digital Engineering\Lab of the Future (MMIC)\Technical Documents\MC_SOSASSN'
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', os.path.join(PROJECT_FOLDER, "output"))
MAPPING_FILE = os.environ.get('MAPPING_FILE', 
    os.path.join(INPUT_DIR, "Mapping_SOSASSN.xlsx"))

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Batch identifier for instance data generation
# to DO: This will be read from config file in future refactoring
BATCH_ID = "AB6004"

# Config Metadata - in this current version the ontology metadata still has to be hardcoded.
# Future versions should take an automated approach based on yet another excel spreadsheet

# Ontology creators (can be multiple)
CREATORS = [
    {
        "name": "Michael Chrubasik",
        "label": "Michael Chrubasik"
    },
    {
        "name": "Moulham Alsuleman",
        "label": "Moulham Alsuleman"
    },
    {
        "name": "Nina Peric",
        "label": "Nina Peric"
    }
]

# Ontology publisher
PUBLISHER = {
    "name": "National Physical Laboratory",
    "uri": "http://npl.co.uk/"
}

# Creation date (will use today's date if not specified)
CREATION_DATE = date(2025, 1, 3)

# Ontology version
ONTOLOGY_VERSION = "1.0.0"

# Ontology-specific metadata (per output file)
ONTOLOGY_METADATA = {
    "LotF_TBox": {
        "label": "Lab of the Future Proof of Concept Ontology - T-box",
        "description": "Core ontology defining analytical instrument concepts following SOSA/SSN patterns for oligonucleotide synthesis and analysis platforms.",
        "comment": "."
    },
    "LotF_DCAT": {
        "label": "Lab of the Future - DCAT Catalog Metadata",
        "description": "DCAT catalog structure for organising experimental datasets, linking lab catalogs to projects, batches, and measurement series for the lab of the future use case between CPI and NPL.",
        "comment": "This catalog structure is a proof-of-concept representation of the lab of the future use case between CPI and NPL, providing a hierarchical organisation of experimental data following W3C DCAT vocabulary."
    },
    "LotF_Synthesis_Platform": {
        "label": "Lab of the Future Proof of Concept Ontology - Synthesis Instances",
        "description": "Synthesis platform instances representing the AKTA OligoSynt oligonucleotide synthesiser and its component sensors, actuators, and systems.",
        "comment": "These are reference instances (A-box) representing the synthesis process platform."
    },
    "LotF_Analysis_Platform": {
        "label": "Lab of the Future Proof of Concept Ontology - Analysis Instances",
        "description": "Analysis platform instances representing the Orbitrap LCMS system and its component sensors, detectors, and measurement systems.",
        "comment": "These are reference instances (A-box) representing the analytical process platform for LC-MS analysis. The model links to external measurement files while maintaining semantic context."
    },
    "LotF_AFO_Alignment": {
        "label": "Lab of the Future - Allotrope Foundation Ontology Alignment",
        "description": "Alignment mappings between LotF ontology concepts and Allotrope Foundation Ontology (AFO) classes and properties.",
        "comment": "Maps to AFO namespaces: af-e (equipment), af-p (process), af-r (results), af-rl (roles)."
    },    
    "LotF_Master": {
        "label": "Lab of the Future - Complete Ontology",
        "description": "Master ontology importing all LotF components.",
        "comment": "Import this single file to load the complete ontology stack."
    }

}

# Namespaces

# Standard namespaces
SOSA = Namespace("http://www.w3.org/ns/sosa/")
SSN = Namespace("http://www.w3.org/ns/ssn/")
PROV = Namespace("http://www.w3.org/ns/prov#")
ORG = Namespace("http://www.w3.org/ns/org#")
DCAT = Namespace("http://www.w3.org/ns/dcat#")

# BFO / OBO
RO = Namespace("http://www.obofoundry.org/ro/ro.owl#")

# Allotrope Foundation Ontologies
AF_E = Namespace("http://purl.allotrope.org/ontologies/equipment#")
AF_P = Namespace("http://purl.allotrope.org/ontologies/process#")
AF_R = Namespace("http://purl.allotrope.org/ontologies/result#")
AF_RL = Namespace("http://purl.allotrope.org/ontologies/role#")

# Custom 
BASE_URI = "http://uk-cpi.com/LotF/NPL-PoC/"
EX = Namespace(f"{BASE_URI}ontology/")
INST_REF = Namespace(f"{BASE_URI}instances/") # Reference instances (platforms, equipment)
INST_BATCH = Namespace(f"{BASE_URI}instances/{BATCH_ID}/") # Batch-specific instances (experiments, observations)


# Utility Functions


def validate_datetime(dt_string: str) -> Optional[str]:
    """
    Validate and correct datetime strings to ISO 8601 format (R09).
    
    Parameter:
        dt_string: String representation of datetime
        
    Output:
        str: Valid ISO 8601 datetime string or None if invalid
    """
    if pd.isna(dt_string):
        return None
        
    dt_string = str(dt_string).strip()
    
    # Fix common malformations like '2024--03-20'
    dt_string = re.sub(r'-{2,}', '-', dt_string)
    
    try:
        # Try parsing as datetime
        dt = pd.to_datetime(dt_string)
        return dt.isoformat()
    except:
        return None


def clean_literal_value(value) -> Optional[str]:
    """
    Clean and prepare literal values for RDF (R08).
    
    Parameter:
        value: Raw value from spreadsheet
        
    Output:
        str: Cleaned value or None
    """
    if pd.isna(value) or value == '' or value == 'undefined':
        return None
    
    value = str(value).strip()
    
    # Remove any existing quotes that might have been in the Excel
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    
    return value


def clean_for_uri(text: str) -> str:
    """
    Replaces spaces and other invalid characters with underscores to make a valid URI local name.
    """
    if pd.isna(text):
        return ""
    # Clean code
    clean_text = re.sub(r'[^a-zA-Z0-9-]+', '_', str(text))
    # Remove any leading or trailing underscores that might result
    return clean_text.strip('_')


def parse_namespace(uri_string: str, namespace_map: Dict) -> URIRef:
    """
    Parse a URI string, sanitize it for valid URI characters, and expand the namespace prefix.
    
    Parameter:
        uri_string: URI string (e.g., 'inst:Pump1', 'ex:Oligonucleotide Synthesizer')
        namespace_map: Dictionary mapping prefixes to Namespace objects
        
    Output:
        URIRef: Expanded and sanitized URI reference
    """
    if pd.isna(uri_string):
        return None
        
    uri_string = str(uri_string).strip()
    
    # Already a full URI, assume it's valid
    if uri_string.startswith('http://') or uri_string.startswith('https://'):
        return URIRef(uri_string)
    
    # Has namespace prefix
    if ':' in uri_string:
        prefix, local_name = uri_string.split(':', 1)
        if prefix in namespace_map:
            # Sanitize the local name part of the URI
            cleaned_local_name = clean_for_uri(local_name)
            return namespace_map[prefix][cleaned_local_name]
    
    # Default to EX namespace if no prefix, and sanitize the whole string
    sanitized_uri_string = clean_for_uri(uri_string)
    return EX[sanitized_uri_string]


def parse_object_value(object_str: str, object_type: str, namespace_map: Dict):
    """
    Parse object value based on Object Type column (R06).
    
    Parameter:
        object_str: Object value as string
        object_type: Type specification ('Class', 'Instance', 'Literal', 'xsd:type')
        namespace_map: Dictionary mapping prefixes to Namespace objects
        
    Output:
        URIRef or Literal: Appropriate rdflib object
    """
    object_str = clean_literal_value(object_str)
    if not object_str:
        return None
    
    object_type = clean_literal_value(object_type)
    
    # Class or Instance -> URI
    if object_type in ['Class', 'Instance']:
        return parse_namespace(object_str, namespace_map)
    
    # XSD typed literal
    if object_type and object_type.startswith('xsd:'):
        datatype_name = object_type.split(':')[1]
        datatype = XSD[datatype_name]
        
        # Special handling for datetime (R09)
        if datatype_name in ['dateTime', 'date']:
            validated_dt = validate_datetime(object_str)
            if validated_dt:
                return Literal(validated_dt, datatype=datatype)
            else:
                return None
        else:
            return Literal(object_str, datatype=datatype)
    
    # Check if it looks like a URI (has namespace prefix)
    if ':' in object_str and not object_str.startswith('"'):
        return parse_namespace(object_str, namespace_map)
    
    return Literal(object_str)


def collect_concepts(row: pd.Series) -> Set[str]:
    """
    Collect concept IDs from both Subject and Object related columns (R05, R15).
    
    Parameter:
        row: DataFrame row
        
    Output:
        Set of concept IDs
    """
    concepts = set()
    
    # Subject related to concept
    subject_concept = clean_literal_value(row.get('Subject related to concept'))
    if subject_concept:
        # Handle comma-separated values (R15)
        concepts.update([c.strip() for c in subject_concept.split(',') if c.strip()])
    
    # Object related to concept
    object_concept = clean_literal_value(row.get('Object related to concept'))
    if object_concept:
        concepts.update([c.strip() for c in object_concept.split(',') if c.strip()])
    
    return concepts

# Ontology Generation


def create_namespace_map() -> Dict[str, Namespace]:
    """
    Create mapping of namespace prefixes to Namespace objects.
    
    Output:
        Dictionary mapping prefix strings to rdflib Namespace objects
    """
    return {
        'ex': EX,
        'inst': INST_REF,  # workaround for not-yet updated instances of just inst
        'inst_ref': INST_REF,
        'inst_batch': INST_BATCH,
        'sosa': SOSA,
        'ssn': SSN,
        'prov': PROV,
        'org': ORG,
        'dcat': DCAT,
        'dcterms': DCTERMS,
        'dct': DCTERMS,        
        'foaf': FOAF,
        'skos': SKOS,
        'owl': OWL,
        'rdf': RDF,
        'rdfs': RDFS,
        'xsd': XSD,
        'af-e': AF_E,
        'af-p': AF_P,
        'af-r': AF_R,
        'af-rl': AF_RL,
        'ro': RO
    }


def bind_namespaces(g: Graph):
    """
    Bind all namespaces to the graph for clean serialization.
    
    Parameter:
        g: rdflib Graph object
    """
    g.bind('ex', EX)
    g.bind('inst_ref', INST_REF)
    g.bind('inst_batch', INST_BATCH) 
    g.bind('sosa', SOSA)
    g.bind('ssn', SSN)
    g.bind('prov', PROV)
    g.bind('org', ORG)
    g.bind('dcat', DCAT)
    g.bind('dcterms', DCTERMS)
    g.bind('dct', DCTERMS)    
    g.bind('foaf', FOAF)
    g.bind('skos', SKOS)
    g.bind('owl', OWL)
    g.bind('rdf', RDF)
    g.bind('rdfs', RDFS)
    g.bind('xsd', XSD)
    g.bind('af-e', AF_E)
    g.bind('af-p', AF_P)
    g.bind('af-r', AF_R)
    g.bind('af-rl', AF_RL)
    g.bind('ro', RO)



def generate_ontology_header(g: Graph, ontology_key: str, import_type: str = 'none'):
    """
    Generate the ontology header with proper metadata structure (Step 1).
    
    Parameter:
        g: rdflib Graph object
        ontology_key: Key to lookup metadata (e.g., 'LotF_TBox')
        import_type: Type of imports to add:
            - 'foundational': Import SOSA/SSN/PROV/ORG (for T-box only)
            - 'tbox': Import LotF_TBox (for A-box ontologies)
            - 'dcat': Import DCAT vocabulary
            - 'none': No imports
    """
    # Get metadata for this ontology
    metadata = ONTOLOGY_METADATA[ontology_key]
    ontology_uri = EX[ontology_key]
    
    # Ontology declaration
    g.add((ontology_uri, RDF.type, OWL.Ontology))
    g.add((ontology_uri, RDFS.label, Literal(metadata['label'], lang='en')))
    
    # Handle imports based on type
    if import_type == 'foundational':
        # T-box imports foundational ontologies
        g.add((ontology_uri, OWL.imports, URIRef("http://www.w3.org/ns/sosa/")))
        g.add((ontology_uri, OWL.imports, URIRef("http://www.w3.org/ns/ssn/")))
        g.add((ontology_uri, OWL.imports, URIRef("http://www.w3.org/ns/prov-o#")))
        g.add((ontology_uri, OWL.imports, URIRef("http://www.w3.org/ns/org#")))
        g.add((ontology_uri, OWL.imports, URIRef("http://www.obofoundry.org/ro/ro.owl#")))        
    elif import_type == 'tbox':
        # A-box ontologies import the T-box
        g.add((ontology_uri, OWL.imports, EX.LotF_TBox))
    elif import_type == 'dcat':
        # DCAT imports DCAT vocabulary
        g.add((ontology_uri, OWL.imports, URIRef("http://www.w3.org/ns/dcat#")))
    elif import_type == 'alignment':
        # Alignment ontologies import T-box and SKOS
        g.add((ontology_uri, OWL.imports, EX.LotF_TBox))
        g.add((ontology_uri, OWL.imports, URIRef("http://www.w3.org/2004/02/skos/core#")))
    
    
    # Creator(s) as foaf:Person
    for creator in CREATORS:
        creator_node = BNode()
        g.add((creator_node, RDF.type, FOAF.Person))
        g.add((creator_node, RDFS.label, Literal(creator['label'])))
        g.add((creator_node, FOAF.name, Literal(creator['name'])))
        g.add((ontology_uri, DCTERMS.creator, creator_node))
    
    # Publisher as org:Organization
    publisher_node = BNode()
    g.add((publisher_node, RDF.type, ORG.Organization))
    g.add((publisher_node, ORG.name, Literal(PUBLISHER['name'])))
    g.add((ontology_uri, DCTERMS.publisher, publisher_node))
    
    # Creation date
    g.add((ontology_uri, DCTERMS.created, Literal(CREATION_DATE, datatype=XSD.date)))
    
    # Version
    g.add((ontology_uri, OWL.versionInfo, Literal(ONTOLOGY_VERSION)))
    
    # Description and comment
    g.add((ontology_uri, DCTERMS.description, Literal(metadata['description'], lang='en')))
    g.add((ontology_uri, RDFS.comment, Literal(metadata['comment'], lang='en')))


def define_custom_properties(g: Graph):
    """
    Define custom datatype properties as specified in R03 (Step 2).
    
    Parameter:
        g: rdflib Graph object
    """
    # ex:relatedConcept
    related_concept = EX.relatedConcept
    g.add((related_concept, RDF.type, OWL.DatatypeProperty))
    g.add((related_concept, RDFS.label, Literal("related concept", lang='en')))
    g.add((related_concept, RDFS.comment, 
           Literal("Relates to an identified concept number.", lang='en')))
    
    # ex:inferenceType
    inference_type = EX.inferenceType
    g.add((inference_type, RDF.type, OWL.DatatypeProperty))
    g.add((inference_type, RDFS.label, Literal("inference type", lang='en')))
    g.add((inference_type, RDFS.comment, 
           Literal("Concept identified from data directly or inferred", lang='en')))


def process_mapping_row(g: Graph, row: pd.Series, namespace_map: Dict, 
                       subject_metadata: Dict, bnode_map: Dict):
    """
    Process a single row from mapping sheet and add triples to graph (R01-R15).
    
    Parameter:
        g: rdflib Graph object
        row: pandas Series representing a row
        namespace_map: Dictionary mapping prefixes to Namespace objects
        subject_metadata: Dictionary to accumulate metadata per subject (for R04)
        bnode_map: Dictionary to track blank nodes by label
    """
    # Extract and parse subject
    subject_str = clean_literal_value(row.get('Subject'))
    if not subject_str:
        return
    
    # Handle blank node subjects (e.g., _:restriction1)
    if subject_str.startswith('_:'):
        if subject_str not in bnode_map:
            bnode_map[subject_str] = BNode()
        subject = bnode_map[subject_str]
    else:
        subject = parse_namespace(subject_str, namespace_map)
    
    # Initialize metadata collection for this subject if not exists
    if subject not in subject_metadata:
        subject_metadata[subject] = {
            'label': None,
            'concepts': set(),
            'inference_types': set(),
            'evidence_sources': set(),
            'evidence_comments': set()
        }
    
    # Collect subject label (R02)
    subject_label = clean_literal_value(row.get('Subject Label'))
    if subject_label and not subject_metadata[subject]['label']:
        subject_metadata[subject]['label'] = subject_label
    
    # Collect concepts (R04, R05, R15)
    concepts = collect_concepts(row)
    subject_metadata[subject]['concepts'].update(concepts)
    
    # Collect inference type (R04)
    inference_type = clean_literal_value(row.get('inference_type'))
    if inference_type:
        subject_metadata[subject]['inference_types'].add(inference_type)
    
    # Collect evidence source (R02)
    evidence_source = clean_literal_value(row.get('evidence_source'))
    if evidence_source and any(ext in evidence_source.lower() 
                               for ext in ['.xlsx', '.csv', '.ttl', '.xml']):
        subject_metadata[subject]['evidence_sources'].add(evidence_source)
    
    # Collect evidence comment (R07)
    evidence_comment = clean_literal_value(row.get('evidence_comment'))
    if evidence_comment and str(subject).startswith(str(EX)):
        subject_metadata[subject]['evidence_comments'].add(evidence_comment)
    
    # Add main predicate-object triple
    predicate_str = clean_literal_value(row.get('Predicate'))
    object_str = clean_literal_value(row.get('Object'))
    
    if predicate_str and object_str:
        predicate = parse_namespace(predicate_str, namespace_map)
        
        # Get object type from column if available
        object_type = row.get('Object Type')
        if pd.isna(object_type):
            # Infer from Object Label / Literal column for BaseModel_TBox
            object_label = row.get('Object Label / Literal')
            if object_label in ['Class', 'Instance']:
                object_type = object_label
        
        # Handle blank node objects (e.g., _:restriction1)
        if object_str.startswith('_:'):
            if object_str not in bnode_map:
                bnode_map[object_str] = BNode()
            obj = bnode_map[object_str]
        else:
            obj = parse_object_value(object_str, object_type, namespace_map)
        
        if obj is not None:
            g.add((subject, predicate, obj))


def add_subject_metadata(g: Graph, subject_metadata: Dict):
    """
    Add accumulated metadata to subjects (R04 - direct attachment).
    
    Parameter:
        g: rdflib Graph object
        subject_metadata: Dictionary of metadata per subject
    """
    for subject, metadata in subject_metadata.items():
        # Add label
        if metadata['label']:
            g.add((subject, RDFS.label, Literal(metadata['label'], lang='en')))
        
        # Add concepts (R05, R15)
        for concept in metadata['concepts']:
            g.add((subject, EX.relatedConcept, Literal(concept)))
        
        # Add inference types
        for inf_type in metadata['inference_types']:
            g.add((subject, EX.inferenceType, Literal(inf_type)))
        
        # Add evidence sources
        for source in metadata['evidence_sources']:
            g.add((subject, DCTERMS.source, Literal(source)))
        
        # Add evidence comments
        for comment in metadata['evidence_comments']:
            g.add((subject, RDFS.comment, Literal(comment, lang='en')))


def process_sheet(df: pd.DataFrame, namespace_map: Dict) -> Tuple[Graph, Dict]:
    """
    Process a complete mapping sheet.
    
    Parameter:
        df: DataFrame containing the sheet data
        namespace_map: Dictionary mapping prefixes to Namespace objects
        
    Output:
        Tuple of (Graph, subject_metadata dictionary)
    """
    g = Graph()
    bind_namespaces(g)
    
    subject_metadata = {}
    bnode_map = {}  # Track blank nodes by label
    
    # Process each row (Step 3)
    for idx, row in df.iterrows():
        try:
            process_mapping_row(g, row, namespace_map, subject_metadata, bnode_map)
        except Exception as e:
            print(f"Error processing row {idx}: {e}")
            continue
    
    return g, subject_metadata


def generate_ontology(mapping_file: str, 
                     sheet_name: str,
                     ontology_key: str,
                     import_type: str = 'none',
                     define_properties: bool = False) -> str:
    """
    Generate ontology from a mapping sheet.
    
    Parameter:
        mapping_file: Path to mapping Excel file
        sheet_name: Name of the Excel sheet to process
        ontology_key: Key for ontology metadata lookup (e.g., 'LotF_TBox')
        import_type: Type of imports ('foundational', 'tbox', 'dcat', "alignment" or 'none')
        define_properties: Whether to define ex:relatedConcept and ex:inferenceType
        
    Output:
        Path to generated TTL file
    """
    print("\n" + "="*5)
    print(f"Processing {sheet_name}")
    print("="*5)
    
    # Read and prepare data
    df = pd.read_excel(mapping_file, sheet_name=sheet_name)
    df.columns = df.columns.str.strip()
    
    namespace_map = create_namespace_map()
    
    # Create graph and process rows
    g, subject_metadata = process_sheet(df, namespace_map)
    
    # Add ontology header with proper metadata
    generate_ontology_header(g, ontology_key, import_type=import_type)
    
    # Define custom properties (only for T-box)
    if define_properties:
        define_custom_properties(g)
    
    # Add accumulated metadata
    add_subject_metadata(g, subject_metadata)
    
    # Serialize
    output_file = os.path.join(OUTPUT_DIR, f"{ontology_key}.ttl")
    g.serialize(destination=output_file, format='turtle')
    
    print(f"Generated: {output_file}")
    print(f"Total triples: {len(g)}")
    
    return output_file


# Main
def main():
    """Main execution function."""
    print("="*5)
    print("LotF Ontology Generator")
    print("="*5)
    print(f"Input: {MAPPING_FILE}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Creation Date: {CREATION_DATE}")
    print(f"Creator(s): {', '.join([c['name'] for c in CREATORS])}")
    print(f"Publisher: {PUBLISHER['name']}")
    
    if not os.path.exists(MAPPING_FILE):
        print(f"\nError: Mapping file not found at {MAPPING_FILE}")
        print("Update the MAPPING_FILE path in the script configuration.")
        return
    
    try:
        # Process all 6 sheets
        files = []
        
        # 1. T-box ontology (imports foundational ontologies)
        files.append(generate_ontology(
            MAPPING_FILE,
            sheet_name='BaseModel_TBox',
            ontology_key='LotF_TBox',
            import_type='foundational',
            define_properties=True
        ))
        
        # 2. DCAT catalog (imports DCAT vocabulary)
        files.append(generate_ontology(
            MAPPING_FILE,
            sheet_name='MappingDCAT',
            ontology_key='LotF_DCAT',
            import_type='dcat',
            define_properties=False
        ))
        
        # 3. Platform Synthesis A-box (imports T-box)
        files.append(generate_ontology(
            MAPPING_FILE,
            sheet_name='PlatformSynthesis_ABox',
            ontology_key='LotF_Synthesis_Platform',
            import_type='tbox',
            define_properties=False
        ))
        
        # 4. Platform Analysis A-box (imports T-box)
        files.append(generate_ontology(
            MAPPING_FILE,
            sheet_name='PlatformAnalysis_ABox',
            ontology_key='LotF_Analysis_Platform',
            import_type='tbox',
            define_properties=False
        ))

        # 5. AFO Alignment (imports T-box and SKOS)
        files.append(generate_ontology(
            MAPPING_FILE,
            sheet_name='AFOAlignment',
            ontology_key='LotF_AFO_Alignment',
            import_type='alignment',
            define_properties=False
        ))        

        files.append(generate_master_ontology())        

        # Summary
        print("\nAll ontologies generated successfully")
        for f in files:
            print(f"  • {os.path.basename(f)}")
        
    except Exception as e:
        print(f"\nError generating ontologies: {e}")
        import traceback
        traceback.print_exc()


# Add after generating the 5 ontologies in main()
def generate_master_ontology(ontology_key='LotF_Master'):
    """Generate master ontology that imports all components."""
    g = Graph()
    bind_namespaces(g)
    
    master_uri = EX.LotF_Master
    metadata = ONTOLOGY_METADATA[ontology_key]    
    
    # Ontology declaration
    g.add((master_uri, RDF.type, OWL.Ontology))
    g.add((master_uri, RDFS.label, Literal("Lab of the Future - Complete Ontology", lang='en')))
    g.add((master_uri, RDFS.label, Literal(metadata['label'], lang='en')))    
    
    # Import all components
    g.add((master_uri, OWL.imports, EX.LotF_TBox))
    g.add((master_uri, OWL.imports, EX.LotF_DCAT))
    g.add((master_uri, OWL.imports, EX.LotF_Synthesis_Platform))
    g.add((master_uri, OWL.imports, EX.LotF_Analysis_Platform))
    g.add((master_uri, OWL.imports, EX.LotF_AFO_Alignment))    
        
    output_file = os.path.join(OUTPUT_DIR, "LotF_Master.ttl")
    g.serialize(destination=output_file, format='turtle')
    return output_file

if __name__ == "__main__":
    main()