# CRC32.py

import zlib

class CRC32:
    @staticmethod
    def calculate(packet):
        """
        Se for token: retorna zlib.crc32 sobre packet['value'].
        Se for dado: constrói string "<value>;<src>:<dest>:<status>:0:<message>"
                  (o campo '0' no meio indica que ainda não colocamos CRC).
        Calcula CRC32 sobre essa string e retorna valor inteiro.
        """
        if packet['type'] == 'token':
            data = packet['value']
        else:
            # Monta string para cálculo do CRC32 (campo '0' indica placeholder para CRC)
            data = (f"{packet['value']};"
                    f"{packet['src_nick']}:{packet['dest_nick']}:"
                    f"{packet['error_status']}:0:"
                    f"{packet['message']}")
        crc_value = zlib.crc32(data.encode('utf-8')) & 0xffffffff
        print(f"[CRC32] Calculado para dados: '{data}' -> {crc_value}")
        return crc_value
