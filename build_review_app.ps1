$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    $page = Get-Content -LiteralPath '스팀 리뷰 분석.html' -Raw -Encoding utf8
    $startMarker = 'const D='
    $start = $page.IndexOf($startMarker,[StringComparison]::Ordinal)
    $end = $page.IndexOf(';const el=',[StringComparison]::Ordinal)
    if ($start -lt 0 -or $end -le $start) { throw 'Analysis data missing' }
    $start += $startMarker.Length
    $tempData = [IO.Path]::GetTempFileName()
    try {
        [IO.File]::WriteAllText($tempData,$page.Substring($start,$end-$start))
        $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
        & $compiler /nologo /target:winexe '/out:스팀 리뷰 분석.exe' "/resource:$tempData,reviews.json" /reference:System.Web.Extensions.dll /reference:System.Windows.Forms.dll /reference:System.Drawing.dll ReviewWindow.cs
        if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    } finally { Remove-Item -LiteralPath $tempData }
} finally { Pop-Location }
