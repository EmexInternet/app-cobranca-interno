# Fase 1 - Arquitetura

## Visao geral

A fase 1 sera executada dentro de uma VPS Linux e tera dois blocos principais:

1. integracao por API
2. automacao Web no Hubsoft

## Fluxo ponta a ponta

```txt
API cancelamentos
  -> filtro motivo_cancelamento
  -> Hubsoft OAuth
  -> consulta atendimentos pendentes
  -> filtro tipo_atendimento = COBRANCA
  -> adicionar relato
  -> fechar atendimento
  -> abrir Hubsoft Web
  -> adicionar observacao obrigatoria no cliente
```

## Regras de negocio

### Janela de consulta

- `dia_inicio` deve ser o primeiro dia do mes anterior
- `dia_fim` deve ser a data atual da execucao

### Criticos de filtro

- API de cancelamentos: somente `CANCELAMENTO AUTOMATICO INADIMPLENCIA`
- API de atendimentos Hubsoft: somente `COBRANCA`

### Texto do relato

```txt
TENTATIVAS DE CONTATO PARA NEGOCIACAO SEM SUCESSO.

> CONTRATO CANCELADO POR INADIMPLENCIA.
```

### Texto da observacao obrigatoria

```txt
CLIENTE POSSUI PENDENCIA FINANCEIRA NO PROTOCOLO {protocolo}
```

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
- relatar e fechar atendimento

### Automacao Hubsoft Web

Responsabilidades:

- manter sessao persistente
- abrir cadastro do cliente
- navegar ate `OBS`
- inserir observacao obrigatoria
- salvar e registrar resultado

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
