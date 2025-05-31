# ring_network.py

import time
import sys
from RingNode import RingNode

if __name__ == "__main__":
    # Precisamos de 2 argumentos: <arquivo_config> <minha_porta>
    if len(sys.argv) < 3:
        print("Uso: python3 ring_network.py <arquivo_configuracao> <minha_porta>")
        sys.exit(1)

    config_file = sys.argv[1]
    # A porta local (onde este nó vai dar bind) estará em sys.argv[2], lida dentro de RingNode
    node = RingNode(config_file)

    try:
        # Mantém o programa vivo para que as threads daemon continuem rodando
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Ctrl+C → encerra nó limpamente
        node.shutdown()
        print("\nNó encerrado com sucesso.")
