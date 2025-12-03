from abc import ABC, abstractmethod

class AFMPlugin(ABC):
    """
    Interface base que todos os plugins devem herdar.
    Isso garante que seu software saiba como conversar com qualquer módulo novo.
    """

    @property
    @abstractmethod
    def name(self):
        """Nome do plugin que aparecerá no Menu."""
        pass

    @property
    def category(self):
        """
        Retorna o nome da categoria (Submenu).
        Se retornar None, fica na raiz do menu Plugins.
        Pode ser sobrescrito pelos plugins, mas definimos um padrão aqui.
        """
        return "Geral"

    @abstractmethod
    def execute(self, data):
        """
        Método principal que recebe os dados (ex: a imagem ou matriz Numpy)
        e realiza o processamento.
        """
        pass