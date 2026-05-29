param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName WindowsBase

$Tagline = [System.Text.Encoding]::UTF8.GetString(
    [System.Convert]::FromBase64String("0J/QoNCe0KTQldCh0IbQmdCd0JUg0KDQhtCo0JXQndCd0K8g0JTQm9CvINCc0JXQkdCb0JXQktCe0JPQniDQktCY0KDQntCR0J3QmNCm0KLQktCQ")
)

function New-Brush($hex) {
    return [System.Windows.Media.SolidColorBrush](
        [System.Windows.Media.ColorConverter]::ConvertFromString($hex)
    )
}

function Draw-Path($context, $data, $fill, $scale, $offsetX, $offsetY) {
    $geometry = ([System.Windows.Media.Geometry]::Parse($data)).Clone()
    $geometry.Transform = New-Object System.Windows.Media.MatrixTransform($scale, 0, 0, $scale, $offsetX, $offsetY)
    $context.DrawGeometry((New-Brush $fill), $null, $geometry)
}

function Draw-MpSymbol($context, $scale, $offsetX, $offsetY, $metal = "#737d87", $green = "#39d353") {
    Draw-Path $context "M0 248V0h78l98 123L274 0h72v248h-80V108l-76 114h-28L82 108v140z" "#121a21" $scale ($offsetX + 12) ($offsetY + 16)
    Draw-Path $context "M365 304V0h152c82 0 136 48 136 124s-54 124-136 124h-72v56zm80-126h66c38 0 62-20 62-54s-24-54-62-54h-66z" "#121a21" $scale ($offsetX + 14) ($offsetY + 18)
    Draw-Path $context "M0 248V0h78l98 123L274 0h72v248h-80V108l-76 114h-28L82 108v140z" $metal $scale $offsetX $offsetY
    Draw-Path $context "M365 304V0h152c82 0 136 48 136 124s-54 124-136 124h-72v56zm80-126h66c38 0 62-20 62-54s-24-54-62-54h-66z" $metal $scale $offsetX $offsetY
    Draw-Path $context "M0 310l76-44v70L0 380z" "#0f6f1f" $scale ($offsetX + 8) ($offsetY + 14)
    Draw-Path $context "M0 310l76-44v70L0 380z" $green $scale $offsetX $offsetY
}

function Draw-Text($context, $text, $x, $y, $size, $weight, $color) {
    $typeface = New-Object System.Windows.Media.Typeface(
        (New-Object System.Windows.Media.FontFamily("Segoe UI")),
        [System.Windows.FontStyles]::Normal,
        $weight,
        [System.Windows.FontStretches]::Normal
    )
    $formatted = New-Object System.Windows.Media.FormattedText(
        $text,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Windows.FlowDirection]::LeftToRight,
        $typeface,
        $size,
        (New-Brush $color),
        1.0
    )
    $context.DrawText($formatted, (New-Object System.Windows.Point($x, $y)))
}

function Save-Png($relativePath, $width, $height, [scriptblock]$draw) {
    $visual = New-Object System.Windows.Media.DrawingVisual
    $context = $visual.RenderOpen()
    & $draw $context
    $context.Close()

    $bitmap = New-Object System.Windows.Media.Imaging.RenderTargetBitmap(
        $width,
        $height,
        96,
        96,
        [System.Windows.Media.PixelFormats]::Pbgra32
    )
    $bitmap.Render($visual)

    $encoder = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
    $encoder.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($bitmap))

    $path = Join-Path $Root $relativePath
    $stream = [System.IO.File]::Create($path)
    try {
        $encoder.Save($stream)
    }
    finally {
        $stream.Dispose()
    }
}

