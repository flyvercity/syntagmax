$cmd = @(
    "uv run gitreqms",
    "--verbose",
    "--suppress-required-children",
    "--allow-top-level-arch",
    "analyze",
    "$PSScriptRoot/../../safir/safir-fusion-rms/rms.toml"
)

Invoke-Expression $($cmd -join " ")
