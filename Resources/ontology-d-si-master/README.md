# 🧠 D-SI Ontology

The **D-SI Ontology** (Digital System of Units Ontology) provides a formal semantic representation of the International System of Units (SI), optimized for use in digital metrology applications. It has been derived from the [D-SI XML Schema](https://gitlab1.ptb.de/d-ptb/d-si/xsd-d-si) by PTB and supports machine-readable descriptions of units, quantities, and constants based on the SI Brochure, and enables advanced data validation and reasoning in linked data and knowledge graph environments.

This ontology was developed as part of the effort to enable **machine-actionable metrology** and is aligned with existing standards such as the [SI Digital Framework](https://si-digital-framework.org/SI) by the BIPM and the [Digital Calibration Certificate (DCC) Schema](https://www.ptb.de/dcc).

---

## 📦 Repository Contents

| File/Folder      | Description                                                                                                |
|------------------|------------------------------------------------------------------------------------------------------------|
| `dsi.ttl`        | The main OWL ontology file in Turtle format.                                                               |
| `public/`        | Auto-generated documentation using [WIDOCO](https://github.com/dgarijo/Widoco), deployed via GitLab Pages. |
| `.gitlab-ci.yml` | CI/CD pipeline for testing and to generate and deploy the documentation.                                   |
| `dsi2dsio.py`    | Main Python script for parsing D-SI XML data and generating turtle data.                                   |
| `dsi2dsio/`      | Contains XML->TTL mapping                                                                                  |
| `ressources/`    | Diagrams and D-SI XML Schema file                                                                          |
| `test/`          | Pytests for the ontology and example XML and TTL data                                                      |


---

## 🔍 Key Features

- Models quantities, fundamental constants, and uses the [SI Digital Framework](https://si-digital-framework.org/SI) to model base and derived SI units, and SI prefixes.
- Supports integration into [Digital Calibration Certificates](https://www.ptb.de/dcc)
- Includes human-readable and machine-readable metadata (DCAT, VoID, Dublin Core, etc.)

---

## 🌐 Ontology URI

**Permanent URI:**  
```text
https://ptb.de/sis/SI_Format.ttl
```

You can browse the human-readable documentation here:  
➡️ **[Ontology Documentation](https://ptb.gitlab.io/dcc/ontology-d-si/)**

---

## 📖 Documentation

This ontology uses [WIDOCO](https://github.com/dgarijo/Widoco) to generate HTML documentation. The documentation includes:

- Overview and description of classes and properties
- Ontology metadata
- Diagram (via WebVowl)
- References and licensing

---

## 📄 License

This ontology is published under the **[CC-BY 4.0 License](https://creativecommons.org/licenses/by/4.0/)**. Please credit appropriately when using or extending the ontology.

---

## 📬 Contact

For questions, feedback, or collaboration opportunities, please contact:

**Moritz Jordan**  
Physikalisch-technische Bundesanstalt  
moritz.jordan@ptb.de

**Giacomo Lanza**  
Physikalisch-technische Bundesanstalt  
giacomo.lanza@ptb.de

---

## 🧩 Related Projects

- [D-SI XML Schema - PTB](https://gitlab1.ptb.de/d-ptb/d-si/xsd-d-si)

---

## 🧪 Coming Soon

- [Digital Calibration Certificate (DCC) Ontology](https://www.ptb.de/dcc)
