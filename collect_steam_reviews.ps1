param([int]$TargetPerGame = 2000)
$ErrorActionPreference = 'Stop'
$outputDir = Join-Path $PSScriptRoot 'steam_review_data'
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$games = @(
    @{ AppId = 1245620; Name = 'ELDEN RING'; File = 'elden_ring' },
    @{ AppId = 413150; Name = 'Stardew Valley'; File = 'stardew_valley' },
    @{ AppId = 578080; Name = 'PUBG: BATTLEGROUNDS'; File = 'pubg' }
)
$allRows = [System.Collections.Generic.List[object]]::new()
$collectionSummary = [System.Collections.Generic.List[object]]::new()
foreach ($game in $games) {
    $rows = [System.Collections.Generic.List[object]]::new()
    $seenIds = [System.Collections.Generic.HashSet[string]]::new()
    $cursor = '*'
    $querySummary = $null
    $startedUtc = [DateTimeOffset]::UtcNow.ToString('o')
    $page = 0
    while ($rows.Count -lt $TargetPerGame) {
        $requestParameters = @{
            appid = $game.AppId
            languages = @('koreana')
            filter = 1
            review_type = 0
            purchase_type = 1
            num_per_page = [Math]::Min(100, $TargetPerGame - $rows.Count)
            cursor = $cursor
            filter_offtopic_activity = $true
        }
        $requestJson = $requestParameters | ConvertTo-Json -Compress
        $url = 'https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/?input_json=' + [uri]::EscapeDataString($requestJson)
        $envelope = $null
        for ($attempt = 0; $attempt -lt 5; $attempt++) {
            try {
                $envelope = Invoke-RestMethod -Uri $url -TimeoutSec 45
                break
            } catch {
                if ($attempt -eq 4) { throw }
                Start-Sleep -Seconds ([Math]::Min(30, [Math]::Pow(2, $attempt + 1)))
            }
        }
        $response = if ($null -ne $envelope.response) { $envelope.response } else { $envelope }
        if ($null -eq $response.reviews) { throw "Unexpected response for $($game.Name)" }
        if ($null -eq $querySummary) { $querySummary = $response.query_summary }
        if (@($response.reviews).Count -eq 0) { break }
        $collectedAt = [DateTimeOffset]::UtcNow.ToString('o')
        foreach ($review in $response.reviews) {
            if (-not $seenIds.Add([string]$review.recommendationid)) { continue }
            $minutes = $review.author.playtime_at_review
            $hours = if ($null -ne $minutes) { [Math]::Round([double]$minutes / 60, 2) } else { $null }
            $group = if ($null -eq $minutes) { 'unknown' } elseif ($minutes -lt 600) { 'under_10h' } elseif ($minutes -lt 3000) { '10_to_50h' } else { '50h_plus' }
            $row = [pscustomobject][ordered]@{
                app_id = $game.AppId
                game_name = $game.Name
                review_id = [string]$review.recommendationid
                language = $review.language
                review_text = [string]$review.review
                recommended = [bool]$review.voted_up
                created_at_utc = [DateTimeOffset]::FromUnixTimeSeconds([long]$review.timestamp_created).ToString('o')
                updated_at_utc = [DateTimeOffset]::FromUnixTimeSeconds([long]$review.timestamp_updated).ToString('o')
                playtime_at_review_minutes = $minutes
                playtime_at_review_hours = $hours
                playtime_group = $group
                helpful_votes = $review.votes_up
                funny_votes = $review.votes_funny
                steam_purchase = $review.steam_purchase
                received_for_free = $review.received_for_free
                written_during_early_access = $review.written_during_early_access
                collected_at_utc = $collectedAt
                has_hangul = ([string]$review.review -match '[\uAC00-\uD7A3\u3131-\u318E]')
                short_review = (([string]$review.review).Trim().Length -lt 10)
            }
            $rows.Add($row)
            $allRows.Add($row)
        }
        $page++
        Write-Output "$($game.Name): $($rows.Count) / $TargetPerGame reviews"
        $rows | Export-Csv -LiteralPath (Join-Path $outputDir "$($game.File)_raw.csv") -NoTypeInformation -Encoding utf8BOM
        if ([string]::IsNullOrEmpty($response.cursor) -or $response.cursor -eq $cursor) { break }
        $cursor = $response.cursor
        if ($page -gt 100) { throw 'Pagination safety limit reached' }
        Start-Sleep -Milliseconds 1500
    }
    $collectionSummary.Add([pscustomobject]@{
        app_id = $game.AppId
        game_name = $game.Name
        collected_count = $rows.Count
        query_summary = $querySummary
        started_at_utc = $startedUtc
        finished_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    })
}
$allRows | Export-Csv -LiteralPath (Join-Path $outputDir 'reviews_raw.csv') -NoTypeInformation -Encoding utf8BOM
$seenTexts = [System.Collections.Generic.HashSet[string]]::new()
$cleanRows = [System.Collections.Generic.List[object]]::new()
$excluded = [System.Collections.Generic.List[object]]::new()
foreach ($row in $allRows) {
    $normalized = ($row.review_text -replace '\s+', ' ').Trim()
    $reason = if ([string]::IsNullOrWhiteSpace($normalized)) { 'empty' } elseif ($normalized -notmatch '[\p{L}\p{N}]') { 'symbols_only' } elseif (-not $seenTexts.Add("$($row.app_id)|$normalized")) { 'duplicate_text_within_game' } else { $null }
    if ($null -ne $reason) {
        $excluded.Add([pscustomobject]@{app_id=$row.app_id; review_id=$row.review_id; reason=$reason})
    } else {
        $cleanRows.Add($row)
    }
}
$cleanRows | Export-Csv -LiteralPath (Join-Path $outputDir 'reviews_clean.csv') -NoTypeInformation -Encoding utf8BOM
if ($excluded.Count -gt 0) { $excluded | Export-Csv -LiteralPath (Join-Path $outputDir 'excluded_reviews.csv') -NoTypeInformation -Encoding utf8BOM }
$stats = foreach ($game in $games) {
    $subset = @($cleanRows | Where-Object app_id -eq $game.AppId)
    [pscustomobject]@{
        app_id = $game.AppId
        game_name = $game.Name
        raw_count = @($allRows | Where-Object app_id -eq $game.AppId).Count
        clean_count = $subset.Count
        recommended_count = @($subset | Where-Object recommended -eq $true).Count
        not_recommended_count = @($subset | Where-Object recommended -eq $false).Count
        under_10h = @($subset | Where-Object playtime_group -eq 'under_10h').Count
        between_10_and_50h = @($subset | Where-Object playtime_group -eq '10_to_50h').Count
        at_least_50h = @($subset | Where-Object playtime_group -eq '50h_plus').Count
        missing_playtime = @($subset | Where-Object playtime_group -eq 'unknown').Count
        without_hangul = @($subset | Where-Object has_hangul -eq $false).Count
        short_review_count = @($subset | Where-Object short_review -eq $true).Count
        oldest_review_utc = ($subset.created_at_utc | Sort-Object | Select-Object -First 1)
        newest_review_utc = ($subset.created_at_utc | Sort-Object | Select-Object -Last 1)
    }
}
$stats | Export-Csv -LiteralPath (Join-Path $outputDir 'summary.csv') -NoTypeInformation -Encoding utf8BOM
[ordered]@{
    endpoint = 'https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/'
    language = 'koreana'
    ordering = 'recent'
    purchase_type = 'all'
    review_type = 'all'
    filter_offtopic_activity = $true
    target_per_game = $TargetPerGame
    raw_count = $allRows.Count
    clean_count = $cleanRows.Count
    excluded_count = $excluded.Count
    games = @($collectionSummary)
} | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $outputDir 'collection_metadata.json') -Encoding utf8
$stats | Format-Table -AutoSize | Out-String | Write-Output
