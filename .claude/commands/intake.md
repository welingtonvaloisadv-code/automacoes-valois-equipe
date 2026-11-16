---
description: Executa a contratacao de um novo cliente (gerar para revisao; enviar so depois da revisao)
---

# Comando: Intake (contratacao)

Procedimento completo: `docs/POPs/POP_06_CONTRATACAO.md`.

## Regra: cliente ja cadastrado no ADVBOX (fluxo padrao)
```bash
python INTAKE/main.py advbox "123.456.789-00"          # CPF, ID do ADVBOX ou nome
python INTAKE/main.py advbox "MARIA" --area PREVIDENCIARIO --acao "Salario-maternidade rural"
```
Gera **contrato de honorarios, declaracao de hipossuficiencia e procuracao** a partir do cadastro
do ADVBOX (sem IA). Area/acao vem do processo do cliente no ADVBOX ou de `--area`/`--acao`.
Dado que o ADVBOX nao tem sai `[PREENCHER]`. Depois: revisao (passo 2) e envio (passo 3).

## 1. Gerar a partir da reuniao (nao envia nada ao cliente)
```bash
python INTAKE/main.py gerar "TRANSCRICAO.pdf" "CNH.pdf" "CADASTRO_CLIENTE.txt" --area PREVIDENCIARIO
```
Areas: PREVIDENCIARIO, CRIMINAL, FAMILIA E SUCESSOES, BANCARIO, CIVEL E CONSUMIDOR.
Opcional: `--unidade IUNA|IBATIBA|IRUPI`, `--sem-drive`. Demonstracao: `gerar --exemplo`.

Resultado: pasta AREA > CLIENTE no Drive, com a Ficha em ATOS INTERNOS, e o Contrato, a Procuracao
e a Declaracao em PASTA DO CLIENTE, todos no timbrado. O caso entra em
`SAIDA/intake/INDICE_CONTRATACOES.csv` como AGUARDANDO REVISAO.

## 2. Revisao humana (obrigatoria)
O advogado da area completa os `[PREENCHER]`, inclusive os honorarios, preenche `revisado_por` e marca `enviar=SIM`.

## 3. Enviar
```bash
python INTAKE/main.py enviar --simular   # confere e gera PDFs
python INTAKE/main.py enviar             # ZapSign + WhatsApp + ADVBOX
python INTAKE/main.py status
```

Nunca rode `enviar` sem o advogado ter revisado: a regra de ouro do escritorio vale aqui.
