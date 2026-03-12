# Documentacao Tecnica - Desafio Vesti

**Maria Laura Marqui** | Novembro 2024

---

## Sobre o projeto

A Vesti e uma confeccao de moda que vende tanto em loja fisica quanto pelo e-commerce. A ideia aqui foi juntar os dados dessas duas operacoes (que estavam em sistemas separados) num dashboard unico, onde cada perfil de usuario consegue acompanhar o que importa pra ele. Alem disso, criei um modelo preditivo pra projetar a receita dos proximos meses.

Trabalhei com 3 fontes de dados:

- **ERP** (`pedido_erp.csv`) - 11.494 pedidos da loja fisica, de outubro/2016 ate abril/2024
- **E-commerce** (`pedido_ecom.json`) - 1.505 pedidos online, de dezembro/2023 ate novembro/2024
- **CRM** (`clientes_crm.csv`) - 24.520 registros de clientes

O dashboard foi pensado pra 4 personas: o CEO que precisa de visao macro, o Marketing que quer entender os clientes e canais, o Gerente de Loja que acompanha a equipe, e o Vendedor que quer ver seus proprios numeros.

---

## Por que escolhi essas ferramentas

**Python pra tratar os dados** - o JSON do e-commerce vinha com dados aninhados (listas dentro de colunas), e isso no Power Query ia ser bem trabalhoso. No Python eu consegui tratar, limpar e ja rodar os modelos preditivos tudo no mesmo lugar. Usei o Jupyter Notebook pra ir documentando cada etapa conforme avancava.

As bibliotecas que usei: pandas pra manipulacao de dados, numpy pra calculos, statsmodels pros modelos de serie temporal (SARIMA e Holt-Winters) e scikit-learn pra regressao linear e metricas.

**Power BI pro dashboard** - alem de ser o mais usado no mercado brasileiro, ele tem suporte nativo a relacionamentos entre tabelas, o que facilita montar o Star Schema. Os filtros interativos tambem ajudam bastante pra cada persona navegar na sua visao.

**Star Schema como modelo de dados** - optei por separar em tabela fato (vendas) e dimensoes (clientes, vendedores, tempo). Assim o dashboard fica mais rapido e se precisar adicionar uma dimensao nova no futuro (tipo produtos), e so criar o CSV e relacionar. Nao precisa mexer na fato.

---

## O que fiz no tratamento dos dados

Essa foi a parte que mais deu trabalho. Cada fonte tinha seus problemas.

**Limpeza:**
- Achei um documento `99.999.999/9999-99` que claramente era dado de teste. Removi do ERP (6 pedidos) e do CRM (1 registro).
- No CRM tinha 30 clientes duplicados pelo mesmo documento. Mantive o cadastro mais recente de cada um.
- O JSON do e-commerce tinha uma coluna `products` que era uma lista de objetos dentro de cada linha - impossivel trabalhar de forma tabular. Removi ela.
- As datas do ERP vinham sem timezone e as do e-commerce vinham em UTC. Padronizei tudo pra datetime sem timezone, so pra nao ter problema na hora de juntar.

**Padronizacao:**
- Nomes de vendedores vinham de todo jeito: "jessica", " JESSICA ", "Jessica". Padronizei tudo com strip + title case.
- O valor do pedido no ERP vinha em formato brasileiro ("1.060,80"). Converti pra float tirando o ponto de milhar e trocando virgula por ponto.
- No CRM, o campo vendedor tinha valores `\N` (null do banco). Troquei por "Venda Direta" que faz mais sentido pro negocio.

**Unificacao:**
- Um problema que encontrei foi que ao fazer o merge do ERP com o CRM, as duas tabelas tinham uma coluna chamada `vendedor`. O pandas criava `vendedor_x` e `vendedor_y`, o que bagunca tudo. Resolvi renomeando o vendedor do CRM pra `vendedor_crm` antes de juntar. Assim ficou claro: `vendedor` e quem fez a venda, `vendedor_crm` e quem ta associado ao cliente no cadastro.
- No final, 99,98% dos pedidos bateram com algum cliente no CRM. So 3 ficaram sem match.

---

## Features que criei

**Temporais** - extrair da data do pedido o ano, mes, trimestre, dia da semana e a combinacao ano_mes. Sao esses campos que alimentam os filtros e eixos dos graficos no Power BI.

**Faixa de valor** - categorizei os pedidos em 6 faixas (ate R$200, R$201-500, R$501-1000, R$1001-2000, R$2001-5000, acima de R$5000). Isso ajuda a entender a distribuicao do ticket. O resultado: 64% dos pedidos ficam entre R$501 e R$2.000, que e o core do negocio.

