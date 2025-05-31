# Packet.py

class Packet:
    @staticmethod
    def create_token():
        """
        Cria um dicionário representando o token.
        """
        return {'type': 'token', 'value': '1000'}

    @staticmethod
    def create_data(src_nick, dest_nick, message, error_status):
        """
        Cria o dicionário básico para um pacote de dados.
        O campo 'value' sempre será '2000' para indicar "pacote de dados".
        'error_status' inicia como "maquinanaoexiste".
        """
        return {
            'type': 'data',
            'value': '2000',
            'src_nick': src_nick,
            'dest_nick': dest_nick,
            'error_status': error_status,  # "maquinanaoexiste", "ACK" ou "NAK"
            'crc': '0',                    # será substituído pelo valor correto
            'message': message
        }

    @staticmethod
    def set_crc(packet_dict, crc_value):
        """
        Ajusta o campo 'crc' no dicionário de pacote de dados.
        """
        packet_dict['crc'] = str(crc_value)
        return packet_dict

    @staticmethod
    def encode(packet_dict):
        """
        Converte o dicionário de pacote em string no formato UDP:
          • Token: apenas '1000'
          • Dados: "2000;<origem>:<destino>:<status>:<CRC>:<mensagem>"
        """
        if packet_dict['type'] == 'token':
            return packet_dict['value']  # "1000"
        else:
            return (f"{packet_dict['value']};"
                    f"{packet_dict['src_nick']}:{packet_dict['dest_nick']}:"
                    f"{packet_dict['error_status']}:"
                    f"{packet_dict['crc']}:"
                    f"{packet_dict['message']}")

    @staticmethod
    def decode(payload_str):
        """
        Converte a string recebida via UDP em dicionário de pacote de dados.
        Espera-se que payload_str comece com "2000;".
        """
        try:
            prefix, rest = payload_str.split(";", 1)
            if prefix != "2000":
                raise ValueError("Pacote de dados deve começar com '2000;'")
            parts = rest.split(":", 4)
            if len(parts) != 5:
                raise ValueError("Campos do pacote de dados incompletos")

            return {
                'type': 'data',
                'value': prefix,
                'src_nick': parts[0],
                'dest_nick': parts[1],
                'error_status': parts[2],
                'crc': parts[3],
                'message': parts[4]
            }
        except Exception as e:
            print(f"[Packet] Erro ao decodificar pacote: {e}")
            raise
