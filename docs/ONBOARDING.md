# Onboarding — Welington Valois Advogados Associados

Checklist de configuracao. Faca **na ordem**. Marque cada item ao concluir.
Todo o preenchimento acontece em `config/.env` (copie de `config/.env.example`),
em `config/equipe.py` e em `config/regras_financeiras.py`.

---

## 0. O que ja se sabe

- **Nome / marca:** Welington Valois Advogados Associados (timbrado novo, 09/2026). Razao social no CNPJ/Asaas:
  WELINGTON VALOIS SOCIEDADE DE ADVOCACIA (64.917.923/0001-95); o briefing cita "PONTES E VALOIS SOCIEDADE DE
  ADVOGADOS" - CONFIRMAR qual e a razao social oficial (afeta contrato/procuracao).
- **Advogado responsavel:** Dr. Welington Dias Valois - OAB/ES 34.912 e OAB/MG 249.303 (no briefing aparece 34.913
  uma vez - conferir).
- **E-mail:** welingtonvaloisadv@gmail.com. Telefone: (28) 99981-5672. WhatsApp do piloto: (28) 99940-2133 (previdenciario).
- **Areas:** Previdenciario ~65%, Criminal ~25%, demais ~10% (familia/sucessoes, bancario, civel/consumidor).
- **Abrangencia:** Iuna/ES, Ibatiba/ES e Irupi/ES (sede no CNPJ: Irupi).
- **Sistema juridico:** ADVBOX, usado so para lancar atividades (sem kanban). API liberada? NAO SABE - verificar no plano.
  Requerimentos do INSS ficam em planilha.
- **Outros sistemas:** ZapSign e Asaas ja contratados. Sem CRM/WhatsApp de atendimento (piloto: Evolution API no numero do prev).
- **Drive:** conta welingtonvaloisadv@gmail.com, organizado por area > cliente; parte ainda em computadores locais.
- **IA hoje:** Claude Max 5x, ChatGPT e Gemini gratuitos. Existe uma maquina que pode ficar ligada em horario comercial.
- **Agentes juridicos de IA:** em `agentes_claude/` (7 agentes: previdenciario, iniciais, quesitos, criminal,
  familia-sucessoes, bancario, civel-consumidor). Todos com base tecnica generica; CALIBRACAO PENDENTE com pecas reais.
- **Timbrado:** recebido em 16/09 e salvo em `config/timbrado_modelo.docx` (gitignored; copiar a parte para a VPS).

## 1. Credenciais de API (config/.env)

Nenhuma credencial foi recebida ate a criacao deste repositorio. Confirmar com o
Dr. Welington, uma a uma:

- [ ] **ANTHROPIC_API_KEY** — chave da API Claude (console.anthropic.com).
- [ ] **ADVBOX_API_TOKEN** — SE o escritorio usar ADVBOX (a confirmar).
- [ ] **ASAAS_API_TOKEN** — SE usar Asaas para cobranca (a confirmar).
- [ ] **ZAPSIGN_API_TOKEN** — SE for usar assinatura digital via ZapSign.
- [ ] **ATENDE_DIREITO_TOKEN** — SE for usar CRM/WhatsApp Atende Direito.
- [ ] **Google Cloud** — coloque o JSON de credenciais em `config/credentials.json`
      (Service Account ou OAuth) e, se OAuth, gere o `token.json` no 1o uso.

## 2. Identidade do escritorio (config/.env)

Ja vem com os defaults do Welington Valois Advogados Associados. Confira/ajuste:
- [x] ESCRITORIO_NOME / NOME_ESCRITORIO = Welington Valois Advogados Associados
- [ ] ESCRITORIO_CNPJ — nao recebido.
- [x] ESCRITORIO_ADVOGADO = Dr. Welington Dias Valois
- [x] ESCRITORIO_OAB = OAB/ES 34.912
- [x] ESCRITORIO_CIDADE / CIDADE_FORO = Iúna/ES, Ibatiba/ES e Irupi/ES
- [ ] ESCRITORIO_ENDERECO — endereco fisico do escritorio, nao recebido.
- [x] ESCRITORIO_TELEFONE = (28) 99981-5672, ESCRITORIO_EMAIL =
      welingtonvaloisadv@gmail.com
