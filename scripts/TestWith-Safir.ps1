$cmd = @(
    "uv run stmx",
    "--verbose",
    "analyze",
    "$PSScriptRoot/../../safir/rms/rms.toml"
)

Invoke-Expression $($cmd -join " ")
