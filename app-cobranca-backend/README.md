# App Cobranca Backend

Base das automacoes internas executadas em VPS Linux.

## Objetivo atual

Executar um fluxo operacional em 2 fases, por cliente:

1. fase 1:
   busca cancelamentos em uma API externa, localiza o atendimento de cobranca, relata, fecha e registra a observacao obrigatoria no Hubsoft Web
2. fase 2:
   localiza o atendimento de cancelamento por inadimplencia, consulta as faturas pendentes, calcula multa e descontos, relata a negociacao e tenta fechar o atendimento

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

### 2.1 Fase 2: atendimento de cancelamento por inadimplencia

Fluxo:

1. consultar atendimentos pendentes do `id_cliente_servico`
2. filtrar apenas `tipo_atendimento = CANCELAMENTO INADIMPLENCIA`
3. consultar faturas pendentes do mesmo `id_cliente_servico`
4. ignorar faturas com detalhamento `MULTA RESCISORIA` ou `EQUIPAMENTO EM COMODATO`
5. calcular multa rescisoria e resumos financeiros
6. relatar a negociacao no atendimento de cancelamento
7. tentar fechar o atendimento
8. se o fechamento falhar por retorno/O.S. em aberto, registrar o relato alternativo e deixar para finalizacao futura

#### Consulta de atendimento de cancelamento

Endpoint:

```txt
GET /api/v1/integracao/cliente/atendimento?busca=id_cliente_servico&termo_busca={id_cliente_servico}&apenas_pendente=sim
```

Campos de interesse:

- `id_atendimento`
- `protocolo`
- `tipo_atendimento`

Filtro obrigatorio:

- considerar apenas itens com `tipo_atendimento = CANCELAMENTO INADIMPLENCIA`
- quando houver mais de um atendimento de cancelamento pendente para o mesmo `id_cliente_servico`, utilizar somente o primeiro retorno da API

#### Consulta de faturas pendentes

Endpoint:

```txt
GET /api/v1/integracao/cliente/financeiro?busca=id_cliente_servico&termo_busca={id_cliente_servico}&limit=50&apenas_pendente=sim
```

Campos armazenados por fatura:

- `id_fatura`
- `status`
- `valor`

Regras:

- ignorar faturas com `detalhamento.descricao = MULTA RESCISORIA`
- ignorar faturas com `detalhamento.descricao = EQUIPAMENTO EM COMODATO`

#### Calculo da multa rescisoria

O backend agora espelha internamente a regra do arquivo [multa-recisoria.js](C:/Users/PROVISORIO/Desktop/JG%20PORTO/PROJETOS%20GITHUB/app-cobranca-interno/multa-recisoria.js), usando:

- `data_venda`
- `data_cancelamento`
- `MULTA_RESCISORIA_VALOR_BENEFICIO_PADRAO` no `.env`

Observacao importante:

- o arquivo JavaScript original usa um `valor` de beneficio alem das duas datas
- como essa origem ainda nao foi detalhada na integracao nova, a fase 2 usa temporariamente o valor configurado em `MULTA_RESCISORIA_VALOR_BENEFICIO_PADRAO`
- por padrao, esse valor esta configurado como `600,00`
- assim que a fonte oficial desse valor for confirmada, o ideal e substituir essa configuracao por dado real da operacao

Variaveis calculadas:

- `ValorMulta = multa rescisoria calculada`
- `DividaSemMulta = soma das faturas validas`
- `TotalDivida = DividaSemMulta + ValorMulta`
- `DividaSemMulta50% = DividaSemMulta com 50% de desconto`
- `Divida40% = TotalDivida com 40% de desconto`

#### Relato do atendimento de cancelamento

Mensagem enviada pelo backend:

