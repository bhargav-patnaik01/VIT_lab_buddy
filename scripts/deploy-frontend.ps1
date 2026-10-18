# Build the React app and publish it to the stack's S3 bucket, then invalidate CloudFront.
# Usage: .\scripts\deploy-frontend.ps1 -StackName cad-tracker
param([Parameter(Mandatory)][string]$StackName)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent

function Output($key) {
  aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs[?OutputKey=='$key'].OutputValue" --output text
}
$bucket = Output 'FrontendBucketName'
$dist = Output 'DistributionId'
if (-not $bucket -or -not $dist) { throw "Could not read stack outputs for $StackName" }

Push-Location "$root\frontend"
npm ci
npm run build
Pop-Location

# Hashed assets are immutable; index.html must always be revalidated.
aws s3 sync "$root\frontend\dist" "s3://$bucket" --delete --exclude index.html --cache-control "public,max-age=31536000,immutable"
aws s3 cp "$root\frontend\dist\index.html" "s3://$bucket/index.html" --cache-control "no-cache"
aws cloudfront create-invalidation --distribution-id $dist --paths "/index.html" | Out-Null
Write-Host "Published. Site: $(Output 'SiteUrl')"
