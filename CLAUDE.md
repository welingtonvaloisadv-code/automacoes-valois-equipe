# Welington Valois Advogados Associados - Central de Automacoes

> Escritorio: **Welington Valois Advogados Associados** | Responsavel:
> **Dr. Welington Dias Valois (OAB/ES 34.912 e OAB/MG 249.303)**
> Sedes: **Iuna/ES** (Rua Galaor Rios, 289, Centro), **Ibatiba/ES** e **Irupi/ES** (sede no CNPJ).
> CNPJ 64.917.923/0001-95 | Contato: welingtonvaloisadv@gmail.com | (28) 99981-5672.
> Areas (por volume): **Previdenciario ~65%** (salario-maternidade, beneficio por incapacidade, BPC/LOAS,
> aposentadoria rural, pensao, auxilio-acidente), **Criminal ~25%** e demais ~10% (familia e sucessoes,
> bancario, civel/consumidor).

## Regra de ouro

**A IA NUNCA protocola.** Toda peca gerada aqui e SEMPRE para revisao humana do advogado responsavel pela
area antes de qualquer protocolo. Nada envia peca direto ao processo. Os agentes terminam toda peca marcada
**"PRONTA PARA REVISAO DO(A) DR(A). ..."**.

## Estrutura

```
VALOIS_ADVOGADOS/
├── agentes_claude/       # agentes juridicos (Claude.ai Projects/Skills)
├── .claude/agents/       # mesmos agentes como subagentes do Claude Code + pipeline operacional
├── .claude/skills/       # skills ADVBOX, peca-escritorio, formatar-escritorio, jurimetria...
├── .claude/rules/        # compliance, fluxo operacional, padroes de documentos
├── INTEGRACOES/          # google, advbox, asaas, zapsign, atendedireito (WhatsApp)
├── INTAKE/               # intake: ficha, contrato, procuracao, declaracao, ZapSign, ADVBOX
├── FINANCEIRO/           # fechamento, conciliacao Asaas x ADVBOX, cobranca (lembretes 10/5/3/2 dias + dia)
├── OPERACIONAL/          # tarefas, processos, prazos, pecas; agente VALOIS.IA (webhook FastAPI)
├── SYNC/                 # docs assinados ZapSign -> Drive
├── SAIDA/                # relatorios e mapas gerados (NAO versionado - dado de cliente)
├── docs/POPs/            # procedimentos do escritorio (uso da IA, mapa, audiencia, WhatsApp, relatorio)
├── DOCS_MODELOS/         # timbrado + pecas-modelo REAIS do escritorio (aguardando)
├── CADASTROS/ BASE_CONHECIMENTO/ UTILS/
├── config/               # .env (nao versionar), equipe.py, regras_financeiras.py, timbrado_modelo.docx
└── docs/                 # ONBOARDING, DEPLOY_VPS
```

## Equipe e areas (briefing 16/09/2026)
| Area | Responsavel |
|---|---|
| Previdenciario | Priscila Araujo de Matos (OAB/ES 39.600) + estagiarios: Mariana Oliveira (administrativo), Maressa Teodoro (judicial), Edmundo Oliveira (comercial) |
| Familia e sucessoes | Derlira Garcia Pimentel Soares (OAB/ES 27.296); apoio: Kauã Moreira Valois (estagiario) |
| Bancario | Heliézer de Medeiros Pontes (OAB/ES 38.904) |
| Civel/consumidor | Gisele Teófilo de Avila (OAB/ES 23.868); apoio: João Pedro (estagiario, Irupi) |
| Criminal | Welington Dias Valois e Guilherme Mota Lopes Costa (OAB/ES 44.599) |
| Secretaria | Kesia Reder (agenda, WhatsApp, financeiro) |

Gestao: principal Welington; secundarios Kauã (Iuna), Gisele (Ibatiba), Priscila (Previdenciario).

## Squad Comercial - contratacao (INTAKE, POP 06)

