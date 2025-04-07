$cmd_args = @(
    'uv run python -m gitreqms',
    '--verbose',
    '--suppress-unexpected-children',
    '--suppress-required-children',
    'analyze',
    "$PSScriptRoot/../../safir/safir-fusion-rms/rms.toml"
)

$cmd = $cmd_args -join ' '
Write-Output $cmd
Invoke-Expression $cmd
