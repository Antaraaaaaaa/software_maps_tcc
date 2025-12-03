import numpy as np
from skimage import filters, measure, util, morphology
from skimage.morphology import skeletonize, disk, opening
from PySide6.QtWidgets import QDialog, QVBoxLayout, QSlider, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt
from core.plugin_interface import AFMPlugin

# --- PLUGIN 1: LIMIARIZAÇÃO AUTOMÁTICA (OTSU) ---
class OtsuThresholdPlugin(AFMPlugin):
    @property
    def name(self): return "Limiarização Automática (Otsu)"

    @property
    def category(self): return "Segmentação"

    def execute(self, data):
        """
        Calcula o limiar ideal baseando-se no histograma bimodal.
        Retorna uma máscara binária (0 ou 255).
        """
        # Calcula o valor de limiar de Otsu
        thresh = filters.threshold_otsu(data)
        
        # Cria a máscara (Booleana: True onde é maior que o limiar)
        binary_mask = data > thresh
        
        # Converte para 0 (fundo) e 255 (objeto) para visualização correta
        return util.img_as_ubyte(binary_mask)


# --- PLUGIN 2: LIMIARIZAÇÃO MANUAL (COM SLIDER) ---
class ManualThresholdPlugin(AFMPlugin):
    @property
    def name(self): return "Limiarização Manual..."

    @property
    def category(self): return "Segmentação"

    def execute(self, data):
        """
        Abre um diálogo para o usuário escolher o limiar visualmente.
        """
        # Normaliza dados temporariamente para o slider (0 a 1000)
        d_min, d_max = data.min(), data.max()
        
        # Diálogo Personalizado
        dialog = QDialog()
        dialog.setWindowTitle("Ajuste de Limiar")
        dialog.resize(400, 150)
        layout = QVBoxLayout(dialog)

        # Label de valor
        lbl_value = QLabel("Valor de Corte: Calculando...")
        lbl_value.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_value)

        # Slider (0 a 1000 para ter precisão)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 1000)
        
        # Define um valor inicial (média)
        start_val = int(((np.mean(data) - d_min) / (d_max - d_min)) * 1000)
        slider.setValue(start_val)
        layout.addWidget(slider)

        # Variável para guardar o resultado final
        self.final_mask = None

        # Função de atualização (Callback)
        def update_preview(val):
            # Converte 0-1000 de volta para a escala física da imagem (ex: nm)
            real_thresh = d_min + (val / 1000.0) * (d_max - d_min)
            lbl_value.setText(f"Corte Z: {real_thresh:.4f}")

        slider.valueChanged.connect(update_preview)
        update_preview(start_val) # Chama uma vez para setar o texto inicial

        # Botões OK/Cancelar
        btns = QHBoxLayout()
        btn_ok = QPushButton("Aplicar")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dialog.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        # Executa o diálogo (bloqueia a tela até fechar)
        if dialog.exec():
            # Se usuário clicou OK, calcula a máscara final
            val = slider.value()
            real_thresh = d_min + (val / 1000.0) * (d_max - d_min)
            binary_mask = data > real_thresh
            return util.img_as_ubyte(binary_mask)
        else:
            # Se cancelou, retorna None (não faz nada)
            return None


# --- PLUGIN 3: ROTULAÇÃO DE PARTÍCULAS (LABELING) ---
class LabelingPlugin(AFMPlugin):
    @property
    def name(self): return "Rotular Partículas (Labeling)"

    @property
    def category(self): return "Segmentação"

    def execute(self, data):
        """
        Identifica regiões conexas (ilhas) em uma imagem BINÁRIA.
        Se a imagem não for binária, aplica Otsu automaticamente antes.
        """
        # 1. Verifica se precisa binarizar (se tem muitos valores únicos)
        if len(np.unique(data)) > 2:
            print("A imagem não é binária. Aplicando Otsu automático...")
            thresh = filters.threshold_otsu(data)
            binary = data > thresh
        else:
            # Assume que já é binária (0 e 255 ou True/False)
            binary = data > 0

        # 2. Limpeza Morfológica (Opcional mas recomendada para AFM)
        # Remove "poeira" (objetos menores que 2 pixels)
        binary = morphology.remove_small_objects(binary, min_size=2)
        
        # 3. Rotulação (Labeling)
        # connectivity=2 considera diagonais como conexão
        label_image = measure.label(binary, connectivity=2)
        
        num_labels = label_image.max()
        print(f"Segmentação concluída: {num_labels} partículas encontradas.")
        
        # Retorna a matriz de labels. 
        # Nota: O ImageCanvas vai plotar isso com 'afmhot', o que pode ficar estranho.
        # O ideal seria usar um cmap colorido (ex: 'nipy_spectral') para ver as ilhas.
        # Mas como retornamos dados, a MainWindow cuida do plot.
        return label_image
    
# --- PLUGIN 4: ESQUELETIZAÇÃO (SKELETONIZE) ---
class SkeletonizationPlugin(AFMPlugin):
    @property
    def name(self): return "Esqueletização"

    @property
    def category(self): return "Morfologia"

    def execute(self, data):
        """
        Reduz os objetos binários a linhas de 1 pixel de largura.
        Ideal para medir comprimento de DNA/Fibras.
        """
        # 1. Pré-requisito: A imagem PRECISA ser binária (Booleana)
        # Se o usuário tentar rodar direto na topografia (float), aplicamos Otsu primeiro.
        if len(np.unique(data)) > 2:
            print("Aviso: Imagem não binária detectada. Aplicando Otsu antes de esqueletizar...")
            thresh = filters.threshold_otsu(data)
            binary = data > thresh
        else:
            # Se já for binária (0/255 ou 0/1), converte para Booleano puro
            binary = data > 0

        # 2. Aplica a Esqueletização
        # O algoritmo corrói as bordas até sobrar apenas o eixo central
        skeleton = skeletonize(binary)
        
        # 3. Retorna como uint8 (0 e 255) para visualização
        # A MainWindow vai detectar que é binário e usar mapa de cor 'gray'
        return util.img_as_ubyte(skeleton)
    
# --- PLUGIN 5: ABERTURA MORFOLÓGICA (LIMPEZA DE RUÍDO) ---
class MorphologicalOpeningPlugin(AFMPlugin):
    @property
    def name(self): return "Abertura (Limpeza)"
    
    @property
    def category(self): return "Morfologia"

    def execute(self, data):
        """
        Aplica Erosão seguida de Dilatação.
        Remove pequenos pontos brancos (ruído) mantendo o formato das partículas grandes.
        """
        # 1. Garante que a imagem seja Binária
        if len(np.unique(data)) > 2:
            # Se for topografia (float), avisa e aplica Otsu
            print("Aplicando limiarização automática antes da abertura...")
            thresh = filters.threshold_otsu(data)
            binary = data > thresh
        else:
            # Se já for máscara, apenas garante booleano
            binary = data > 0

        # 2. Define o Elemento Estruturante
        # Um disco de raio 1 (matriz 3x3) remove pixels isolados e pequenas arestas.
        # Para ruídos maiores, poderíamos pedir o tamanho ao usuário, mas 1 é o padrão seguro.
        selem = disk(1)

        # 3. Aplica a Abertura
        # footprint=selem é a sintaxe moderna do scikit-image
        cleaned_mask = opening(binary, footprint=selem)
        
        # 4. Retorna como uint8 (0 e 255) para visualização correta (Cinza)
        return util.img_as_ubyte(cleaned_mask)