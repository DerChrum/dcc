import json
import logging
from dsi2dsio.src import make_first_letter_lowercase


logger = logging.getLogger(__name__)


class SIS:
    def __init__(self, prefix_file="config/prefixes.json", mapping_file="config/mapping.json"):
        # Load dictionary from JSON file with prefixes necessary for the ontology
        self.prefixes = self._load_prefixes(prefix_file)

        # Load mapping (D-SI XSD -> SIS Ontology) from JSON file and expand prefixes
        raw_mapping = self._load_mapping(mapping_file)
        self.mapping = self._expand_mapping(raw_mapping, self.prefixes)

    # ---------- File Loaders ----------

    @staticmethod
    def _load_prefixes(config_file) -> dict:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _load_mapping(config_file) -> dict:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # ---------- Expansion Helpers ----------

    @staticmethod
    def _expand_prefix(value, pfxs):
        if isinstance(value, str) and ":" in value:
            prefix, local = value.split(":", 1)
            if prefix in pfxs:
                return pfxs[prefix] + local
        return value

    def _expand_mapping(self, obj, pfxs):
        if isinstance(obj, dict):
            return {k: self._expand_mapping(v, pfxs) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_mapping(i, pfxs) for i in obj]
        else:
            return self._expand_prefix(obj, pfxs)

    # ---------- Public API ----------

    def elt2class(self, elt: str):
        """Return ontology class mapping for a given XML element string."""
        identifier = self._normalize_identifier(elt)
        try:
            return self.mapping[identifier]
        except KeyError:
            logger.warning(f"❌ Did not find element {elt} (normalized: {identifier}) in mapping.")
            return None

    # ---------- Utility ----------

    @staticmethod
    def _normalize_identifier(elt: str) -> str:
        """Extracts local identifier from a QName, URI, or CURIE-like string."""
        if "}" in elt:
            identifier = elt.split('}')[-1]
        elif "/" in elt:
            identifier = elt.split('/')[-1]
        elif ":" in elt:
            identifier = elt.split(":")[-1]
        else:
            identifier = elt
        return make_first_letter_lowercase(identifier)