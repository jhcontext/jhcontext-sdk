import json
def canonicalize(obj: dict) -> str:
    # Deterministic JSON serialization for canonical form.
    # For real JSON-LD URDNA2015 canonicalization, use a proper library.
    return json.dumps(obj, sort_keys=True, separators=(',',':'), ensure_ascii=False)
