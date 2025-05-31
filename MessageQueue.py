# MessageQueue.py

import queue

class MessageQueue:
    def __init__(self, max_size=10):
        self.queue = queue.Queue(maxsize=max_size)

    def enqueue(self, message):
        """
        Enfileira um dicionário {'dest': ..., 'content': ..., 'attempts': ...}.
        Retorna True se conseguiu, False se fila cheia ou formato inválido.
        """
        try:
            if not isinstance(message, dict) or 'dest' not in message or 'content' not in message or 'attempts' not in message:
                raise ValueError("Mensagem deve ser um dicionário com 'dest', 'content' e 'attempts'")
            self.queue.put(message, block=False)
            print(f"[MessageQueue] Mensagem enfileirada para {message['dest']}")
            return True
        except queue.Full:
            print("[MessageQueue] Fila cheia! Mensagem não adicionada.")
            return False
        except Exception as e:
            print(f"[MessageQueue] Erro ao enfileirar: {e}")
            return False

    def peek(self):
        """
        Retorna o elemento da frente da fila sem removê-lo (ou None se vazia).
        """
        try:
            with self.queue.mutex:
                if self.queue.queue:
                    return self.queue.queue[0]
            return None
        except Exception as e:
            print(f"[MessageQueue] Erro ao ver fila: {e}")
            return None

    def dequeue(self):
        """
        Remove e retorna o elemento da frente (ou None se vazia).
        """
        try:
            return self.queue.get(block=False)
        except queue.Empty:
            return None

    def is_empty(self):
        return self.queue.empty()

    def size(self):
        return self.queue.qsize()
