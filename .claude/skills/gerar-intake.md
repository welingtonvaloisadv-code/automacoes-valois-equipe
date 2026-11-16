---
name: gerar-intake
description: Gera a contratacao de um novo cliente - ficha, contrato, procuracao e declaracao para revisao
trigger: /intake
---

# Skill: Contratacao (intake)

Procedimento: `docs/POPs/POP_06_CONTRATACAO.md`.

## Uso
```
python INTAKE/main.py gerar "TRANSCRICAO.pdf" "CNH.pdf" "COMPROVANTE.pdf" "CADASTRO.txt" --area PREVIDENCIARIO
```
O primeiro arquivo e sempre a transcricao/gravacao transcrita da reuniao.

## Formatos aceitos
- `.pdf`: transcricao, CNH/RG, CNIS, comprovantes. A IA le direto, inclusive escaneado.
- `.jpg` / `.png`: foto de documento
- `.txt` / `.docx`: cadastro preenchido na reuniao

## O que gera (para REVISAO, nada vai ao cliente)
1. Pasta AREA > NOME DO CLIENTE no Drive (3 subpastas)
2. Ficha do Cliente: analise da IA, dados da area, documentos faltantes e pendencias
3. Contrato de Honorarios, com objeto e honorarios conforme a area
4. Procuracao, com os poderes da area e os advogados da area mais o Dr. Welington
5. Declaracao de Hipossuficiencia, quando ha pedido de gratuidade

## Depois da revisao do advogado
`python INTAKE/main.py enviar --simular`, depois `python INTAKE/main.py enviar`.

## Regras
- Nunca rodar `enviar` sem `revisado_por` preenchido pelo advogado da area.
- Dado que nao esta nos documentos/conversa sai `[PREENCHER]`, nunca inventado.
