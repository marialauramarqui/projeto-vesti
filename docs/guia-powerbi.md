# Guia de Construcao — Dashboard Power BI Vesti

## Passo 1: Importar Dados

1. Abrir Power BI Desktop
2. **Obter Dados** → **Texto/CSV**
3. Importar cada arquivo da pasta `data_powerbi/`:
   - Separador: **Ponto e virgula (;)**
   - Codificacao: **UTF-8**
   - Ao carregar cada arquivo, renomear a query para o nome da tabela

| Arquivo | Nome da Tabela |
|---------|---------------|
| `fato_vendas.csv` | fato_vendas |
| `dim_clientes.csv` | dim_clientes |
| `dim_vendedores.csv` | dim_vendedores |
| `serie_temporal.csv` | serie_temporal |
| `serie_historico_previsao.csv` | serie_historico_previsao |
| `previsao_proximos_meses.csv` | previsao_proximos_meses |
| `comparacao_modelos.csv` | comparacao_modelos |

### Tipos de dados importantes (conferir no Power Query)

| Tabela | Coluna | Tipo |
|--------|--------|------|
| fato_vendas | valor_pedido | Numero Decimal |
| fato_vendas | data_pedido | Data/Hora |
| fato_vendas | ano | Numero Inteiro |
| fato_vendas | mes | Numero Inteiro |
| dim_clientes | recencia | Numero Inteiro |
| dim_clientes | frequencia | Numero Inteiro |
| dim_clientes | monetario | Numero Decimal |
| dim_clientes | ticket_medio | Numero Decimal |
| dim_vendedores | total_vendas | Numero Decimal |
| dim_vendedores | qtd_pedidos | Numero Inteiro |
| serie_temporal | receita_total | Numero Decimal |
| serie_temporal | ano_mes_dt | Data |
| serie_historico_previsao | ano_mes_dt | Data |
| serie_historico_previsao | receita_total | Numero Decimal |
| previsao_proximos_meses | receita_prevista | Numero Decimal |
| comparacao_modelos | MAPE_% | Numero Decimal |

---

## Passo 2: Criar Relacionamentos

Em **Modelo** → arrastar e soltar:

```
fato_vendas.documento  ──N:1──>  dim_clientes.documento
fato_vendas.vendedor   ──N:1──>  dim_vendedores.vendedor
fato_vendas.ano_mes    ──N:1──>  serie_temporal.ano_mes
```

**Configuracoes de cada relacao:**
- Cardinalidade: Muitos para Um (N:1)
- Direcao de filtro cruzado: Unica (dimensao filtra fato)
- Ativa: Sim

---

## Passo 3: Medidas DAX

Criar uma tabela de medidas: **Modelagem** → **Nova Tabela** → `Medidas = {0}`

Depois, criar cada medida abaixo dentro dessa tabela:

### Medidas Basicas

```dax
Receita Total = SUM(fato_vendas[valor_pedido])

Qtd Pedidos = COUNTROWS(fato_vendas)

Ticket Medio = DIVIDE([Receita Total], [Qtd Pedidos], 0)

Clientes Ativos = DISTINCTCOUNT(fato_vendas[documento])
```

### Medidas Temporais

```dax
Receita Mes Anterior =
CALCULATE(
    [Receita Total],
    DATEADD(serie_temporal[ano_mes_dt], -1, MONTH)
)

Variacao MoM =
DIVIDE(
    [Receita Total] - [Receita Mes Anterior],
    [Receita Mes Anterior],
    0
)

Receita Acumulada Ano =
CALCULATE(
    [Receita Total],
    DATESYTD(serie_temporal[ano_mes_dt])
)
```

### Medidas de Segmentacao

```dax
Clientes VIP =
CALCULATE(
    DISTINCTCOUNT(dim_clientes[documento]),
    dim_clientes[segmento] = "VIP"
)

Clientes Em Risco =
CALCULATE(
    DISTINCTCOUNT(dim_clientes[documento]),
    dim_clientes[segmento] IN {"Em Risco", "Perdendo VIP"}
)

Pct Omnichannel =
DIVIDE(
    CALCULATE(
        DISTINCTCOUNT(dim_clientes[documento]),
        dim_clientes[omnichannel] = TRUE
    ),
    DISTINCTCOUNT(dim_clientes[documento]),
    0
)
```

### Medidas de Previsao

```dax
Receita Prevista = SUM(previsao_proximos_meses[receita_prevista])

MAPE Modelo =
CALCULATE(
    MIN(comparacao_modelos[MAPE_%]),
    comparacao_modelos[modelo] = "SARIMA"
)
```