**Segmentacao RFM** - essa foi a parte mais legal. Calculei Recencia, Frequencia e Valor Monetario por cliente, dei uma nota de 1 a 4 pra cada dimensao usando rank percentual (que funciona melhor do que quartis quando tem muitos empates) e classifiquei em 7 segmentos:

| Segmento | Quantidade | O que significa |
|----------|------------|-----------------|
| VIP | 904 (25%) | Compra recente, frequente e com valor alto |
| Novo Promissor | 750 (21%) | Comprou recentemente mas so uma vez - potencial |
| Inativo | 534 (15%) | Faz tempo que nao compra |
| Regular | 454 (13%) | Nem muito ativo nem inativo |
| Em Risco | 442 (12%) | Costumava comprar mas ta esfriando |
| Perdendo VIP | 361 (10%) | Era VIP mas sumiu |
| Leal | 137 (4%) | Compra com frequencia, recem ativo |

Tambem identifiquei que 8,2% dos clientes sao omnichannel (compram tanto na loja quanto online). Esses clientes tendem a gastar mais.

---

## Modelo preditivo

Testei 3 modelos de serie temporal pra prever a receita mensal:

| Modelo | MAPE | Observacao |
|--------|------|-----------|
| SARIMA(1,1,1)(1,1,1,12) | 10,5% | Melhor resultado |
| Regressao Linear com features sazonais | 14,2% | Serviu como baseline |
| Holt-Winters | 18,1% | Pior dos tres |

Fui de **SARIMA** porque teve o menor erro (MAPE de 10,5%), consegue capturar a sazonalidade anual de 12 meses e lida bem com a tendencia dos dados. Separei os ultimos 6 meses pra validacao e treinei com os 92 meses anteriores.

A previsao que o modelo gerou:

| Mes | Receita | Pedidos | Ticket Medio |
|-----|---------|---------|--------------|
| Dez/2024 | R$ 201.388 | 57 | R$ 3.510 |
| Jan/2025 | R$ 191.315 | 81 | R$ 2.348 |
| Fev/2025 | R$ 209.214 | 126 | R$ 1.658 |

Faz sentido: dezembro tem menos pedidos mas ticket mais alto (presente de fim de ano, colecao verao). Janeiro cai um pouco e fevereiro ja recupera volume.

**O que o modelo nao pega:** eventos pontuais tipo Black Friday ou lancamento de colecao. Tambem tem o fato de que o e-commerce so tem 1 ano de dados, entao o modelo aprende mais o padrao da loja fisica. Pra producao, o ideal e retreinar todo mes.

---

## Arquitetura dos dados no Power BI

Organizei num Star Schema simples:

```
                    dim_clientes (24.489)
                    PK: documento
                         |
dim_vendedores (20)      |       serie_temporal (96 meses)
PK: vendedor  ---------- | ---------- PK: ano_mes
                         |
                    fato_vendas (12.993)
                    FK: documento, vendedor, ano_mes
```

Os relacionamentos sao todos N:1 da fato pras dimensoes. Exportei 7 CSVs pra pasta `data_powerbi/`:

- `fato_vendas.csv` - todos os pedidos (ERP + E-commerce), ja com features temporais
- `dim_clientes.csv` - cadastro de clientes com RFM e segmento
- `dim_vendedores.csv` - metricas agregadas por vendedor
- `serie_temporal.csv` - receita e pedidos agregados por mes
- `serie_historico_previsao.csv` - historico + previsao no mesmo formato (pra fazer o grafico de real vs previsto)
- `previsao_proximos_meses.csv` - previsao detalhada dos 3 meses
- `comparacao_modelos.csv` - metricas de cada modelo testado

---

## Indicadores por persona

**CEO** - receita total, ticket medio, quantidade de clientes ativos, variacao mes a mes e a previsao do proximo trimestre. A ideia e que ele bata o olho e entenda se o negocio ta crescendo ou nao.

**Marketing** - distribuicao dos clientes por segmento RFM, quantidade de clientes em risco ou perdendo VIP (pra acionar campanhas de retencao), desempenho por canal do e-commerce e taxa de uso de cupom. Hoje 88,5% dos pedidos online nao usam cupom - tem espaco pra explorar isso.

**Gerente de Loja** - ranking de vendedores por receita, pedidos por vendedor, ticket medio e tamanho da carteira de clientes. Da pra ver que as top 3 (Keli, Denize e Natalia) concentram quase metade da receita.

