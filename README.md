# Prop Labs — automatic league-wide NBA dashboard

Free GitHub Pages site with an ESPN-derived NBA box-score updater. This is **not an official ESPN integration**, and the feeds may change or become unavailable.

## Install into your existing GitHub Pages repo

1. Download and unzip `prop-labs-auto.zip`.
2. Open https://github.com/mkinder2006-del/prop-labs and choose **Add file → Upload files**. Upload `index.html`, `update_data.py`, `data/props.json`, and `README.md` at their indicated paths. **Important:** GitHub's web upload may not preserve the hidden `.github` folder. Create the workflow separately in step 3.
3. Choose **Add file → Create new file** and enter the exact filename `.github/workflows/update-nba.yml`. Paste the contents of that file from the ZIP and commit. Alternatively, use GitHub Desktop to commit the entire unzipped folder structure, which preserves `.github`.
4. In **Settings → Actions → General → Workflow permissions**, ensure GitHub Actions can write repository contents (the workflow requests `contents: write`; repository policies can override it).
5. Go to **Actions → Update Prop Labs NBA data → Run workflow** to initialize. The first run may take several minutes to backfill completed regular-season games.
6. Confirm the workflow is green and `data/props.json` now has `"status":"ok"` and a non-empty `rows` array. Refresh https://mkinder2006-del.github.io/prop-labs/.

## What updates

- Schedule: today's and next seven days' games.
- Box scores: completed regular-season games from all 30 NBA teams, starting October 1.
- League-wide integer prop thresholds for points, rebounds, assists, threes, steals, blocks, P+R, P+A, R+A and PRA, with hit rates >=80% (use **100% only** for perfect records).
- Source and timestamp displayed in the dashboard. No arbitrary minimum appearances; use **5+ games only** to filter.
- Automatic GitHub Actions run at UTC minute 17 and 47 (approximately every 30 minutes). GitHub can delay or skip scheduled runs and may disable schedules after 60 days of inactivity on public repos.

## Important limits

- ESPN endpoints are unofficial and subject to changes, access restrictions, and rate limiting. You must review ESPN's terms before sustained automated use. The workflow does not circumvent access controls.
- Stats are only as complete as successfully fetched box scores; check `fetchErrors` and `gamesCached` in `data/props.json`.
- Game logs are derived from **completed games only**. No real-time player prop progress or verified sportsbook odds.
- Thresholds are **custom statistical cutoffs**, not actual posted betting lines. A 100% historical hit rate does not imply a 100% future probability.
- Dashboard loads a published JSON snapshot when opened. The rocket button refreshes it. No paid hosting or API key is needed.
- If the workflow fails, the previous successful JSON remains in place, and the dashboard's timestamp exposes stale data.

## Troubleshooting

- `DATA NOT READY`: Run the workflow manually and inspect its logs. It may have failed to access ESPN or parse an updated response.
- `403` on Git push: Check workflow permissions and organization/repository policy.
- Site does not change: verify Pages deploys from the `main` branch root and allow a few minutes for GitHub Pages to publish.
