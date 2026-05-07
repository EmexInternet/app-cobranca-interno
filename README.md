# App Cobranca Interno

Projeto interno dividido em 2 fases:

1. `app-cobranca-backend`: automacoes internas executadas em uma VPS Linux.
2. `site`: interface operacional que sera hospedada na Hostinger em uma etapa posterior.

## Estrutura atual

```txt
app-cobranca-interno/
|-- .gitignore
|-- README.md
`-- app-cobranca-backend/
    |-- README.md
    |-- .env.example
    |-- requirements.txt
    |-- docs/
    |   `-- fase1-arquitetura.md
    |-- logs/
    |   `-- .gitkeep
    `-- storage/
        `-- .gitkeep
```

## Fase 1 - Automacoes internas na VPS

Objetivo:

- consumir a API de cancelamentos
- filtrar somente clientes com `motivo_cancelamento = CANCELAMENTO AUTOMATICO INADIMPLENCIA`
- consultar atendimentos pendentes de cobranca no Hubsoft
- relatar e fechar os atendimentos encontrados
- acessar o Hubsoft Web via Chrome para registrar a observacao obrigatoria no cadastro do cliente
- manter persistencia de login para evitar autenticacao manual a cada execucao

Detalhamento tecnico:

- pasta: [app-cobranca-backend](C:/Users/PROVISORIO/Desktop/JG%20PORTO/PROJETOS%20GITHUB/app-cobranca-interno/app-cobranca-backend)
- documentacao principal: [app-cobranca-backend/README.md](C:/Users/PROVISORIO/Desktop/JG%20PORTO/PROJETOS%20GITHUB/app-cobranca-interno/app-cobranca-backend/README.md)
- arquitetura e fluxo: [app-cobranca-backend/docs/fase1-arquitetura.md](C:/Users/PROVISORIO/Desktop/JG%20PORTO/PROJETOS%20GITHUB/app-cobranca-interno/app-cobranca-backend/docs/fase1-arquitetura.md)

## Fase 2 - Site hospedado na Hostinger

Esta fase ficara separada da automacao interna.

Objetivo:

- oferecer uma interface web para acompanhamento e apoio operacional
- centralizar resultados, filtros, historico e acoes manuais
- consumir os dados produzidos pela fase 1

## Regras de documentacao

- o `README.md` raiz registra o panorama do projeto
- a pasta `app-cobranca-backend` concentra a documentacao e a base tecnica da fase 1
- conforme avancarmos, a documentacao deve ser atualizada antes ou junto das implementacoes

## Status atual

Fase 1 estruturada em nivel de arquitetura e preparacao inicial do backend.
