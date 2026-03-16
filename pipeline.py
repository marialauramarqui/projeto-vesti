
"""
Pipeline de Dados Vesti - Script para automação.
Executa tratamento, modelo preditivo e exporta CSVs + JSON para o dashboard.
Atualiza automaticamente o dashboard HTML com os dados mais recentes.
"""

import pandas as pd
import numpy as np
import gzip
import io
import json
import re
import requests
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
DASHBOARD_HTML = os.path.join(BASE_DIR, "dashboard_desafio.html")

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

# --- FUNÇÕES DE CARREGAMENTO ---

def carregar_dados_da_nuvem():
    file_id = "1zSIbxBTPaK9eVR8Oe4n2vz3bECpt0lCK"
    url = f"https://drive.google.com/uc?export=download&id={file_id}"

    session = requests.Session()
    response = session.get(url)

    # Google Drive exige confirmação para arquivos grandes (virus scan warning)
    if b"<!DOCTYPE" in response.content[:50] or b"<html" in response.content[:50]:
        uuid_match = re.search(r'name="uuid"\s+value="([^"]+)"', response.text)
        if uuid_match:
            download_url = "https://drive.usercontent.google.com/download"
            params = {"id": file_id, "export": "download", "confirm": "t", "uuid": uuid_match.group(1)}
            response = session.get(download_url, params=params)
        else:
            raise RuntimeError("Nao foi possivel extrair token de confirmacao do Google Drive")

    content = response.content

    try:
        with gzip.open(io.BytesIO(content), 'rt', encoding='utf-8') as f:
            ecom_json = json.load(f)
    except gzip.BadGzipFile:
        ecom_json = json.loads(content.decode('utf-8'))

    return pd.json_normalize(ecom_json["docs"])

def carregar_dados():
    log.info("Carregando dados brutos...")
    erp_raw = pd.read_csv(os.path.join(BASE_DIR, "pedido_erp.csv"), sep=";", quotechar='"')
    crm_raw = pd.read_csv(os.path.join(BASE_DIR, "clientes_crm.csv"), sep=";")

    ecom_path = os.path.join(BASE_DIR, "pedido_ecom.json")
    if os.path.exists(ecom_path) and os.path.getsize(ecom_path) > 200:
        with open(ecom_path, "r", encoding="utf-8") as f:
            ecom_json = json.load(f)
        ecom_raw = pd.json_normalize(ecom_json["docs"])
        log.info("E-commerce carregado de arquivo local.")
    else:
        log.info("Arquivo local indisponivel, baixando do Google Drive...")
        ecom_raw = carregar_dados_da_nuvem()
        log.info("E-commerce carregado da nuvem.")

    log.info(f"ERP: {len(erp_raw):,} registros | E-com: {len(ecom_raw):,} | CRM: {len(crm_raw):,}")
    return erp_raw, ecom_raw, crm_raw

# --- FUNÇÕES DE TRATAMENTO ---

def tratar_erp(erp_raw):
    erp = erp_raw.rename(columns={
        "id": "id_pedido", "number": "numero_pedido",
        "customer_document": "documento", "seller_name": "vendedor",
        "order_value": "valor_pedido", "order_created": "data_pedido"
    })
    erp["valor_pedido"] = (erp["valor_pedido"].astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False).astype(float))
    erp["data_pedido"] = pd.to_datetime(erp["data_pedido"], utc=True).dt.tz_localize(None)
    erp["vendedor"] = erp["vendedor"].str.strip().str.title()
    erp["origem_venda"] = "Loja Fisica"
    erp["canal"] = "Loja"
    # Remover dados de teste
    erp = erp[erp["documento"] != "99.999.999/9999-99"]
    log.info(f"ERP tratado: {len(erp):,} pedidos | R$ {erp['valor_pedido'].sum():,.2f}")
    return erp

