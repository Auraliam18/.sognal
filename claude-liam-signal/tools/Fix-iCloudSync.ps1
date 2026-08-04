<#
.SYNOPSIS
  پیدا کردن دقیقِ فایلی که آی‌کلاد نمی‌تواند سینک کند — و درست کردنش.

.DESCRIPTION
  آی‌کلاد ویندوز وقتی یک پوشه را رد می‌کند، نمی‌گوید کدام فایل مقصر است. فقط
  می‌گوید «Folder Not Synced» و کل پوشه می‌ماند. این اسکریپت همان چیزی را
  می‌گوید که آی‌کلاد نمی‌گوید.

  پنج علتی که واقعاً اتفاق می‌افتند — به‌خصوص برای خروجی n8n، چون n8n اسم
  ورک‌فلو را مستقیم می‌گذارد روی اسم فایل و اسم ورک‌فلو هر چیزی می‌تواند باشد:

    ۱. کاراکتر غیرمجاز در اسم    مثل  : * ? " < > |
    ۲. مسیر بلندتر از ۲۵۵ کاراکتر
    ۳. اسم تکراری با حروف بزرگ/کوچک متفاوت
    ۴. نقطه یا فاصله در انتهای اسم
    ۵. اسم رزروشدهٔ ویندوز        CON, PRN, AUX, NUL, COM1..9, LPT1..9

  پیش‌فرض فقط گزارش می‌دهد. برای اینکه واقعاً تغییر بدهد باید -Fix بزنی، و
  حتی آن وقت هم اول می‌گوید چه کار می‌خواهد بکند.

.EXAMPLE
  # فقط ببین مشکل کجاست
  .\Fix-iCloudSync.ps1 -Path "C:\Users\hrooz\iCloudDrive\auraliam\n8n-shadow-lab"

.EXAMPLE
  # درستش کن
  .\Fix-iCloudSync.ps1 -Path "C:\Users\hrooz\iCloudDrive\auraliam\n8n-shadow-lab" -Fix

.EXAMPLE
  # پوشه‌های بکاپ قدیمی را زیپ کن — یک فایل هیچ‌وقت مشکل سینک ندارد
  .\Fix-iCloudSync.ps1 -Path "C:\Users\hrooz\iCloudDrive\auraliam\n8n-shadow-lab" -ZipSnapshots
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [switch]$Fix,
    [switch]$ZipSnapshots,
    [int]$MaxPath = 255
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Path)) { throw "پیدا نشد: $Path" }

$Bad      = '[:\*\?"<>\|]'
$Reserved = @('CON','PRN','AUX','NUL') + (1..9 | ForEach-Object { "COM$_"; "LPT$_" })
$problems = New-Object System.Collections.Generic.List[object]

function Add-Problem($kind, $item, $detail, $suggest) {
    $problems.Add([pscustomobject]@{
        Kind = $kind; FullName = $item.FullName; Detail = $detail; Suggest = $suggest
    })
}

Write-Host ""
Write-Host "بررسی: $Path" -ForegroundColor Cyan
Write-Host ("=" * 78)

$all = Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue

foreach ($i in $all) {
    $name = $i.Name

    # ۱ — کاراکتر غیرمجاز
    if ($name -match $Bad) {
        $clean = ($name -replace $Bad, '-')
        Add-Problem 'کاراکتر غیرمجاز' $i "اسم شامل $([regex]::Matches($name,$Bad).Value -join ' ')" $clean
    }

    # ۴ — نقطه یا فاصله در انتها. ویندوز می‌سازد، آی‌کلاد رد می‌کند، و چون با
    #     چشم دیده نمی‌شود معمولاً آخرین چیزی است که آدم بهش شک می‌کند.
    #
    #     هم انتهای کل اسم را نگاه می‌کند هم انتهای بخش قبل از پسوند: فایلی مثل
    #     «Daily Report .json» به چشم سالم می‌آید و نیست. اولین نسخهٔ همین
    #     اسکریپت این را رد می‌کرد، تا وقتی روی نمونه‌های واقعی امتحانش کردم.
    $stemRaw = [System.IO.Path]::GetFileNameWithoutExtension($name)
    $extRaw  = [System.IO.Path]::GetExtension($name)
    if ($name -match '[ \.]$' -or $stemRaw -match '[ ]$') {
        $suggest = if ($name -match '[ \.]$') { $name.TrimEnd(' ', '.') }
                   else { $stemRaw.TrimEnd(' ') + $extRaw }
        Add-Problem 'انتهای اسم' $i "فاصله یا نقطهٔ نامرئی در انتهای اسم" $suggest
    }

    # ۵ — اسم رزروشده
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($name)
    if ($Reserved -contains $stem.ToUpper()) {
        Add-Problem 'اسم رزروشده' $i "«$stem» اسم دستگاه در ویندوز است" ("_" + $name)
    }

    # ۲ — مسیر بلند
    if ($i.FullName.Length -gt $MaxPath) {
        Add-Problem 'مسیر بلند' $i "$($i.FullName.Length) کاراکتر (سقف $MaxPath)" '—'
    }
}

# ۳ — هم‌نامیِ حروف بزرگ و کوچک. ویندوز و آی‌کلاد هر دو به بزرگی حروف حساس
#     نیستند، ولی خروجی ابزارهایی مثل n8n که روی لینوکس ساخته شده می‌تواند هر
#     دو را داشته باشد. آن وقت یکی‌شان هیچ‌وقت سینک نمی‌شود.
$all | Group-Object { $_.DirectoryName } | ForEach-Object {
    $_.Group | Group-Object { $_.Name.ToLower() } | Where-Object { $_.Count -gt 1 } | ForEach-Object {
        foreach ($d in $_.Group) {
            Add-Problem 'هم‌نامی بزرگ/کوچک' $d ("همراه با: " + (($_.Group.Name) -join ' | ')) '—'
        }
    }
}

