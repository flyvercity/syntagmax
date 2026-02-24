#!/usr/bin/env python3
# type: ignore

from duct import cmd
from pathlib import Path

# Setup paths relative to the script location
locales_dir = Path('src/syntagmax/resources/locales')
pot_file = locales_dir / 'messages.pot'

# 1. Extract messages
# Replaces: uv run pybabel extract -F babel.cfg -o $potFile .
extract = cmd('uv', 'run', 'pybabel', 'extract', '-F', 'babel.cfg', '-o', str(pot_file), '.')

# 2. Update locales
# Replaces: uv run pybabel update -i $potFile -d $localesDir
update = cmd('uv', 'run', 'pybabel', 'update', '-i', str(pot_file), '-d', str(locales_dir))

# Execute sequence: only update if extraction succeeds
print(f'Extracting to {pot_file}...')
extract.run()

print(f'Updating locales in {locales_dir}...')
update.run()

print('Done.')
