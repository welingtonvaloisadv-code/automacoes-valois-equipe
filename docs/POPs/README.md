# POPs — Welington Valois Advogados Associados

Procedimentos Operacionais Padrão do escritório. Origem: roteiros das reuniões internas do
Dr. Welington Dias Valois (OAB/ES 34.912).

| POP | Assunto | Principais responsáveis |
|---|---|---|
| [POP 01](POP_01_USO_DA_IA.md) | Uso da IA: link do Drive, modelo do escritório, revisão adversarial | todos |
| [POP 02](POP_02_MAPA_DO_PROCESSO.md) | Mapa do processo impresso entregue ao cliente (com chocolate) | advogado da área + secretaria |
| [POP 03](POP_03_AUDIENCIA.md) | Audiência, testemunhas, relatório e controle do processo pela área | advogado da área |
| [POP 04](POP_04_WHATSAPP.md) | WhatsApp: etiqueta por área, quem responde o quê, postura um passo à frente | secretaria + advogado da área |
| [POP 05](POP_05_RELATORIO_MENSAL.md) | Relatório mensal ao cliente até o 5º dia útil, com áudio | advogado da área + secretaria |
| [POP 06](POP_06_CONTRATACAO.md) | Contratação: ficha, contrato, procuração e declaração; revisão antes do ZapSign | advogado da área + comercial + secretaria |
| [POP 07](POP_07_PRIMEIRO_ATENDIMENTO.md) | Primeiro atendimento no WhatsApp: pergunta de área, perguntas por área, urgências, relatório de triagem e agendamento | secretaria + advogado da área |
| [POP 08](POP_08_CADASTRO_E_ORIGEM_DO_CLIENTE.md) | Organização do cliente: controle de atendimentos, origem/indicação, conflito de interesse, LGPD, indicadores | secretaria + comercial + advogado da área |
| [POP 09](POP_09_CONTROLADORIA_DE_PRAZOS.md) | Controladoria de prazos judiciais e extrajudiciais: controller por área, prazo interno de 3 dias, baixa e sprint de sexta | controllers + advogado da área + suporte |
| [POP 10](POP_10_TRATAMENTO_AUTOMATICO_DE_PUBLICACOES.md) | Tratamento automático de publicações do Sync: decisão de tratamento, prazo, minuta, tarefa no ADVBOX e painel das 7h do Dr. Welington | IA + controllers + advogado da área + Dr. Welington |
| [POP 11](POP_11_AUDIENCIA_CRIMINAL.md) | Audiência criminal: análise dos autos, intimação das testemunhas, comunicado e preparação do cliente, atos da audiência, relatório e retorno | advogados do criminal + Kauã + Kesia |

## Regras que atravessam todos os POPs

- **A IA nunca protocola e nunca envia sozinha.** Tudo passa pela revisão do advogado responsável pela área.
- **Cada advogado responde pelos processos da sua área**, mesmo que outro advogado tenha feito a inicial.
- **Linguagem simples com o cliente.** O público do escritório é do interior e boa parte é rural.
- **Nunca inventar dado, prazo ou jurisprudência.** Sem certeza, escreve-se **[CONFERIR]** e resolve-se antes.
- Onde o procedimento ainda não foi definido, o texto traz **[DEFINIR com o Dr. Welington]**.

## Ferramentas ligadas aos POPs

- `UTILS/mapa_do_processo.py` — gera o mapa do processo em HTML pronto para imprimir (POP 02):
  `python UTILS/mapa_do_processo.py previdenciario` → `SAIDA/mapa_processo_previdenciario.html`
  Áreas: `previdenciario`, `criminal`, `familia`, `bancario`, `civel`.
- `INTAKE/main.py` — contratação (POP 06): `gerar` para revisão, `enviar` depois da revisão.
- `docs/POPs/modelos/POP07_FOLHA_DE_MESA_SECRETARIA.docx` (e `.pdf`) — folha de mesa da secretaria,
  frente e verso no timbrado (POP 07).
- `docs/POPs/modelos/CONTROLE_DE_ATENDIMENTOS.xlsx` — modelo vazio do controle de atendimentos (POP 08).
  A cópia preenchida fica no Drive, nunca no repositório.
