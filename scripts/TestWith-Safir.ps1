$cmd = @(
    "uv run stmx",
    "--verbose",
    "--render-tree",
    "--ai",
    "analyze",
    "$PSScriptRoot/../../safir/rms/rms.toml"
)

Invoke-Expression $($cmd -join " ")