function Save-LogoPng($path, $darkBackground, $lightText) {
    Save-Png $path 1440 480 {
        param($context)
        if ($darkBackground) {
            $context.DrawRectangle((New-Brush "#0d141a"), $null, (New-Object System.Windows.Rect(0, 0, 1440, 480)))
        }
        elseif ($path -notlike "*transparent*") {
            $context.DrawRectangle((New-Brush "#f7fafc"), $null, (New-Object System.Windows.Rect(0, 0, 1440, 480)))
        }
        Draw-MpSymbol $context 0.62 68 54 "#737d87" "#39d353"
        $mainColor = if ($lightText) { "#f7fafc" } else { "#111820" }
        $mutedColor = if ($lightText) { "#a8b1ba" } else { "#46515c" }
        Draw-Text $context "MProject" 540 154 82 ([System.Windows.FontWeights]::Bold) $mainColor
        Draw-Text $context ".furniture" 890 154 82 ([System.Windows.FontWeights]::Bold) "#39d353"
        Draw-Text $context $Tagline 544 258 24 ([System.Windows.FontWeights]::Medium) $mutedColor
    }
}

Save-LogoPng "branding\logo\mproject-logo-transparent.png" $false $true
Save-LogoPng "branding\logo\mproject-logo-dark.png" $true $true
Save-LogoPng "branding\logo\mproject-logo-light.png" $false $false
Save-LogoPng "branding\logo\mproject-logo-flat.png" $true $true

Save-Png "branding\logo\mp-symbol-3d.png" 512 512 {
    param($context)
    Draw-MpSymbol $context 0.66 40 82 "#737d87" "#39d353"
}

Save-Png "branding\logo\mp-symbol-flat.png" 512 512 {
    param($context)
    Draw-MpSymbol $context 0.66 40 82 "#202932" "#39d353"
}

foreach ($size in 16, 32, 48, 64) {
    Save-Png "branding\icons\favicon-$size.png" $size $size {
        param($context)
        $context.DrawRoundedRectangle((New-Brush "#111820"), $null, (New-Object System.Windows.Rect(0, 0, $size, $size)), ($size * 0.22), ($size * 0.22))
        Draw-MpSymbol $context ($size / 760) ($size * 0.1) ($size * 0.23) "#737d87" "#39d353"
    }
}

foreach ($size in 192, 512) {
    Save-Png "branding\icons\app-icon-$size.png" $size $size {
        param($context)
        $context.DrawRoundedRectangle((New-Brush "#111820"), $null, (New-Object System.Windows.Rect(0, 0, $size, $size)), ($size * 0.2), ($size * 0.2))
        Draw-MpSymbol $context ($size / 760) ($size * 0.1) ($size * 0.23) "#737d87" "#39d353"
    }
}

Save-Png "branding\icons\app-icon-maskable-512.png" 512 512 {
    param($context)
    $context.DrawRectangle((New-Brush "#111820"), $null, (New-Object System.Windows.Rect(0, 0, 512, 512)))
    Draw-MpSymbol $context (512 / 760) (512 * 0.1) (512 * 0.23) "#737d87" "#39d353"
}

Save-Png "branding\social\telegram-avatar-512.png" 512 512 {
    param($context)
    $context.DrawEllipse((New-Brush "#111820"), $null, (New-Object System.Windows.Point(256, 256)), 256, 256)
    Draw-MpSymbol $context (512 / 760) (512 * 0.1) (512 * 0.23) "#737d87" "#39d353"
}

Save-Png "branding\social\social-preview.png" 1200 630 {
    param($context)
    $context.DrawRectangle((New-Brush "#0d141a"), $null, (New-Object System.Windows.Rect(0, 0, 1200, 630)))
    Draw-MpSymbol $context 0.54 84 118 "#737d87" "#39d353"
    Draw-Text $context "MProject" 520 230 72 ([System.Windows.FontWeights]::Bold) "#f7fafc"
    Draw-Text $context ".furniture" 820 230 72 ([System.Windows.FontWeights]::Bold) "#39d353"
    Draw-Text $context $Tagline 524 318 22 ([System.Windows.FontWeights]::Medium) "#a8b1ba"
}

Write-Output "Brand PNG assets generated."
