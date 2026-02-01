import hashlib
import base64

def compute_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

# Mock sign/verify (placeholder)
def mock_sign(hex_hash: str, signer_did: str) -> str:
    # simple reversible mock: base64(signerdid + ':' + hash) - DO NOT use in production
    s = (signer_did + ':' + hex_hash).encode('utf-8')
    return base64.urlsafe_b64encode(s).decode('utf-8')

def mock_verify(hex_hash: str, signature: str, signer_did: str) -> bool:
    try:
        import base64
        raw = base64.urlsafe_b64decode(signature.encode('utf-8')).decode('utf-8')
        return raw == (signer_did + ':' + hex_hash)
    except Exception:
        return False
