# Simulador de Rede em Anel com Token Passing

Este projeto simula uma rede local em anel (Token Ring) utilizando comunicação UDP em Python, com controle de erros por CRC32, retransmissão de pacotes, inserção aleatória de erros, suporte a broadcast e gerenciamento automático de tokens perdidos ou duplicados.

---

## 📌 Índice

- [Simulador de Rede em Anel com Token Passing](#simulador-de-rede-em-anel-com-token-passing)
  - [📌 Índice](#-índice)
  - [📖 Descrição do Projeto](#-descrição-do-projeto)
  - [✅ Pré-requisitos](#-pré-requisitos)
  - [📁 Estrutura dos Arquivos](#-estrutura-dos-arquivos)
  - [🛠️ Como Configurar](#️-como-configurar)
  - [🚀 Como Executar](#-como-executar)
  - [🖥️ Detalhes Técnicos](#️-detalhes-técnicos)
    - [Formato dos Pacotes](#formato-dos-pacotes)
    - [Fluxo de Token e Dados](#fluxo-de-token-e-dados)
    - [Controle de Erros e Retransmissão](#controle-de-erros-e-retransmissão)
    - [Broadcast](#broadcast)
    - [Detecção de Token Perdido e Duplicado](#detecção-de-token-perdido-e-duplicado)
  - [⌨️ Comandos Disponíveis](#️-comandos-disponíveis)
  - [📜 Logs e Depuração](#-logs-e-depuração)
  - [📌 Licença](#-licença)

---

## 📖 Descrição do Projeto

O simulador implementa um protocolo Token Ring com comunicação UDP em Python. Cada nó realiza as seguintes tarefas:

- Lê configuração inicial (endereço do vizinho, apelido, tempo de retenção do token e indicação de geração do token inicial);
- Cria um socket UDP para comunicação;
- Mantém uma fila de mensagens (máx. 10);
- Implementa controle de erros com CRC32;
- Insere erros aleatórios (30% das mensagens);
- Retransmite pacotes após erro detectado (NAK);
- Suporta mensagens broadcast;
- Gerencia tokens perdidos e duplicados automaticamente.

---

## ✅ Pré-requisitos

- Python 3.8 ou superior instalado;
- Rede configurada com acesso UDP (ou localhost);
- Não requer bibliotecas externas além das padrão do Python.

---

## 📁 Estrutura dos Arquivos

    projeto/
    ├── ring_network.py         # Script principal
    ├── RingNode.py             # Classe principal do nó
    ├── Packet.py               # Formato e codificação dos pacotes
    ├── CRC32.py                # Cálculo de CRC32
    ├── ErrorInserter.py        # Inserção aleatória de erros
    ├── MessageQueue.py         # Fila das mensagens (máx. 10)
    ├── config_alice.txt        # Exemplo de configuração
    ├── config_bob.txt          # Exemplo de configuração
    └── config_charlie.txt      # Exemplo de configuração

---

## 🛠️ Como Configurar

Cada nó utiliza um arquivo texto com exatamente 4 linhas, seguindo o formato abaixo:

    ip_do_vizinho:porta_vizinho
    apelido_da_maquina
    tempo_do_token_em_segundos
    gera_token_inicial (true ou false)

**Exemplo:**

    127.0.0.1:6001
    Alice
    2
    true

Cada máquina (nó) precisa ter seu próprio arquivo de configuração.

---

## 🚀 Como Executar

Abra um terminal em cada máquina (ou em diferentes abas do mesmo computador) e execute:

    python3 ring_network.py arquivo_configuracao.txt porta_local

Exemplo:

    python3 ring_network.py config_alice.txt 6000
    python3 ring_network.py config_bob.txt 6001
    python3 ring_network.py config_charlie.txt 6002

---

## 🖥️ Detalhes Técnicos

### Formato dos Pacotes

- Token:  
`1000`

- Dados:  
`2000;origem:destino:status:CRC:mensagem`

- Status:  
  - `maquinanaoexiste` (inicialmente)
  - `ACK` (sem erro)
  - `NAK` (com erro)

### Fluxo de Token e Dados

- Um nó só envia dados quando possui o token;
- Cada mensagem permanece na rede até retornar à origem com ACK, NAK ou `maquinanaoexiste`;
- Após ACK ou `maquinanaoexiste`, mensagem sai da fila;
- Após NAK, mensagem permanece na fila para retransmissão (até 3 tentativas).

### Controle de Erros e Retransmissão

- O CRC32 é calculado antes do envio;
- Recalculado ao chegar no destino:
  - Correto: responde com ACK;
  - Erro: responde com NAK;
- Nó origem trata ACK/NAK conforme acima descrito.

### Broadcast

- Mensagem enviada com destino `TODOS`;
- Nós exibem e repassam sem alterar ou responder com ACK/NAK.

### Detecção de Token Perdido e Duplicado

- Token perdido (não recebido em 5×tempo_token):  
  Nó gera um novo token automaticamente.
- Token duplicado (recebido antes do tempo esperado):  
  Token duplicado é descartado e exibido alerta no console.

---

## ⌨️ Comandos Disponíveis

Durante execução, você pode enviar mensagens digitando no terminal:

    destino mensagem

Exemplos:

    Bob Olá, Bob!
    TODOS Esta é uma mensagem broadcast para todos os nós!

---

## 📜 Logs e Depuração

O console exibe constantemente logs detalhados sobre:

- Recebimento e envio do token;
- Transmissão e recepção de pacotes de dados;
- Resultados de CRC (OK ou erro);
- Retransmissões (NAK);
- Detecção de token perdido ou duplicado.

Isso permite acompanhar em tempo real o estado completo da rede.

---

## 📌 Licença

Este projeto foi desenvolvido com finalidade acadêmica e não possui restrições específicas quanto à sua utilização ou modificação.
