# API Contract — Scan Results Viewer

## GET /api/scans

Returns all scan results grouped by scan run.

```json
{
  "scans": [
    {
      "filename": "dip_scan_2026-06-26_20260628_215406.csv",
      "scan_date": "2026-06-26",
      "run_time": "2026-06-28T21:54:06",
      "hits": [
        {
          "ticker": "GUNKUL.BK",
          "close": 4.28,
          "stop": 3.82,
          "riskU": 0.46,
          "t1": 4.74,
          "t2": 4.97,
          "size": 21739,
          "distPct": 9.66,
          "rsi": 69.01,
          "adx": 46.60
        }
      ]
    }
  ]
}
```

Sorted newest `run_time` first. Empty `hits` array for CSVs with no signals.

## GET /api/events (SSE)

Server-Sent Events stream. Sends `event: reload\ndata: {}\n\n` when a new
`dip_scan_*.csv` file is created or modified in the watched directory.

## GET /

Serves the HTML viewer page.