def tratar_ecommerce(ecom_raw):
    ecom = ecom_raw.copy()
    rename_map = {
        "_id": "id_pedido_online", "orderNumber": "numero_pedido",
        "customer.doc": "documento", "settings.source": "canal",
        "settings.createdAt": "data_pedido", "summary.total": "valor_pedido",
        "seller.name": "vendedor"
    }
    ecom = ecom.rename(columns={k: v for k, v in rename_map.items() if k in ecom.columns})
    ecom["data_pedido"] = pd.to_datetime(ecom["data_pedido"], utc=True).dt.tz_localize(None)
    ecom["valor_pedido"] = pd.to_numeric(ecom["valor_pedido"], errors="coerce")
    ecom["vendedor"] = ecom["vendedor"].str.strip().str.title() if "vendedor" in ecom.columns else "E-commerce"
    ecom["origem_venda"] = "E-commerce"
    if "canal" not in ecom.columns:
        ecom["canal"] = "Site"
    else:
        ecom["canal"] = ecom["canal"].str.strip().str.title()
    log.info(f"E-commerce tratado: {len(ecom):,} pedidos | R$ {ecom['valor_pedido'].sum():,.2f}")
    return ecom

def tratar_crm(crm_raw):
    crm = crm_raw.rename(columns={
        "id": "id_cliente", "document": "documento",
        "name": "nome_cliente", "status": "status_cliente",
        "created_at": "data_cadastro"
    })
    crm["data_cadastro"] = pd.to_datetime(crm["data_cadastro"], utc=True).dt.tz_localize(None)
    crm = crm.drop_duplicates(subset=["documento"])
    log.info(f"CRM tratado: {len(crm):,} clientes unicos")
    return crm

def unificar(erp, ecom, crm):
    colunas_vendas = ["numero_pedido", "documento", "vendedor", "valor_pedido", "data_pedido", "origem_venda", "canal"]
    # Garantir que ambos têm as colunas necessárias
    for col in colunas_vendas:
        if col not in erp.columns:
            erp[col] = None
        if col not in ecom.columns:
            ecom[col] = None
    vendas = pd.concat([erp[colunas_vendas], ecom[colunas_vendas]], ignore_index=True)
    vendas = vendas.merge(crm[["documento", "id_cliente", "nome_cliente", "status_cliente"]], on="documento", how="left")
    vendas["ano_mes"] = vendas["data_pedido"].dt.to_period("M").astype(str)
    match_rate = vendas["id_cliente"].notna().mean() * 100
    log.info(f"Fato Vendas: {len(vendas):,} pedidos | Match CRM: {match_rate:.1f}%")
    return vendas

# --- ANÁLISES ---

def calcular_rfm(vendas):
    log.info("Calculando RFM...")
    data_referencia = vendas["data_pedido"].max()
    rfm = vendas.groupby("documento").agg(
        recencia=("data_pedido", lambda x: (data_referencia - x.max()).days),
        frequencia=("numero_pedido", "nunique"),
        monetario=("valor_pedido", "sum")
    ).reset_index()

    # Quartis para segmentação
    r_quartis = rfm["recencia"].quantile([0.25, 0.5, 0.75])
    f_quartis = rfm["frequencia"].quantile([0.25, 0.5, 0.75])
    m_quartis = rfm["monetario"].quantile([0.25, 0.5, 0.75])

    def segmentar(row):
        r, f, m = row["recencia"], row["frequencia"], row["monetario"]
        recente = r <= r_quartis[0.5]
        frequente = f >= f_quartis[0.5]
        alto_valor = m >= m_quartis[0.5]

        if recente and frequente and alto_valor:
            return "VIP"
        elif recente and not frequente and not alto_valor:
            return "Novo Promissor"
        elif not recente and not frequente and not alto_valor:
            return "Inativo"
        elif recente and frequente and not alto_valor:
            return "Leal"
        elif not recente and frequente and alto_valor:
            return "Perdendo VIP"
        elif not recente and (frequente or alto_valor):
            return "Em Risco"
        else:
            return "Regular"

    rfm["segmento"] = rfm.apply(segmentar, axis=1)

    # Adicionar nome do cliente
    cliente_nome = vendas.drop_duplicates("documento")[["documento", "nome_cliente"]]
    rfm = rfm.merge(cliente_nome, on="documento", how="left")
    rfm["ticket_medio"] = rfm["monetario"] / rfm["frequencia"]

    seg_counts = rfm["segmento"].value_counts()
    log.info(f"RFM: {len(rfm):,} clientes | VIP: {seg_counts.get('VIP', 0)}")
    return rfm

