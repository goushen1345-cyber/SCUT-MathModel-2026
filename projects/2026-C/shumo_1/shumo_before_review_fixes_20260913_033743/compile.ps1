# Compile to build/ so Windows file lock on an open main.pdf cannot kill xelatex.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
New-Item -ItemType Directory -Force -Path "build" | Out-Null

$xelatex = Get-Command xelatex -ErrorAction SilentlyContinue
if (-not $xelatex) {
    throw "找不到 xelatex。请先安装 MiKTeX 并确保 xelatex 在 PATH 中。"
}

& xelatex -synctex=1 -interaction=nonstopmode -file-line-error -output-directory=build main.tex
if ($LASTEXITCODE -ne 0) { throw "xelatex 第一次编译失败，见 build/main.log" }
& xelatex -synctex=1 -interaction=nonstopmode -file-line-error -output-directory=build main.tex
if ($LASTEXITCODE -ne 0) { throw "xelatex 第二次编译失败，见 build/main.log" }

try {
    Copy-Item -Force "build\main.pdf" "main.pdf"
    Write-Output "已写入 build\main.pdf，并复制到 main.pdf"
} catch {
    Write-Warning "build\main.pdf 已生成，但 main.pdf 正被占用，无法覆盖。请关掉 PDF 预览后再运行本脚本，或直接看 build\main.pdf。"
}
