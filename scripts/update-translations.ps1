# Update translations for syntagmax metrics.
# Prerequisites: uv run pip install babel
# Usage: from syntagmax root: .\scripts\update-translations.ps1

$localesDir = 'src/syntagmax/resources/locales'
$potFile = "$localesDir/messages.pot"

# Extract messages from Jinja templates
uv run pybabel extract -F babel.cfg -o $potFile .

# Update existing locale .po files
uv run pybabel update -i $potFile -d $localesDir

# Compile .po to .mo (optional - syntagmax loads .po directly)
# uv run pybabel compile -d $localesDir
