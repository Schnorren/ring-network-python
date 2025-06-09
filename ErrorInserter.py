# ErrorInserter.py

import random

class ErrorInserter:
    @staticmethod
    def insert_error(packet):
        """
        Insere um erro aleatório em um pacote de dados para simular corrupção de mensagem na transmissão.

        Parâmetros:
        - packet: dict contendo os campos do pacote (deve ter 'type' e 'message').

        Retorno:
        - O mesmo dicionário de pacote, possivelmente com uma mensagem modificada.
        """
        # Só proceed se for pacote de dados (não alteramos tokens)
        if packet.get('type') == 'data':
            message = packet.get('message', '')
            # Verifica se há conteúdo na mensagem para corromper
            if message:
                # Escolhe uma posição aleatória dentro da string
                pos = random.randint(0, len(message) - 1)
                original_char = message[pos]
                # Determina o caractere corrompido:
                # - Se não for o último caractere ASCII (126), incrementa o código em 1
                # - Caso contrário, substitui por espaço
                if ord(original_char) < 126:
                    corrupted_char = chr(ord(original_char) + 1)
                else:
                    corrupted_char = ' '
                # Monta a nova mensagem com o caractere corrompido
                corrupted = message[:pos] + corrupted_char + message[pos+1:]
                # Atualiza o campo 'message' do pacote
                packet['message'] = corrupted
                # Loga a alteração realizada para depuração
                print(f"[ErrorInserter] Caractere na posição {pos} alterado de '{original_char}' para '{corrupted_char}'")
        # Retorna o pacote (corrompido ou não)
        return packet