- [ ] ADVOGADO_RESPONSAVEL_EMAIL — confirmar se e o mesmo e-mail institucional
      acima ou um pessoal diferente, para signatario padrao (ZapSign/ADVBOX).

## 3. Usuarios ADVBOX (config/.env + config/equipe.py)

SE o escritorio usar ADVBOX, no painel ADVBOX > Usuarios, pegue os IDs e preencha:
- [ ] **ADVBOX_USER_RESPONSAVEL** — ID do Dr. Welington Dias Valois.
- [ ] ADVBOX_USER_OPERACIONAL — ID de quem recebe tarefas operacionais.
- [ ] ADVBOX_USER_FINANCEIRO — ID de quem lanca transacoes financeiras.
- [ ] ADVBOX_USER_FROM — ID do usuario que "assina" as tarefas (/posts).
- [ ] ADVBOX_USER_AGENTE — ID da conta-agente (VALOIS.IA) que recebe as
      tarefas do robo.
- [ ] ADVBOX_TASK_TYPE_ACOMPANHAMENTO — ID do tipo de tarefa de acompanhamento.
- [ ] (Opcional) ADVBOX_USERS_MAP = "ID:NOME,ID:NOME" para exibir nomes nos
      relatorios.

## 4. Google Drive / Docs (config/.env)

### 4.1 Credencial (uma vez, na maquina do escritorio)
1. Em console.cloud.google.com, logado como welingtonvaloisadv@gmail.com: criar um projeto,
   ativar **Google Drive API**, **Google Docs API** e **Google Sheets API**.
2. Tela de consentimento OAuth: tipo "Externo", adicionar a propria conta como usuario de teste.
   Publicar o app ("Em producao") para o token nao expirar a cada 7 dias.
3. Credenciais > Criar ID do cliente OAuth > **App para computador**. Baixar o JSON e salvar
   como `config/oauth_credentials.json` (gitignored).
4. `python INTEGRACOES/google_setup.py` — abre o navegador para o login e grava
   `config/token.json`. Depois so confere o acesso; nao cria nada no Drive.

### 4.2 IDs (o ID e o final da URL da pasta/arquivo)
- [ ] DRIVE_PASTA_PREVIDENCIARIO / _CRIMINAL / _FAMILIA_E_SUCESSOES / _BANCARIO /
      _CIVEL_E_CONSUMIDOR — pastas de area; a pasta do cliente nasce dentro da area
      (`INTAKE/main.py gerar ... --area PREVIDENCIARIO`).
- [ ] GOOGLE_PLANILHA_CONTRATOS (+ GOOGLE_ABA_CONTRATOS) — planilha .xlsx de numeracao de
      contratos (opcional; sem ela o contrato sai sem numero).
- [ ] Modelos reais da contratacao (contrato por area, procuracao, declaracao) em
      `DOCS_MODELOS/contratacao/` — ver `INTAKE/modelos/LEIA-ME.md`. Ate la, sai o texto-base
      PROVISORIO. Honorarios padrao por area em `config/regras_financeiras.py`
      (HONORARIOS_PADRAO).
- [ ] Financeiro: DRIVE_PASTA_FECHAMENTO_ID, DRIVE_PASTA_FINANCEIRO_ID,
      DRIVE_PLANILHA_HISTORICO_ID, DRIVE_PLANILHA_RESULTADO_ID.
- [ ] DRIVE_PASTA_CLIENTES_ID — usada pelo handler de sincronizacao de assinados.

## 5. Regras financeiras (config/regras_financeiras.py)

Vem VAZIO de proposito (sem comissao nenhuma calculada). O escritorio tem um
unico advogado responsavel — nao ha indicacao ate agora de estrutura de
comissionamento com terceiros. Cadastrar apenas se/quando isso for definido:
- [ ] **COMISSOES** — para cada comissionado: rotulo, sufixos na descricao do
      Asaas, percentual, advbox_customers_id, exclusoes e (se for o caso)
      lista_fechada.
