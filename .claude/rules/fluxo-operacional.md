# Fluxo Operacional - Welington Valois Advogados Associados

## Contratacao (INTAKE) - ver docs/POPs/POP_06_CONTRATACAO.md

### Regra: cliente cadastrado no ADVBOX -> contrato, declaracao e procuracao
Quando a equipe cadastra o cliente no ADVBOX, os 3 documentos de contratacao (contrato de
honorarios, declaracao de hipossuficiencia, procuracao) sao gerados A PARTIR DO CADASTRO:
`python INTAKE/main.py advbox <CPF | ID | nome>` (area/acao do processo no ADVBOX, ou
`--area` e `--acao`). Dado ausente no ADVBOX = `[PREENCHER]`, completado pelo advogado na
revisao. Mesma revisao e mesmo `enviar` do fluxo abaixo. Nao recadastra no ADVBOX.

### Fluxo a partir da reuniao (sem cadastro previo)

1. **Reuniao inicial** - cadastro do cliente (CADASTRO_CLIENTE.txt) + gravacao/transcricao
2. **Coleta de documentos** - CNH/RG, comprovante de endereco e os da area
3. **Gerar** - `python INTAKE/main.py gerar TRANSCRICAO.pdf CNH.pdf CADASTRO.txt --area <AREA>`
   (analise da IA, pasta AREA > CLIENTE no Drive, Ficha, Contrato, Procuracao, Declaracao)
4. **Revisao humana** - advogado da area completa os [PREENCHER], assina `revisado_por` e
   marca `enviar=SIM` em SAIDA/intake/INDICE_CONTRATACOES.csv
5. **Enviar** - `python INTAKE/main.py enviar --simular`, depois `enviar`
   (ZapSign + WhatsApp + cadastro ADVBOX)
6. **Assinados** - SYNC/sync_assinados.py desce os PDFs para DOCUMENTOS DO CLIENTE
7. **Depois** - computar prazos (PFI e PF) e cobrar documentos faltantes (lista da Ficha)

## Regras gerais
- Pecas geradas pela IA sao SEMPRE para revisao do advogado antes de protocolar.
- Nunca alterar dados no ADVBOX sem autorizacao explicita (consulta livre).
- Nunca criar pasta/arquivo no Drive sem autorizacao explicita (excecao: o `gerar` da contratacao,
  rodado pelo advogado, cria a pasta AREA > CLIENTE e sobe os documentos para revisao).
