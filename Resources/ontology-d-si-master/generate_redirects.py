import argparse
import os
import rdflib

def generate_redirects(redirect_base):
    # Configuration
    ttl_path = "SI_Format.ttl"  # Path to your ontology Turtle file
    output_dir = "public"
    base_iri = "https://ptb.de/sis/"

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Load the ontology
    g = rdflib.Graph()
    g.parse(ttl_path, format="turtle")

    # Extract all subjects with the specified base IRI
    for s in g.subjects():
        if isinstance(s, rdflib.URIRef) and str(s).startswith(base_iri):
            local_name = str(s).split("/")[-1]
            if len(local_name) > 0:
                print(local_name)
                # Create HTML redirect file
                filename = os.path.join(output_dir, f"{local_name}.html")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(f"""<!DOCTYPE html>
    <html>
      <head>
        <meta http-equiv="refresh" content="0;url=index.html#{local_name}" />
        <link rel="canonical" href="{redirect_base}#{local_name}" />
        <title>Redirecting to {local_name}</title>
      </head>
      <body>
        <p>Redirecting to <a href="{redirect_base}#{local_name}">{redirect_base}#{local_name}</a>…</p>
      </body>
    </html>""")

    print(f"✅ Generated HTML redirect pages in '{output_dir}/'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--redirect_base", required=True, help="Redirect base URL")
    args = ap.parse_args()

    generate_redirects(args.redirect_base)


if __name__ == "__main__":
    main()