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
        # 1) Lê arquivo de configuração e porta local via sys.argv[2]
        self.load_config(config_file)

        # 2) Fila interna de mensagens pendentes (capacidade 10)
        self.message_queue = MessageQueue(max_size=10)

        # 3) Estado do token
        self.token_holder = False

        # 4) Controle de tempo do token
        self.last_token_time = None            # Última vez que o token foi visto (enviado ou recebido)
        self.time_i_last_sent_token = None     # Hora em que este nó enviou o token por último
        
        # Token considerado perdido se não retornar em (5 × token_hold_time) segundos
        self.token_timeout = self.token_hold_time * 5

        # min_token_time: tempo mínimo para o token circular pelos N-1 outros nós e voltar
        # Para 3 nós, é (3-1) × token_hold_time = 2 × token_hold_time, com um buffer pequeno.
        self.min_token_time = self.token_hold_time * 2 + 0.5

        # 5) Flag para manter as threads rodando
        self.running = True

        # 6) Controle de “aguardar ACK/NAK antes de repassar token”
        self.waiting_for_answer = False

        # Configura o logging para arquivo próprio de cada nó
        logging.basicConfig(
            filename=f"{self.nickname}.log",
            level=logging.INFO,
            format='[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        )

        # 7) Cria o socket UDP e faz bind na porta local (via sys.argv[2])
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(('0.0.0.0', self.port))
            self.socket.settimeout(1.0)  # Timeout para recvfrom
        except Exception as e:
            print(f"[{self.nickname}] Erro ao bindar na porta {self.port}: {e}")
            sys.exit(1)

        # 8) Dispara threads como daemon:
        threading.Thread(target=self.generate_initial_token, daemon=True).start()
        threading.Thread(target=self.receive_packets, daemon=True).start()
        threading.Thread(target=self.token_monitor, daemon=True).start()
        threading.Thread(target=self.user_input_handler, daemon=True).start()

    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                if len(lines) < 4:
                    raise ValueError("Arquivo de configuração deve ter 4 linhas não vazias.")

                dest_ip, dest_port = lines[0].split(':')
                self.right_neighbor = (dest_ip, int(dest_port))
                self.nickname = lines[1]
                self.token_hold_time = int(lines[2])
                self.generate_token = lines[3].lower() == 'true'

                if len(sys.argv) < 3:
                    print("Uso: python3 ring_network.py <arquivo_config> <minha_porta>")
                    sys.exit(1)
                self.port = int(sys.argv[2])

                print(f"[{self.nickname}] Configuração carregada:")
                print(f"  - Porta local (bind): 0.0.0.0:{self.port}")
                print(f"  - Vizinho direito: {self.right_neighbor}")
                print(f"  - Tempo para segurar token: {self.token_hold_time}s")
                print(f"  - Gera token inicial? {'Sim' if self.generate_token else 'Não'}")

        except Exception as e:
            print(f"[{self.nickname if hasattr(self, 'nickname') else '??'}] Erro ao ler arquivo de configuração: {e}")
            sys.exit(1)

    def generate_initial_token(self):
        if self.generate_token:
            time.sleep(1.0)
            self.token_holder = True
            logging.info(f"[{self.nickname}] Gerando token inicial...")
            self.send_token()

    def send_token(self):
        try:
            token_payload = Packet.create_token()
            encoded_token_payload = Packet.encode(token_payload).encode('utf-8')
            self.socket.sendto(encoded_token_payload, self.right_neighbor)

            current_time = time.time()
            self.last_token_time = current_time
            self.time_i_last_sent_token = current_time

            logging.info(f"[{self.nickname}] Enviou token para {self.right_neighbor}")
            self.token_holder = False
        except Exception as e:
            logging.info(f"[{self.nickname}] Erro ao enviar token: {e}")

    def receive_packets(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                payload_str = data.decode('utf-8')

                # Verifica se é token ("1000")
                if payload_str == Packet.encode(Packet.create_token()):
                    self.handle_token_received(addr)
                # Verifica se é pacote de dados ("2000;...")
                elif payload_str.startswith(Packet.encode(Packet.create_data("", "", "", ""))[0:4]):
                    self.process_data_packet(payload_str, addr)
                else:
                    # Ignorar qualquer outro payload
                    pass
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logging.info(f"[{self.nickname}] Erro ao receber pacote: {e}")

    def handle_token_received(self, addr_from):
        current_time = time.time()

        if self.token_holder:
            # Token duplicado recebido
            logging.info(f"[{self.nickname}] AVISO: Token recebido de {addr_from} enquanto já possuía o token. Ignorando.")
            return

        # Marca que agora este nó possui o token
        self.token_holder = True
        logging.info(f"[{self.nickname}] Recebeu token de {addr_from}")

        # Verifica se veio muito rápido (token duplicado implícito)
        if self.time_i_last_sent_token is not None:
            elapsed_since_i_sent_it = current_time - self.time_i_last_sent_token
            if elapsed_since_i_sent_it < self.min_token_time:
                logging.info(f"[{self.nickname}] INFO: Token retornou em {elapsed_since_i_sent_it:.2f}s < min_token_time ({self.min_token_time}s).")

        self.last_token_time = current_time

        # Se há mensagem na fila e não está aguardando resposta, envia dados
        if not self.message_queue.is_empty() and not self.waiting_for_answer:
            self.send_data()
            self.waiting_for_answer = True
        # Se fila vazia, segura token por token_hold_time e repassa
        elif self.message_queue.is_empty():
            time.sleep(self.token_hold_time)
            self.send_token()
        # Se aguardando ACK/NAK, não faz nada até processar retorno

    def send_data(self):
        try:
            msg_details = self.message_queue.peek()
            if not msg_details:
                if self.token_holder:
                    time.sleep(self.token_hold_time)
                    self.send_token()
                return

            dest = msg_details['dest']
            content = msg_details['content']
            attempts = msg_details['attempts']

            status = "maquinanaoexiste"
            data_packet_dict = Packet.create_data(
                src_nick=self.nickname,
                dest_nick=dest,
                message=content,
                error_status=status
            )

            crc = CRC32.calculate(data_packet_dict)
            data_packet_dict = Packet.set_crc(data_packet_dict, crc)

            if random.random() < 0.3:
                data_packet_dict = ErrorInserter.insert_error(data_packet_dict)

            encoded_payload = Packet.encode(data_packet_dict).encode('utf-8')
            self.socket.sendto(encoded_payload, self.right_neighbor)
            logging.info(f"[{self.nickname}] Enviou pacote de dados para {dest} (tentativa {attempts+1}) via {self.right_neighbor}")
        except Exception as e:
            logging.info(f"[{self.nickname}] Erro ao enviar dados: {e}")
            if self.token_holder and self.waiting_for_answer:
                self.waiting_for_answer = False
                time.sleep(self.token_hold_time)
                self.send_token()

    def process_data_packet(self, payload_str, addr_from):
        try:
            data_packet = Packet.decode(payload_str)
            origem = data_packet['src_nick']
            destino = data_packet['dest_nick']
            status_atual = data_packet['error_status']
            mensagem = data_packet['message']

            logging.info(f"[{self.nickname}] Pacote de dados recebido de {addr_from} (origem: {origem}, destino: {destino}, status: {status_atual})")

            # Se for retorno ao remetente
            if origem == self.nickname:
                self.waiting_for_answer = False
                if status_atual == "ACK":
                    dequeued_msg = self.message_queue.dequeue()
                    logging.info(f"[{self.nickname}] Mensagem para {destino} entregada com ACK. Removendo da fila.")
                elif status_atual == "NAK":
                    msg_in_queue = self.message_queue.peek()
                    if msg_in_queue and msg_in_queue['dest'] == destino:
                        msg_in_queue['attempts'] += 1
                        if msg_in_queue['attempts'] >= 3:
                            self.message_queue.dequeue()
                            logging.info(f"[{self.nickname}] Mensagem para {destino} falhou após {msg_in_queue['attempts']} tentativas. Descartando.")
                        else:
                            logging.info(f"[{self.nickname}] Falha (NAK) ao entregar para {destino}. Tentativa {msg_in_queue['attempts']}. Será retransmitida.")
                    else:
                        logging.info(f"[{self.nickname}] Recebeu NAK para {destino}, mas não corresponde ao topo da fila.")
                elif status_atual == "maquinanaoexiste":
                    self.message_queue.dequeue()
                    logging.info(f"[{self.nickname}] Destino {destino} inexistente. Mensagem descartada.")
                else:
                    logging.info(f"[{self.nickname}] Status desconhecido '{status_atual}' para {destino}.")

                if self.token_holder:
                    if not self.message_queue.is_empty():
                        self.send_data()
                        self.waiting_for_answer = True
                    else:
                        time.sleep(self.token_hold_time)
                        self.send_token()
                return

            # Se for destinado a este nó (unicast)
            if destino == self.nickname:
                temp_packet_for_crc = {
                    'type': 'data', 
                    'value': data_packet['value'],
                    'src_nick': origem,
                    'dest_nick': destino,
                    'error_status': status_atual,
                    'message': mensagem
                }
                crc_calculado = CRC32.calculate(temp_packet_for_crc)
                try:
                    crc_recebido = int(data_packet['crc'])
                except ValueError:
                    logging.info(f"[{self.nickname}] CRC recebido inválido '{data_packet['crc']}'. Enviando NAK.")
                    data_packet['error_status'] = "NAK"
                    data_packet['crc'] = '0'
                    new_crc = CRC32.calculate(data_packet)
                    Packet.set_crc(data_packet, new_crc)
                    self.socket.sendto(Packet.encode(data_packet).encode('utf-8'), self.right_neighbor)
                    return

                if crc_calculado != crc_recebido:
                    data_packet['error_status'] = "NAK"
                    logging.info(f"[{self.nickname}] CRC falhou (origem={origem}). Enviando NAK.")
                else:
                    data_packet['error_status'] = "ACK"
                    logging.info(f"[{self.nickname}] CRC OK. Mensagem de {origem}: \"{mensagem}\". Enviando ACK.")

                data_packet['crc'] = '0'
                new_crc_for_ack = CRC32.calculate(data_packet)
                Packet.set_crc(data_packet, new_crc_for_ack)
                self.socket.sendto(Packet.encode(data_packet).encode('utf-8'), self.right_neighbor)
                return

            # Se for broadcast (destino == "TODOS")
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
                try:
                    crc_recebido_bcast = int(data_packet['crc'])
                    if crc_calculado_bcast == crc_recebido_bcast:
                        logging.info(f"[{self.nickname}] Broadcast de {origem}: \"{mensagem}\" (CRC OK)")
                    else:
                        logging.info(f"[{self.nickname}] Broadcast de {origem}: \"{mensagem}\" (CRC FALHOU)")
                except ValueError:
                    logging.info(f"[{self.nickname}] Broadcast de {origem}: \"{mensagem}\" (CRC inválido)")

                self.socket.sendto(payload_str.encode('utf-8'), self.right_neighbor)
                return

            # Se não for para mim e não for broadcast, repassa
            self.socket.sendto(payload_str.encode('utf-8'), self.right_neighbor)

        except Exception as e:
            logging.info(f"[{self.nickname}] Erro ao processar pacote: {e}. Payload: '{payload_str}'")

    def token_monitor(self):
        while self.running:
            time.sleep(1)
            if self.last_token_time is not None:
                elapsed = time.time() - self.last_token_time
                if elapsed > self.token_timeout and not self.token_holder:
                    logging.info(f"[{self.nickname}] Token perdido (sem atividade por {elapsed:.2f}s). Gerando novo token...")
                    self.token_holder = True
                    self.generate_token = True
                    self.send_token()

    def user_input_handler(self):
        print(f"\n[{self.nickname}] Pronto para receber comandos (formato: <destino> <mensagem>):")
        while self.running:
            try:
                ready, _, _ = select.select([sys.stdin], [], [], 1.0)
                if ready:
                    line = sys.stdin.readline().strip()
                    if not line:
                        continue

                    parts = line.split(' ', 1)
                    if len(parts) < 2:
                        print(f"[{self.nickname}] Comando inválido. Use: <destino> <mensagem>")
                        continue

                    dest_nick = parts[0]
                    message_content = parts[1]

                    queued_ok = self.message_queue.enqueue({
                        'dest': dest_nick,
                        'content': message_content,
                        'attempts': 0
                    })

                    if not queued_ok:
                        print(f"[{self.nickname}] Fila cheia. Não foi possível enfileirar para {dest_nick}.")
                    elif self.token_holder and not self.waiting_for_answer:
                        print(f"[{self.nickname}] Possui token, enviando dados imediatamente...")
                        self.send_data()
                        self.waiting_for_answer = True
            except Exception as e:
                if self.running:
                    print(f"[{self.nickname}] Erro no input do usuário: {e}")

    def shutdown(self):
        print(f"[{self.nickname}] Encerrando nó...")
        self.running = False
        try:
            self.socket.close()
        except Exception as e:
            print(f"[{self.nickname}] Erro ao fechar socket: {e}")
