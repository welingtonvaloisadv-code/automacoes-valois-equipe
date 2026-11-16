# Regra - Tratamento automatico de publicacoes (POP 10)

Determinacao do Dr. Welington (06/11/2026): toda publicacao nova do Sync e tratada automaticamente,
todo dia, e o resultado aparece no painel dele as 7h.

- Pipeline: `OPERACIONAL/tratamento_publicacoes.py`; catalogo de tratamento: `config/regras_publicacoes.py`;
  painel: `OPERACIONAL/painel_dr_welington.py`; agendador: `OPERACIONAL/agendar_painel_diario.ps1`.
- Esta e a **autorizacao permanente** do Dr. Welington para a automacao lancar no ADVBOX as tarefas
  de prazo (advogado + controller) e as do suporte geradas por este pipeline. Fora dele, continua valendo:
  nunca criar tarefa sem autorizacao explicita.
- Como o escritorio trata: catalogo + historico de tarefas do proprio processo no ADVBOX. Nao duplicar
  tarefa que a equipe ja lancou depois da publicacao.
- Prazo interno = 3 dias uteis antes do fatal (POP 09); urgencia (reu preso, HC, liminar) = mesmo dia.
  Todo prazo calculado leva [CONFERIR]; em duvida, o menor.
- Minuta no timbrado, terminando em "PRONTA PARA REVISAO DO(A) DR(A). ..." do advogado da area.
  Sem jurisprudencia de memoria: placeholder [INSERIR JURISPRUDENCIA VERIFICADA].
- A IA nunca protocola e nunca marca intimacao como tratada no Sync (POP 09, item 6.3).
- Ao falar com o Dr. Welington (painel, respostas, relatorios para ele): trata-lo por **"senhor"**.
