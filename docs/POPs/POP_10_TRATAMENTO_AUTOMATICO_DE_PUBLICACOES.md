# POP 10 — Tratamento automático de publicações e painel diário do Dr. Welington

**Escritório:** Welington Valois Advogados Associados
**Aplica-se a:** controllers de prazo, advogados de cada área, suporte e Dr. Welington
**Responsável pelo POP:** Dr. Welington Dias Valois (OAB/ES 34.912)
**Origem:** determinação do Dr. Welington em 06/11/2026
**Complementa:** POP 09 (controladoria de prazos) — não o substitui.

---

## 1. Regra

Toda publicação nova capturada pelo **Sync (Atende Direito / DJEN)** é tratada automaticamente pela IA,
todos os dias, antes das 7h:

1. **Identifica o processo** no ADVBOX (área, cliente, ação, fase e histórico de tarefas).
2. **Decide como o escritório trata aquela publicação**: escolhe o tratamento no catálogo do escritório
   (`config/regras_publicacoes.py`), olhando o teor da publicação **e o que a equipe já fez no próprio
   processo** em situações parecidas.
3. **Calcula o prazo fatal e o prazo interno** (3 dias úteis antes do fatal; urgência = mesmo dia). Todo
   prazo sai marcado **[CONFERIR]**. Em dúvida, o prazo menor (POP 09, item 4.3).
4. **Minuta a peça** no timbrado, quando o tratamento pede peça, terminando em
   **"PRONTA PARA REVISÃO DO(A) DR(A). ..."** do advogado da área.
5. **Lança a tarefa no ADVBOX** para o advogado da área e o controller (POP 09), com prazo interno na
   data da tarefa e o prazo fatal no texto. Se o tratamento pede contato com o cliente, lança também a
   tarefa do suporte (Edmundo no previdenciário, Kesia nas demais áreas).
6. **Agenda:** a tarefa com prazo aparece na agenda do ADVBOX; o prazo já fica na agenda do Sync.
   Opcional: evento de dia inteiro no Google Agenda, no prazo fatal (`AGENDA_GOOGLE=1`).
7. **Abre o painel do Dr. Welington** às 7h e sempre que ele entra no notebook.

**A IA nunca protocola.** **Nada é marcado como tratado no Sync** (POP 09, item 6.3). Se a equipe já lançou
a mesma tarefa depois da publicação, a automação **não duplica** e registra isso no painel.

## 2. Catálogo: como o escritório trata cada publicação

| Publicação | Tratamento | Tarefa no ADVBOX | Minuta | Suporte |
|---|---|---|---|---|
| Decisão favorável, nada a recorrer | Ciência | CIENTE SENTENÇA, AUD. E OUTROS. (controller) | — | Informar o cliente |
| Despacho de mero expediente | Acompanhar | ACOMPANHAR DECISÃO/DESPACHO (controller) | — | — |
| Omissão, contradição, erro material | Embargos | EMBARGOS DE DECLARAÇÃO | sim | — |
| Sentença desfavorável/parcial | Apelação / inominado | RECURSO DE APELAÇÃO/INOMINADO | sim | Informar o cliente |
| Recurso da parte contrária | Contrarrazões | ELABORAR CONTRARRAZÕES | sim | — |
| Interlocutória desfavorável agravável | Agravo | AGRAVO DE INSTRUMENTO | sim | — |
| Contestação juntada | Réplica | RÉPLICA/IMPUGNAÇÃO À CONTESTAÇÃO | sim | — |
| Laudo, estudo social, cálculo | Manifestação | MANIFESTAÇÃO COMPLEXA | sim | — |
| Provas, ciência, juntada, rol | Manifestação simples | MANIFESTAÇÃO SIMPLES | sim | — |
| Emenda/juntada sob pena de indeferimento | Emenda | EMENDA À INICIAL | sim | Solicitar documentos |
| Perícia com prazo de quesitos | Quesitos | ELABORAR QUESITOS | sim | Avisar da perícia |
| Perícia/audiência designada | Acompanhar | ACOMPANHAR PERÍCIA / AUDIÊNCIA | — | Avisar o cliente |
| Trânsito favorável / cálculos | Cumprimento | ELABORAR PETIÇÃO DE CUMPRIMENTO DE SENTENÇA | sim | Informar o cliente |
| Implantação, RPV, alvará | Acompanhar | INTIMAÇÃO INSS PARA IMPLANTAR / LEVANTAMENTO DE RPV | — | Informar o cliente |
| Criminal: resposta, alegações finais | Peça | RESPOSTA À ACUSAÇÃO / ALEGAÇÕES FINAIS | sim | — |
| Réu preso, HC, liminar | **Urgente** | PEDIDO DE REVOGAÇÃO / HABEAS CORPUS | sim | — |
| Acórdão desfavorável | Análise de cabimento | ACOMPANHAR DECISÃO/ACÓRDÃO | — | Informar o cliente |

Quem faz o quê segue o POP 09: advogado da área faz e revisa a peça; controller acompanha o prazo e dá baixa.
Para mudar um tratamento, edite `config/regras_publicacoes.py`.

## 3. Painel diário do Dr. Welington (7h)

Abre sozinho no navegador. Mostra:
- **o que precisa da decisão dele** (urgências, processo fora do ADVBOX, área não identificada, prazo vencido, erro);
- **cada publicação tratada**: resumo, providência, prazo fatal e interno, responsáveis, como o escritório
  costuma tratar, link da minuta no timbrado, tarefas lançadas e o que conferir;
- **prazos fatais dos próximos 7 dias**;
- **as demais entregas do dia** (relatórios, minutas, mapas gerados em `SAIDA/`);
- pendências do Sync anteriores ao início da automação (o controller lança, POP 09).

Em cada item o Dr. Welington marca **Validado** ou **Corrigir** (com observação) e clica em
**Baixar validação**; a rotina seguinte registra a validação.

## 4. Revisão humana (obrigatória)

1. O advogado da área abre a minuta, completa `[PREENCHER]`/`[CONFERIR]`, insere a jurisprudência
   verificada (a IA não cita precedente de memória) e confere o prazo no sistema do tribunal.
2. Só então protocola. A baixa segue o POP 09, item 6.

## 5. Comandos

```
python OPERACIONAL/tratamento_publicacoes.py rodar                # simulação (não lança no ADVBOX)
python OPERACIONAL/tratamento_publicacoes.py rodar --executar     # lança as tarefas
python OPERACIONAL/tratamento_publicacoes.py painel --abrir       # só abre o painel
python OPERACIONAL/tratamento_publicacoes.py autorizar-agenda     # 1a vez do Google Agenda
powershell -ExecutionPolicy Bypass -File OPERACIONAL\agendar_painel_diario.ps1   # agenda 7h + login
```

Saídas (não versionadas, dado de cliente): `SAIDA/publicacoes/AAAA-MM-DD/<ÁREA>/` (minutas),
`SAIDA/publicacoes/estado.json`, `SAIDA/publicacoes/logs/`, `SAIDA/painel/HOJE.html`.