---

## Passo 4: Paginas do Dashboard

### Pagina 1: CEO — Visao Executiva

**Layout sugerido (1280x720):**

```
┌─────────────────────────────────────────────────────────┐
│  VESTI — Painel Executivo                    [Filtro Ano]│
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│ Receita  │ Pedidos  │ Ticket   │ Clientes │ Variacao    │
│ Total    │ Total    │ Medio    │ Ativos   │ MoM %       │
│ R$18,8M  │ 12.993   │ R$1.452  │ 3.582    │ +X%         │
├──────────┴──────────┴──────────┴──────────┴─────────────┤
│                                                         │
│  Grafico de Linhas: Receita Mensal (Real vs Previsao)   │
│  Eixo X: ano_mes | Eixo Y: receita_total               │
│  Usar serie_historico_previsao com campo "tipo"         │
│  Linha azul = Realizado | Linha laranja = Previsto      │
│                                                         │
├─────────────────────────────┬───────────────────────────┤
│                             │                           │
│  Grafico de Barras:         │  Cartoes de Previsao:     │
│  Receita por Trimestre      │  Dez/2024: R$ 201.388     │
│  Eixo X: trimestre+ano     │  Jan/2025: R$ 191.315     │
│  Eixo Y: Receita Total     │  Fev/2025: R$ 209.214     │
│                             │  MAPE: 10,5%              │
└─────────────────────────────┴───────────────────────────┘
```

**Visuais:**

| # | Tipo | Dados | Config |
|---|------|-------|--------|
| 1 | Cartao | [Receita Total] | Formato: R$ moeda, 0 decimais |
| 2 | Cartao | [Qtd Pedidos] | Formato: numero inteiro |
| 3 | Cartao | [Ticket Medio] | Formato: R$ moeda, 0 decimais |
| 4 | Cartao | [Clientes Ativos] | Formato: numero inteiro |
| 5 | Cartao | [Variacao MoM] | Formato: percentual, cor condicional (verde/vermelho) |
| 6 | Grafico de Linhas | serie_historico_previsao: ano_mes_dt (eixo, tipo Data, hierarquia desativada), receita_total (valor), tipo (legenda) | Cores: azul=Realizado, laranja=Previsto. IMPORTANTE: clicar no eixo X e expandir ate "Mes" ou desativar hierarquia de datas para mostrar cada mes individualmente |
| 7 | Grafico de Barras | fato_vendas: trimestre+ano (eixo), [Receita Total] (valor) | Agrupado por ano |
| 8 | Cartao Multiplo | previsao_proximos_meses: mes, receita_prevista | 3 cartoes lado a lado |
| 9 | Segmentacao | fato_vendas[ano] | Filtro de ano |

---

### Pagina 2: Marketing — Clientes e Canais

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  VESTI — Marketing & Clientes          [Filtro Segmento]│
├──────────┬──────────┬──────────┬────────────────────────┤
│ Total    │ VIPs     │ Em Risco │ % Omnichannel          │
│ Clientes │ 904      │ 803      │ 8,2%                   │
├──────────┴──────────┴──────────┴────────────────────────┤
│                             │                           │
│  Grafico de Rosca:          │  Grafico de Barras Horiz: │
│  Distribuicao por Segmento  │  Receita por Canal        │
│  VIP, Leal, Em Risco, etc.  │  (Loja, Link, Site, App)  │
│                             │                           │
├─────────────────────────────┬───────────────────────────┤
│                             │                           │
│  Treemap:                   │  Grafico de Barras:       │
│  Faixa de Valor             │  Uso de Cupom (com/sem)   │
│  (por qtd de pedidos)       │  Tipo de cupom            │
│                             │                           │
├─────────────────────────────┴───────────────────────────┤
│  Tabela: Top 20 clientes por valor total (RFM detalhes) │
└─────────────────────────────────────────────────────────┘
```

**Visuais:**

| # | Tipo | Dados | Config |
|---|------|-------|--------|
| 1 | Cartao | DISTINCTCOUNT(dim_clientes[documento]) | Total clientes |
| 2 | Cartao | [Clientes VIP] | Com icone de estrela |
| 3 | Cartao | [Clientes Em Risco] | Cor vermelha |
| 4 | Cartao | [Pct Omnichannel] | Formato percentual |
| 5 | Rosca | dim_clientes[segmento] (legenda), COUNT documento (valor) | 7 segmentos, cores distintas |
| 6 | Barras Horizontais | fato_vendas[canal] (eixo), [Receita Total] (valor) | Filtrar canal != vazio |
| 7 | Treemap | fato_vendas[faixa_valor] (categoria), [Qtd Pedidos] (tamanho) | Cores gradiente |
| 8 | Barras Empilhadas | fato_vendas[tipo_cupom] (eixo), [Qtd Pedidos] (valor) | Separar com/sem cupom |
| 9 | Tabela | dim_clientes: nome, segmento, frequencia, monetario, ticket_medio | Top N por monetario |
| 10 | Segmentacao | dim_clientes[segmento] | Filtro de segmento |

---

### Pagina 3: Gerente de Loja — Performance da Equipe

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  VESTI — Performance da Equipe              [Filtro Ano]│
├──────────┬──────────┬──────────┬────────────────────────┤
│ Vendedores│ Receita  │ Ticket   │ Melhor Vendedor       │
│ Ativos: 20│ Total   │ Medio    │ Keli (R$ 3,1M)        │
├──────────┴──────────┴──────────┴────────────────────────┤
│                                                         │
│  Grafico de Barras Horizontal:                          │
│  Ranking de Vendedores por Receita Total                │
│  (dim_vendedores, ordenado desc por total_vendas)       │
│                                                         │
├─────────────────────────────┬───────────────────────────┤
│                             │                           │
│  Grafico Dispersao:         │  Tabela Detalhada:        │
│  X = qtd_pedidos            │  vendedor, total_vendas,  │
│  Y = ticket_medio           │  qtd_pedidos, ticket_medio│
│  Tamanho = total_vendas     │  clientes, pedidos/cliente│
│  (identifica perfis)        │                           │
├─────────────────────────────┴───────────────────────────┤
│  Grafico de Linhas: Top 5 vendedores — evolucao mensal  │
│  (fato_vendas filtrado por top 5 vendedores, por mes)   │
└─────────────────────────────────────────────────────────┘
```

