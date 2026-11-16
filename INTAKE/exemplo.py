"""Caso FICTICIO para demonstrar a contratacao sem IA, sem Drive e sem dado real."""

DADOS_EXEMPLO = {
    'nome': 'Maria Aparecida dos Santos (EXEMPLO)',
    'cpf': '52998224725',
    'rg': '1.234.567',
    'orgao_emissor': 'SPTC/ES',
    'data_nascimento': '12/03/1996',
    'nacionalidade': 'brasileira',
    'estado_civil': 'casada',
    'profissao': 'lavradora',
    'telefone': '28999990000',
    'email': '',
    'logradouro': 'Córrego São José',
    'numero': 's/n',
    'bairro': 'Zona Rural',
    'cidade': 'Iúna',
    'uf': 'ES',
    'cep': '29390000',
    'tipo_acao': 'Salário-maternidade rural',
    'parte_contraria': 'INSS',
    'numero_processo': '',
    'data_reuniao': '01/10/2026',
    'indicante': 'Vizinha (cliente antiga)',
    'origem': 'Indicação',
    'motivo_urgencia': '',
    'pedir_gratuidade': 'SIM',
    'dados_area': [
        {'campo': 'Benefício pretendido', 'valor': 'Salário-maternidade (segurada especial)'},
        {'campo': 'Data do nascimento da criança', 'valor': '05/07/2026'},
        {'campo': 'Situação no INSS', 'valor': 'Não requerido'},
        {'campo': 'Atividade rural', 'valor': 'Lavoura de café em regime de meação desde 2019'},
        {'campo': 'Prova material citada', 'valor': 'Contrato de parceria agrícola e notas de venda de café'},
    ],
    'documentos_necessarios': [
        'Certidão de nascimento da criança',
        'Contrato de parceria agrícola e notas de produtor rural dos últimos 10 meses',
    ],
    'pendencias': [
        'Confirmar se o marido tem vínculo urbano (pode afastar a condição de segurada especial)',
    ],
    'resumo_fatos': (
        '**Síntese dos Fatos**\n'
        'CASO FICTÍCIO DE DEMONSTRAÇÃO. A Requerente relata trabalhar em regime de economia '
        'familiar na lavoura de café desde 2019 e ter dado à luz em 05/07/2026.\n'
        '**Enquadramento Jurídico**\n'
        '1. Qualidade de segurada especial: a confirmar com prova material e testemunhas.\n'
        '2. Carência de 10 meses de atividade rural anteriores ao parto: a confirmar.\n'
        '**Via Recomendada**\n'
        'Requerimento administrativo no INSS; se indeferido, ação na comarca local '
        '(competência delegada).\n'
        '**Conclusão**\n'
        'Viável, condicionado à prova material do período de carência.'
    ),
}
