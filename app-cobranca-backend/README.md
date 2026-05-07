# App Cobranca Backend

Base da fase 1 do projeto, responsavel pelas automacoes internas executadas em VPS Linux.

## Objetivo da fase 1

Executar um fluxo operacional que:

1. busca cancelamentos em uma API externa
2. filtra somente cancelamentos por inadimplencia
3. consulta atendimentos pendentes de cobranca no Hubsoft
4. adiciona relato padrao no atendimento
5. fecha o atendimento com o motivo configurado
6. acessa o Hubsoft Web para registrar a observacao obrigatoria no cadastro do cliente

## Regras principais do processo

### 1. Origem dos dados de cancelamento

Endpoint:

```txt
GET http://200.229.156.16:3002/cancelamentos?dia_inicio=YYYY-MM-DD&dia_fim=YYYY-MM-DD
Header: x-api-key
```

Regras dos parametros:

- `dia_inicio`: sempre o primeiro dia do mes anterior ao mes atual da execucao
- `dia_fim`: data atual da execucao

Exemplo considerando execucao em `2026-05-07`:

- `dia_inicio = 2026-04-01`
- `dia_fim = 2026-05-07`

Campos que devem ser armazenados do retorno:

- `codigo_cliente`
- `id_cliente`
- `id_cliente_servico`
- `nome_razaosocial`
- `telefone_primario`
- `email_principal`
- `numero_plano`
- `plano`
- `data_venda`
- `data_cancelamento`
- `motivo_cancelamento`
- `cidade`
- `bairro`

Filtro obrigatorio:

- processar apenas registros com `motivo_cancelamento = CANCELAMENTO AUTOMATICO INADIMPLENCIA`

### 2. Integracao com a API do Hubsoft

Fluxo:

1. autenticar na API OAuth
2. consultar atendimentos pelo `id_cliente_servico`
3. filtrar apenas `tipo_atendimento = COBRANCA`
4. adicionar relato no atendimento encontrado
5. fechar o atendimento

Credenciais e URLs devem ficar em variaveis de ambiente na VPS. O arquivo [.env.example](C:/Users/PROVISORIO/Desktop/JG%20PORTO/PROJETOS%20GITHUB/app-cobranca-interno/app-cobranca-backend/.env.example) mostra a estrutura esperada, sem versionar segredos reais.

#### Login

Endpoint:

```txt
POST https://api.emex.hubsoft.com.br:443/oauth/token
Content-Type: application/json
```

Body:

```json
{
  "grant_type": "password",
  "client_id": "${HUBSOFT_CLIENT_ID}",
  "client_secret": "${HUBSOFT_CLIENT_SECRET}",
  "username": "${HUBSOFT_USERNAME}",
  "password": "${HUBSOFT_PASSWORD}"
}
```

Campos esperados na resposta:

- `refresh_token`
- `access_token`
- `token_type`

#### Consulta de atendimentos de cobranca

Endpoint:

```txt
GET /api/v1/integracao/cliente/atendimento?busca=id_cliente_servico&termo_busca={id_cliente_servico}&apenas_pendente=sim
```

Campos de interesse:

- `id_atendimento`
- `protocolo`
- `descricao_abertura`
- `tipo_atendimento`

Filtro obrigatorio:

- considerar apenas itens com `tipo_atendimento = COBRANCA`
- quando houver mais de um atendimento de cobranca pendente para o mesmo `id_cliente_servico`, utilizar somente o primeiro retorno da API

#### Relato padrao

Endpoint:

```txt
POST /api/v1/integracao/atendimento/adicionar_mensagem/{id_atendimento}
```

Mensagem:

```txt
TENTATIVAS DE CONTATO PARA NEGOCIACAO SEM SUCESSO.

> CONTRATO CANCELADO POR INADIMPLENCIA.
```

#### Fechamento do atendimento

Endpoint:

```txt
PUT /api/v1/integracao/atendimento/{id_atendimento}
```

Payload:

```json
{
  "parametros_fechamento": {
    "id_motivo_fechamento_atendimento": 17,
    "descricao_fechamento": "CONTRATO CANCELADO POR INADIMPLENCIA",
    "status_fechamento": "concluido"
  },
  "fechar_atendimento": true
}
```