**REGRA - cliente cadastrado no ADVBOX (fluxo padrao):** a equipe cadastra o cliente no ADVBOX
(e, se ja houver, o processo); a IA gera **contrato de honorarios, declaracao de hipossuficiencia
e procuracao** a partir desse cadastro:
`python INTAKE/main.py advbox <CPF | ID | nome> [--area X --acao "..."] [--processo ID] [--unidade IBATIBA]`
- Area e acao vem do processo do cliente no ADVBOX; sem processo, informar `--area` e `--acao`.
- O ADVBOX e a fonte dos dados: o que nao estiver la (ex.: nacionalidade) sai `[PREENCHER]` e o
  advogado completa na revisao. Nunca completar com suposicao.
- Daqui em diante e igual ao fluxo abaixo: revisao -> `enviar` (o `enviar` nao recadastra no ADVBOX).

Fluxo alternativo, a partir da reuniao (sem cadastro previo no ADVBOX):
`python INTAKE/main.py gerar TRANSCRICAO.pdf CNH.pdf CADASTRO.txt --area PREVIDENCIARIO [--unidade IBATIBA]`
-> a IA (Claude, le PDF escaneado direto) extrai os dados e faz a analise; sai no timbrado:
Ficha (ATOS INTERNOS, "PRONTA PARA REVISAO"), Contrato, Procuracao e Declaracao (PASTA DO CLIENTE),
na pasta AREA > CLIENTE do Drive, e uma linha em `SAIDA/intake/INDICE_CONTRATACOES.csv`.

**Nada sai para o cliente no `gerar`.** O advogado da area revisa (completa os `[PREENCHER]`,
inclusive honorarios), assina `revisado_por`, marca `enviar=SIM`; entao
`python INTAKE/main.py enviar --simular` (confere, gera PDFs) e `enviar` (ZapSign + links no
WhatsApp pela Evolution + cadastro ADVBOX; processo so com a coluna `tipo_advbox`). O envio
trava se faltar revisor ou sobrar `[PREENCHER]`/`[CONFERIR]` no documento revisado.
- `gerar --exemplo` demonstra com caso ficticio, sem IA e sem Drive. `status` lista o andamento.
- Textos-base em `INTAKE/modelos/` sao PROVISORIOS; o modelo real vai em `DOCS_MODELOS/contratacao/`.
- Honorarios: previdenciario no exito (parcelas fixas apos a concessao); valores padrao por area
  em `config/regras_financeiras.py` (HONORARIOS_PADRAO, vazio). Asaas fica para a fase financeira.

## Relatorio mensal ao cliente (POP 05)
`python OPERACIONAL/relatorio_mensal.py` — gera, em lote, o relatorio de situacao processual de
todo processo ativo do ADVBOX: texto em linguagem do dia a dia + **audio** explicando a fase
(edge-tts, voz pt-BR). Sai em `SAIDA/relatorios/AAAA-MM/<CLIENTE>/` com um `INDICE_PARA_REVISAO.csv`.

**Nao envia nada sozinho.** O advogado da area revisa, assina a coluna `revisado_por` e marca
`enviar=SIM`; so entao `--enviar` dispara pela Evolution API. O envio para se faltar revisor ou
se sobrar `[PREENCHER]` no texto.

- `--exemplo` roda com dados ficticios, sem tocar no ADVBOX (serve para demonstrar)
- `--responsavel PRISCILA` | `--mes 09/2026` | `--sem-audio`
- Prazo do POP: ate o 5o dia util de cada mes. Disparo em LOTE, nao cliente a cliente.
- `SAIDA/` e gitignored: contem nome e telefone de cliente e este repositorio e publico.

## Tratamento automatico de publicacoes + painel do Dr. Welington (POP 10)
Determinacao do Dr. Welington (06/11/2026). Todo dia as 7h (e ao entrar no Windows) o agendador roda
`python OPERACIONAL/tratamento_publicacoes.py diario --executar --abrir`:
publicacao nova do Sync -> processo no ADVBOX -> a IA decide como o escritorio trata (catalogo em
`config/regras_publicacoes.py` + historico de tarefas do processo) -> prazo fatal/interno [CONFERIR] ->
minuta no timbrado (PRONTA PARA REVISAO) -> tarefa no ADVBOX p/ advogado + controller (+ suporte) ->
painel `SAIDA/painel/HOJE.html`, que abre sozinho. Regra completa: `.claude/rules/tratamento-publicacoes.md`.
- `rodar` sem `--executar` = simulacao (nada vai ao ADVBOX). Agendar: `OPERACIONAL\agendar_painel_diario.ps1`.
- IA: `OPERACIONAL/ia_backend.py` (chave de API se houver; senao o Claude Code da maquina, `claude -p`).
- Nao duplica tarefa ja lancada pela equipe; nao marca intimacao como tratada no Sync; nunca protocola.
- O Dr. Welington e tratado por **"senhor"**.

