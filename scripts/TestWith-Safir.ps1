$cmd = @(
    "uv run stmx",
    "--verbose",
    "--render-tree",
    "analyze",
    "$PSScriptRoot/../../safir/rms/rms.toml"
)

Invoke-Expression $($cmd -join " ")
