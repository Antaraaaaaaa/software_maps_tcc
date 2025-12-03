import numpy as np
from scipy import ndimage
from skimage import exposure
from skimage.filters import gaussian
from core.plugin_interface import AFMPlugin

# --- PLUGIN 1: NIVELAMENTO DE PLANO (Plane Fit) ---
class PlaneFitPlugin(AFMPlugin):
    @property
    def name(self):
        return "Nivelamento de Plano (1ª Ordem)"

    @property
    def category(self):
        return "Pré-processamento"

    def execute(self, data):
        """
        Ajusta um plano (z = ax + by + c) aos dados e o subtrai.
        Isso corrige a inclinação física da amostra.
        """
        # Cria grid de coordenadas X, Y
        rows, cols = data.shape
        Y, X = np.indices((rows, cols))
        
        # Achata os arrays para formato de coluna para usar mínimos quadrados
        X_flat = X.flatten()
        Y_flat = Y.flatten()
        Z_flat = data.flatten()
        
        # Monta a matriz A para o sistema A*p = Z
        # Queremos encontrar coeficientes [a, b, c] para Z = aX + bY + c
        A = np.column_stack((X_flat, Y_flat, np.ones_like(Z_flat)))
        
        # Resolve mínimos quadrados (coeficientes do plano)
        coefs, _, _, _ = np.linalg.lstsq(A, Z_flat, rcond=None)
        a, b, c = coefs
        
        # Calcula o plano de fundo estimado
        background_plane = a * X + b * Y + c
        
        # Subtrai o plano da imagem original
        corrected_data = data - background_plane
        
        return corrected_data


# --- PLUGIN 2: CORREÇÃO DE LINHA (Line Flatten) ---
class LineFlattenPlugin(AFMPlugin):
    @property
    def name(self):
        return "Correção de Linhas (Flatten)"
    
    @property
    def category(self):
        return "Pré-processamento"

    def execute(self, data):
        """
        Subtrai a mediana de cada linha.
        Remove artefatos de varredura (riscos horizontais) comuns em AFM.
        """
        # Calcula a mediana de cada linha (eixo 1)
        # keepdims=True mantém o formato (N, 1) para permitir subtração direta (broadcasting)
        row_medians = np.median(data, axis=1, keepdims=True)
        
        # Subtrai
        corrected_data = data - row_medians
        
        return corrected_data


# --- PLUGIN 3: FILTRO DA MEDIANA ---
class MedianFilterPlugin(AFMPlugin):
    @property
    def name(self):
        return "Filtro da Mediana (Ruído)"
    
    @property
    def category(self):
        return "Pré-processamento"

    def execute(self, data):
        """
        Aplica um filtro de mediana 3x3 para remover ruído sem borrar bordas.
        """
        # size=3 significa uma janela 3x3
        filtered_data = ndimage.median_filter(data, size=3)
        
        return filtered_data
    
# --- PLUGIN 4: CLAHE (Realce de Contraste Local) ---
class CLAHEFilterPlugin(AFMPlugin):
    @property
    def name(self):
        return "Realce de Contraste (CLAHE)"
    
    @property
    def category(self):
        return "Pré-processamento"

    def execute(self, data):
        """
        Aplica Equalização de Histograma Adaptativa (CLAHE).
        Ótimo para revelar texturas escondidas em áreas muito claras ou escuras.
        
        Nota: Este filtro altera os valores absolutos de altura (Z) para maximizar
        o contraste visual (0.0 a 1.0).
        """
        # 1. Normalização Robustas (0 a 1)
        # O CLAHE do scikit-image espera floats entre 0 e 1 ou inteiros.
        # Como dados de AFM são floats arbitrários (ex: -50nm a +50nm), normalizamos antes.
        data_min = np.nanmin(data)
        data_max = np.nanmax(data)
        
        if data_max - data_min == 0:
            return data # Imagem constante, não faz nada
            
        # Normaliza para 0-1
        norm_data = (data - data_min) / (data_max - data_min)
        
        # 2. Aplica o CLAHE
        # clip_limit: Limite de contraste (quanto maior, mais contraste e mais ruído). 
        # 0.01 é padrão, 0.02 é um bom balanço para AFM.
        # kernel_size: Tamanho do bloco local. None = calcula automático (1/8 da imagem).
        clahe_data = exposure.equalize_adapthist(norm_data, clip_limit=0.02)
        
        return clahe_data
    
# --- PLUGIN 5: FILTRO GAUSSIANO (SUAVIZAÇÃO) ---
class GaussianFilterPlugin(AFMPlugin):
    @property
    def name(self):
        return "Filtro Gaussiano (Suavização)"
    
    @property
    def category(self):
        return "Pré-processamento"

    def execute(self, data):
        """
        Aplica um filtro Gaussiano para remover ruído de alta frequência (chiado).
        Diferente da Mediana, este filtro é linear e suaviza tudo uniformemente.
        """
        # Sigma controla a intensidade do borramento.
        # sigma=1.0 é um padrão conservador para AFM (remove ruído sem matar estruturas).
        # preserve_range=True é importante para manter os valores de altura (nm).
        return gaussian(data, sigma=1.0, preserve_range=True)