## Squad Financeiro (FINANCEIRO)
`python FINANCEIRO/fechamento_mensal.py MM/YYYY`
- Fonte da verdade: ADVBOX (por vencimento). Cobranca recorrente via Asaas com lembretes 10, 5, 3, 2 dias antes e no dia.
- Comissoes/excecoes: `config/regras_financeiras.py` (vazio ate o escritorio definir).
- Distribuicao de lucros NAO e despesa operacional. Inadimplencia hoje ~2%.

## Squad Operacional (OPERACIONAL)
- `python OPERACIONAL/main.py tarefas | processos | prazos`
- `python OPERACIONAL/main.py criar-tarefa <lawsuit_id> ACOMPANHAMENTO <responsavel> -m "msg" -p AAAA-MM-DD --urgente`
- Tarefas ADVBOX usam `/posts` (nao `/tasks`); campo de mensagem e `comments`; `from` = `config/equipe.py`.
- Nunca criar tarefa sem autorizacao explicita.

## Prioridades de implantacao (definidas pelo escritorio)
1. Pecas previdenciarias (inicial, recurso) no timbrado
2. Relatorio mensal de andamento em linguagem simples ao cliente (ate o 5o dia util; hoje nao existe modelo)
3. Varredura diaria (8h) de e-mails do INSS: welingtondiasvalois@gmail.com e welingtonvaloisadv@gmail.com
4. Leitura de intimacoes/publicacoes do ADVBOX -> tarefa de prazo automatica
5. Intake de cliente novo (procuracao + declaracao + contrato via ZapSign + cadastro ADVBOX)
6. Cobranca recorrente no Asaas
7. Banco de teses / segundo cerebro (decisoes e sentencas favoraveis, foco previdenciario)

Piloto de WhatsApp: numero do previdenciario (28) 99940-2133.

## Confirmado na reunião gravada de 14/09/2026
- **Previdenciario ajuiza na COMARCA LOCAL (competencia delegada), nao na Justica Federal.** A Federal
  so entra em grau de recurso. Sao duas comarcas locais (confirmar quais no kickoff). Os juizes locais
  conhecem a realidade dos agricultores da regiao.
- **Portal de autoatendimento nao serve para o publico previdenciario dele** (rural, pouca familiaridade
  com tecnologia: "se eu pedir para mandar uma foto, ele nao manda"). O canal e WhatsApp + relatorio
  explicado em linguagem simples.
- **A automacao roda na maquina do escritorio**, nao em VPS nossa ("faco tudo na sua maquina").
- **Relatorio mensal e disparado em lote**, nao cliente a cliente. Horario do relatorio do INSS e
  configuravel (ele cogitou 6h, nao so 8h).
- **Implantacao em 3 fases** (reunioes de 2h, uma por semana): plugar tudo -> banco de teses -> produzir
  peca; treinamento geral depois. ~3 semanas.
- **KPIs que ele quer do ADVBOX:** tempo medio de processo, ticket medio, processos ativos e encerrados.
- Origem: reuniao de apresentacao de 14/09/2026 (gravacao transcrita).

## Regras que a IA nunca ignora
- Beneficio por incapacidade: laudo medico com menos de 60 dias e descricao da CID.
- BPC/LOAS: renda per capita inferior a 1/4 do salario minimo, laudo medico atualizado e cadastro no CRAS/CadUnico atualizado.
- A IA ajuda no trabalho, nao o substitui: procuracoes, declaracoes e contratos com modelo usam o modelo do escritorio.
- Ao terminar uma peca, o agente pode gerar a "peca da parte contraria" rebatendo os pontos (revisao adversarial).
- Nunca inventar dado do cliente nem jurisprudencia; sem dado -> placeholder / "[CONFERIR]".
- Arquivos entram por link do Drive, nao colados inteiros no chat.

