@echo off
REM update_graph.bat - Update Repository Knowledge Graph (Windows)
REM
REM This script regenerates the knowledge graph after code changes.
REM It tracks the current and previous graphs for easy comparison.
REM
REM Usage:
REM   update_graph.bat              - Update current directory
REM   update_graph.bat backend      - Update backend folder
REM   update_graph.bat backend /compare - Update and compare with previous
REM
REM Features:
REM   - Automatic timestamp-based naming
REM   - Keeps previous graph for comparison
REM   - Auto-compares if requested
REM   - Generates HTML report
REM

setlocal enabledelayedexpansion

REM Configuration
set REPO_PATH=%1
if "%REPO_PATH%"=="" set REPO_PATH=.

set COMPARE_FLAG=%2

REM Generate timestamp (YYYYMMDD_HHMMSS)
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set TIMESTAMP=%mydate%_%mytime%

set OUTPUT_DIR=graph_output
set PYTHON_SCRIPT=graph_generator.py

REM Check if Python script exists
if not exist "%PYTHON_SCRIPT%" (
    color 0C
    echo.
    echo ERROR: %PYTHON_SCRIPT% not found in current directory
    echo.
    color 07
    exit /b 1
)

REM Check if repo path exists
if not exist "%REPO_PATH%" (
    color 0C
    echo.
    echo ERROR: Repository path '%REPO_PATH%' not found
    echo.
    color 07
    exit /b 1
)

REM Create output directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

cls
color 0B
echo.
echo ===============================================================
echo Repository Knowledge Graph Update
echo ===============================================================
echo.
color 07
echo Repository: %REPO_PATH%
echo Output Dir: %OUTPUT_DIR%
echo Timestamp:  %TIMESTAMP%
echo.

REM ======================================================================
REM Step 1: Backup previous graph
REM ======================================================================
color 0A
echo [1/4] Backing up previous graph...
color 07

if exist "%OUTPUT_DIR%\current_graph.json" (
    copy "%OUTPUT_DIR%\current_graph.json" "%OUTPUT_DIR%\previous_graph.json" >nul
    echo [OK] Previous graph backed up
) else (
    echo [INFO] No previous graph found (first run)
)
echo.

REM ======================================================================
REM Step 2: Generate new graph
REM ======================================================================
color 0A
echo [2/4] Analyzing repository and generating new graph...
color 07
echo.

setlocal
set start_time=%time%

python "%PYTHON_SCRIPT%" "%REPO_PATH%" "%OUTPUT_DIR%" 

setlocal endlocal

REM Find the latest generated graph
for /f %%F in ('dir /b /o-d "%OUTPUT_DIR%\graph_*.json" 2^>nul ^| findstr /v /c:"current" /c:"previous"') do (
    set LATEST_GRAPH=%%F
    goto :found_graph
)

:found_graph
if "%LATEST_GRAPH%"=="" (
    color 0C
    echo.
    echo ERROR: No graph file generated
    echo.
    color 07
    exit /b 1
)

copy "%OUTPUT_DIR%\%LATEST_GRAPH%" "%OUTPUT_DIR%\current_graph.json" >nul

REM Find latest report
for /f %%F in ('dir /b /o-d "%OUTPUT_DIR%\report_*.html" 2^>nul') do (
    set LATEST_REPORT=%%F
    goto :found_report
)

:found_report
if not "%LATEST_REPORT%"=="" (
    copy "%OUTPUT_DIR%\%LATEST_REPORT%" "%OUTPUT_DIR%\current_report.html" >nul
)

color 0A
echo [OK] Graph generated
color 07
echo.

REM ======================================================================
REM Step 3: Extract statistics
REM ======================================================================
color 0A
echo [3/4] Extracting statistics...
color 07
echo.

python <<PYTHON_END
import json
try:
    with open("graph_output/current_graph.json") as f:
        data = json.load(f)
    
    stats = data['metadata']['stats']
    metrics = data['metadata']['metrics']
    
    print(f"Files Analyzed:    {stats['files_analyzed']}")
    print(f"Classes Found:     {stats['classes_found']}")
    print(f"Functions Found:   {stats['functions_found']}")
    print(f"Imports Found:     {stats['imports_found']}")
    print(f"Graph Nodes:       {metrics['nodes']}")
    print(f"Graph Edges:       {metrics['edges']}")
    print(f"Parsing Errors:    {stats['errors']}")
except Exception as e:
    print(f"Error: {e}")
PYTHON_END

echo.

REM ======================================================================
REM Step 4: Compare with previous (optional)
REM ======================================================================
if /i "%COMPARE_FLAG%"=="/compare" (
    if /i "%COMPARE_FLAG%"=="/c" (
        goto :do_compare
    )
    :do_compare
    if exist "%OUTPUT_DIR%\previous_graph.json" (
        color 0A
        echo [4/4] Comparing with previous graph...
        color 07
        echo.
        
        python compare_graphs.py "%OUTPUT_DIR%\previous_graph.json" "%OUTPUT_DIR%\current_graph.json"
        
        if exist "graph_comparison_report.txt" (
            move "graph_comparison_report.txt" "%OUTPUT_DIR%\comparison_%TIMESTAMP%.txt" >nul
            echo.
            color 0A
            echo [OK] Comparison report saved: %OUTPUT_DIR%\comparison_%TIMESTAMP%.txt
            color 07
        )
    ) else (
        color 0A
        echo [4/4] Skipping comparison (no previous graph)
        color 07
    )
) else (
    color 0A
    echo [4/4] Skipping comparison (use /compare flag to enable)
    color 07
)

echo.
cls
color 0B
echo.
echo ===============================================================
echo [OK] Graph update complete!
echo ===============================================================
echo.
color 07

if "%LATEST_REPORT%"=="" (
    echo Generated files:
    echo   - Graph:   %OUTPUT_DIR%\%LATEST_GRAPH%
) else (
    echo Generated files:
    echo   - Graph:   %OUTPUT_DIR%\%LATEST_GRAPH%
    echo   - Report:  %OUTPUT_DIR%\%LATEST_REPORT%
)

echo.
echo Quick links:
echo   - Current:       graph_output\current_graph.json
echo   - Previous:      graph_output\previous_graph.json
echo   - HTML Report:   graph_output\current_report.html
echo.
echo Next steps:
echo   - View HTML report: open graph_output\current_report.html
echo   - Compare with previous: update_graph.bat %REPO_PATH% /compare
echo   - Visualize: Import GraphML file to Cytoscape
echo.

endlocal
