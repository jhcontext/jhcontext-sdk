def validate_envelope(d: dict) -> None:
    required = ['@type','context_id','schema_version','producer','created_at','ttl','status','performative','semantic_payload','proof']
    missing = [k for k in required if k not in d]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    # basic checks
    if not isinstance(d.get('semantic_payload'), list):
        raise ValueError('semantic_payload must be a list')