```txt
> CONTRATO CANCELADO POR INADIMPLENCIA.
> E-MAIL E WHATSAPP ENVIADOS.

VALOR TOTAL DA DIVIDA: R$ {TotalDivida}

CASO O(A) CLIENTE ENTRE EM CONTATO, FAVOR INFORMAR SOBRE A PENDENCIA FINANCEIRA EM ABERTO E NEGOCIACOES DISPONIVEIS:

OPCAO 1 - SE O(A) CLIENTE DESEJAR RETORNAR COM O SERVICO:

FICARA ISENTO DA MULTA RESCISORIA E O VALOR DO DEBITO PASSA A SER R$ {DividaSemMulta}.
SERA CONCEDIDO 50% DE DESCONTO E O VALOR PARA PAGAMENTO FICA EM R$ {DividaSemMulta50%} + TAXA DE ATIVACAO (SUJEITO A AVALIACAO).
A NEGOCIACAO PODERA SER PAGA POR BOLETO OU NA LOJA COM VENCIMENTO PARA 3 DIAS A FRENTE.
DEIXAR O(A) CLIENTE CIENTE QUE A INSTALACAO SO OCORRERA APOS O PAGAMENTOS DOS DEBITOS E ENTREGA DOS EQUIPAMENTOS EM COMODATO (CASO NAO TENHAM SIDO REMOVIDOS).

OPCAO 2 - SE O(A) CLIENTE DESEJAR SOMENTE LIQUIDAR O DEBITO:

SERA CONCEDIDO 40% DE DESCONTO E O VALOR TOTAL PARA PAGAMENTO FICA EM R$ {Divida40%}.
A NEGOCIACAO PODERA SER PAGA POR BOLETO OU NA LOJA COM VENCIMENTO PARA 3 DIAS A FRENTE.
DEIXAR O(A) CLIENTE CIENTE SOBRE A DEVOLUCAO DOS EQUIPAMENTOS EM COMODATO (CASO NAO TENHAM SIDO REMOVIDOS).

> SE O(A) CLIENTE ALEGAR PERDA/DANO, VERIFICAR COM O SETOR DE FATURAMENTO UMA NOVA NEGOCIACAO.
```

#### Fallback quando nao for possivel fechar o atendimento

Se o fechamento falhar, o backend relata:

```txt
ATENDIMENTO NAO PODE SER FINALIZADO DEVIDO O.S EM ABERTO - SERA FINALIZADO EM MASSA QUANDO NOVO PROCESSO DO FLUXO DE RETIRADA FOR RODADO
```

### 3. Automacao Web no Hubsoft

Site:

- `https://emex.hubsoft.com.br/login`

Tecnologia prevista:

- Python
- Google Chrome
- Selenium com perfil persistente em disco

Motivo da escolha:

- permite controlar o Chrome da VPS Linux
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

- usar diretorio de perfil persistente do Chrome
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
- `storage/`: sessao persistente do Chrome e arquivos operacionais locais
- `logs/`: logs da automacao na VPS
- `requirements.txt`: dependencias previstas da fase 1
- `.env.example`: modelo das variaveis de ambiente
- `app_python_automacao/`: codigo da automacao
- `tests/`: testes unitarios iniciais

## Implementacao inicial criada

Ja existe uma primeira base funcional com:

- cliente HTTP para API de cancelamentos
- cliente HTTP para autenticacao e operacoes da API Hubsoft
- consulta de financeiro pendente para a fase 2
- calculo interno da multa rescisoria espelhando a regra do `multa-recisoria.js`
- resumo financeiro com desconto de 50% sem multa e 40% sobre a divida total
- filtro normalizado para comparar textos com e sem acento
- automacao Web via Selenium com perfil persistente de Chrome
- CLI com subcomandos para fluxo completo, fluxo direto por cliente_servico e observacao isolada
- testes unitarios basicos para janela de datas e filtros

## Como preparar o ambiente

1. Criar um ambiente virtual Python.
2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Garantir que o Google Chrome esteja instalado no sistema.

```bash
google-chrome --version
```

Se o Chrome nao estiver no `PATH`, preencher `HUBSOFT_CHROME_BINARY_PATH` no `.env`.

4. Copiar `.env.example` para `.env` e preencher os valores reais na VPS.

Variaveis novas da fase 2:

- `TIPO_ATENDIMENTO_CANCELAMENTO_ALVO`
- `FINANCEIRO_DESCRICOES_IGNORADAS`
- `MULTA_RESCISORIA_VALOR_BENEFICIO_PADRAO`

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
5. confirmar a fonte oficial do valor-base usado no calculo da multa rescisoria
