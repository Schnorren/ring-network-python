# ErrorInserter.py

import random

class ErrorInserter:
    @staticmethod
    def insert_error(packet):
        """
        Se packet['type']=='data', altera aleatoriamente um caractere da mensagem.
        Retorna o dicionário de pacote corrompido (packet['message'] modificado).
        """
        if packet['type'] == 'data':
            message = packet['message']
            if len(message) > 0:
                pos = random.randint(0, len(message) - 1)
                original_char = message[pos]
                # Mudar para próximo ASCII (ou espaço se for 126)
                corrupted_char = chr(ord(original_char) + 1) if ord(original_char) < 126 else ' '
                corrupted = message[:pos] + corrupted_char + message[pos+1:]
                packet['message'] = corrupted
                print(f"[ErrorInserter] Caractere na posição {pos} alterado de '{original_char}' para '{corrupted_char}'")
        return packet