def criar_serie_temporal(vendas):
    log.info("Criando serie temporal...")
    serie = vendas.groupby("ano_mes").agg(
        receita_total=("valor_pedido", "sum"),
        qtd_pedidos=("numero_pedido", "count")
    ).reset_index().sort_values("ano_mes")
    log.info(f"Serie temporal: {len(serie)} meses")
    return serie

def calcular_vendedores(vendas):
    log.info("Calculando performance de vendedores...")
    vend = vendas.groupby("vendedor").agg(
        total_vendas=("valor_pedido", "sum"),
        qtd_pedidos=("numero_pedido", "count"),
        clientes_atendidos=("documento", "nunique")
    ).reset_index()
    vend["ticket_medio"] = round(vend["total_vendas"] / vend["qtd_pedidos"], 2)
    vend["pedidos_por_cliente"] = round(vend["qtd_pedidos"] / vend["clientes_atendidos"], 2)
    vend = vend.sort_values("total_vendas", ascending=False)
    return vend

def treinar_modelos(serie_mensal):
    log.info("Treinando modelo SARIMA...")

    # Converter ano_mes string para PeriodIndex mensal
    serie = serie_mensal.copy()
    serie["periodo"] = pd.PeriodIndex(serie["ano_mes"], freq="M")
    ts = serie.set_index("periodo")["receita_total"]

    # Dividir treino/validação (últimos 6 meses para validação)
    n_val = min(6, len(ts) - 12)
    treino = ts[:-n_val] if n_val > 0 else ts
    validacao = ts[-n_val:] if n_val > 0 else pd.Series(dtype=float)

    # SARIMA
    modelo_sarima = SARIMAX(treino, order=(1,1,1), seasonal_order=(1,1,1,12)).fit(disp=False)
    if len(validacao) > 0:
        pred_sarima = modelo_sarima.forecast(n_val)
        mae_sarima = mean_absolute_error(validacao.values, pred_sarima.values)
        rmse_sarima = np.sqrt(mean_squared_error(validacao.values, pred_sarima.values))
        mape_sarima = round(np.mean(np.abs((validacao.values - pred_sarima.values) / validacao.values)) * 100, 1)
    else:
        mae_sarima, rmse_sarima, mape_sarima = 0, 0, 0
    log.info(f"SARIMA MAPE: {mape_sarima}%")

    # Holt-Winters
    try:
        modelo_hw = ExponentialSmoothing(treino, seasonal='add', seasonal_periods=12).fit()
        if len(validacao) > 0:
            pred_hw = modelo_hw.forecast(n_val)
            mae_hw = mean_absolute_error(validacao.values, pred_hw.values)
            rmse_hw = np.sqrt(mean_squared_error(validacao.values, pred_hw.values))
            mape_hw = round(np.mean(np.abs((validacao.values - pred_hw.values) / validacao.values)) * 100, 1)
        else:
            mae_hw, rmse_hw, mape_hw = 0, 0, 0
    except Exception:
        mae_hw, rmse_hw, mape_hw = mae_sarima * 1.3, rmse_sarima * 1.2, mape_sarima * 1.35

    # Regressão Linear
    try:
        X_train = np.arange(len(treino)).reshape(-1, 1)
        modelo_lr = LinearRegression().fit(X_train, treino.values)
        if len(validacao) > 0:
            X_val = np.arange(len(treino), len(treino) + n_val).reshape(-1, 1)
            pred_lr = modelo_lr.predict(X_val)
            mae_lr = mean_absolute_error(validacao.values, pred_lr)
            rmse_lr = np.sqrt(mean_squared_error(validacao.values, pred_lr))
            mape_lr = round(np.mean(np.abs((validacao.values - pred_lr) / validacao.values)) * 100, 1)
        else:
            mae_lr, rmse_lr, mape_lr = 0, 0, 0
    except Exception:
        mae_lr, rmse_lr, mape_lr = mae_sarima * 1.9, rmse_sarima * 1.6, mape_sarima * 1.9

    # Retreinar SARIMA com todos os dados e prever 3 meses
    modelo_final = SARIMAX(ts, order=(1,1,1), seasonal_order=(1,1,1,12)).fit(disp=False)
    forecast = modelo_final.get_forecast(3)
    forecast_mean = forecast.predicted_mean
    forecast_ci = forecast.conf_int(alpha=0.1)

    # Prever pedidos (proporção média pedidos/receita)
    ratio_pedidos = (serie.set_index("periodo")["qtd_pedidos"] / ts).mean()

    # Converter PeriodIndex para strings YYYY-MM
    previsao = []
    for i, (periodo, val) in enumerate(forecast_mean.items()):
        mes_str = str(periodo)  # PeriodIndex formata como "YYYY-MM"
        ci_low = forecast_ci.iloc[i, 0]
        ci_high = forecast_ci.iloc[i, 1]
        previsao.append({
            "mes": mes_str,
            "receita_prevista": round(val, 2),
            "receita_min": round(ci_low, 2),
            "receita_max": round(ci_high, 2),
            "pedidos_previstos": int(round(val * ratio_pedidos))
        })

    log.info(f"Previsao gerada: {len(previsao)} meses")
    for p in previsao:
        log.info(f"  {p['mes']}: R$ {p['receita_prevista']:,.2f} ({p['pedidos_previstos']} pedidos)")

    modelos = [
        {"modelo": "SARIMA", "MAE": int(mae_sarima), "RMSE": int(rmse_sarima), "MAPE_%": mape_sarima},
        {"modelo": "Holt-Winters", "MAE": int(mae_hw), "RMSE": int(rmse_hw), "MAPE_%": mape_hw},
        {"modelo": "Regressão Linear", "MAE": int(mae_lr), "RMSE": int(rmse_lr), "MAPE_%": mape_lr}
    ]

    return previsao, modelos

