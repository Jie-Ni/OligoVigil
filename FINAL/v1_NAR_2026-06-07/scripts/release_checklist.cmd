@echo off
REM ============================================================================
REM OligoVigil v1.0.0 — release checklist (Windows .cmd)
REM ----------------------------------------------------------------------------
REM Paper-skill do_not.yaml: this script DOES NOT push, mint, or deploy on its
REM own. It prints the exact commands you run, after you set two env vars.
REM ============================================================================

setlocal
echo.
echo ===== OligoVigil v1.0.0 release checklist =====
echo Repo: %~dp0..\..\..
echo.

REM ----- Step 1: GitHub push (manual) -----
echo --- 1. Push to GitHub ----------------------------------------------------
echo Set GIT_REMOTE first, e.g.:
echo     set GIT_REMOTE=https://github.com/^<your-user^>/oligovigil.git
echo Then run:
echo     %~dp0..\push_to_github.cmd
echo (This is the script the parent kit already ships at FINAL/.../push_to_github.cmd.)
echo.

REM ----- Step 2: Tag v1.0.0 -----
echo --- 2. Tag v1.0.0 --------------------------------------------------------
echo After the initial push, tag and push the tag:
echo     git tag -a v1.0.0 -m "OligoVigil v1.0.0 — NAR Database Issue submission release"
echo     git push origin v1.0.0
echo.

REM ----- Step 3: Mint Zenodo DOI -----
echo --- 3. Mint Zenodo DOI ---------------------------------------------------
echo Recommended path: link the GitHub repo to your Zenodo account once
echo  (https://zenodo.org/account/settings/github/), then PUBLISHING a release
echo  on GitHub mints the DOI automatically. The .zenodo.json shipped at
echo     FINAL/v1_NAR_2026-06-07/.zenodo.json
echo  is the metadata Zenodo will read (review it first; fill the [TBD]).
echo.
echo Alternative API path (you set ZENODO_TOKEN first):
echo     set ZENODO_TOKEN=^<your-personal-token^>
echo     curl -X POST "https://zenodo.org/api/deposit/depositions" ^
echo          -H "Authorization: Bearer %%ZENODO_TOKEN%%" ^
echo          -H "Content-Type: application/json" ^
echo          -d "@FINAL/v1_NAR_2026-06-07/.zenodo.json"
echo Then upload the zipped repo as the deposition file and PUBLISH via the UI
echo to get a citeable DOI of the form 10.5281/zenodo.NNNNNN .
echo.

REM ----- Step 4: Update manuscript + cover with the real URLs -----
echo --- 4. Replace [TBD] with real identifiers -------------------------------
echo After steps 1-3 succeed, replace these literal placeholders in:
echo     04_delivery/MANUSCRIPT_DRAFT_v4.md
echo     FINAL/v1_NAR_2026-06-07/04_cover_letter.md
echo     FINAL/v1_NAR_2026-06-07/03_title_page.md
echo     FINAL/v1_NAR_2026-06-07/metadata_ledger.md
echo     FINAL/v1_NAR_2026-06-07/declarations/03_data_availability.md
echo     CITATION.cff
echo with:
echo     public HTTPS URL            -- https://oligovigil.pages.dev/
echo     [TBD: GitHub URL]           -- e.g. https://github.com/^<owner^>/oligovigil
echo     Zenodo DOI                  -- 10.5281/zenodo.20633779
echo.
echo Then recompile the manuscript PDF and re-run the audit:
echo     pandoc 04_delivery/MANUSCRIPT_DRAFT_v4_compile.md -o 04_delivery/MANUSCRIPT_DRAFT_v4.pdf --pdf-engine=xelatex -V mainfont="Times New Roman" -V fontsize=11pt -V geometry:margin=1in
echo     python C:\Users\Jie\.claude\skills\paper\submission_kit_audit.py --dir FINAL/v1_NAR_2026-06-07 --journal NAR_database
echo.

echo ===== End of release checklist =====
endlocal
