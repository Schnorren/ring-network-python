import socket
import threading
import time
import select
import sys
import random
import logging
from MessageQueue import MessageQueue
from Packet import Packet
from CRC32 import CRC32
from ErrorInserter import ErrorInserter

class RingNode:
    def __init__(self, config_file):
        # Carrega configurações do nó a partir de um arquivo externo
        self.load_config(config_file)

        # Inicializa a fila de mensagens pendentes (limite máximo de 10)
        self.message_queue = MessageQueue(max_size=10)

        # Indica se o nó possui o token inicialmente (começa sem token)
        self.token_holder = False

        # Registra o último momento que viu ou enviou o token
        self.last_token_time = None
        self.time_i_last_sent_token = None

        # Define o tempo limite para detectar perda do token (timeout)
        self.token_timeout = self.token_hold_time * 5

        # Tempo mínimo esperado para o retorno do token após ser enviado
        self.min_token_time = self.token_hold_time * 2 + 0.5

        # Flag que indica se o nó está rodando (para controle das threads)
        self.running = True

        # Indica se o nó está aguardando resposta (ACK ou NAK) de mensagem enviada
        self.waiting_for_answer = False

        # Configuração do sistema de logs (salvos em arquivo específico do nó)
        logging.basicConfig(
            filename=f"{self.nickname}.log",
            level=logging.INFO,
            format='[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        )

        # Cria o socket UDP para comunicação na rede em anel
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Vincula (bind) o socket à porta especificada (tenta ouvir na porta configurada)
        try:
            self.socket.bind(('0.0.0.0', self.port))
            self.socket.settimeout(1.0)  # Define um timeout curto para não bloquear infinitamente
        except Exception as e:
            print(f"[{self.nickname}] Erro ao bindar na porta {self.port}: {e}")
            sys.exit(1)  # Sai caso não consiga vincular o socket à porta

        # Inicializa as threads para diferentes funções essenciais do nó
        threading.Thread(target=self.generate_initial_token, daemon=True).start()  # Thread que gera token inicial se configurado
        threading.Thread(target=self.receive_packets, daemon=True).start()        # Thread que recebe e processa pacotes continuamente
        threading.Thread(target=self.token_monitor, daemon=True).start()          # Thread que monitora se o token foi perdido
        threading.Thread(target=self.user_input_handler, daemon=True).start()     # Thread que escuta comandos do usuário para envio de mensagens

    def load_config(self, config_file):
        try:
            # Abre o arquivo de configuração para leitura
            with open(config_file, 'r') as f:
                # Lê todas as linhas não vazias e remove espaços em branco das extremidades
                lines = [line.strip() for line in f.readlines() if line.strip()]

                # Verifica se o arquivo contém exatamente 4 linhas obrigatórias
                if len(lines) < 4:
                    raise ValueError("Arquivo de configuração deve ter 4 linhas não vazias.")

                # Extrai endereço IP e porta do vizinho direito (formato IP:Porta)
                dest_ip, dest_port = lines[0].split(':')
                self.right_neighbor = (dest_ip, int(dest_port))

                # Obtém o nickname (identificador) do nó atual
                self.nickname = lines[1]

                # Configura o tempo que o nó segurará o token antes de passar adiante
                self.token_hold_time = int(lines[2])

                # Determina se este nó será responsável por gerar o token inicial
                self.generate_token = lines[3].lower() == 'true'

                # Verifica se o usuário forneceu a porta local como argumento via linha de comando
                if len(sys.argv) < 3:
                    print("Uso: python3 ring_network.py <arquivo_config> <minha_porta>")
                    sys.exit(1)

                # Atribui a porta local fornecida como argumento do sistema
                self.port = int(sys.argv[2])

                # Exibe as configurações carregadas no console para validação
                print(f"[{self.nickname}] Configuração carregada:")
                print(f"  - Porta local (bind): 0.0.0.0:{self.port}")
                print(f"  - Vizinho direito: {self.right_neighbor}")
                print(f"  - Tempo para segurar token: {self.token_hold_time}s")
                print(f"  - Gera token inicial? {'Sim' if self.generate_token else 'Não'}")

        except Exception as e:
            # Trata exceções e exibe erro com detalhe apropriado
            print(f"[{self.nickname if hasattr(self, 'nickname') else '??'}] Erro ao ler arquivo de configuração: {e}")
            sys.exit(1)  # Encerra o programa devido a erro crítico

    def generate_initial_token(self):
        # Verifica se este nó é responsável por gerar o token inicial (conforme arquivo de configuração)
        if self.generate_token:
            # Espera 1 segundo para garantir que todos os nós estejam prontos na rede antes de gerar o token
            time.sleep(1.0)

            # Marca o nó como possuidor atual do token
            self.token_holder = True

            # Registra no log que o token inicial está sendo gerado
            logging.info(f"🛠️ [{self.nickname}] Gerando token inicial...")

            # Chama a função que envia o token ao próximo nó
            self.send_token()

    def send_token(self):
        try:
            # Cria o pacote de token para ser transmitido
            token_payload = Packet.create_token()

            # Codifica o pacote em formato string e depois em bytes UTF-8 para envio via UDP
            encoded_token_payload = Packet.encode(token_payload).encode('utf-8')

            # Envia o token para o próximo nó na rede (vizinho direito)
            self.socket.sendto(encoded_token_payload, self.right_neighbor)

            # Atualiza o registro do tempo atual como o momento em que o token foi enviado
            current_time = time.time()
            self.last_token_time = current_time
            self.time_i_last_sent_token = current_time

            # Registra no log a ação de envio do token
            logging.info(f"🔄 [{self.nickname}] Enviou TOKEN para {self.right_neighbor}")
            logging.info(f"🚚 Token agora em trânsito para {self.right_neighbor}")

            # Marca que o nó não possui mais o token após enviá-lo
            self.token_holder = False

        except Exception as e:
            # Registra qualquer exceção ocorrida durante o envio do token no log
            logging.info(f"❌ [{self.nickname}] Erro ao enviar token: {e}")

    def receive_packets(self):
        # Loop infinito para receber pacotes continuamente enquanto o nó está ativo
        while self.running:
            try:
                # Recebe um pacote UDP (até 4096 bytes)
                data, addr = self.socket.recvfrom(4096)

                # Decodifica os dados recebidos para string UTF-8
                payload_str = data.decode('utf-8')

                # Verifica se o pacote recebido é o token (comparação direta)
                if payload_str == Packet.encode(Packet.create_token()):
                    self.handle_token_received(addr)

                # Verifica se o pacote recebido é um pacote de dados (verifica prefixo identificador)
                elif payload_str.startswith(Packet.encode(Packet.create_data("", "", "", ""))[0:4]):
                    self.process_data_packet(payload_str, addr)

            except socket.timeout:
                # Ignora a exceção de timeout e continua o loop (para manter o programa ativo)
                continue

            except Exception as e:
                # Registra outros erros inesperados durante a recepção no log
                if self.running:
                    logging.info(f"⚠️ [{self.nickname}] Erro ao receber pacote: {e}")

    def handle_token_received(self, addr_from):
        # Armazena o momento atual do recebimento do token
        current_time = time.time()

        # Verifica se este nó já possui o token (evitando duplicidade)
        if self.token_holder:
            logging.info(f"⚠️ [{self.nickname}] TOKEN duplicado recebido de {addr_from} — Ignorando")
            return  # Sai do método sem realizar mais ações

        # Marca o nó como possuidor atual do token
        self.token_holder = True
        logging.info(f"🟢 [{self.nickname}] TOKEN chegou de {addr_from} — Agora em {self.nickname}")

        # Verifica o tempo transcorrido desde o envio anterior do token, caso já tenha sido enviado antes
        if self.time_i_last_sent_token is not None:
            elapsed = current_time - self.time_i_last_sent_token
            if elapsed < self.min_token_time:
                logging.info(f"⏱️ [{self.nickname}] Token retornou em {elapsed:.2f}s (esperado mínimo: {self.min_token_time}s)")

        # Atualiza o último tempo registrado em que o token foi visto
        self.last_token_time = current_time

        # Verifica se há mensagens pendentes na fila e se não está aguardando resposta
        if not self.message_queue.is_empty() and not self.waiting_for_answer:
            # Se houver mensagem, tenta enviá-la imediatamente
            self.send_data()
            self.waiting_for_answer = True
        elif self.message_queue.is_empty():
            # Se não houver mensagem, aguarda um tempo definido e então envia o token adiante
            time.sleep(self.token_hold_time)
            self.send_token()

    def send_data(self):
        try:
            # Verifica a próxima mensagem na fila sem removê-la
            msg = self.message_queue.peek()

            # Se não houver mensagens para enviar, verifica se possui token para passá-lo adiante
            if not msg:
                if self.token_holder:
                    time.sleep(self.token_hold_time)  # Aguarda o tempo definido antes de passar o token
                    self.send_token()  # Envia o token ao próximo nó
                return  # Encerra o método caso não haja mensagem a ser enviada

            # Extrai informações da mensagem pendente (destinatário, conteúdo e número de tentativas)
            dest, content, attempts = msg['dest'], msg['content'], msg['attempts']

            # Define um status inicial padrão caso o destinatário não exista (será ajustado posteriormente)
            status = "maquinanaoexiste"

            # Cria o pacote de dados utilizando informações do remetente, destinatário e conteúdo
            data_packet = Packet.create_data(self.nickname, dest, content, status)

            # Calcula o valor de checksum CRC32 para garantir integridade dos dados
            crc = CRC32.calculate(data_packet)

            # Insere o CRC no pacote criado
            data_packet = Packet.set_crc(data_packet, crc)

            # Simula ocorrência de erro com 30% de chance (para testar robustez do sistema)
            if random.random() < 0.3:
                data_packet = ErrorInserter.insert_error(data_packet)

            # Codifica o pacote completo para string e depois bytes UTF-8
            encoded = Packet.encode(data_packet).encode('utf-8')

            # Envia o pacote para o próximo nó na rede
            self.socket.sendto(encoded, self.right_neighbor)

            # Registra a tentativa de envio no log com detalhes
            logging.info(f"✉️ [{self.nickname}] Enviando para {dest} (tentativa {attempts+1}) via {self.right_neighbor}")
            logging.info(f"📦 Pacote agora em trânsito para {self.right_neighbor}")

        except Exception as e:
            # Trata erros durante o envio, registrando-os no log
            logging.info(f"❌ [{self.nickname}] Erro ao enviar dados: {e}")

            # Caso esteja aguardando uma resposta e possua o token, passa-o adiante após timeout
            if self.token_holder and self.waiting_for_answer:
                self.waiting_for_answer = False
                time.sleep(self.token_hold_time)
                self.send_token()

    def process_data_packet(self, payload_str, addr_from):
        try:
            # Decodifica o pacote de dados recebido
            data_packet = Packet.decode(payload_str)
            
            # Extrai informações principais do pacote
            origem = data_packet['src_nick']
            destino = data_packet['dest_nick']
            status_atual = data_packet['error_status']
            mensagem = data_packet['message']

            logging.info(f"[{self.nickname}] Pacote recebido de {addr_from} (origem: {origem}, destino: {destino}, status: {status_atual})")

            # Verifica se o pacote retornou ao remetente original (este nó)
            if origem == self.nickname:
                self.waiting_for_answer = False
                
                # Se o pacote foi um broadcast, remove imediatamente da fila ao retornar
                if destino == "TODOS":
                    dequeued_msg = self.message_queue.dequeue()
                    logging.info(f"[{self.nickname}] Broadcast para TODOS completou a volta e foi removido da fila.")
                else:
                    # Se a mensagem retornada foi confirmada com sucesso (ACK)
                    if status_atual == "ACK":
                        dequeued_msg = self.message_queue.dequeue()
                        logging.info(f"[{self.nickname}] Mensagem para {destino} entregue com sucesso (ACK). Removendo da fila.")
                    
                    # Se houve falha na entrega (NAK)
                    elif status_atual == "NAK":
                        msg_in_queue = self.message_queue.peek()
                        if msg_in_queue and msg_in_queue['dest'] == destino:
                            msg_in_queue['attempts'] += 1
                            
                            # Limita a apenas uma retransmissão
                            if msg_in_queue['attempts'] >= 2:
                                self.message_queue.dequeue()
                                logging.info(f"[{self.nickname}] Mensagem para {destino} falhou após 1 retransmissão. Removendo.")
                            else:
                                logging.info(f"[{self.nickname}] Falha (NAK) para {destino}. Retransmitindo (tentativa {msg_in_queue['attempts']}).")
                        else:
                            logging.info(f"[{self.nickname}] Recebido NAK para {destino}, mas não corresponde ao topo da fila.")

                    # Se o destino não existe
                    elif status_atual == "maquinanaoexiste":
                        self.message_queue.dequeue()
                        logging.info(f"[{self.nickname}] Destino {destino} inexistente. Mensagem descartada.")
                    else:
                        logging.info(f"[{self.nickname}] Status desconhecido '{status_atual}' recebido.")

                # Decide se há outra mensagem para enviar ou se deve passar o token
                if self.token_holder:
                    if not self.message_queue.is_empty():
                        self.send_data()
                        self.waiting_for_answer = True
                    else:
                        time.sleep(self.token_hold_time)
                        self.send_token()
                return

            # Se o pacote é destinado diretamente a este nó (unicast)
            if destino == self.nickname:
                # Cria um pacote temporário para calcular CRC
                temp_packet_for_crc = {
                    'type': 'data',
                    'value': data_packet['value'],
                    'src_nick': origem,
                    'dest_nick': destino,
                    'error_status': status_atual,
                    'message': mensagem
                }
                crc_calculado = CRC32.calculate(temp_packet_for_crc)
                
                # Validação do CRC recebido
                try:
                    crc_recebido = int(data_packet['crc'])
                except ValueError:
                    logging.info(f"[{self.nickname}] CRC inválido '{data_packet['crc']}'. Enviando NAK.")
                    data_packet['error_status'] = "NAK"
                    data_packet['crc'] = '0'
                    new_crc = CRC32.calculate(data_packet)
                    Packet.set_crc(data_packet, new_crc)
                    self.socket.sendto(Packet.encode(data_packet).encode('utf-8'), self.right_neighbor)
                    return

                # Verifica CRC para confirmar integridade
                if crc_calculado != crc_recebido:
                    data_packet['error_status'] = "NAK"
                    logging.info(f"[{self.nickname}] Falha no CRC (origem={origem}). Enviando NAK.")
                else:
                    data_packet['error_status'] = "ACK"
                    logging.info(f"[{self.nickname}] CRC válido. Mensagem de {origem}: \"{mensagem}\". Enviando ACK.")

                # Recalcula CRC e encaminha o pacote ACK ou NAK
                data_packet['crc'] = '0'
                new_crc_for_ack = CRC32.calculate(data_packet)
                Packet.set_crc(data_packet, new_crc_for_ack)
                self.socket.sendto(Packet.encode(data_packet).encode('utf-8'), self.right_neighbor)
                return

            # Se o pacote é um broadcast (destino "TODOS")
            if destino == "TODOS":
                temp_packet_bcast = {
                    'type': 'data',
                    'value': data_packet['value'],
                    'src_nick': origem,
                    'dest_nick': destino,
                    'error_status': status_atual,
                    'message': mensagem
                }
                crc_calculado_bcast = CRC32.calculate(temp_packet_bcast)

                # Validação do CRC do pacote broadcast recebido
                try:
                    crc_recebido_bcast = int(data_packet['crc'])
                    if crc_calculado_bcast == crc_recebido_bcast:
                        logging.info(f"[{self.nickname}] Broadcast válido de {origem}: \"{mensagem}\" (CRC OK)")
                    else:
                        logging.info(f"[{self.nickname}] Broadcast inválido de {origem}: \"{mensagem}\" (CRC falhou)")
                except ValueError:
                    logging.info(f"[{self.nickname}] Broadcast de {origem} com CRC inválido: \"{mensagem}\"")

                # Encaminha o broadcast para o próximo nó
                self.socket.sendto(payload_str.encode('utf-8'), self.right_neighbor)
                return

            # Se o pacote não é destinado a este nó nem é broadcast, simplesmente encaminha ao próximo nó
            self.socket.sendto(payload_str.encode('utf-8'), self.right_neighbor)

        except Exception as e:
            logging.info(f"[{self.nickname}] Erro ao processar pacote: {e}. Payload: '{payload_str}'")

    def token_monitor(self):
        # Monitora continuamente a presença do token na rede
        while self.running:
            # Aguarda 1 segundo antes de cada verificação
            time.sleep(1)

            # Verifica se o token já foi visto antes
            if self.last_token_time is not None:
                # Calcula quanto tempo se passou desde a última vez que viu o token
                elapsed = time.time() - self.last_token_time

                # Se o tempo ultrapassou o limite (token_timeout) e o nó não possui o token atualmente
                if elapsed > self.token_timeout and not self.token_holder:
                    # Registra no log que o token foi considerado perdido
                    logging.info(f"🕳️ [{self.nickname}] TOKEN perdido após {elapsed:.2f}s — Gerando novo...")

                    # Marca o nó como possuidor atual do token
                    self.token_holder = True

                    # Ajusta flag para indicar que irá gerar um novo token
                    self.generate_token = True

                    # Envia o novo token gerado ao próximo nó
                    self.send_token()

    def user_input_handler(self):
        # Exibe mensagem inicial para indicar que o nó está pronto para receber comandos
        print(f"\n[{self.nickname}] Pronto para comandos (<destino> <mensagem>):")
        
        # Loop para escutar continuamente os comandos do usuário enquanto o nó estiver ativo
        while self.running:
            try:
                # Aguarda até 1 segundo por entrada do usuário sem bloquear o restante do programa
                ready, _, _ = select.select([sys.stdin], [], [], 1.0)
                
                # Se houver entrada disponível do usuário
                if ready:
                    # Lê a linha digitada pelo usuário e remove espaços em branco adicionais
                    line = sys.stdin.readline().strip()
                    # Comando: /forcartoken
                    if line == "/forcartoken":
                        if not self.token_holder:
                            self.token_holder = True
                            logging.info(f"[{self.nickname}] Comando manual: forçando token.")
                            self.send_token()
                        continue

                    # Comando: /removertoken
                    if line == "/removertoken":
                        self.token_holder = False
                        logging.info(f"[{self.nickname}] Comando manual: removendo token (não será passado).")
                        continue

                    # Comando: /limparfila
                    if line == "/limparfila":
                        while not self.message_queue.is_empty():
                            self.message_queue.dequeue()
                        print(f"[{self.nickname}] Fila de mensagens limpa.")
                        logging.info(f"[{self.nickname}] Comando manual: limpando fila de mensagens.")
                        continue

                    if line == "/debug":
                        tempo_desde_token = time.time() - self.last_token_time if self.last_token_time else "nunca"
                        print(f"[{self.nickname}] STATUS DEBUG")
                        print(f"  Possui token? {'Sim' if self.token_holder else 'Não'}")
                        print(f"  Aguardando ACK/NAK? {'Sim' if self.waiting_for_answer else 'Não'}")
                        print(f"  Último token visto há: {tempo_desde_token} segundos")
                        continue

                    if line == "/duplicartoken":
                        token = Packet.create_token()
                        self.socket.sendto(Packet.encode(token).encode('utf-8'), self.right_neighbor)
                        self.socket.sendto(Packet.encode(token).encode('utf-8'), self.right_neighbor)
                        logging.info(f"[{self.nickname}] Comando: token duplicado enviado.")
                        continue

                    if line == "/statusanel":
                        print(f"[{self.nickname}] Status do anel:")
                        print(f"  Token: {'Sim' if self.token_holder else 'Não'}")
                        print(f"  Fila vazia: {'Sim' if self.message_queue.is_empty() else 'Não'}")
                        print(f"  Esperando resposta? {'Sim' if self.waiting_for_answer else 'Não'}")
                        continue


                    if line == "/mostrafila":
                        with self.message_queue.queue.mutex:
                            fila = list(self.message_queue.queue.queue)
                            print(f"[{self.nickname}] Fila atual:")
                            for i, msg in enumerate(fila):
                                print(f"  {i+1}. Para {msg['dest']} – \"{msg['content']}\" (tentativas: {msg['attempts']})")
                        continue

                    if line.startswith("/tempo "):
                        try:
                            novo_tempo = float(line.split()[1])
                            self.token_hold_time = novo_tempo
                            self.token_timeout = self.token_hold_time * 5
                            self.min_token_time = self.token_hold_time * 2 + 0.5
                            print(f"[{self.nickname}] Tempo do token ajustado para {novo_tempo} segundos.")
                        except ValueError:
                            print(f"[{self.nickname}] Valor inválido para tempo.")
                        continue


                    # Ignora linhas vazias
                    if not line:
                        continue
                    
                    # Divide a linha em duas partes: destino e mensagem
                    parts = line.split(' ', 1)
                    
                    # Valida se a entrada contém ao menos duas partes (destinatário e mensagem)
                    if len(parts) < 2:
                        print(f"[{self.nickname}] Comando inválido. Use: <destino> <mensagem>")
                        continue
                    
                    # Extrai destinatário e mensagem digitados pelo usuário
                    dest, msg = parts[0], parts[1]
                    
                    # Tenta enfileirar a mensagem na fila de mensagens pendentes
                    ok = self.message_queue.enqueue({'dest': dest, 'content': msg, 'attempts': 0})
                    
                    # Se a fila estiver cheia, informa o usuário
                    if not ok:
                        print(f"[{self.nickname}] Fila cheia. Não foi possível enfileirar.")
                    # Se possuir o token e não estiver aguardando resposta, inicia envio imediatamente
                    elif self.token_holder and not self.waiting_for_answer:
                        print(f"[{self.nickname}] Possui token, enviando...")
                        self.send_data()
                        self.waiting_for_answer = True
                        
            except Exception as e:
                # Trata e exibe erros inesperados durante a leitura de entrada do usuário
                if self.running:
                    print(f"[{self.nickname}] Erro no input do usuário: {e}")

    def shutdown(self):
        # Exibe mensagem indicando que o nó está sendo encerrado
        print(f"[{self.nickname}] Encerrando nó...")

        # Altera a flag para encerrar os loops das threads que dependem de 'self.running'
        self.running = False

        try:
            # Tenta fechar o socket UDP utilizado pela aplicação
            self.socket.close()
        except Exception as e:
            # Caso ocorra algum erro ao fechar o socket, exibe uma mensagem de erro
            print(f"[{self.nickname}] Erro ao fechar socket: {e}")