### 3. Automacao Web no Hubsoft

Site:

- `https://emex.hubsoft.com.br/login`

Tecnologia prevista:

- Python
- Chromium
- Playwright com perfil persistente em disco

Motivo da escolha:

- permite controlar Chromium na VPS Linux
- facilita persistencia de sessao sem relogar sempre
- oferece espera e interacao mais robustas do que automacao baseada so em tempo fixo

Credenciais Web:

- email: configurar em variavel de ambiente
- senha: configurar em variavel de ambiente

Sequencia documentada de login:

1. acessar `/login`
2. esperar 1 segundo
3. preencher email
4. esperar 1 segundo
5. clicar em `validar`
6. esperar 1 segundo
7. preencher senha
8. esperar 1 segundo
9. clicar em `entrar`

Persistencia de login:

- usar diretorio de perfil ou `storage_state` salvo localmente
- reutilizar a sessao nas proximas execucoes
- relogar apenas quando a sessao expirar

### 4. Inclusao da observacao obrigatoria

Pagina alvo:

```txt
https://emex.hubsoft.com.br/cliente/editar/{id_cliente}/cadastro
```

Fluxo esperado:

1. abrir o cadastro do cliente
2. localizar a aba `OBS`
3. clicar em `OBS`
4. clicar em `ADICIONAR`
5. preencher o campo `Observacao *` com:

```txt
CLIENTE POSSUI PENDENCIA FINANCEIRA NO PROTOCOLO {protocolo}
```

6. ativar o toggle para mudar de `Visualizacao obrigatoria? Nao` para `Visualizacao obrigatoria? Sim`
7. clicar em `Salvar`

### 5. Modo de teste

Cliente de teste informado para validacoes sem depender da primeira API:

- `codigo_cliente = 45098`
- `id_cliente = 44847`

Regra de teste:

- durante testes controlados, pode pular a API de cancelamentos e iniciar o fluxo diretamente com esse cliente

## Estrutura inicial da pasta

- `docs/`: detalhes tecnicos e arquitetura
- `storage/`: sessao persistente do Chromium e arquivos operacionais locais
- `logs/`: logs da automacao na VPS
- `requirements.txt`: dependencias previstas da fase 1
- `.env.example`: modelo das variaveis de ambiente
- `app_python_automacao/`: codigo da automacao
- `tests/`: testes unitarios iniciais

## Implementacao inicial criada

Ja existe uma primeira base funcional com:

- cliente HTTP para API de cancelamentos
- cliente HTTP para autenticacao e operacoes da API Hubsoft
- filtro normalizado para comparar textos com e sem acento
- automacao Web via Playwright com perfil persistente de Chromium
- CLI com subcomandos para fluxo completo, fluxo direto por cliente_servico e observacao isolada
- testes unitarios basicos para janela de datas e filtros

## Como preparar o ambiente

1. Criar um ambiente virtual Python.
2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Instalar o navegador do Playwright:

```bash
python -m playwright install chromium
```

4. Copiar `.env.example` para `.env` e preencher os valores reais na VPS.

## Como executar

Fluxo completo a partir da API de cancelamentos:

```bash
python -m app_python_automacao executar
```

Fluxo completo sem gravar alteracoes:

```bash
python -m app_python_automacao executar --dry-run
```

Fluxo direto para um cliente_servico especifico, sem consultar a primeira API:

```bash
python -m app_python_automacao atendimento --cliente-id 44847 --cliente-servico-id 123456 --dry-run
```

Adicionar somente a observacao obrigatoria:

```bash
python -m app_python_automacao observacao --cliente-id 44847 --protocolo 2026050700001
```

Abrir o navegador com interface visual:

```bash
python -m app_python_automacao executar --headful
```

## Como testar

Rodar os testes unitarios:

```bash
python -m unittest discover -s tests
```

## Proximos passos sugeridos

1. validar os seletores reais do Hubsoft Web com um teste controlado
2. confirmar o formato exato de retorno da API de cancelamentos e de atendimentos
3. adicionar retentativas, timeout por etapa e relatorio de execucao em JSON
4. preparar agendamento em VPS via `cron`
