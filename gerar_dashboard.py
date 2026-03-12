"""
Dashboard Interativo Vesti — Gera HTML completo com Plotly.
Replica as 5 paginas do guia Power BI em um unico arquivo HTML.

Uso: python gerar_dashboard.py
Saida: dashboard_vesti.html (abrir no navegador)
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os, json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data_powerbi")

# Paleta do guia
COR = {
    "primaria": "#1B2A4A",
    "secundaria": "#4472C4",
    "positivo": "#2E7D32",
    "negativo": "#C62828",
    "previsao": "#FF8F00",
    "fundo": "#F5F5F5",
    "texto": "#333333",
    "branco": "#FFFFFF",
    "cinza": "#E0E0E0",
}

CORES_SEGMENTOS = {
    "VIP": "#1B2A4A",
    "Leal": "#4472C4",
    "Novo Promissor": "#2E7D32",
    "Regular": "#78909C",
    "Em Risco": "#FF8F00",
    "Perdendo VIP": "#C62828",
    "Inativo": "#BDBDBD",
}


def carregar_dados():
    kw = dict(sep=";", decimal=",", encoding="utf-8-sig")
    vendas = pd.read_csv(os.path.join(DATA_DIR, "fato_vendas.csv"), **kw)
    clientes = pd.read_csv(os.path.join(DATA_DIR, "dim_clientes.csv"), **kw)
    vendedores = pd.read_csv(os.path.join(DATA_DIR, "dim_vendedores.csv"), **kw)
    serie = pd.read_csv(os.path.join(DATA_DIR, "serie_temporal.csv"), **kw)
    serie_hp = pd.read_csv(os.path.join(DATA_DIR, "serie_historico_previsao.csv"), **kw)
    previsao = pd.read_csv(os.path.join(DATA_DIR, "previsao_proximos_meses.csv"), **kw)
    modelos = pd.read_csv(os.path.join(DATA_DIR, "comparacao_modelos.csv"), **kw)

    vendas["data_pedido"] = pd.to_datetime(vendas["data_pedido"], format="mixed")
    serie_hp["ano_mes_dt"] = pd.to_datetime(serie_hp["ano_mes_dt"])

    return vendas, clientes, vendedores, serie, serie_hp, previsao, modelos


def kpi_card_html(titulo, valor, subtitulo="", cor_valor=None):
    cor = cor_valor or COR["primaria"]
    return f"""
    <div style="background:{COR['branco']};border-radius:12px;padding:20px 16px;
                text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.08);
                min-width:160px;flex:1;margin:0 6px;">
        <div style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:1px;
                    margin-bottom:6px;">{titulo}</div>
        <div style="font-size:28px;font-weight:700;color:{cor};">{valor}</div>
        <div style="font-size:11px;color:#aaa;margin-top:4px;">{subtitulo}</div>
    </div>"""


def fmt_moeda(v):
    if abs(v) >= 1_000_000:
        return f"R$ {v/1_000_000:,.1f}M"
    if abs(v) >= 1_000:
        return f"R$ {v/1_000:,.1f}K"
    return f"R$ {v:,.0f}"


def fmt_num(v):
    return f"{v:,.0f}".replace(",", ".")


def fig_to_div(fig, height=400):
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False, "responsive": True},
                       default_height=f"{height}px")


# ============================================================
# PAGINA 1: CEO
# ============================================================
def pagina_ceo(vendas, serie_hp, previsao, modelos):
    receita = vendas["valor_pedido"].sum()
    pedidos = len(vendas)
    ticket = vendas["valor_pedido"].mean()
    clientes_ativos = vendas["documento"].nunique()

    # Variacao MoM (ultimos 2 meses)
    mensal = vendas.groupby("ano_mes")["valor_pedido"].sum().sort_index()
    if len(mensal) >= 2:
        var_mom = (mensal.iloc[-1] - mensal.iloc[-2]) / mensal.iloc[-2] * 100
        var_str = f"{var_mom:+.1f}%"
        var_cor = COR["positivo"] if var_mom >= 0 else COR["negativo"]
    else:
        var_str = "N/A"
        var_cor = COR["texto"]

    cards = f"""
    <div style="display:flex;gap:0;margin-bottom:20px;flex-wrap:wrap;">
        {kpi_card_html("Receita Total", fmt_moeda(receita))}
        {kpi_card_html("Pedidos", fmt_num(pedidos))}
        {kpi_card_html("Ticket Medio", fmt_moeda(ticket))}
        {kpi_card_html("Clientes Ativos", fmt_num(clientes_ativos))}
        {kpi_card_html("Variacao MoM", var_str, cor_valor=var_cor)}
    </div>"""

    # Grafico Receita Mensal: Realizado vs Previsto
    realizado = serie_hp[serie_hp["tipo"] == "Realizado"].sort_values("ano_mes_dt")
    previsto = serie_hp[serie_hp["tipo"] == "Previsto"].sort_values("ano_mes_dt")

    fig_linha = go.Figure()
    fig_linha.add_trace(go.Scatter(
        x=realizado["ano_mes_dt"], y=realizado["receita_total"],
        mode="lines", name="Realizado",
        line=dict(color=COR["secundaria"], width=2.5),
        hovertemplate="<b>%{x|%b/%Y}</b><br>R$ %{y:,.0f}<extra></extra>"
    ))
    fig_linha.add_trace(go.Scatter(
        x=previsto["ano_mes_dt"], y=previsto["receita_total"],
        mode="lines+markers", name="Previsto",
        line=dict(color=COR["previsao"], width=2.5, dash="dash"),
        marker=dict(size=8),
        hovertemplate="<b>%{x|%b/%Y}</b><br>R$ %{y:,.0f}<extra></extra>"
    ))
    fig_linha.update_layout(
        title="Receita Mensal — Realizado vs Previsto",
        xaxis_title="", yaxis_title="Receita (R$)",
        template="plotly_white", legend=dict(orientation="h", y=1.12),
        margin=dict(l=60, r=20, t=60, b=40),
        yaxis_tickprefix="R$ ", yaxis_tickformat=",.",
    )

    # Receita por Trimestre/Ano
    vendas["trim_ano"] = vendas["ano"].astype(str) + "-T" + vendas["trimestre"].astype(str)
    trim = vendas.groupby(["ano", "trimestre", "trim_ano"])["valor_pedido"].sum().reset_index()
    trim = trim.sort_values(["ano", "trimestre"])
    # Ultimos 12 trimestres
    trim = trim.tail(12)

    fig_bar = go.Figure(go.Bar(
        x=trim["trim_ano"], y=trim["valor_pedido"],
        marker_color=COR["secundaria"],
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.0f}<extra></extra>"
    ))
    fig_bar.update_layout(
        title="Receita por Trimestre (ultimos 12)",
        xaxis_title="", yaxis_title="Receita (R$)",
        template="plotly_white",
        margin=dict(l=60, r=20, t=60, b=40),
        yaxis_tickprefix="R$ ", yaxis_tickformat=",.",
    )

    # Cards de Previsao
    prev_cards = ""
    mape = modelos.loc[modelos["modelo"] == "SARIMA", "MAPE_%"]
    mape_val = mape.values[0] if len(mape) > 0 else 0

    meses_nome = {"01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr", "05": "Mai",
                  "06": "Jun", "07": "Jul", "08": "Ago", "09": "Set", "10": "Out",
                  "11": "Nov", "12": "Dez"}

    for _, r in previsao.iterrows():
        mes_num = r["mes"].split("-")[1]
        ano = r["mes"].split("-")[0]
        nome_mes = meses_nome.get(mes_num, mes_num)
        prev_cards += kpi_card_html(
            f"{nome_mes}/{ano}",
            fmt_moeda(r["receita_prevista"]),
            f"Min: {fmt_moeda(r['receita_min'])} | Max: {fmt_moeda(r['receita_max'])}"
        )
    prev_cards += kpi_card_html("MAPE", f"{mape_val:.1f}%", "Precisao SARIMA", COR["previsao"])

    return f"""
    {cards}
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px;">
        <div style="flex:3;min-width:500px;">{fig_to_div(fig_linha, 380)}</div>
    </div>
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px;">
        <div style="flex:2;min-width:400px;">{fig_to_div(fig_bar, 350)}</div>
        <div style="flex:1;min-width:300px;">
            <h3 style="color:{COR['primaria']};margin:0 0 12px 6px;font-size:14px;">
                Previsao SARIMA — Proximos Meses</h3>
            <div style="display:flex;flex-wrap:wrap;gap:0;">{prev_cards}</div>
        </div>
    </div>"""


# ============================================================
# PAGINA 2: MARKETING
# ============================================================
def pagina_marketing(vendas, clientes):
    total_cli = clientes["documento"].nunique()
    vips = clientes[clientes["segmento"] == "VIP"]["documento"].nunique() if "segmento" in clientes.columns else 0
    em_risco = clientes[clientes["segmento"].isin(["Em Risco", "Perdendo VIP"])]["documento"].nunique() if "segmento" in clientes.columns else 0
    omni = clientes[clientes["omnichannel"] == True]["documento"].nunique() if "omnichannel" in clientes.columns else 0
    pct_omni = omni / total_cli * 100 if total_cli > 0 else 0

    cards = f"""
    <div style="display:flex;gap:0;margin-bottom:20px;flex-wrap:wrap;">
        {kpi_card_html("Total Clientes", fmt_num(total_cli))}
        {kpi_card_html("Clientes VIP", fmt_num(vips), cor_valor=COR["positivo"])}
        {kpi_card_html("Em Risco", fmt_num(em_risco), cor_valor=COR["negativo"])}
        {kpi_card_html("% Omnichannel", f"{pct_omni:.1f}%", cor_valor=COR["previsao"])}
    </div>"""

    # Rosca: Segmentos RFM
    if "segmento" in clientes.columns:
        seg = clientes.groupby("segmento")["documento"].nunique().reset_index()
        seg.columns = ["segmento", "qtd"]
        seg = seg.sort_values("qtd", ascending=False)
        cores_seg = [CORES_SEGMENTOS.get(s, "#999") for s in seg["segmento"]]

        fig_rosca = go.Figure(go.Pie(
            labels=seg["segmento"], values=seg["qtd"],
            hole=0.5, marker=dict(colors=cores_seg),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>%{value} clientes (%{percent})<extra></extra>"
        ))
        fig_rosca.update_layout(
            title="Segmentacao de Clientes (RFM)",
            template="plotly_white", showlegend=False,
            margin=dict(l=20, r=20, t=60, b=20),
        )
    else:
        fig_rosca = go.Figure()

    # Barras: Receita por Canal
    canal = vendas.groupby("canal")["valor_pedido"].sum().sort_values(ascending=True).reset_index()
    fig_canal = go.Figure(go.Bar(
        y=canal["canal"], x=canal["valor_pedido"],
        orientation="h", marker_color=COR["secundaria"],
        hovertemplate="<b>%{y}</b><br>R$ %{x:,.0f}<extra></extra>"
    ))
    fig_canal.update_layout(
        title="Receita por Canal",
        template="plotly_white",
        margin=dict(l=100, r=20, t=60, b=40),
        xaxis_tickprefix="R$ ", xaxis_tickformat=",.",
    )

    # Treemap: Faixa de Valor
    faixa = vendas.groupby("faixa_valor", observed=True).agg(
        qtd=("valor_pedido", "count"),
        receita=("valor_pedido", "sum")
    ).reset_index()
    faixa = faixa[faixa["qtd"] > 0]

    fig_tree = go.Figure(go.Treemap(
        labels=faixa["faixa_valor"],
        values=faixa["qtd"],
        parents=[""] * len(faixa),
        marker=dict(colors=[COR["primaria"], COR["secundaria"], "#5B9BD5",
                            "#70AD47", COR["previsao"], COR["negativo"]][:len(faixa)]),
        texttemplate="<b>%{label}</b><br>%{value} pedidos",
        hovertemplate="<b>%{label}</b><br>%{value} pedidos<extra></extra>"
    ))
    fig_tree.update_layout(
        title="Distribuicao por Faixa de Valor (qtd pedidos)",
        template="plotly_white",
        margin=dict(l=10, r=10, t=60, b=10),
    )

    # Tabela Top 20 Clientes
    if "monetario" in clientes.columns:
        top20 = clientes.nlargest(20, "monetario")[
            ["nome_cliente", "segmento", "frequencia", "monetario", "ticket_medio"]
        ].copy()
        top20["monetario"] = top20["monetario"].apply(lambda x: f"R$ {x:,.2f}" if pd.notna(x) else "")
        top20["ticket_medio"] = top20["ticket_medio"].apply(lambda x: f"R$ {x:,.2f}" if pd.notna(x) else "")

        fig_tab = go.Figure(go.Table(
            header=dict(
                values=["Cliente", "Segmento", "Frequencia", "Total Compras", "Ticket Medio"],
                fill_color=COR["primaria"], font=dict(color="white", size=12),
                align="left"
            ),
            cells=dict(
                values=[top20[c] for c in top20.columns],
                fill_color=[COR["fundo"]], font=dict(size=11),
                align="left", height=28
            )
        ))
        fig_tab.update_layout(
            title="Top 20 Clientes por Valor Total",
            margin=dict(l=10, r=10, t=60, b=10),
        )
    else:
        fig_tab = go.Figure()

    return f"""
    {cards}
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px;">
        <div style="flex:1;min-width:350px;">{fig_to_div(fig_rosca, 380)}</div>
        <div style="flex:1;min-width:350px;">{fig_to_div(fig_canal, 380)}</div>
    </div>
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px;">
        <div style="flex:1;min-width:350px;">{fig_to_div(fig_tree, 350)}</div>
    </div>
    <div style="margin-bottom:20px;">{fig_to_div(fig_tab, 500)}</div>
    """


# ============================================================
# PAGINA 3: GERENTE DE LOJA
# ============================================================
def pagina_gerente(vendas, vendedores):
    n_vend = vendedores["vendedor"].nunique()
    receita = vendedores["total_vendas"].sum()
    ticket_geral = vendas["valor_pedido"].mean()
    top_vend = vendedores.iloc[0]

    cards = f"""
    <div style="display:flex;gap:0;margin-bottom:20px;flex-wrap:wrap;">
        {kpi_card_html("Vendedores", fmt_num(n_vend))}
        {kpi_card_html("Receita Total", fmt_moeda(receita))}
        {kpi_card_html("Ticket Medio", fmt_moeda(ticket_geral))}
        {kpi_card_html("Melhor Vendedor", top_vend['vendedor'],
                        fmt_moeda(top_vend['total_vendas']), COR["positivo"])}
    </div>"""

    # Ranking Vendedores (top 15)
    top15 = vendedores.head(15).sort_values("total_vendas", ascending=True)
    fig_rank = go.Figure(go.Bar(
        y=top15["vendedor"], x=top15["total_vendas"],
        orientation="h",
        marker_color=COR["secundaria"],
        hovertemplate="<b>%{y}</b><br>R$ %{x:,.0f}<extra></extra>"
    ))
    fig_rank.update_layout(
        title="Ranking de Vendedores por Receita",
        template="plotly_white",
        margin=dict(l=120, r=20, t=60, b=40),
        xaxis_tickprefix="R$ ", xaxis_tickformat=",.",
    )

    # Dispersao: Pedidos vs Ticket Medio
    fig_disp = go.Figure(go.Scatter(
        x=vendedores["qtd_pedidos"], y=vendedores["ticket_medio"],
        mode="markers+text",
        marker=dict(
            size=vendedores["total_vendas"] / vendedores["total_vendas"].max() * 50 + 8,
            color=COR["secundaria"], opacity=0.7,
            line=dict(width=1, color=COR["primaria"])
        ),
        text=vendedores["vendedor"],
        textposition="top center", textfont=dict(size=9),
        hovertemplate="<b>%{text}</b><br>Pedidos: %{x}<br>Ticket: R$ %{y:,.0f}<extra></extra>"
    ))
    fig_disp.update_layout(
        title="Perfil de Vendedores (Pedidos vs Ticket Medio)",
        xaxis_title="Qtd Pedidos", yaxis_title="Ticket Medio (R$)",
        template="plotly_white",
        margin=dict(l=60, r=20, t=60, b=50),
        yaxis_tickprefix="R$ ",
    )

    # Tabela detalhada
    vend_tab = vendedores.copy()
    vend_tab["total_vendas_fmt"] = vend_tab["total_vendas"].apply(lambda x: f"R$ {x:,.2f}")
    vend_tab["ticket_medio_fmt"] = vend_tab["ticket_medio"].apply(lambda x: f"R$ {x:,.2f}")

    fig_tab = go.Figure(go.Table(
        header=dict(
            values=["Vendedor", "Total Vendas", "Pedidos", "Ticket Medio", "Clientes", "Ped/Cliente"],
            fill_color=COR["primaria"], font=dict(color="white", size=12), align="left"
        ),
        cells=dict(
            values=[vend_tab["vendedor"], vend_tab["total_vendas_fmt"],
                    vend_tab["qtd_pedidos"], vend_tab["ticket_medio_fmt"],
                    vend_tab["clientes_atendidos"], vend_tab["pedidos_por_cliente"]],
            fill_color=[COR["fundo"]], font=dict(size=11), align="left", height=28
        )
    ))
    fig_tab.update_layout(
        title="Detalhamento por Vendedor",
        margin=dict(l=10, r=10, t=60, b=10),
    )

    # Evolucao mensal Top 5
    top5_nomes = vendedores.head(5)["vendedor"].tolist()
    vendas_top5 = vendas[vendas["vendedor"].isin(top5_nomes)].copy()
    evo = vendas_top5.groupby(["ano_mes", "vendedor"])["valor_pedido"].sum().reset_index()
    evo = evo.sort_values("ano_mes")
    # Ultimos 24 meses
    meses_unicos = sorted(evo["ano_mes"].unique())
    ultimos_24 = meses_unicos[-24:] if len(meses_unicos) > 24 else meses_unicos
    evo = evo[evo["ano_mes"].isin(ultimos_24)]

    cores_top5 = [COR["primaria"], COR["secundaria"], COR["positivo"], COR["previsao"], COR["negativo"]]
    fig_evo = go.Figure()
    for i, nome in enumerate(top5_nomes):
        dados = evo[evo["vendedor"] == nome]
        fig_evo.add_trace(go.Scatter(
            x=dados["ano_mes"], y=dados["valor_pedido"],
            mode="lines", name=nome,
            line=dict(color=cores_top5[i % len(cores_top5)], width=2),
            hovertemplate=f"<b>{nome}</b><br>%{{x}}<br>R$ %{{y:,.0f}}<extra></extra>"
        ))
    fig_evo.update_layout(
        title="Evolucao Mensal — Top 5 Vendedores (ultimos 24 meses)",
        template="plotly_white",
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=60, r=20, t=70, b=40),
        yaxis_tickprefix="R$ ",
    )

    return f"""
    {cards}
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px;">
        <div style="flex:1;min-width:400px;">{fig_to_div(fig_rank, 400)}</div>
        <div style="flex:1;min-width:400px;">{fig_to_div(fig_disp, 400)}</div>
    </div>
    <div style="margin-bottom:20px;">{fig_to_div(fig_evo, 350)}</div>
    <div style="margin-bottom:20px;">{fig_to_div(fig_tab, 450)}</div>
    """


# ============================================================
# PAGINA 4: VENDEDOR (visao individual)
# ============================================================
def pagina_vendedor(vendas, vendedores, clientes):
    top10_nomes = vendedores.head(10)["vendedor"].tolist()
    sections = ""

    for vendedor_nome in top10_nomes:
        v = vendas[vendas["vendedor"] == vendedor_nome]
        rec = v["valor_pedido"].sum()
        cli = v["documento"].nunique()
        tkt = v["valor_pedido"].mean()
        rank_pos = vendedores[vendedores["vendedor"] == vendedor_nome].index[0] + 1
        total_vend = len(vendedores)
        media_equipe = vendas["valor_pedido"].sum() / vendedores["vendedor"].nunique()

        cards = f"""
        <div style="display:flex;gap:0;margin-bottom:14px;flex-wrap:wrap;">
            {kpi_card_html("Minhas Vendas", fmt_moeda(rec))}
            {kpi_card_html("Meus Clientes", fmt_num(cli))}
            {kpi_card_html("Meu Ticket", fmt_moeda(tkt))}
            {kpi_card_html("Ranking", f"#{rank_pos} de {total_vend}")}
        </div>"""

        # Evolucao mensal
        evo = v.groupby("ano_mes")["valor_pedido"].sum().reset_index().sort_values("ano_mes")
        evo = evo.tail(24)

        fig_evo = go.Figure()
        fig_evo.add_trace(go.Scatter(
            x=evo["ano_mes"], y=evo["valor_pedido"],
            mode="lines+markers", name=vendedor_nome,
            line=dict(color=COR["secundaria"], width=2),
            marker=dict(size=5),
            hovertemplate="%{x}<br>R$ %{y:,.0f}<extra></extra>"
        ))
        fig_evo.add_hline(y=media_equipe / 12, line_dash="dash", line_color=COR["negativo"],
                          annotation_text="Media Equipe/Mes", annotation_position="top right")
        fig_evo.update_layout(
            title=f"Evolucao Mensal",
            template="plotly_white", showlegend=False,
            margin=dict(l=60, r=20, t=50, b=40),
            yaxis_tickprefix="R$ ", height=280,
        )

        # Top 10 clientes do vendedor
        top_cli = v.groupby(["documento", "nome_cliente"]).agg(
            total=("valor_pedido", "sum"),
            pedidos=("numero_pedido", "count")
        ).reset_index().nlargest(10, "total")

        fig_cli = go.Figure(go.Table(
            header=dict(
                values=["Cliente", "Total Compras", "Pedidos"],
                fill_color=COR["primaria"], font=dict(color="white", size=11), align="left"
            ),
            cells=dict(
                values=[top_cli["nome_cliente"],
                        top_cli["total"].apply(lambda x: f"R$ {x:,.2f}"),
                        top_cli["pedidos"]],
                fill_color=[COR["fundo"]], font=dict(size=10), align="left", height=26
            )
        ))
        fig_cli.update_layout(
            title="Meus Top 10 Clientes",
            margin=dict(l=10, r=10, t=50, b=10), height=340,
        )

        sections += f"""
        <div style="background:{COR['branco']};border-radius:12px;padding:20px;
                    margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.06);
                    border-left:4px solid {COR['secundaria']};">
            <h3 style="color:{COR['primaria']};margin:0 0 12px 0;">
                {vendedor_nome}</h3>
            {cards}
            <div style="display:flex;gap:16px;flex-wrap:wrap;">
                <div style="flex:1;min-width:400px;">{fig_to_div(fig_evo, 280)}</div>
                <div style="flex:1;min-width:350px;">{fig_to_div(fig_cli, 340)}</div>
            </div>
        </div>"""

    return sections


# ============================================================
# PAGINA 5: MODELO PREDITIVO
# ============================================================
def pagina_modelo(serie_hp, previsao, modelos):
    sarima = modelos[modelos["modelo"] == "SARIMA"]
    mape = sarima["MAPE_%"].values[0] if len(sarima) > 0 else 0
    mae = sarima["MAE"].values[0] if len(sarima) > 0 else 0
    rmse = sarima["RMSE"].values[0] if len(sarima) > 0 else 0

    cards = f"""
    <div style="display:flex;gap:0;margin-bottom:20px;flex-wrap:wrap;">
        {kpi_card_html("MAPE", f"{mape:.1f}%", "Erro medio percentual")}
        {kpi_card_html("MAE", fmt_moeda(mae), "Erro absoluto medio")}
        {kpi_card_html("RMSE", fmt_moeda(rmse), "Raiz do erro quadratico")}
        {kpi_card_html("Modelo", "SARIMA", "(1,1,1)(1,1,1,12)", COR["previsao"])}
    </div>"""

    # Grafico historico + previsao com area de confianca
    realizado = serie_hp[serie_hp["tipo"] == "Realizado"].sort_values("ano_mes_dt")
    previsto = serie_hp[serie_hp["tipo"] == "Previsto"].sort_values("ano_mes_dt")

    fig = go.Figure()

    # Ultimos 24 meses do realizado
    realizado_recente = realizado.tail(24)

    fig.add_trace(go.Scatter(
        x=realizado_recente["ano_mes_dt"], y=realizado_recente["receita_total"],
        mode="lines", name="Realizado",
        line=dict(color=COR["secundaria"], width=2.5),
        hovertemplate="<b>%{x|%b/%Y}</b><br>R$ %{y:,.0f}<extra></extra>"
    ))

    fig.add_trace(go.Scatter(
        x=previsto["ano_mes_dt"], y=previsto["receita_total"],
        mode="lines+markers", name="Previsto",
        line=dict(color=COR["previsao"], width=2.5, dash="dash"),
        marker=dict(size=10, symbol="diamond"),
        hovertemplate="<b>%{x|%b/%Y}</b><br>R$ %{y:,.0f}<extra></extra>"
    ))

    # Area de confianca
    if "receita_min" in previsao.columns:
        prev_dts = pd.to_datetime(previsao["mes"])
        fig.add_trace(go.Scatter(
            x=pd.concat([prev_dts, prev_dts[::-1]]),
            y=pd.concat([previsao["receita_max"], previsao["receita_min"][::-1]]),
            fill="toself", fillcolor="rgba(255,143,0,0.15)",
            line=dict(color="rgba(255,143,0,0)"),
            name="Intervalo de Confianca",
            hoverinfo="skip"
        ))

    fig.update_layout(
        title="Historico + Previsao SARIMA (ultimos 24 meses)",
        template="plotly_white",
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=60, r=20, t=70, b=40),
        yaxis_tickprefix="R$ ", yaxis_tickformat=",.",
    )

    # Tabela comparacao modelos
    mod_tab = modelos.copy()
    mod_tab["MAE"] = mod_tab["MAE"].apply(lambda x: f"R$ {x:,.0f}" if pd.notna(x) else "")
    mod_tab["RMSE"] = mod_tab["RMSE"].apply(lambda x: f"R$ {x:,.0f}" if pd.notna(x) else "")
    mod_tab["MAPE_%"] = mod_tab["MAPE_%"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "")

    fig_mod = go.Figure(go.Table(
        header=dict(
            values=["Modelo", "MAE", "RMSE", "MAPE"],
            fill_color=COR["primaria"], font=dict(color="white", size=13), align="center"
        ),
        cells=dict(
            values=[mod_tab["modelo"], mod_tab["MAE"], mod_tab["RMSE"], mod_tab["MAPE_%"]],
            fill_color=[COR["fundo"]], font=dict(size=12), align="center", height=35
        )
    ))
    fig_mod.update_layout(
        title="Comparacao dos Modelos",
        margin=dict(l=10, r=10, t=60, b=10),
    )

    # Cards de previsao detalhados
    meses_nome = {"01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr", "05": "Mai",
                  "06": "Jun", "07": "Jul", "08": "Ago", "09": "Set", "10": "Out",
                  "11": "Nov", "12": "Dez"}
    prev_detail = ""
    for _, r in previsao.iterrows():
        m = r["mes"].split("-")
        nome = f"{meses_nome.get(m[1], m[1])}/{m[0]}"
        prev_detail += f"""
        <div style="background:{COR['branco']};border-radius:10px;padding:16px;
                    flex:1;min-width:180px;box-shadow:0 2px 6px rgba(0,0,0,0.08);
                    border-top:3px solid {COR['previsao']};">
            <div style="font-size:13px;color:#888;font-weight:600;">{nome}</div>
            <div style="font-size:22px;font-weight:700;color:{COR['primaria']};margin:8px 0;">
                {fmt_moeda(r['receita_prevista'])}</div>
            <div style="font-size:11px;color:#aaa;">
                {int(r['pedidos_previstos'])} pedidos | {int(r['clientes_previstos'])} clientes</div>
            <div style="font-size:11px;color:#aaa;">
                Ticket: {fmt_moeda(r['ticket_medio_previsto'])}</div>
            <div style="font-size:10px;color:{COR['previsao']};margin-top:6px;">
                {fmt_moeda(r['receita_min'])} ~ {fmt_moeda(r['receita_max'])}</div>
        </div>"""

    return f"""
    {cards}
    <div style="margin-bottom:20px;">{fig_to_div(fig, 420)}</div>
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px;">
        <div style="flex:1;min-width:400px;">{fig_to_div(fig_mod, 220)}</div>
        <div style="flex:1;min-width:400px;">
            <h3 style="color:{COR['primaria']};margin:0 0 12px 0;font-size:14px;">
                Detalhamento da Previsao</h3>
            <div style="display:flex;gap:12px;flex-wrap:wrap;">{prev_detail}</div>
        </div>
    </div>"""


# ============================================================
# MONTAR HTML FINAL
# ============================================================
def montar_html(paginas):
    tabs_btns = ""
    tabs_content = ""

    nomes = ["CEO", "Marketing", "Gerente", "Vendedor", "Modelo Preditivo"]
    icones = ["\U0001F4CA", "\U0001F3AF", "\U0001F465", "\U0001F464", "\U0001F52E"]

    for i, (nome, conteudo) in enumerate(zip(nomes, paginas)):
        ativo = "active" if i == 0 else ""
        display = "block" if i == 0 else "none"

        tabs_btns += f"""
            <button class="tab-btn {ativo}" onclick="showTab({i})"
                    style="padding:12px 24px;border:none;background:{'#fff' if i==0 else 'transparent'};
                    color:{COR['primaria']};font-size:14px;font-weight:{'700' if i==0 else '400'};
                    cursor:pointer;border-radius:8px 8px 0 0;
                    {'box-shadow:0 -2px 8px rgba(0,0,0,0.06);' if i==0 else ''}
                    transition:all 0.2s;">
                {nome}
            </button>"""

        tabs_content += f"""
            <div class="tab-content" id="tab-{i}" style="display:{display};">
                {conteudo}
            </div>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VESTI — Painel de Gestao de Vendas</title>
    <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', -apple-system, sans-serif;
            background: {COR['fundo']};
            color: {COR['texto']};
        }}
        .header {{
            background: linear-gradient(135deg, {COR['primaria']} 0%, #2C3E6B 100%);
            padding: 20px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{
            color: white;
            font-size: 22px;
            font-weight: 600;
        }}
        .header .subtitle {{
            color: rgba(255,255,255,0.7);
            font-size: 12px;
        }}
        .tabs {{
            display: flex;
            background: {COR['fundo']};
            padding: 0 24px;
            gap: 4px;
            border-bottom: 2px solid {COR['cinza']};
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }}
        .tab-btn:hover {{
            background: rgba(255,255,255,0.8) !important;
        }}
        @media (max-width: 768px) {{
            .tabs {{ flex-wrap: wrap; }}
            .tab-btn {{ font-size: 12px !important; padding: 8px 12px !important; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>VESTI — Painel de Gestao de Vendas</h1>
            <div class="subtitle">Dashboard Interativo | Dados atualizados do pipeline</div>
        </div>
        <div style="color:rgba(255,255,255,0.5);font-size:11px;text-align:right;">
            Gerado automaticamente<br>Python + Plotly
        </div>
    </div>

    <div class="tabs">{tabs_btns}</div>

    <div class="container">{tabs_content}</div>

    <div style="text-align:center;padding:20px;color:#bbb;font-size:11px;">
        VESTI Dashboard v1.0 — Dados de pedido_erp.csv + pedido_ecom.json + clientes_crm.csv
    </div>

    <script>
        function showTab(idx) {{
            document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.tab-btn').forEach(el => {{
                el.classList.remove('active');
                el.style.background = 'transparent';
                el.style.fontWeight = '400';
                el.style.boxShadow = 'none';
            }});
            document.getElementById('tab-' + idx).style.display = 'block';
            const btns = document.querySelectorAll('.tab-btn');
            btns[idx].classList.add('active');
            btns[idx].style.background = '#fff';
            btns[idx].style.fontWeight = '700';
            btns[idx].style.boxShadow = '0 -2px 8px rgba(0,0,0,0.06)';

            // Force plotly resize
            setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
        }}
    </script>
</body>
</html>"""


def main():
    print("Carregando dados...")
    vendas, clientes, vendedores, serie, serie_hp, previsao, modelos = carregar_dados()

    print("Gerando Pagina 1: CEO...")
    p1 = pagina_ceo(vendas, serie_hp, previsao, modelos)

    print("Gerando Pagina 2: Marketing...")
    p2 = pagina_marketing(vendas, clientes)

    print("Gerando Pagina 3: Gerente...")
    p3 = pagina_gerente(vendas, vendedores)

    print("Gerando Pagina 4: Vendedor...")
    p4 = pagina_vendedor(vendas, vendedores, clientes)

    print("Gerando Pagina 5: Modelo Preditivo...")
    p5 = pagina_modelo(serie_hp, previsao, modelos)

    print("Montando HTML final...")
    html = montar_html([p1, p2, p3, p4, p5])

    output_path = os.path.join(BASE_DIR, "dashboard_vesti.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nDashboard gerado: {output_path}")
    print("Abra no navegador para visualizar!")


if __name__ == "__main__":
    main()
