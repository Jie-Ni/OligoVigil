@echo off
REM ==========================================================================
REM push_to_github.cmd  --  OligoVigil v1 release push helper
REM
REM   This batch is NOT auto-run. The /paper skill honesty lock
REM   (do_not.yaml: no-public-publish) forbids the agent from pushing.
REM   Ni Jie runs this MANUALLY after:
REM     1) reviewing FINAL/v1_NAR_2026-06-07/00_SUBMISSION_CHECKLIST.md
REM     2) confirming no secrets / .env / tokens are staged
REM     3) setting GIT_REMOTE to the intended GitHub URL
REM
REM   Usage (cmd.exe; PowerShell users use $env:GIT_REMOTE then invoke this):
REM     set GIT_REMOTE=https://github.com/Jie-Ni/OligoVigil.git
REM     FINAL\v1_NAR_2026-06-07\push_to_github.cmd
REM
REM   If GIT_REMOTE is unset, the script ABORTS without making changes.
REM ==========================================================================

setlocal enabledelayedexpansion

if "%GIT_REMOTE%"=="" (
    echo [push_to_github] ABORT: environment variable GIT_REMOTE is not set.
    echo                  Set it first, for example:
    echo                      set GIT_REMOTE=https://github.com/Jie-Ni/OligoVigil.git
    echo                  then re-run this script.
    exit /b 2
)

REM Anchor to the repo root regardless of where this batch is invoked from.
cd /d "C:\Users\Jie\Desktop\NAR_OligoSafetyDB\repo_ready"
if errorlevel 1 (
    echo [push_to_github] ABORT: cannot cd into repo_ready/. Check the path.
    exit /b 3
)

echo [push_to_github] Working directory: %CD%
echo [push_to_github] Remote will be:    %GIT_REMOTE%
echo.

REM 1. git init (idempotent)
if not exist ".git" (
    echo [push_to_github] git init ...
    git init -b main
    if errorlevel 1 ( echo [push_to_github] ABORT: git init failed. & exit /b 4 )
) else (
    echo [push_to_github] .git already exists -- skipping init.
)

REM 2. stage everything (Ni Jie: verify .gitignore covers secrets / *.bak / large DBs)
echo [push_to_github] staging files ...
git add -A
if errorlevel 1 ( echo [push_to_github] ABORT: git add failed. & exit /b 5 )

REM 3. commit (skip if working tree is clean)
git diff --cached --quiet
if errorlevel 1 (
    echo [push_to_github] committing ...
    git commit -m "OligoVigil v1 release"
    if errorlevel 1 ( echo [push_to_github] ABORT: git commit failed. & exit /b 6 )
) else (
    echo [push_to_github] nothing to commit, working tree clean.
)

REM 4. add remote (idempotent)
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo [push_to_github] adding remote 'origin' -> %GIT_REMOTE%
    git remote add origin "%GIT_REMOTE%"
    if errorlevel 1 ( echo [push_to_github] ABORT: git remote add failed. & exit /b 7 )
) else (
    echo [push_to_github] remote 'origin' already configured:
    git remote get-url origin
)

REM 5. push
echo [push_to_github] pushing to origin/main ...
git push -u origin main
if errorlevel 1 (
    echo [push_to_github] ABORT: git push failed. Inspect output above.
    exit /b 8
)

echo.
echo [push_to_github] DONE. Verify on GitHub then mint a tag + Zenodo DOI.
endlocal
exit /b 0
