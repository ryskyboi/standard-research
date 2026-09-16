"""Verify the frozen source trace and its inherited evidence dependencies."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
m=json.loads((root/'seller-origin-manifest.json').read_text())
for name,digest in m['sha256'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,f'Changed seller-origin artifact: {name}'
print(f'Verified {len(m["sha256"])} source-trace and inherited evidence files.')
