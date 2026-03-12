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

**HTML hospedado no GitHub Pages pro dashboard** - optei por construir o dashboard em HTML puro com Chart.js, hospedado diretamente no GitHub Pages. Essa escolha traz algumas vantagens: o dashboard fica acessivel por qualquer navegador sem precisar instalar nada, funciona em qualquer dispositivo (desktop, tablet, celular), e o deploy e automatico — basta dar push no repositorio que o GitHub Pages ja publica a versao atualizada. Alem disso, nao depende de licenca de software como o Power BI, o que facilita o compartilhamento com qualquer stakeholder.

**Automacao com GitHub Actions** - criei um workflow de CI/CD (`.github/workflows/main.yml`) que roda automaticamente todos os dias as 08:00 no horario de Brasilia. O workflow faz o seguinte: instala o Python e as dependencias, executa o `pipeline.py` (que trata os dados, recalcula o RFM, retreina o modelo SARIMA e exporta o JSON atualizado), e se houver mudancas no `dados_dashboard.json`, faz commit e push automaticamente. Tambem pode ser disparado manualmente pelo botao "Run workflow" no GitHub. Isso garante que o dashboard esteja sempre com os dados do dia sem nenhuma intervencao manual.

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

**Temporais** - extrair da data do pedido o ano, mes, trimestre, dia da semana e a combinacao ano_mes. Sao esses campos que alimentam os filtros e eixos dos graficos no dashboard.

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

## Arquitetura dos dados

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

Os relacionamentos sao todos N:1 da fato pras dimensoes. O pipeline exporta os dados tratados em formato JSON (`dados_dashboard.json`), que e consumido diretamente pelo HTML do dashboard. Tambem sao gerados 7 CSVs na pasta `data_powerbi/`:

- `fato_vendas.csv` - todos os pedidos (ERP + E-commerce), ja com features temporais
- `dim_clientes.csv` - cadastro de clientes com RFM e segmento
- `dim_vendedores.csv` - metricas agregadas por vendedor
- `serie_temporal.csv` - receita e pedidos agregados por mes
- `serie_historico_previsao.csv` - historico + previsao no mesmo formato (pra fazer o grafico de real vs previsto)
- `previsao_proximos_meses.csv` - previsao detalhada dos 3 meses
- `comparacao_modelos.csv` - metricas de cada modelo testado

---

## Design e UX do dashboard

O dashboard foi construido em HTML com a biblioteca Chart.js e segue um design system coeso pensado para facilitar a leitura e navegacao.

### Identidade visual

- **Tema escuro** com fundo em tons de roxo profundo (`#0F0820`, `#1A0D35`) que reduz fadiga visual e destaca os dados
- **Paleta de cores** consistente: teal (`#00C9A7`) como cor primaria de destaque, roxo (`#6B3FA0`) como secundaria, laranja (`#FFB347`) para alertas e previsoes, vermelho (`#FF5A7E`) para indicadores negativos
- **Tipografia** em Segoe UI/system-ui, garantindo boa legibilidade em qualquer sistema operacional

### Estrutura de navegacao

O layout segue o padrao de aplicacao web moderna com **sidebar fixa a esquerda** + **area de conteudo a direita**:

- **Sidebar (220px):** logo da Vesti no topo, menu de navegacao com 5 paginas e footer com identificacao. Os itens de menu tem efeito hover com destaque teal e o item ativo recebe um gradiente sutil
- **Header:** titulo da pagina atual com indicador "Ao Vivo" (dot pulsante) para reforcar que os dados sao atualizados automaticamente
- **Conteudo:** scroll vertical com cards organizados em grids responsivos

### Paginas e personas

O dashboard tem **5 paginas**, cada uma pensada para um perfil de usuario:

**1. Visao CEO** - Pagina inicial com 5 KPI cards no topo (receita total, pedidos, ticket medio, clientes ativos, variacao MoM), grafico de linha de receita mensal real vs previsao SARIMA, cards de previsao dos proximos 3 meses com intervalo de confianca, receita por trimestre agrupada por ano e receita por canal.

**2. Marketing** - 4 KPI cards (total clientes, VIP, em risco, % omnichannel), grafico donut de segmentacao RFM com 7 segmentos, receita por canal em barras horizontais, distribuicao de faixa de valor dos pedidos, uso de cupom (sem cupom, frete gratis, desconto, cashback, parceiro) e tabela dos top 10 clientes com detalhes de RFM.

**3. Performance** - 4 KPI cards (vendedores ativos, receita total, ticket medio, top vendedora), ranking de vendedores por receita em barras horizontais, grafico de dispersao pedidos x ticket (tamanho do ponto = receita total), evolucao mensal das top 5 vendedoras em grafico de linhas e tabela completa com todas as 20 vendedoras.

**4. Vendedor** - Pagina personalizada com **slicer de vendedoras** no topo (botoes pill para selecionar o nome). Ao clicar, exibe: perfil com avatar, nome, posicao no ranking, 4 KPI cards individuais (minhas vendas, meus pedidos, meu ticket medio, meus clientes), grafico de evolucao mensal, comparacao com media da equipe (gauge visual) e lista dos top clientes daquele vendedor.