**Visuais:**

| # | Tipo | Dados | Config |
|---|------|-------|--------|
| 1 | Cartao | DISTINCTCOUNT(dim_vendedores[vendedor]) | Vendedores ativos |
| 2 | Cartao | [Receita Total] | Formato moeda |
| 3 | Cartao | [Ticket Medio] | Formato moeda |
| 4 | Cartao | Texto: top vendedor | Ou usar medida TOPN |
| 5 | Barras Horizontais | dim_vendedores[vendedor] (eixo), dim_vendedores[total_vendas] (valor) | Ordenar desc, cor gradiente |
| 6 | Dispersao | dim_vendedores: qtd_pedidos (X), ticket_medio (Y), total_vendas (tamanho), vendedor (detalhes) | Mostrar labels |
| 7 | Tabela | dim_vendedores: todas as colunas | Formatacao condicional nas vendas |
| 8 | Linhas | fato_vendas filtrado top 5: ano_mes (eixo), [Receita Total] (valor), vendedor (legenda) | 5 linhas coloridas |

---

### Pagina 4: Vendedor — Meus Resultados

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  VESTI — Meus Resultados   [Filtro Vendedor ▼] [Ano ▼] │
├──────────┬──────────┬──────────┬────────────────────────┤
│ Minhas   │ Meus     │ Meu      │ Meu Ranking           │
│ Vendas   │ Clientes │ Ticket   │ #X de 20              │
├──────────┴──────────┴──────────┴────────────────────────┤
│                                                         │
│  Grafico de Linhas: Minha evolucao mensal               │
│  (receita por mes, filtrado pelo vendedor selecionado)  │
│                                                         │
├─────────────────────────────┬───────────────────────────┤
│                             │                           │
│  Grafico de Rosca:          │  Tabela:                  │
│  Segmentacao dos MEUS       │  Meus Top 10 clientes     │
│  clientes (RFM)             │  por valor total           │
│                             │                           │
├─────────────────────────────┴───────────────────────────┤
│  Indicador: Minhas vendas vs Media da equipe            │
│  (barra de progresso ou gauge)                          │
└─────────────────────────────────────────────────────────┘
```

**Visuais:**

| # | Tipo | Dados | Config |
|---|------|-------|--------|
| 1 | Segmentacao | fato_vendas[vendedor] | **Seletor principal** — filtra toda a pagina |
| 2 | Cartao | [Receita Total] | Filtrado pelo seletor |
| 3 | Cartao | [Clientes Ativos] | Filtrado pelo seletor |
| 4 | Cartao | [Ticket Medio] | Filtrado pelo seletor |
| 5 | Cartao | Ranking (medida RANKX) | Ver medida abaixo |
| 6 | Linhas | fato_vendas: ano_mes (eixo), [Receita Total] (valor) | Filtrado pelo vendedor |
| 7 | Rosca | dim_clientes[segmento] via fato_vendas (filtrado) | Mostra RFM dos clientes do vendedor |
| 8 | Tabela | Top 10 clientes do vendedor: nome, total, frequencia | TOPN filtrado |
| 9 | Gauge | [Receita Total] vs media da equipe | Meta = media |

**Medida DAX para Ranking:**

```dax
Meu Ranking =
RANKX(
    ALL(dim_vendedores[vendedor]),
    CALCULATE([Receita Total]),
    ,
    DESC,
    Dense
)
```

**Medida DAX para Media da Equipe:**

```dax
Media Equipe =
DIVIDE(
    CALCULATE([Receita Total], ALL(fato_vendas[vendedor])),
    DISTINCTCOUNT(ALL(fato_vendas[vendedor])),
    0
)
```

---

## Passo 5: Pagina de Modelo Preditivo (Bonus)

**Opcional — pagina extra para demonstrar o modelo:**

```
┌─────────────────────────────────────────────────────────┐
│  VESTI — Modelo Preditivo SARIMA                        │
├──────────┬──────────┬──────────┬────────────────────────┤
│ MAPE     │ MAE      │ RMSE     │ Modelo Selecionado     │
│ 10,5%    │ R$30.603 │ R$45.132 │ SARIMA(1,1,1)(1,1,1,12)│
├──────────┴──────────┴──────────┴────────────────────────┤
│                                                         │
│  Grafico de Linhas + Area:                              │
│  serie_historico_previsao                               │
│  Linha solida = Realizado | Area tracejada = Previsto   │
│  (usar campo "tipo" para diferenciar)                   │
│                                                         │
├─────────────────────────────┬───────────────────────────┤
│                             │                           │
│  Tabela: Comparacao Modelos │  Cartoes: Previsao 3M     │
│  (comparacao_modelos.csv)   │  Dez: R$201K              │
│  Modelo, MAE, RMSE, MAPE   │  Jan: R$191K              │
│                             │  Fev: R$209K              │
│                             │  (com min-max)            │
└─────────────────────────────┴───────────────────────────┘
```

---

## Passo 6: Formatacao e Tema

### Paleta de Cores Sugerida

| Uso | Cor | Hex |
|-----|-----|-----|
| Primaria (destaques, titulos) | Azul escuro | #1B2A4A |
| Secundaria (barras, linhas) | Azul medio | #4472C4 |
| Destaque positivo | Verde | #2E7D32 |
| Destaque negativo | Vermelho | #C62828 |
| Previsao | Laranja | #FF8F00 |
| Fundo | Cinza claro | #F5F5F5 |
| Texto | Cinza escuro | #333333 |

### Formatacao Geral

- **Titulo do relatorio:** "VESTI — Painel de Gestao de Vendas"
- **Formato de moeda:** R$ #.###,00
- **Fonte:** Segoe UI (padrao Power BI) ou DIN
- **Tamanho de cartoes:** Titulo 10pt, Valor 28pt
- **Bordas:** Arredondadas, sombra suave
- **Cabecalho de pagina:** Barra superior com logo + titulo + filtros

### Dicas de UX

1. Usar **Bookmarks** para simular troca de persona (botoes no cabecalho)
2. Adicionar **Tooltips personalizados** nos graficos com detalhes extras
3. Usar **Formatacao condicional** nos cartoes (verde se positivo, vermelho se negativo)
4. Adicionar **Botoes de navegacao** entre paginas no cabecalho
5. Usar **Sync Slicers** para que o filtro de ano funcione em todas as paginas

---

## Passo 7: Publicar

1. Salvar como `dashboard_vesti.pbix`
2. **Publicar** → Power BI Service (workspace)
3. Configurar **agendamento de atualizacao** (se Gateway configurado)
4. Compartilhar link com stakeholders

---

## Checklist Rapido

- [ ] 7 tabelas importadas com tipos corretos
- [ ] 3 relacionamentos criados (documento, vendedor, ano_mes)
- [ ] Medidas DAX criadas na tabela "Medidas"
- [ ] Pagina 1: CEO — KPIs macro + previsao + tendencia
- [ ] Pagina 2: Marketing — RFM + canais + cupons
- [ ] Pagina 3: Gerente — Ranking + dispersao + evolucao
- [ ] Pagina 4: Vendedor — Filtro individual + meus resultados
- [ ] Pagina 5: Modelo Preditivo (bonus)
- [ ] Tema e cores aplicados
- [ ] Navegacao entre paginas funcionando
- [ ] Filtros sincronizados
