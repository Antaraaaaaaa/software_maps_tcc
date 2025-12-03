from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

class ImageCanvas(FigureCanvasQTAgg):
    """
    Um widget personalizado que encapsula o Matplotlib dentro do Qt.
    """
    def __init__(self, parent=None):
        # Cria a figura e os eixos
        self.fig = Figure(figsize=(5, 4), dpi=100)
        
        # Inicializa a classe pai (o canvas do Qt)
        super().__init__(self.fig)
        self.setParent(parent)

        # Define o estado inicial com a mensagem
        self.show_empty_message()

    def show_empty_message(self):
        """Exibe um texto instrutivo quando não há imagem carregada"""
        self.fig.clf()  # Limpa tudo
        ax = self.fig.add_subplot(111)
        
        # Escreve o texto no centro (0.5, 0.5 são coordenadas relativas)
        ax.text(0.5, 0.5, 
                "Nenhuma imagem carregada.\n\nSelecione uma pasta ou abra um arquivo\nno menu 'Arquivo' para começar.", 
                horizontalalignment='center',
                verticalalignment='center',
                fontsize=12,
                color='gray',
                transform=ax.transAxes) # Importante: usa coordenadas do eixo, não de dados
        
        ax.axis('off')  # Esconde as bordas e números
        self.draw()

    def plot_image(self, image_data, cmap='afmhot', title="Visualização"):
        """
        Recebe uma matriz Numpy (2D) e plota como imagem térmica.
        """
        self.fig.clf()  # Limpa a figura inteira (remove subplots antigos)
        
        # Cria um único eixo (1 linha, 1 coluna, posição 1)
        ax = self.fig.add_subplot(111)

        # 'afmhot' é o mapa de cores padrão para Microscopia de Força Atômica
        # origin='lower' é importante pois dados físicos geralmente crescem de baixo para cima
        if image_data is not None:
            ax.imshow(image_data, cmap=cmap, origin='lower')
            ax.set_title(title)
            ax.axis('off')  # Remove os eixos de pixel
        
        # Atualiza o desenho
        self.draw()

    def plot_comparison(self, img_original, img_processed, cmap_processed='afmhot'):
        """Plota duas imagens lado a lado"""
        self.fig.clf()  # Limpa layout anterior
        
        # --- Plot 1: Original (Esquerda) ---
        ax1 = self.fig.add_subplot(121) # 1 linha, 2 colunas, índice 1
        if img_original is not None:
            # Se for RGB usa cor real, se for cinza usa 'gray'
            cmap = 'gray' if img_original.ndim == 2 else None
            ax1.imshow(img_original, cmap=cmap, origin='lower')
            ax1.set_title("Original")
            ax1.axis('off')

        # --- Plot 2: Processada (Direita) ---
        ax2 = self.fig.add_subplot(122) # 1 linha, 2 colunas, índice 2
        if img_processed is not None:
            ax2.imshow(img_processed, cmap=cmap_processed, origin='lower')
            ax2.set_title("Processada (AFM)")
            ax2.axis('off')

        self.draw()