- [ ] **ADVBOX_FINANCEIRO** — banco/centro de custo/categoria para lancar
      comissoes.
- [ ] **EXCLUIR_FATURAMENTO** — clientes que nao contam como receita (se houver).
- [ ] **PERCENTUAL_PROVISAO_LUCRO** — se o escritorio usa provisao/reserva
      (default 0).

## 6. Listas de cobranca (FINANCEIRO/)

- [ ] `clientes_nao_cobrar.txt` — um cliente por linha (quem NUNCA recebe
      cobranca).
- [ ] `clientes_negociar.txt` — clientes em negociacao/acordo.

## 7. Padrao de pecas / timbrado

- [x] `config/timbrado_modelo.docx` — recebido em 16/09 e copiado (fica fora do git). Se mudar, o escritorio precisa
      enviar o .docx oficial (logo + cabecalho/rodape) — ver
      `config/timbrado_modelo.LEIA-ME.txt` para o formato exigido.
- [ ] Confirmar margens (o motor aplica 2,54cm em todos os lados (igual ao timbrado recebido) por
      default e recuo provisorio de 1,25cm — confirmar com o escritorio; fonte Segoe UI 12, espacamento 1,15).
- [ ] **Calibracao dos agentes:** o escritorio disse que ja enviou pecas-modelo (previdenciaria inicial, recurso
      administrativo, replica) - localizar no Drive e calibrar `valois-previdenciario`, `valois-iniciais` e `valois-quesitos`.
      Para criminal, familia, bancario e civel/consumidor pedir 1-2 pecas protocoladas por tipo e refazer os agentes
      no estilo real (Segoe UI 12, linguagem tecnica, formal e objetiva).

## 8. Agente Operacional (VALOIS.IA)

- [ ] AGENTE_OP_TOKEN — defina um token forte (autentica o webhook).
- [ ] AGENTE_OP_PORT — porta do servidor (default 8787).
- [ ] (Opcional) AGENTE_OP_USER_PHONES — JSON {"<id_advbox>":"<telefone>"} para
      notificacao WhatsApp ao concluir tarefa.
- [ ] Suba o servico: `OPERACIONAL/agente_operacional/iniciar_servicos.bat`
      (Windows) ou `.sh` (macOS/Linux). Testar com `verificar_servicos` e parar
      com `parar_servicos`.
- [ ] Configure o gatilho/n8n (`n8n_workflow.json`) apontando para a URL do
      webhook e usando o AGENTE_OP_TOKEN.
- [ ] Para rodar 24/7, avaliar deploy em VPS (`docs/DEPLOY_VPS.md`, systemd) —
      decidir com o escritorio se sera VPS propria ou compartilhada.

## 9. Agendamentos

- [ ] SYNC de assinados 3x/dia: `SYNC/sync_assinados.bat` (Windows) / `.sh`
      (macOS/Linux). Agendar via Task Scheduler (Windows) ou cron/launchd
      (macOS/Linux).
- [ ] (Opcional) Cobranca semanal: agendar `FINANCEIRO/cobranca_semanal.py` do
      mesmo jeito.

---

### Verificacao final

- [ ] `python OPERACIONAL/main.py tarefas` lista tarefas do ADVBOX sem erro
      (depende de ADVBOX_API_TOKEN + ADVBOX_USER_RESPONSAVEL preenchidos, e de
      confirmar que o escritorio usa ADVBOX).
- [ ] `python FINANCEIRO/fechamento_mensal.py MM/YYYY --sem-lancar` roda o
      fechamento (modo seguro) — depende das regras financeiras (secao 5).
- [ ] `python INTAKE/main.py gerar --exemplo` gera os 4 documentos no timbrado; um caso
      real de teste passa por revisao e `enviar --simular` antes do primeiro envio de verdade
      (POP 06).
- [ ] Testar os 7 agentes juridicos em `agentes_claude/` — ver
      `GUIA_INSTALACAO_CLAUDE_AI.md` para instalar como Projects no Claude.ai.
