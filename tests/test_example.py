import json
from jhcontext import from_dict

def test_example():
    with open('example_envelope.json','r',encoding='utf-8') as f:
        d = json.load(f)
    env = from_dict(d)
    env.validate()
    can = env.canonical()
    h = env.hash()
    print('Example context_id:', d['context_id'])
    print('Canonical len:', len(can))
    print('Hash:', h)
    # mock signature test
    proof = env.sign(d.get('producer'))
    assert env.verify_signature(proof['signature'], proof['signer'])
