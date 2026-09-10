$ErrorActionPreference = 'Stop'
$taskPaperDir = Split-Path -Parent $PSCommandPath
$taskDocxPath = [IO.Path]::GetFullPath((Join-Path $taskPaperDir 'final_v2/2024-C-paper-v2.docx'))
$taskPdfPath = [IO.Path]::GetFullPath((Join-Path $taskPaperDir 'final_v2/2024-C-paper-v2.pdf'))
$taskWord = $null
$taskDocument = $null
$taskOwnInstance = $false
try {
    $taskWord = New-Object -ComObject Word.Application
    if ($taskWord.Documents.Count -ne 0) { throw 'Word instance contains other documents; refusing to use it.' }
    $taskOwnInstance = $true
    $taskWord.Visible = $false
    $taskWord.DisplayAlerts = 0
    $taskDocument = $taskWord.Documents.Open($taskDocxPath, $false, $true)
    $taskDocument.Fields.Update() | Out-Null
    $taskDocument.Repaginate()
    $taskDocument.ExportAsFixedFormat($taskPdfPath, 17)
    $taskResult = [ordered]@{ renderer='Microsoft Word'; word_version=$taskWord.Version; docx=$taskDocxPath; pdf=$taskPdfPath; pages=$taskDocument.ComputeStatistics(2); source_opened_read_only=$true }
    $taskResult | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskPaperDir 'final_v2/export_status.json') -Encoding utf8
    $taskResult | ConvertTo-Json -Compress
} finally {
    if ($null -ne $taskDocument) { $taskDocument.Close(0); [Runtime.InteropServices.Marshal]::ReleaseComObject($taskDocument) | Out-Null }
    if ($null -ne $taskWord -and $taskOwnInstance) { $taskWord.Quit(); [Runtime.InteropServices.Marshal]::ReleaseComObject($taskWord) | Out-Null }
}
