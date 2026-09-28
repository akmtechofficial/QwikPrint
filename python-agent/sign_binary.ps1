param (
    [string]$FilePath
)

if (-not (Test-Path $FilePath)) {
    Write-Error "Target binary file not found: $FilePath"
    exit 1
}

Write-Host "=========================================================="
Write-Host "      AUTHENTICODE DIGITALLY SIGNING EXECUTABLE BINARY     "
Write-Host "=========================================================="
Write-Host "Target Binary: $FilePath"

# 1. Locate existing Code Signing Certificate or create official certificate
$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -like "*QwikPrint*" -or $_.Subject -like "*Akm Tech*" } | Select-Object -First 1

if (-not $cert) {
    Write-Host "[Cert] Creating New Authenticode Code Signing Certificate for Akm Tech / QwikPrint..."
    $cert = New-SelfSignedCertificate -Type CodeSigningCert `
        -Subject "CN=Akm Tech QwikPrint Official Code Authority, O=QwikPrint Inc, C=IN" `
        -KeyUsage DigitalSignature `
        -FriendlyName "QwikPrint Official Code Signing Certificate" `
        -CertStoreLocation Cert:\CurrentUser\My `
        -NotAfter (Get-Date).AddYears(5)
}

Write-Host "[Cert] Certificate Thumbprint: $($cert.Thumbprint)"
Write-Host "[Cert] Subject: $($cert.Subject)"

# 2. Export public certificate to .cer for installer distribution
$cerPath = Join-Path (Split-Path $FilePath) "QwikPrint_Code_Authority.cer"
Export-Certificate -Cert $cert -FilePath $cerPath -Force | Out-Null
Write-Host "[Cert] Exported public certificate to: $cerPath"

# 3. Apply Authenticode Digital Signature to the target .exe binary
$sigResult = Set-AuthenticodeSignature -FilePath $FilePath -Certificate $cert
Write-Host "[Signature Status] $($sigResult.Status)"
Write-Host "[Signature Detail] $($sigResult.StatusMessage)"

if ($sigResult.Status -eq "Valid") {
    Write-Host "[SUCCESS] Executable successfully signed with VALID Authenticode signature!"
} else {
    Write-Host "[INFO] Authenticode signature applied to binary."
}
Write-Host "=========================================================="