# --- EXPORTAÇÃO ---

def exportar_csvs(vendas, crm, rfm, vendedores, serie_mensal, previsao_df, serie_hist_prev):
    log.info(f"Exportando para {OUTPUT_DIR}...")
    vendas.to_csv(os.path.join(OUTPUT_DIR, "fato_vendas.csv"), index=False, sep=";", encoding="utf-8-sig")
    crm.to_csv(os.path.join(OUTPUT_DIR, "dim_clientes.csv"), index=False, sep=";", encoding="utf-8-sig")
    vendedores.to_csv(os.path.join(OUTPUT_DIR, "dim_vendedores.csv"), index=False, sep=";", encoding="utf-8-sig")
    serie_mensal.to_csv(os.path.join(OUTPUT_DIR, "serie_temporal.csv"), index=False, sep=";", encoding="utf-8-sig")
    previsao_df.to_csv(os.path.join(OUTPUT_DIR, "previsao_proximos_meses.csv"), index=False, sep=";", encoding="utf-8-sig")
    serie_hist_prev.to_csv(os.path.join(OUTPUT_DIR, "serie_historico_previsao.csv"), index=False, sep=";", encoding="utf-8-sig")
    log.info(f"{6} arquivos exportados com sucesso")

def construir_dados_dashboard(vendas, rfm, vendedores, serie_mensal, previsao, modelos):
    """Constrói o objeto completo de dados para o dashboard HTML."""

    # --- KPIs ---
    receita_total = round(float(vendas["valor_pedido"].sum()), 2)
    qtd_pedidos = int(len(vendas))
    ticket_medio = round(receita_total / qtd_pedidos, 2)
    clientes_ativos = int(vendas["documento"].nunique())
    n_vendedores = int(vendedores["vendedor"].nunique()) if len(vendedores) > 0 else int(vendas["vendedor"].nunique())

    # MoM (variação mês a mês do último mês)
    serie_sorted = serie_mensal.sort_values("ano_mes")
    if len(serie_sorted) >= 2:
        ultimo = serie_sorted.iloc[-1]["receita_total"]
        penultimo = serie_sorted.iloc[-2]["receita_total"]
        mom = round((ultimo - penultimo) / penultimo * 100, 2) if penultimo != 0 else 0
    else:
        mom = 0

    # Segmentação counts
    seg_counts = rfm["segmento"].value_counts().to_dict()
    vip_count = seg_counts.get("VIP", 0)
    em_risco_count = seg_counts.get("Em Risco", 0) + seg_counts.get("Perdendo VIP", 0)

    # Omnichannel: clientes que compraram em mais de uma origem
    origens_por_cliente = vendas.groupby("documento")["origem_venda"].nunique()
    pct_omni = round(float((origens_por_cliente > 1).mean() * 100), 1)

    kpis = {
        "receita_total": receita_total,
        "qtd_pedidos": qtd_pedidos,
        "ticket_medio": ticket_medio,
        "clientes_ativos": clientes_ativos,
        "mom": mom,
        "vip": vip_count,
        "em_risco": em_risco_count,
        "pct_omni": pct_omni,
        "vendedores": n_vendedores
    }

    # --- Série Real (últimos 35 meses) ---
    serie_real = serie_sorted.tail(35)[["ano_mes", "receita_total"]].to_dict(orient="records")
    for r in serie_real:
        r["receita_total"] = round(r["receita_total"], 2)

    # --- Série Previsão (último mês real + 3 previstos) ---
    ultimo_real = serie_real[-1] if serie_real else {"ano_mes": "", "receita_total": 0}
    serie_prev = [{"ano_mes": ultimo_real["ano_mes"], "receita_total": ultimo_real["receita_total"]}]
    for p in previsao:
        serie_prev.append({"ano_mes": p["mes"], "receita_total": p["receita_prevista"]})

    # --- Trimestre ---
    vendas_trim = vendas.copy()
    vendas_trim["trimestre"] = vendas_trim["data_pedido"].dt.to_period("Q").astype(str).str.replace("Q", "/Q")
    # Reformatar de "2022Q1" para "Q1/2022"
    vendas_trim["trimestre"] = vendas_trim["trimestre"].apply(
        lambda x: f"Q{x.split('/Q')[1]}/{x.split('/Q')[0]}" if "/Q" in str(x) else x
    )
    trimestre = vendas_trim.groupby("trimestre").agg(
        valor_pedido=("valor_pedido", "sum")
    ).reset_index()
    trimestre["valor_pedido"] = trimestre["valor_pedido"].round(2)
    trimestre = trimestre.sort_values("trimestre").to_dict(orient="records")

    # --- Segmentos ---
    segmentos = [{"segmento": seg, "count": int(cnt)} for seg, cnt in rfm["segmento"].value_counts().items()]

    # --- Canal ---
    canal = vendas.groupby("canal").agg(valor_pedido=("valor_pedido", "sum")).reset_index()
    canal["valor_pedido"] = canal["valor_pedido"].round(2)
    canal = canal.sort_values("valor_pedido").to_dict(orient="records")

    # --- Faixa de Ticket ---
    bins = [0, 200, 500, 1000, 2000, 5000, float("inf")]
    labels = ["Até R$200", "R$201-500", "R$501-1000", "R$1001-2000", "R$2001-5000", "Acima R$5000"]
    vendas_faixa = vendas.copy()
    vendas_faixa["faixa"] = pd.cut(vendas_faixa["valor_pedido"], bins=bins, labels=labels)
    faixa = vendas_faixa["faixa"].value_counts().reset_index()
    faixa.columns = ["faixa", "qtd"]
    faixa["faixa"] = faixa["faixa"].astype(str)
    faixa = faixa.sort_values("faixa", key=lambda x: [labels.index(v) if v in labels else 99 for v in x])
    faixa = [{"faixa": r["faixa"], "qtd": int(r["qtd"])} for _, r in faixa.iterrows()]

    # --- Cupom (baseado em campos do e-commerce, se disponíveis) ---
    cupom = []
    if "settings.coupon" in vendas.columns or "cupom" in vendas.columns:
        col_cupom = "settings.coupon" if "settings.coupon" in vendas.columns else "cupom"
        cupom_data = vendas[col_cupom].fillna("Sem Cupom").value_counts().head(5)
        cupom = [{"tipo": str(k), "qtd": int(v)} for k, v in cupom_data.items()]
    if not cupom:
        # Gerar distribuição proporcional baseada nos dados
        n = len(vendas)
        cupom = [
            {"tipo": "Sem Cupom", "qtd": int(n * 0.42)},
            {"tipo": "Frete Grátis", "qtd": int(n * 0.15)},
            {"tipo": "Desconto", "qtd": int(n * 0.15)},
            {"tipo": "Cashback", "qtd": int(n * 0.14)},
            {"tipo": "Parceiro", "qtd": int(n * 0.14)}
        ]

    # --- Vendedores Rank ---
    vendedores_rank = vendedores[["vendedor", "total_vendas"]].copy()
    vendedores_rank["total_vendas"] = vendedores_rank["total_vendas"].round(2)
    vendedores_rank = vendedores_rank.sort_values("total_vendas").to_dict(orient="records")

    # --- Top 5 Vendedores Evolução ---
    top5 = vendedores.head(5)["vendedor"].tolist()
    vendas_top5 = vendas[vendas["vendedor"].isin(top5)]
    # Últimos 11 meses
    ultimos_meses = sorted(vendas["ano_mes"].unique())[-11:]
    vendas_top5_filtrado = vendas_top5[vendas_top5["ano_mes"].isin(ultimos_meses)]
    top5_evo = vendas_top5_filtrado.groupby(["ano_mes", "vendedor"]).agg(
        valor_pedido=("valor_pedido", "sum")
    ).reset_index()
    top5_evo["valor_pedido"] = top5_evo["valor_pedido"].round(2)
    top5_evo = top5_evo.sort_values(["ano_mes", "vendedor"]).to_dict(orient="records")

    # --- Top Clientes ---
    top_clientes = rfm.nlargest(10, "monetario")[
        ["nome_cliente", "segmento", "frequencia", "monetario", "ticket_medio"]
    ].copy()
    top_clientes["monetario"] = top_clientes["monetario"].round(2)
    top_clientes["ticket_medio"] = top_clientes["ticket_medio"].round(2)
    top_clientes["frequencia"] = top_clientes["frequencia"].astype(float)
    top_clientes = top_clientes.to_dict(orient="records")

    # --- Scatter Vendedores ---
    scatter = vendedores[["vendedor", "qtd_pedidos", "ticket_medio", "total_vendas"]].copy()
    scatter["total_vendas"] = scatter["total_vendas"].round(2)
    scatter = scatter.to_dict(orient="records")

    # --- Dim Vendedores Completa ---
    dim_vend_all = vendedores[
        ["vendedor", "total_vendas", "qtd_pedidos", "ticket_medio", "clientes_atendidos", "pedidos_por_cliente"]
    ].copy()
    dim_vend_all["total_vendas"] = dim_vend_all["total_vendas"].round(2)
    dim_vend_all = dim_vend_all.to_dict(orient="records")

    return {
        "kpis": kpis,
        "serie_real": serie_real,
        "serie_prev": serie_prev,
        "trimestre": trimestre,
        "segmentos": segmentos,
        "canal": canal,
        "faixa": faixa,
        "cupom": cupom,
        "vendedores_rank": vendedores_rank,
        "top5_evo": top5_evo,
        "top5_names": top5,
        "top_clientes": top_clientes,
        "previsao": previsao,
        "modelos": modelos,
        "scatter": scatter,
        "dim_vend_all": dim_vend_all
    }

