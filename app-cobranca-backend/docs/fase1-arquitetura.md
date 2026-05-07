# Backend - Arquitetura Operacional

## Visao geral

O backend sera executado dentro de uma VPS Linux e hoje possui duas etapas operacionais por cliente:

1. integracao por API
2. automacao Web no Hubsoft

## Fluxo ponta a ponta

```txt
API cancelamentos
  -> filtro motivo_cancelamento
  -> Hubsoft OAuth
  -> fase 1
    -> consulta atendimentos pendentes
    -> filtro tipo_atendimento = COBRANCA
    -> adicionar relato
    -> fechar atendimento
    -> abrir Hubsoft Web
    -> adicionar observacao obrigatoria no cliente
  -> fase 2
    -> consulta atendimento tipo CANCELAMENTO INADIMPLENCIA
    -> consulta financeiro pendente
    -> ignorar MULTA RESCISORIA e EQUIPAMENTO EM COMODATO
    -> calcular multa e descontos
    -> relatar negociacao
    -> tentar fechar atendimento
  -> etapa futura
    -> disparo de e-mail e WhatsApp via API ao final do processo do cliente
```

## Regras de negocio

### Janela de consulta

- `dia_inicio` deve ser o primeiro dia do mes anterior
- `dia_fim` deve ser a data atual da execucao

### Criticos de filtro

- API de cancelamentos: somente `CANCELAMENTO AUTOMATICO INADIMPLENCIA`
- API de atendimentos Hubsoft: somente `COBRANCA`
- API de atendimento da fase 2: somente `CANCELAMENTO INADIMPLENCIA`
- API financeira da fase 2: ignorar `MULTA RESCISORIA` e `EQUIPAMENTO EM COMODATO`

### Texto do relato da fase 1

```txt
TENTATIVAS DE CONTATO PARA NEGOCIACAO SEM SUCESSO.

> CONTRATO CANCELADO POR INADIMPLENCIA.
```

### Texto da observacao obrigatoria

```txt
CLIENTE POSSUI PENDENCIA FINANCEIRA NO PROTOCOLO {protocolo}
```

### Calculos da fase 2

- `ValorMulta`
- `DividaSemMulta`
- `DividaSemMulta50%`
- `TotalDivida`
- `Divida40%`

## Componentes previstos

### Coletor de cancelamentos

Responsabilidades:

- calcular datas dinamicamente
- chamar a API externa
- normalizar e guardar os campos necessarios
- devolver apenas os cancelamentos elegiveis

### Cliente Hubsoft API

Responsabilidades:

- autenticar via OAuth
- consultar atendimentos por `id_cliente_servico`
- identificar atendimentos pendentes de cobranca
- identificar atendimentos pendentes de cancelamento por inadimplencia
- consultar financeiro pendente
- calcular resumos da negociacao da fase 2
- relatar e fechar atendimento

### Automacao Hubsoft Web

Responsabilidades:

- manter sessao persistente
- abrir cadastro do cliente
- navegar ate `OBS`
- inserir observacao obrigatoria
- salvar e registrar resultado

### Disparador de comunicacoes

Responsabilidade futura:

- disparar e-mail e WhatsApp via API ao final do fluxo individual por cliente

## Persistencia minima recomendada

- arquivo de sessao do navegador
- logs de execucao por data
- cache simples dos clientes processados na execucao atual

## Estrategia de execucao

Opcoes possiveis:

1. execucao manual por comando
2. execucao agendada via `cron`

Recomendacao inicial:

- comecar com execucao manual e modo teste
- depois adicionar agendamento controlado na VPS

## Modo teste

Cliente fixo:

- `codigo_cliente = 45098`
- `id_cliente = 44847`

Uso previsto:

- validar login
- validar navegacao
- validar escrita da observacao
- testar o fluxo sem depender da API de cancelamentos

## Registro de implementacao atual

Ja implementado:

- fase 1 operacional completa com observacao obrigatoria no Hubsoft Web
- fase 2 operacional com atendimento de cancelamento, faturas, multa e descontos
- suporte a janela manual de datas para teste da API de cancelamentos

Pendente planejado:

- disparo de e-mail e WhatsApp via API no fim do processo individual por cliente
