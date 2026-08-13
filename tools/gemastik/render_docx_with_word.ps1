param(
    [Parameter(Mandatory = $true)]
    [string]$InputDirectory,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$inputRoot = (Resolve-Path -LiteralPath $InputDirectory).Path
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
[System.IO.Directory]::CreateDirectory($outputRoot) | Out-Null

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $files = Get-ChildItem -LiteralPath $inputRoot -Filter '*.docx' | Sort-Object Name
    foreach ($file in $files) {
        $document = $word.Documents.Open($file.FullName, $false, $false)
        try {
            foreach ($toc in $document.TablesOfContents) {
                $toc.Update()
            }
            foreach ($story in $document.StoryRanges) {
                $range = $story
                while ($null -ne $range) {
                    $range.Fields.Update() | Out-Null
                    $range = $range.NextStoryRange
                }
            }
            $document.Repaginate()
            $document.Save()
            $pdfPath = Join-Path $outputRoot ($file.BaseName + '.pdf')
            $document.ExportAsFixedFormat($pdfPath, 17)
            Write-Output "Rendered $($file.Name) -> $pdfPath"
        }
        finally {
            $document.Close(0)
        }
    }
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