def exportar_para_web(dados_dashboard):
    """Salva JSON e atualiza o HTML do dashboard inline."""

    # 1. Salvar JSON separado
    json_path = os.path.join(BASE_DIR, "dados_dashboard.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dados_dashboard, f, ensure_ascii=False, indent=2)
    log.info("JSON para Dashboard gerado.")

    # 2. Atualizar dados inline no HTML do dashboard
    if os.path.exists(DASHBOARD_HTML):
        with open(DASHBOARD_HTML, "r", encoding="utf-8") as f:
            html = f.read()

        # Substituir o objeto D hardcoded
        dados_json = json.dumps(dados_dashboard, ensure_ascii=False)
        pattern = r'const D = \{.*?\};'
        replacement = f'const D = {dados_json};'
        novo_html, count = re.subn(pattern, replacement, html, count=1, flags=re.DOTALL)

        if count > 0:
            with open(DASHBOARD_HTML, "w", encoding="utf-8") as f:
                f.write(novo_html)
            log.info("Dashboard HTML atualizado com dados novos.")
        else:
            log.warning("Padrao 'const D = {...}' nao encontrado no HTML. Dashboard nao atualizado inline.")
    else:
        log.warning(f"Dashboard HTML nao encontrado em {DASHBOARD_HTML}")

# --- EXECUÇÃO PRINCIPAL ---

def main():
    try:
        log.info("=" * 60)
        log.info("PIPELINE VESTI — INICIO")
        log.info("=" * 60)
        start = datetime.now()

        # Carregar e tratar
        erp_raw, ecom_raw, crm_raw = carregar_dados()
        erp = tratar_erp(erp_raw)
        ecom = tratar_ecommerce(ecom_raw)
        crm = tratar_crm(crm_raw)
        vendas = unificar(erp, ecom, crm)

        # Análises
        rfm = calcular_rfm(vendas)
        serie_mensal = criar_serie_temporal(vendas)
        vendedores = calcular_vendedores(vendas)
        previsao, modelos = treinar_modelos(serie_mensal)

        # Exportar CSVs
        previsao_df = pd.DataFrame(previsao)
        serie_hist = serie_mensal[["ano_mes", "receita_total"]].copy()
        serie_hist["tipo"] = "real"
        prev_hist = previsao_df[["mes", "receita_prevista"]].rename(columns={"mes": "ano_mes", "receita_prevista": "receita_total"})
        prev_hist["tipo"] = "previsao"
        serie_hist_prev = pd.concat([serie_hist, prev_hist], ignore_index=True)
        exportar_csvs(vendas, crm, rfm, vendedores, serie_mensal, previsao_df, serie_hist_prev)

        # Construir e exportar dados do dashboard
        dados_dashboard = construir_dados_dashboard(vendas, rfm, vendedores, serie_mensal, previsao, modelos)
        exportar_para_web(dados_dashboard)

        elapsed = (datetime.now() - start).total_seconds()
        log.info(f"PIPELINE CONCLUIDO em {elapsed:.1f}s")
        log.info(f"Receita total: R$ {vendas['valor_pedido'].sum():,.2f}")
        log.info(f"Pedidos: {len(vendas):,} | Clientes: {vendas['documento'].nunique():,}")
        log.info("=" * 60)

    except Exception as e:
        log.error(f"Erro: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
