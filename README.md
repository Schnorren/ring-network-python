# Simulador de Rede em Anel com Token Passing

Este projeto simula uma rede local em anel (Token Ring) utilizando comunicação UDP em Python, com controle de erros por CRC32, retransmissão de pacotes, inserção aleatória de erros, suporte a broadcast e gerenciamento automático de tokens perdidos ou duplicados.

---

## 📌 Índice

- Simulador de Rede em Anel com Token Passing
  - 📌 Índice
  - 📖 Descrição do Projeto
  - ✅ Pré-requisitos
  - 📁 Estrutura dos Arquivos
  - 🛠️ Como Configurar
  - 🚀 Como Executar
  - 💻 Detalhes Técnicos
    - Formato dos Pacotes
    - Fluxo de Token e Dados
    - Controle de Erros e Retransmissão
    - Broadcast
    - Detecção de Token Perdido e Duplicado
  - ⌨️ Comandos Disponíveis
  - 📜 Logs e Depuração
  - 📌 Licença

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
    ├── config_alice.txt        # Configuração da Alice
    ├── config_bob.txt          # Configuração do Bob
    └── config_charlie.txt      # Configuração do Charlie

---

## 🛠️ Como Configurar

Cada nó utiliza um arquivo texto com exatamente 4 linhas:

    ip_do_vizinho:porta_vizinho
    apelido_da_maquina
    tempo_do_token_em_segundos
    gera_token_inicial (true ou false)

**Exemplo:**

    127.0.0.1:6001
    Alice
    2
    true

Cada nó precisa ter seu próprio arquivo `.txt`.

---

## 🚀 Como Executar

Abra um terminal por nó (ou abas diferentes) e execute:

    python3 ring_network.py arquivo_configuracao.txt porta_local

**Exemplo:**

    python3 ring_network.py config_alice.txt 6001
    python3 ring_network.py config_bob.txt 6002
    python3 ring_network.py config_charlie.txt 6000

---

## 💻 Detalhes Técnicos

### Formato dos Pacotes

- Token:
1000

- Dados:
2000;origem:destino:status:CRC:mensagem

- Status:
  - maquinanaoexiste
  - ACK
  - NAK

### Fluxo de Token e Dados

- Só envia dados se possuir o token;
- A mensagem circula até voltar com ACK, NAK ou maquinanaoexiste;
- ACK ou maquinanaoexiste: mensagem removida;
- NAK: mensagem permanece para retransmissão (1 vez).

### Controle de Erros e Retransmissão

- CRC32 calculado antes do envio;
- Recalculado no destino;
  - CRC correto: ACK
  - CRC incorreto: NAK

### Broadcast

- Destino = TODOS
- Todos exibem e repassam
- Sem ACK/NAK

### Detecção de Token Perdido e Duplicado

- Token perdido: novo token gerado após timeout
- Token duplicado: detectado se token voltar antes do tempo mínimo esperado, token extra é descartado

---

## ⌨️ Comandos Disponíveis

Durante a execução, digite no terminal:

### Envio de mensagens:

    destino mensagem

Exemplo:

    Bob Olá, Bob!
    TODOS Esta é uma mensagem para todos!

### Comandos de depuração e controle:

    /forcartoken       # Força o envio de token manualmente
    /removertoken      # Simula perda do token
    /limparfila        # Esvazia a fila de mensagens
    /mostrafila        # Exibe todas as mensagens na fila
    /debug             # Mostra status do nó (token, fila, espera...)
    /duplicartoken     # Envia manualmente um token duplicado
    /statusanel        # Mostra o que o nó está fazendo
    /tempo <segundos>  # Altera o tempo de retenção do token em tempo real

---

## 📜 Logs e Depuração

Cada nó gera um arquivo `.log` com eventos como:

- Recebimento/envio de token
- Envio/recebimento de mensagens
- Detecção de erro CRC
- Retransmissões (NAK)
- Geração ou descarte de token

---

## 📌 Licença

Projeto acadêmico. Uso livre para fins educacionais.
