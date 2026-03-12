@echo off
echo [%date% %time%] Iniciando pipeline Vesti...

cd /d "C:\Users\maria\Projetos\projeto-vesti"

python pipeline.py

IF %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] ERRO no pipeline Python
    exit /b 1
)

REM Descomente a linha abaixo se usar OneDrive para sync com Power BI Service
REM xcopy /Y "data_powerbi\*.csv" "%USERPROFILE%\OneDrive\Vesti\data_powerbi\"

echo [%date% %time%] Pipeline concluido com sucesso
