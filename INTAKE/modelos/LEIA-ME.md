# Modelos da contratacao

Textos-base usados por `python INTAKE/main.py gerar` para montar, no timbrado do escritorio
(`config/timbrado_modelo.docx`), a ficha, o contrato, a procuracao e a declaracao.

> **Estes textos sao PROVISORIOS.** Foram escritos como base generica ate o escritorio
> mandar os modelos reais dele (regra do CLAUDE.md: contrato, procuracao e declaracao usam
> o modelo do escritorio). Enquanto isso, o indice de revisao marca a coluna `modelo` como
> `PROVISORIO`.

## Como o escritorio troca pelo modelo dele

Coloque um arquivo com o **mesmo nome** em `DOCS_MODELOS/contratacao/`. Ele passa a valer
no lugar do daqui. `DOCS_MODELOS/` nao vai para o GitHub, porque este repositorio e publico.

| Arquivo | Documento |
|---|---|
| `ficha.txt` | Ficha do cliente (documento guia, interno) |
| `contrato.txt` | Contrato de honorarios (corpo comum) |
| `objeto/<AREA>.txt` | Clausula do objeto, por area |
| `honorarios/<AREA>.txt` | Clausula de honorarios, por area |
| `procuracao.txt` | Procuracao (corpo comum) |
| `poderes/<AREA>.txt` | Poderes especificos da area na procuracao |
| `declaracao_hipossuficiencia.txt` | Declaracao de hipossuficiencia |

`<AREA>`: `PREVIDENCIARIO`, `CRIMINAL`, `FAMILIA E SUCESSOES`, `BANCARIO`, `CIVEL E CONSUMIDOR`.

## Marcacao

| Marca | Vira |
|---|---|
| `# TEXTO` | titulo centralizado em negrito |
| `## TEXTO` | subtitulo/clausula em negrito, justificado, sem recuo |
| `>> TEXTO` | linha centralizada (local e data, assinatura) |
| `**texto**` | negrito dentro do paragrafo |
| linha comum | paragrafo justificado com recuo de 1a linha |
| `% ...` | comentario, nao sai no documento |
| `{{campo}}` | dado do cliente; se faltar, sai `[PREENCHER: campo]` e o envio fica bloqueado |
| `{{?campo}}` | dado opcional; se faltar, some sem bloquear |

Campos disponiveis: ver `CAMPOS` em `INTAKE/contratacao.py`.
