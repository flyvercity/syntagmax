$cmd_args = @(
    'uv run python -m gitreqms',
    '--verbose',
    '--suppress-required-children',
    '--allow-top-level-arch',
    'analyze',
    "$PSScriptRoot/../../safir/safir-fusion-rms/rms.toml"
)

$cmd = $cmd_args -join ' '
Write-Output $cmd
Invoke-Expression $cmd