if ($problems.Count -eq 0) {
    Write-Host "هیچ‌کدام از علت‌های شناخته‌شده پیدا نشد." -ForegroundColor Green
    Write-Host ""
    Write-Host "اگر باز سینک نمی‌شود، معمولاً یکی از این‌هاست:"
    Write-Host "  • فایلی باز است در برنامه‌ای دیگر — همه را ببند و آی‌کلاد را ری‌استارت کن"
    Write-Host "  • فضای آی‌کلاد پر است — iCloud.exe را باز کن و ببین"
    Write-Host "  • لینک یا junction در پوشه هست — آی‌کلاد این‌ها را سینک نمی‌کند:"
    Write-Host "      Get-ChildItem -Recurse -Force '$Path' | Where-Object { `$_.LinkType }"
} else {
    $problems | Group-Object Kind | ForEach-Object {
        Write-Host ""
        Write-Host "$($_.Name) — $($_.Count) مورد" -ForegroundColor Yellow
        $_.Group | Select-Object -First 12 | ForEach-Object {
            Write-Host "  $($_.FullName)"
            Write-Host "      $($_.Detail)"
            if ($_.Suggest -ne '—') { Write-Host "      پیشنهاد: $($_.Suggest)" -ForegroundColor DarkGray }
        }
        if ($_.Count -gt 12) { Write-Host "  … و $($_.Count - 12) مورد دیگر" }
    }
}

Write-Host ""
Write-Host ("=" * 78)
Write-Host "جمع: $($problems.Count) مورد"

# ── درست کردن ───────────────────────────────────────────────────────────────

if ($Fix) {
    $renamable = $problems | Where-Object { $_.Suggest -ne '—' }
    if ($renamable.Count -eq 0) {
        Write-Host "چیزی برای تغییر نام نیست." -ForegroundColor Yellow
    } else {
        Write-Host ""
        Write-Host "تغییر نام $($renamable.Count) مورد:" -ForegroundColor Cyan
        # از عمیق به کم‌عمق، وگرنه تغییر نام یک پوشه مسیر فایل‌های داخلش را
        # عوض می‌کند و بقیهٔ مسیرهای ذخیره‌شده باطل می‌شوند.
        $renamable | Sort-Object { $_.FullName.Length } -Descending | ForEach-Object {
            $dir = Split-Path -LiteralPath $_.FullName -Parent
            $to  = Join-Path $dir $_.Suggest
            $n = 1
            while (Test-Path -LiteralPath $to) {
                $b = [System.IO.Path]::GetFileNameWithoutExtension($_.Suggest)
                $e = [System.IO.Path]::GetExtension($_.Suggest)
                $to = Join-Path $dir "$b($n)$e"; $n++
            }
            try {
                Rename-Item -LiteralPath $_.FullName -NewName (Split-Path $to -Leaf) -ErrorAction Stop
                Write-Host "  ✓ $(Split-Path $_.FullName -Leaf)  →  $(Split-Path $to -Leaf)"
            } catch {
                Write-Host "  ✗ $($_.FullName): $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    }
}

# ── زیپ کردن اسنپ‌شات‌ها ────────────────────────────────────────────────────

if ($ZipSnapshots) {
    # پوشه‌هایی مثل 20260731-040447-before-TwinMap18R1x26 بکاپ‌اند، نه چیزی که
    # روزانه بازشان کنی. یک فایل زیپ هیچ‌وقت مشکل طول مسیر، کاراکتر غیرمجاز یا
    # هم‌نامی ندارد — و این ریشه را می‌خشکاند به‌جای اینکه هر بار برگی بچینیم.
    Write-Host ""
    Write-Host "زیپ کردن پوشه‌های اسنپ‌شات:" -ForegroundColor Cyan
    Get-ChildItem -LiteralPath $Path -Directory |
        Where-Object { $_.Name -match '^\d{8}-\d{6}' } | ForEach-Object {
            $zip = "$($_.FullName).zip"
            if (Test-Path -LiteralPath $zip) { Write-Host "  – $($_.Name) از قبل زیپ شده"; return }
            try {
                Compress-Archive -Path "$($_.FullName)\*" -DestinationPath $zip -Force -ErrorAction Stop
                Write-Host "  ✓ $($_.Name).zip ساخته شد"
                Write-Host "      پوشهٔ اصلی دست‌نخورده ماند. بعد از اینکه زیپ سینک شد، خودت پاکش کن:"
                Write-Host "      Remove-Item -LiteralPath '$($_.FullName)' -Recurse -Force" -ForegroundColor DarkGray
            } catch {
                Write-Host "  ✗ $($_.Name): $($_.Exception.Message)" -ForegroundColor Red
            }
        }
}

Write-Host ""
Write-Host "بعد از تغییرات، آی‌کلاد را ری‌استارت کن تا دوباره اسکن کند:"
Write-Host "  Get-Process iCloud* | Stop-Process -Force; Start-Sleep 3" -ForegroundColor DarkGray
Write-Host "  Start-Process 'C:\Program Files (x86)\Common Files\Apple\Internet Services\iCloudDrive.exe'" -ForegroundColor DarkGray
Write-Host ""
