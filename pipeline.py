
"""
Pipeline de Dados Vesti - Script para automação.
Executa tratamento, modelo preditivo e exporta CSVs + JSON para o dashboard.
"""

import pandas as pd
import numpy as np
import gzip
import warnings
import os
import sys
import logging
from datetime import datetime
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

# --- CONFIGURAÇÕES ---
warnings.filterwarnings("ignore")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "data_powerbi")
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "pipeline.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("vesti-pipeline")

# --- FUNÇÕES DE TRATAMENTO ---

def carregar_dados():
    log.info("Carregando dados brutos...")
    erp_raw = pd.read_csv(os.path.join(BASE_DIR, "pedido_erp.csv"), sep=";", quotechar='"')
    crm_raw = pd.read_csv(os.path.join(BASE_DIR, "clientes_crm.csv"), sep=";")
    
    # Lendo o arquivo compactado (GZIP)
    caminho_ecom = os.path.join(BASE_DIR, "pedido_ecom.json.gz")
    with gzip.open(caminho_ecom, 'rt', encoding='utf-8') as f:
        ecom_json = json.load(f)
        
    ecom_raw = pd.json_normalize(ecom_json["docs"])
    return erp_raw, ecom_raw, crm_raw

def tratar_erp(erp_raw):
    erp = erp_raw.rename(columns={"id": "id_pedido", "number": "numero_pedido", "customer_document": "documento", "seller_name": "vendedor", "order_value": "valor_pedido", "order_created": "data_pedido"})
    erp["valor_pedido"] = erp["valor_pedido"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False).astype(float)
    erp["data_pedido"] = pd.to_datetime(erp["data_pedido"], utc=True).dt.tz_localize(None)
    erp["origem_venda"] = "Loja Fisica"
    return erp

def tratar_ecommerce(ecom_raw):
    ecom = ecom_raw.copy()
    rename_map = {"_id": "id_pedido_online", "orderNumber": "numero_pedido", "customer.doc": "documento", "settings.source": "canal", "settings.createdAt": "data_pedido", "summary.total": "valor_pedido", "seller.name": "vendedor"}
    ecom = ecom.rename(columns={k: v for k, v in rename_map.items() if k in ecom.columns})
    ecom["data_pedido"] = pd.to_datetime(ecom["data_pedido"], utc=True).dt.tz_localize(None)
    ecom["valor_pedido"] = pd.to_numeric(ecom["valor_pedido"], errors="coerce")
    ecom["origem_venda"] = "E-commerce"
    return ecom

def tratar_crm(crm_raw):
    crm = crm_raw.rename(columns={"id": "id_cliente", "document": "documento", "name": "nome_cliente", "status": "status_cliente", "created_at": "data_cadastro"})
    crm["data_cadastro"] = pd.to_datetime(crm["data_cadastro"], utc=True).dt.tz_localize(None)
    return crm.drop_duplicates(subset=["documento"])

def unificar(erp, ecom, crm):
    colunas_vendas = ["numero_pedido", "documento", "vendedor", "valor_pedido", "data_pedido", "origem_venda"]
    vendas = pd.concat([erp[colunas_vendas], ecom[colunas_vendas]], ignore_index=True)
    vendas = vendas.merge(crm[["documento", "id_cliente", "nome_cliente", "status_cliente"]], on="documento", how="left")
    vendas["ano_mes"] = vendas["data_pedido"].dt.to_period("M").astype(str)
    return vendas

def calcular_rfm(vendas):
    data_referencia = vendas["data_pedido"].max()
    rfm = vendas.groupby("documento").agg(recencia=("data_pedido", lambda x: (data_referencia - x.max()).days), frequencia=("numero_pedido", "nunique"), monetario=("valor_pedido", "sum")).reset_index()
    rfm["segmento"] = "Regular" # Simplificado para exemplo
    return rfm

def criar_serie_temporal(vendas):
    return vendas.groupby("ano_mes").agg(receita_total=("valor_pedido", "sum"), qtd_pedidos=("numero_pedido", "count")).reset_index()

def treinar_modelo(serie_mensal):
    ts = serie_mensal.set_index("ano_mes")
    # Modelo simplificado para garantir execução
    model = SARIMAX(ts["receita_total"], order=(1,1,1), seasonal_order=(0,0,0,0)).fit(disp=False)
    forecast = model.forecast(3)
    previsao = pd.DataFrame({"mes": forecast.index, "receita_prevista": forecast.values})
    return previsao, pd.DataFrame()

# --- EXPORTAÇÃO ---
def exportar(vendas, crm, rfm, vendedores, serie_mensal, previsao, resultados):
    vendas.to_csv(os.path.join(OUTPUT_DIR, "fato_vendas.csv"), index=False, sep=";", encoding="utf-8-sig")
    log.info("CSVs exportados.")

def exportar_para_web(vendas, serie_mensal, previsao, rfm, vendedores):
    dados_dashboard = {
        "kpis": {
            "receita_total": float(vendas['valor_pedido'].sum()),
            "qtd_pedidos": int(len(vendas)),
            "ticket_medio": float(vendas['valor_pedido'].mean())
        },
        "serie_historica": serie_mensal.to_dict(orient='records'),
        "previsao": previsao.to_dict(orient='records')
    }
    with open("dados_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dados_dashboard, f, ensure_ascii=False, indent=4)
    log.info("JSON para Dashboard gerado.")

# --- EXECUÇÃO PRINCIPAL ---
def main():
    try:
        erp_raw, ecom_raw, crm_raw = carregar_dados()
        erp = tratar_erp(erp_raw)
        ecom = tratar_ecommerce(ecom_raw)
        crm = tratar_crm(crm_raw)
        vendas = unificar(erp, ecom, crm)
        rfm = calcular_rfm(vendas)
        serie_mensal = criar_serie_temporal(vendas)
        vendedores = pd.DataFrame() # Adicione sua lógica de vendedores aqui
        previsao, resultados = treinar_modelo(serie_mensal)
        
        exportar(vendas, crm, rfm, vendedores, serie_mensal, previsao, resultados)
        exportar_para_web(vendas, serie_mensal, previsao, rfm, vendedores)
        log.info("Pipeline concluído com sucesso!")
    except Exception as e:
        log.error(f"Erro: {e}", exc_info=True)

if __name__ == "__main__":
    main()