**Vendedor** - uma pagina com filtro onde cada um seleciona o proprio nome e ve suas vendas, seus clientes, sua posicao no ranking e a evolucao mensal. Funciona como um painel individual.

---

## Insights que achei nos dados

Alguns destaques do que encontrei durante a analise:

1. A receita total acumulada e de R$ 18,87M com ticket medio de R$ 1.452
2. O e-commerce responde por 16% dos pedidos - parece pouco, mas foi lancado so em dezembro/2023 e ja mostra boa tracao
3. 904 clientes sao VIP e precisam de atencao especial pra retencao
4. 442 clientes estao "em risco" e 361 estao "perdendo VIP" - sao quase 800 clientes que ja compraram bastante e estao se afastando. Campanha de reativacao aqui faz sentido
5. Keli, Denize e Natalia juntas representam 48% do faturamento. Se uma dessas sair, o impacto e grande
6. Natalia atende mais clientes que todo mundo (688) mas com ticket menor. Danisio tem o maior ticket medio (R$ 1.612) - perfis de venda bem diferentes
7. No e-commerce, 67% das vendas vem por "Link" - vale investigar se e link compartilhado por WhatsApp/redes sociais
8. So 11,5% dos pedidos online usam cupom. Tem espaco pra testar estrategias de desconto sem canibalizar margem

---

## Como manter atualizado

O fluxo e simples:

1. Exportar os dados novos do ERP, E-commerce e CRM nos mesmos formatos (CSV e JSON)
2. Substituir os arquivos na pasta do projeto
3. Rodar o script Python (`python pipeline.py`) - ele faz tudo: trata, calcula RFM, treina o modelo e exporta os CSVs
4. No Power BI, clicar em "Atualizar Dados" (Ctrl+F5)

Tambem criei um `pipeline.py` que pode ser agendado no Task Scheduler do Windows pra rodar automaticamente. O notebook `tratamento_analise.ipynb` continua disponivel pra quem preferir rodar celula por celula e ver os outputs.

O modelo SARIMA e retreinado toda vez que o pipeline roda, entao ele vai se ajustando com os dados novos. Se em algum momento o MAPE passar de 20%, vale revisar os parametros ou considerar outro modelo.

---

## Escalabilidade

O Star Schema facilita bastante a evolucao:

- Precisa de uma dimensao de produtos? Cria um `dim_produtos.csv`, relaciona por SKU e pronto
- Quer novas metricas? Adiciona medidas DAX no Power BI sem mexer nos dados
- Nova fonte de dados (marketplace, por exemplo)? Trata em Python seguindo o mesmo padrao e concatena na fato

O notebook tambem e extensivel - da pra adicionar celulas novas sem quebrar as existentes. E o modelo preditivo pode evoluir pra incluir variaveis externas (tipo datas comerciais) ou previsoes por canal/vendedor separadamente.

---

## Estrutura do repositorio

```
projeto-vesti/
├── tratamento_analise.ipynb    # Notebook com todo o tratamento + modelo
├── pipeline.py                 # Script pra automacao (mesma logica do notebook)
├── run_pipeline.bat            # Wrapper pra agendar no Task Scheduler
├── data_powerbi/               # CSVs exportados pro Power BI
│   ├── fato_vendas.csv
│   ├── dim_clientes.csv
│   ├── dim_vendedores.csv
│   ├── serie_temporal.csv
│   ├── serie_historico_previsao.csv
│   ├── previsao_proximos_meses.csv
│   └── comparacao_modelos.csv
├── docs/
│   └── documentacao-tecnica.md
├── logs/                       # Logs do pipeline automatizado
├── pedido_erp.csv              # Dados brutos (nao versionados)
├── pedido_ecom.json            # Dados brutos (nao versionados)
├── clientes_crm.csv            # Dados brutos (nao versionados)
└── desafio.pdf                 # Briefing do desafio
```

---

## Checklist dos criterios de avaliacao

| # | Criterio | Onde ta |
|---|----------|---------|
| 1 | Plataforma e modelagem | Power BI com Star Schema |
| 2 | Indicadores | KPIs por persona, RFM, previsao SARIMA |
| 3 | Insights | 8 insights acionaveis ao longo do documento |
| 4 | Sustentacao | Pipeline automatizavel, fluxo de atualizacao definido |
| 5 | Escalabilidade | Star Schema extensivel, notebook modular |
| 6 | Personalizacao | 4 visoes (CEO, Marketing, Gerente, Vendedor) |
| 7 | Documentacao | Este documento |
