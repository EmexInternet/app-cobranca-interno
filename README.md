# App Cobranca Interno

Projeto interno para tratativa de multa rescisória, automações operacionais de cobrança e apoio ao time no fluxo de cancelamento por inadimplência.

## Contexto

O projeto foi definido a partir de uma reunião com a Angélica, onde foram identificados pontos de atenção no processo de cobrança.

O objetivo é estruturar um fluxo com integrações ao Hubsoft, automações em Python e uma interface interna para apoio operacional.

## Escopo

Este projeto está dividido em 3 fases.

### Fase 1 - Fechamento em massa de atendimentos

Automação de finalização em massa para atendimentos de cobrança quando o cliente for cancelado.

Tecnologias previstas:

- `FastAPI`
- API de relato do Hubsoft
- API de atendimentos do Hubsoft

Fluxo previsto:

1. Consultar cancelamentos no Hubsoft.
2. Identificar os atendimentos de cobrança vinculados ao cliente.
3. Finalizar os atendimentos em massa.
4. Registrar o relato padrão de encerramento.

Relato padrao:

```txt
TENTATIVAS DE CONTATO PARA NEGOCIAÇÃO SEM SUCESSO.
CONTRATO CANCELADO POR INADIMPLÊNCIA.
```

### Fase 2 - Observação obrigatória no Hubsoft

Automação para acessar o Hubsoft Web e adicionar a observação obrigatória, já que esse processo não possui recurso nativo no sistema.

Abordagem prevista:

1. Localizar o protocolo correto.
2. Acessar o Hubsoft via automacao em Python.
3. Inserir a observação obrigatória no cadastro ou atendimento correspondente.

Observacao padrao:

```txt
CLIENTE POSSUI PENDÊNCIA FINANCEIRA NO PROTOCOLO XXXXXXXXXXX.
```

### Fase 3 - Site interno de cobrança

Criação do site `app-cobranca-interno` para centralizar o fluxo operacional.

Fluxo previsto:

1. Puxar informações do Hubsoft.
2. Realizar cálculos internos.
3. Gerar texto de relato.
4. Exibir campo visual para envio do relato.
5. Permitir disparos de email e SMS.

## Entregas previstas

- Automação de fechamento de atendimentos de cobrança
- Automação de inclusão de observação obrigatória no Hubsoft
- Interface interna para operação de cobrança

## Pontos de atenção

- O fluxo depende de integrações com APIs do Hubsoft.
- Parte da operação exigirá automação web em Python.
- Os relatos e observações devem seguir o padrão operacional definido.
- O site interno será usado como apoio à execução manual e semiautomática do processo.

## Status atual

Repositório em fase inicial.

Neste primeiro momento, a entrega prevista é somente a documentação inicial do projeto via `README.md`.