**5. Modelo SARIMA** - Pagina dedicada ao modelo preditivo com 4 KPI cards (MAPE, MAE, RMSE, modelo selecionado), grafico de serie historica completa + previsao com ponto de conexao, cards de previsao dos 3 meses, tabela comparativa dos 3 modelos testados e grafico de barras de MAPE por modelo.

### Componentes visuais

- **KPI cards** com barra de acento colorida no topo, icone, valor em destaque e label. Efeito hover com elevacao sutil
- **Cards de previsao** com mes, valor previsto em teal, intervalo min-max e quantidade de pedidos em laranja
- **Tabelas** com header em fundo teal translucido, hover nas linhas e badges coloridos para segmentos RFM
- **Graficos** configurados com tooltips customizados (fundo escuro, borda teal), grid sutil e formatacao em BRL
- **Slicer de vendedoras** com botoes arredondados (pill buttons), estado ativo em teal com animacao de transicao
- **Gauge visual** para comparacao vendedor vs media, com barra de progresso gradiente

### Responsividade

O layout usa CSS Grid com breakpoint em 1200px — a grade de 5 KPI cards reorganiza para 3 colunas em telas menores. Tabelas tem scroll horizontal quando necessario.

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

O dashboard e atualizado automaticamente via **GitHub Actions**. O workflow (`.github/workflows/main.yml`) roda todos os dias as 08:00 no horario de Brasilia e executa o seguinte fluxo:

1. Faz checkout do repositorio
2. Configura o Python 3.9 e instala as dependencias (pandas, numpy, statsmodels, scikit-learn)
3. Roda o `pipeline.py` que trata os dados, recalcula o RFM, retreina o SARIMA e exporta o `dados_dashboard.json`
4. Se houver mudancas no JSON, faz commit e push automaticamente
5. O GitHub Pages publica a versao atualizada do dashboard

Tambem e possivel disparar o workflow manualmente pelo botao "Run workflow" na interface do GitHub.

Para adicionar dados novos, basta atualizar os arquivos fonte (`pedido_erp.csv`, `pedido_ecom.json`, `clientes_crm.csv`) no repositorio — a automacao cuida do resto.

O modelo SARIMA e retreinado toda vez que o pipeline roda, entao ele vai se ajustando com os dados novos. Se em algum momento o MAPE passar de 20%, vale revisar os parametros ou considerar outro modelo.

O notebook `tratamento_analise.ipynb` continua disponivel pra quem preferir rodar celula por celula e ver os outputs.

---

## Escalabilidade

O Star Schema facilita bastante a evolucao:

- Precisa de uma dimensao de produtos? Cria um `dim_produtos.csv`, relaciona por SKU e pronto
- Quer novas metricas? Adiciona novas visualizacoes no HTML ou medidas no pipeline sem mexer nos dados
- Nova fonte de dados (marketplace, por exemplo)? Trata em Python seguindo o mesmo padrao e concatena na fato

O notebook tambem e extensivel - da pra adicionar celulas novas sem quebrar as existentes. E o modelo preditivo pode evoluir pra incluir variaveis externas (tipo datas comerciais) ou previsoes por canal/vendedor separadamente.

---

## Estrutura do repositorio

```
projeto-vesti/
├── dashboard_desafio.html         # Dashboard HTML (GitHub Pages)
├── tratamento_analise.ipynb       # Notebook com todo o tratamento + modelo
├── pipeline.py                    # Script pra automacao (mesma logica do notebook)
├── run_pipeline.bat               # Wrapper pra agendar no Task Scheduler
├── dados_dashboard.json           # JSON com dados agregados (gerado pelo pipeline)
├── data_powerbi/                  # CSVs exportados
│   ├── fato_vendas.csv
│   ├── dim_clientes.csv
│   ├── dim_vendedores.csv
│   ├── serie_temporal.csv
│   ├── serie_historico_previsao.csv
│   ├── previsao_proximos_meses.csv
│   └── comparacao_modelos.csv
├── .github/
│   └── workflows/
│       └── main.yml               # GitHub Actions — automacao diaria
├── docs/
│   └── documentacao-tecnica.md
├── logs/                          # Logs do pipeline automatizado
├── pedido_erp.csv                 # Dados brutos (nao versionados)
├── pedido_ecom.json               # Dados brutos (nao versionados)
├── clientes_crm.csv               # Dados brutos (nao versionados)
└── desafio.pdf                    # Briefing do desafio
```

---

## Checklist dos criterios de avaliacao

| # | Criterio | Onde ta |
|---|----------|---------|
| 1 | Plataforma e modelagem | HTML + Chart.js com Star Schema, hospedado no GitHub Pages |
| 2 | Indicadores | KPIs por persona, RFM, previsao SARIMA |
| 3 | Insights | 8 insights acionaveis ao longo do documento |
| 4 | Sustentacao | GitHub Actions com automacao diaria + pipeline Python |
| 5 | Escalabilidade | Star Schema extensivel, notebook modular, HTML componentizado |
| 6 | Personalizacao | 5 visoes (CEO, Marketing, Performance, Vendedor, Modelo SARIMA) |
| 7 | Documentacao | Este documento |
