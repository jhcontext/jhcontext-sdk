# Simple CLI to load a JSON file and print canonical form and hash
import sys, json
from jhcontext import from_dict

def main():
    if len(sys.argv) < 2:
        print('Usage: python cli.py envelope.json')
        sys.exit(1)
    path = sys.argv[1]
    with open(path,'r',encoding='utf-8') as f:
        d = json.load(f)
    env = from_dict(d)
    try:
        env.validate()
    except Exception as e:
        print('Validation error:', e)
        sys.exit(2)
    print('Canonical:', env.canonical())
    print('Hash:', env.hash())
    proof = env.sign(env.raw.get('producer','did:example:unknown'))
    print('Mock proof:', proof)

if __name__ == '__main__':
    main()