## Agentes juridicos (agentes_claude/ e .claude/agents/)
`valois-previdenciario`, `valois-iniciais`, `valois-quesitos`, `valois-criminal`, `valois-familia-sucessoes`,
`valois-bancario`, `valois-civel-consumidor` - todos com CALIBRACAO PENDENTE ate o escritorio enviar pecas reais
(1-2 protocoladas por tipo). Pipeline: analista-juridica, gerador-documentos, revisora-controladoria, compliance-reviewer.

## Padroes de peca
Segoe UI 12pt, justificado, espacamento 1,15, linguagem tecnica/formal/objetiva, sempre no timbrado
(`config/timbrado_modelo.docx`, versao nova "Advogados Associados"). Recuo da 1a linha: provisorio 1,25cm - confirmar.
Ver `.claude/rules/padroes-documentos.md`.

## Sync - Atende Direito (monitoramento PDPJ/DJEN)
Processos, intimacoes/publicacoes com resumo e data fatal, prazos, audiencias, autos e jurimetria.
- Claude Code: servidor MCP `atendedireito-sync` em `.mcp.json` (le `ATENDEDIREITO_SYNC_TOKEN` do ambiente).
- Python: `INTEGRACOES/sync_atendedireito.py` (`painel | prazos | intimacoes | processo <CNJ> | ferramentas`).
- Consulta livre. Ferramentas que alteram a conta (`tratar_intimacao`, `registrar_processo`, `criar_monitor`,
  `criar_mineracao`, `excluir_processo`, `bloquear_processo`...) so com autorizacao explicita; mineracao tem custo.

## Infinitum (POPs / kanban do escritorio)
Organizacao "Welington Valois Advogados Associados" (plano trial). POPs: CRM Comercial, Ativacao do cliente,
Producao juridica inicial, Protocolo / Distribuicao, Peticionamento. Cadastro "Clientes". Membros: Welington
(owner), Kauã (admin), Guilherme. Cards de Peticionamento/Protocolo ja nascem de tarefas do ADVBOX.
- Claude Code: servidor MCP `infinitum` em `.mcp.json` (le `INFINITUM_PUBLIC_TOKEN` do ambiente).
- Python: `INTEGRACOES/infinitum_integration.py` (`pops | fases <pop> | cards [pop] | card <id> | tarefas | usuarios | cadastros | ferramentas`).
- Consulta livre. Criar/mover/editar/excluir card, tarefa, registro, evento, automacao, campo, POP e qualquer
  cobranca Asaas pela Infinitum so com autorizacao explicita (cobranca e real).
- Swagger da API REST publica: https://public.infinitum.app.br/swagger/ (header `X-Public-Token`).

## ADVBOX API (confirmar se o plano tem API liberada)
Base `https://app.advbox.com.br/api/v1` | Bearer token + User-Agent | `/posts` tarefas, `/lawsuits` processos,
`/transactions` financeiro | Rate limit GET 30/min, POST 500/dia | Token em `config/.env` (`ADVBOX_API_TOKEN`).
O escritorio hoje so lanca atividades no ADVBOX (sem kanban); requerimentos INSS ficam em planilha.

## Migracao ADVBOX -> Infinitum (UTILS/migrar_advbox_infinitum.py)
Le o ADVBOX (so GET) e grava no Infinitum clientes, processos, movimentacoes, financeiro e tarefas.
`extrair` -> `resumo` -> `migrar` (simulacao) -> `migrar --executar --limite 3` -> `status`.
Retomavel e idempotente (clientes casados por CPF/CNPJ). A API do Infinitum NAO tem DELETE:
sempre comecar com `--limite 3` e conferir na tela. Gravar no Infinitum so com autorizacao explicita.
Snapshot/estado em `SAIDA/migracao_infinitum/` (dado de cliente, nao versionado).
Config: `INFINITUM_PUBLIC_TOKEN`, `INFINITUM_ORG_ID`, `INFINITUM_DB_CLIENTES` (opcional) no `config/.env`.

## Credenciais
Tudo em `config/.env` (copiar de `.env.example`). NUNCA versionar. Credenciais so chegam em canal seguro,
depois da assinatura do contrato.
