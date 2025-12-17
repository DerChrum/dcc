import json
from rdflib import Namespace, URIRef
import requests


# --- Load JSON prefixes ---
def load_prefixes(config_file="config/prefixes.json") -> dict:
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


# Function to expand prefixed strings like "xsd:string"
def expand_prefix(value, pfxs):
    if isinstance(value, str) and ":" in value:
        prefix, local = value.split(":", 1)
        if prefix in pfxs:
            return pfxs[prefix] + local
    return value


# Recursive traversal of the mapping
def expand_mapping(obj, pfxs):
    if isinstance(obj, dict):
        return {k: expand_mapping(v, pfxs) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [expand_mapping(i, pfxs) for i in obj]
    else:
        return expand_prefix(obj, pfxs)


# --- Load JSON mapping ---
def load_mapping(config_file="config/mapping.json"):
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def update_prefixes(g):
    for prefix, iri in prefixes.items():
        g.bind(prefix, Namespace(iri))
    return g


def make_first_letter_lowercase(s):
    if not s:
        return s  # Return the string as-is if it's empty
    return s[0].lower() + s[1:]

def make_first_letter_uppercase(s):
    if not s:
        return s
    return s[0].upper() + s[1:]


si_prefixes = [
    "quecto", "ronto", "yocto", "zepto", "atto", "femto", "pico", "nano", "micro",
    "milli", "centi", "deci", "deca", "hecto", "kilo", "mega", "giga", "tera",
    "peta", "exa", "zetta", "yotta", "ronna", "quetta"
]


# Load dictionary from JSON file with prefixes necessary for the ontology
prefixes = load_prefixes()


# Load mapping (D-SI XSD -> SIS Ontology) from JSON file and expand prefixes
mapping = expand_mapping(load_mapping(), prefixes)


def elt_is_in_namespace(elt: str, prefix: str) -> bool:
    return elt.startswith('{' + Namespace(prefixes[prefix]) + '}')


def create_uri_ref(prefix: str, identifier: str) -> URIRef:
    return URIRef(f"{Namespace(prefixes[prefix])}{identifier}")


# Transform D-SI unit string to SIRP unit identifier
def parse_dsi_unit(unit: str) -> str:
    elements = unit.split("\\")
    elements = [elt for elt in elements if elt]
    last_elt = None
    per = False
    si_unit = ""
    for elt in elements:
        if elt == "per":
            per = True
        elif elt.startswith("tothe{"):
            si_unit += elt.split("tothe{")[1].split("}")[0]
        elif (last_elt not in si_prefixes) and (last_elt is not None):
            si_unit += f".{elt}"
            if per:
                si_unit += "-1"
        elif elt == "degreecelsius":
            si_unit += "degreeCelsius"
        else:
            si_unit += elt
        last_elt = elt
    return f"{prefixes['units']}{si_unit}"


def parse_qudt_quantitykind(quantitykind_string: str) -> str:
    return f"{prefixes['quantitykind']}{make_first_letter_uppercase(quantitykind_string)}"


def prefixes_to_ttl(pfxs: dict) -> str:
    return "\n".join(f"@prefix {k}: <{v}> ." for k, v in pfxs.items())


def inject_custom_prefixes(turtle_string: str) -> str:
    filtered_lines = [line for line in turtle_string.splitlines() if not line.startswith("@prefix")]
    filtered_turtle = "\n".join(filtered_lines)
    custom_prefixes = prefixes_to_ttl(prefixes)
    return f"{custom_prefixes}\n{filtered_turtle}"


def get_si_unit_expression(pid: str, timeout=5) -> str:  # timeout in seconds
    headers = {
        "Accept": "text/turtle",
        "Accept-Language": "en-US,en;q=0.5"
    }
    try:
        response = requests.get(pid, headers=headers, allow_redirects=True, timeout=timeout)

        if response.status_code == 200:
            return response.text
        print(f"❌ Failed to fetch unit data for {pid}. Status code: {response.status_code}")
        return None

    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout: The request to {pid} took longer than {timeout} seconds.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Request failed for {pid}: {e}")
        return None
