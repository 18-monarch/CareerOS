import json
from pathlib import Path
from careeros.main import app

Path('packages/shared/openapi.json').write_text(json.dumps(app.openapi(), indent=2) + '\n')
print('Exported packages/shared/openapi.json')
