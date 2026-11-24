$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$address='http://127.0.0.1:8767'
function Ready {
    try { return ((Invoke-RestMethod "$address/health" -TimeoutSec 1).service -eq 'klue-review-v1') } catch { return $false }
}
if (Ready) {Start-Process $address; exit 0}
$python=Join-Path $PWD '.bert_venv/Scripts/python.exe'
if (!(Test-Path $python) -and (Test-Path '.bert_lib/torch')) {
    $pkg=Get-AppxPackage 'OpenAI.CodexPrimaryRuntime*' -ErrorAction SilentlyContinue | Sort-Object Version -Descending | Select-Object -First 1
    if ($pkg) {
        $bundled=Join-Path $pkg.InstallLocation 'dependencies/python/python.exe'
        if (Test-Path $bundled) {$python=$bundled}
    }
}
if (!(Test-Path $python)) {
    Write-Host 'Preparing Python 3.12 environment...'
    py -3.12 -m venv .bert_venv
    if ($LASTEXITCODE -ne 0) {throw 'Install Python 3.12 for Windows, then run this launcher again.'}
}
& $python -c "import sys; sys.path.insert(0,'.bert_lib'); import importlib.util as u; sys.exit(0 if u.find_spec('transformers') and u.find_spec('torch') else 1)"
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install -r web/requirements.txt
    if ($LASTEXITCODE -ne 0) {throw 'Package installation failed.'}
}
$revision='77c8b3d707df785034b4e50f2da5d37be5f0f546'
New-Item -ItemType Directory -Force .bert_model,.bert_runs | Out-Null
foreach($n in 'config.json','tokenizer.json','special_tokens_map.json','tokenizer_config.json','vocab.txt','model.safetensors'){
    $file=Join-Path '.bert_model' $n
    if (!(Test-Path -LiteralPath $file)) {
        curl.exe -fLsS --retry 2 "https://huggingface.co/klue/bert-base/resolve/$revision/$n" -o "$file.part"
        if ($LASTEXITCODE -ne 0) {throw "Download failed: $n"}
        Move-Item -LiteralPath "$file.part" -Destination $file
    }
}
Set-Content -LiteralPath '.bert_model/revision.txt' -Value $revision -Encoding ascii
$proc=Start-Process -FilePath $python -ArgumentList 'web/app.py' -WorkingDirectory $PWD.Path -WindowStyle Hidden -RedirectStandardError '.bert_runs/app-error.log' -PassThru
for($i=0;$i -lt 180;$i++){
    if(Ready){Start-Process $address;exit 0}
    if($proc.HasExited){throw (Get-Content '.bert_runs/app-error.log' -Tail 8 | Out-String)}
    Start-Sleep -Seconds 1
}
throw "Startup took longer than expected. Check .bert_runs/app-error.log"

