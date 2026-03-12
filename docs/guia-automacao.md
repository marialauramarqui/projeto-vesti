# Guia de Automacao — Pipeline de Dados Vesti

## Visao Geral

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Fontes (ERP,   │     │  Python Script   │     │  Power BI       │
│  E-com, CRM)    │────>│  (tratamento +   │────>│  Refresh        │
│  atualizadas    │     │  modelo)         │     │  automatico     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        Manual ou              Agendador              Power BI
        API/Export            Windows Task           Service ou
                              Scheduler              Gateway
```

**Frequencia recomendada:** Diaria (06:00) ou conforme atualizacao das fontes.

---

## Parte 1: Converter Notebook em Script Executavel

O notebook `.ipynb` nao e ideal para automacao. Temos 2 opcoes:

### Opcao A: Executar o notebook direto (mais simples)

```bash
jupyter nbconvert --to notebook --execute tratamento_analise.ipynb --output tratamento_analise_executado.ipynb
```

### Opcao B: Converter para `.py` (recomendado para producao)

Criar um script `pipeline.py` que faz tudo que o notebook faz, mas sem depender do Jupyter.

> O script `pipeline.py` sera criado na raiz do projeto. Veja a secao "Script pipeline.py" abaixo.

---

## Parte 2: Agendar no Windows Task Scheduler

### Passo a passo:

1. **Abrir Agendador de Tarefas** (Task Scheduler)
   - Pressionar `Win + R` → digitar `taskschd.msc` → Enter

2. **Criar Tarefa Basica**
   - Nome: `Vesti - Pipeline de Dados`
   - Descricao: `Executa tratamento de dados e modelo preditivo`

3. **Disparador (Trigger)**
   - Diariamente, as 06:00 (ou horario desejado)
   - Repetir a cada 1 dia

4. **Acao**
   - Programa: caminho do Python (ex: `C:\Users\maria\AppData\Local\Programs\Python\Python314\python.exe`)
   - Argumentos: `pipeline.py`
   - Iniciar em: `C:\Users\maria\Projetos\projeto-vesti`

5. **Condicoes**
   - Desmarcar "Iniciar somente se o computador estiver na alimentacao AC" (se notebook)

6. **Configuracoes**
   - Marcar "Executar tarefa assim que possivel apos um inicio agendado ser perdido"
   - Interromper tarefa se executar por mais de 30 minutos

### Via linha de comando (alternativa):

```powershell
schtasks /create /tn "Vesti-Pipeline" /tr "python C:\Users\maria\Projetos\projeto-vesti\pipeline.py" /sc daily /st 06:00
```

---

## Parte 3: Refresh Automatico do Power BI

### Opcao 1: Power BI Service + Gateway (profissional)

Requer licenca Power BI Pro ou Premium.

1. **Instalar Power BI Gateway** no computador
   - Download em: powerbi.microsoft.com → Gateway
   - Configurar com sua conta Microsoft

2. **Publicar o dashboard** no Power BI Service
   - No Power BI Desktop: Arquivo → Publicar → Selecionar workspace

3. **Configurar fonte de dados no Gateway**
   - Power BI Service → Configuracoes → Gerenciar Gateways
   - Adicionar fonte de dados: tipo "Arquivo" apontando para `C:\Users\maria\Projetos\projeto-vesti\data_powerbi\`

4. **Agendar atualizacao**
   - Power BI Service → Dataset → Configuracoes → Atualizacao agendada
   - Frequencia: Diaria, as 07:00 (1h depois do Python rodar)
   - Ativar "Manter dados atualizados"

### Opcao 2: Script PowerShell para refresh local (sem Gateway)

Se nao tiver Power BI Pro, pode usar PowerShell para abrir e atualizar o .pbix:

Criar `refresh_powerbi.ps1`:

```powershell
# Abre Power BI, atualiza e fecha
$pbiPath = "C:\Users\maria\Projetos\projeto-vesti\dashboard_vesti.pbix"

# Abrir o arquivo .pbix (Power BI Desktop abre automaticamente)
Start-Process $pbiPath

# Aguardar Power BI abrir (ajustar conforme necessidade)
Start-Sleep -Seconds 30

# Simular Ctrl+F5 (Atualizar Tudo) via SendKeys
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("^{F5}")

# Aguardar refresh completar
Start-Sleep -Seconds 120

# Salvar (Ctrl+S) e fechar
[System.Windows.Forms.SendKeys]::SendWait("^s")
Start-Sleep -Seconds 10
[System.Windows.Forms.SendKeys]::SendWait("%{F4}")
```

> Nota: essa opcao e fragil (depende de UI). Prefira a Opcao 1 com Gateway.

### Opcao 3: Power BI com OneDrive/SharePoint (intermediaria)

1. Salvar os CSVs em uma pasta do OneDrive
2. O Power BI Service detecta mudancas e atualiza automaticamente
3. Adicionar ao `pipeline.py` uma copia dos CSVs para a pasta OneDrive

---

## Parte 4: Pipeline Completo (bat wrapper)

Criar `run_pipeline.bat` para encadear tudo:

```bat
@echo off
echo [%date% %time%] Iniciando pipeline Vesti... >> logs\pipeline.log

REM Passo 1: Executar tratamento + modelo
python pipeline.py >> logs\pipeline.log 2>&1

IF %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] ERRO no pipeline Python >> logs\pipeline.log
    exit /b 1
)

echo [%date% %time%] Pipeline concluido com sucesso >> logs\pipeline.log

REM Passo 2 (opcional): Copiar para OneDrive
REM xcopy /Y data_powerbi\*.csv "C:\Users\maria\OneDrive\Vesti\data_powerbi\"

REM Passo 3 (opcional): Refresh Power BI local
REM powershell -ExecutionPolicy Bypass -File refresh_powerbi.ps1
```

Agendar o `.bat` no Task Scheduler em vez do Python diretamente.

---

## Parte 5: Monitoramento

### Log de execucao

O `pipeline.py` grava logs em `logs/pipeline.log`. Verificar periodicamente:

```bash
tail -20 logs/pipeline.log
```

### Alertas (opcional avancado)

Adicionar ao final do `pipeline.py`:

```python
# Enviar email se erro
import smtplib
from email.mime.text import MIMEText

def enviar_alerta(assunto, corpo):
    msg = MIMEText(corpo)
    msg["Subject"] = assunto
    msg["From"] = "pipeline@vesti.com"
    msg["To"] = "maria@email.com"
    # Configurar SMTP conforme provedor
```

---

## Resumo da Arquitetura

```
06:00  Task Scheduler executa run_pipeline.bat
         │
         ├── python pipeline.py
         │     ├── Carrega dados brutos (ERP, E-com, CRM)
         │     ├── Trata e unifica
         │     ├── Calcula RFM + features
         │     ├── Treina SARIMA + previsao
         │     └── Exporta 7 CSVs → data_powerbi/
         │
         ├── (opcional) Copia CSVs → OneDrive
         │
         └── Log em logs/pipeline.log

07:00  Power BI Service refresh agendado
         └── Atualiza dataset a partir dos CSVs
```
