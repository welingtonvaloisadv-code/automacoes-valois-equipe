# POP 06 — Contratação de cliente novo

**Escritório:** Welington Valois Advogados Associados
**Aplica-se a:** advogado da área, estagiário comercial e secretaria
**Responsável pelo POP:** Dr. Welington Dias Valois (OAB/ES 34.912)
**Ferramenta:** `INTAKE/main.py` (prioridade 5 de implantação)

---

## 1. A regra

> A IA prepara a ficha, o contrato, a procuração e a declaração. **Nada vai para o cliente
> assinar sem o advogado da área revisar.**

Contrato, procuração e declaração saem no **timbrado** e no **modelo do escritório**. Enquanto o
escritório não enviar os modelos reais, sai um texto-base marcado **PROVISÓRIO** no índice.

## 1.1 Regra: cliente cadastrado no ADVBOX

> Cadastrou o cliente no ADVBOX? A automação gera, **a partir desse cadastro**, o **contrato de
> honorários**, a **declaração de hipossuficiência** e a **procuração**.

```
python INTAKE/main.py advbox 123.456.789-00
python INTAKE/main.py advbox "MARIA APARECIDA" --area PREVIDENCIARIO --acao "Salário-maternidade rural"
```

- Busca o cliente pelo **CPF** (melhor), pelo **ID do ADVBOX** ou pelo **nome**.
- **Área e ação** vêm do processo do cliente no ADVBOX. Se o cliente ainda não tem processo,
  informe `--area` e `--acao`. Se tiver mais de um, escolha com `--processo ID`.
- O local, a data e o foro saem da unidade da cidade do cliente (Iúna, Ibatiba ou Irupi). Para
  mudar, use `--unidade`.
- O que não estiver no cadastro do ADVBOX sai como `[PREENCHER]`. A nacionalidade, por exemplo,
  normalmente não está lá. **Quanto mais completo o cadastro, menos se completa à mão.**
- Revisão e envio seguem os passos 2 a 6 abaixo. O `enviar` não cadastra de novo no ADVBOX.

## 2. Quem faz o quê

| Etapa | Quem | Como |
|---|---|---|
| Reunião, cadastro e documentos | Comercial / advogado | Gravação ou transcrição da reunião, CNH/RG, comprovante, documentos da área |
| Gerar os documentos | Comercial / secretaria | `python INTAKE/main.py gerar TRANSCRICAO.pdf CNH.pdf CADASTRO.txt --area PREVIDENCIARIO` |
| Revisar | **Advogado da área** | Ficha + contrato + procuração + declaração no Drive |
| Liberar o envio | **Advogado da área** | Índice: `revisado_por` = nome, `enviar` = SIM |
| Enviar para assinatura | Secretaria | `python INTAKE/main.py enviar --simular` e depois `enviar` |
| Documentos assinados | Automático | `SYNC/sync_assinados.py` salva em DOCUMENTOS DO CLIENTE |
| Prazos e documentos faltantes | Advogado da área + secretaria | Lista da seção V da Ficha |

Responsável pela revisão, por área: Previdenciário, Dra. Priscila; Família e Sucessões, Dra. Derlira;
Bancário, Dr. Heliézer; Cível e Consumidor, Dra. Gisele; Criminal, Dr. Welington e Dr. Guilherme.

## 3. Passo a passo

1. **Gerar.** Primeiro a transcrição da reunião, depois os documentos (PDF, foto, `.txt` ou `.docx`).
   PDF escaneado e foto de documento podem ir direto, porque a IA lê. Use `--unidade IBATIBA` ou
   `--unidade IRUPI` quando o local, a data e o foro do contrato não forem Iúna.
2. **Revisar no Drive**, na pasta `ÁREA > NOME DO CLIENTE`:
   - Em `ATOS INTERNOS` fica a **Ficha**, o documento guia, com a análise da IA, os documentos que
     faltam e as pendências.
   - Em `PASTA DO CLIENTE` ficam o contrato, a procuração e a declaração. Corrija **no próprio .docx**:
     abra, edite e salve. Não use "Salvar como Documentos Google".
   - Complete todo `[PREENCHER: ...]`, principalmente os **honorários**. O previdenciário é **no êxito**,
     com parcelas fixas após a concessão.
3. **Liberar.** Abra `SAIDA/intake/INDICE_CONTRATACOES.csv` no Excel. Escreva seu nome em
   `revisado_por` e `SIM` em `enviar`. Para cadastrar também o processo no ADVBOX, preencha
   `tipo_advbox` com o tipo de ação **exatamente** como aparece no ADVBOX.
4. **Conferir.** Rode `python INTAKE/main.py enviar --simular`. Ele baixa a versão revisada e gera
   os PDFs, mas não envia nada. Se aparecer **BLOQUEADO**, corrija o que ele apontar.
5. **Enviar.** Rode `python INTAKE/main.py enviar` e digite SIM para confirmar. O sistema:
   - cria os documentos no ZapSign. O contrato tem também a assinatura do escritório;
   - manda **uma** mensagem no WhatsApp do cliente com os links, pela Evolution;
   - cadastra o cliente no ADVBOX.
6. **Acompanhar.** `python INTAKE/main.py status`. Se o status ficar **PARCIAL**, a coluna `obs`
   diz o que faltou; rodar `enviar` de novo completa só o que faltou.

## 4. O envio trava quando

- a coluna `revisado_por` está vazia;
- sobrou `[PREENCHER]`, `[CONFERIR]` ou `{{...}}` no contrato, na procuração ou na declaração;
- o cliente está sem telefone e sem e-mail;
- não há Word nem LibreOffice para gerar o PDF.

## 5. Regras que não mudam

- **Benefício por incapacidade:** laudo médico com menos de 60 dias e com a CID.
- **BPC/LOAS:** renda per capita inferior a 1/4 do salário mínimo, laudo atualizado e CadÚnico atualizado.
- **Bancário:** parecer de viabilidade antes de qualquer ação.
- **Nenhum dado é inventado.** O que falta sai como `[PREENCHER]`.
- A análise da IA na Ficha é ponto de partida. A jurisprudência sai como `[CONFERIR]`.

## 6. Ainda a definir

- Os modelos reais de contrato, procuração e declaração. Vão em `DOCS_MODELOS/contratacao/`; ver `INTAKE/modelos/LEIA-ME.md`.
- Os honorários padrão de cada área (`config/regras_financeiras.py`, `HONORARIOS_PADRAO`). **[DEFINIR com o Dr. Welington]**
- A cobrança recorrente no Asaas a partir do contrato fica para a fase financeira.
