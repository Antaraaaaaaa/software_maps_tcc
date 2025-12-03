import numpy as np
import pandas as pd
from skimage import measure
from PySide6.QtWidgets import QMessageBox, QInputDialog
from core.plugin_interface import AFMPlugin
from ui.results_dialog import ResultsDialog

# --- PLUGIN 1: RUGOSIDADE GLOBAL ---
class GlobalRoughnessPlugin(AFMPlugin):
    @property
    def name(self):
        return "Rugosidade Global (Ra, Rq)"
    
    @property
    def category(self): return "Análise Quantitativa"

    def execute(self, data):
        """Calcula métricas estatísticas de toda a superfície"""
        # Verifica se é dado numérico (Topografia)
        if np.issubdtype(data.dtype, np.integer) and len(np.unique(data)) > 2:
            QMessageBox.warning(None, "Aviso", "Parece que você está tentando medir rugosidade em uma imagem de labels (segmentada).\nUse a imagem de topografia (Original ou Nivelada).")
            return None

        # Remove NaNs se houver
        clean_data = data[~np.isnan(data)]
        
        # Cálculos Físicos
        mean_height = np.mean(clean_data)
        
        # Ra (Roughness Average): Média aritmética dos desvios absolutos
        ra = np.mean(np.abs(clean_data - mean_height))
        
        # Rq (Root Mean Square): Desvio padrão das alturas
        rq = np.std(clean_data)
        
        # Peak-to-Valley
        rt = np.max(clean_data) - np.min(clean_data)

        # Mostra Resultado
        msg = (f"=== Parâmetros de Rugosidade ===\n\n"
                f"Ra (Média Aritmética): {ra:.4f} (u.a.)\n"
                f"Rq (RMS/Desvio Padrão): {rq:.4f} (u.a.)\n"
                f"Rt (Pico-Vale): {rt:.4f} (u.a.)\n\n"
                f"Nota: 'u.a.' = unidades da imagem (ex: nm ou µm)")
        
        QMessageBox.information(self.main_window, "Rugosidade", msg)
        return None # Não altera a imagem


# --- PLUGIN 2: TABELA DE PARTÍCULAS ---
class ParticleAnalysisPlugin(AFMPlugin):
    @property
    def name(self):
        return "Tabela de Partículas (Área, Altura...)"
    
    @property
    def category(self): return "Análise Quantitativa"

    def execute(self, data):
        """
        Gera tabela de métricas para cada partícula identificada.
        Requer uma imagem de Labels (Inteiros) como entrada.
        """
        # 1. Validação: O dado atual TEM que ser Labels (Inteiro)
        is_labels = np.issubdtype(data.dtype, np.integer) and len(np.unique(data)) > 2
        
        if not is_labels:
            QMessageBox.warning(self.main_window, "Erro de Fluxo", 
                                "Para analisar partículas, a imagem atual deve ser um Mapa de Rótulos (Colorido).\n\n"
                                "Passo a passo:\n"
                                "1. Carregue a Topografia\n"
                                "2. Aplique Segmentação -> Labeling\n"
                                "3. Execute este plugin novamente.")
            return None

        # 2. Tenta pegar a imagem de intensidade original (Topografia)
        # Acessamos via a injeção que fizemos no PluginManager
        intensity_image = None
        if self.main_window.original_data is not None:
            # Se original for RGB, converte pra cinza pra medir altura
            if self.main_window.original_data.ndim == 3:
                from skimage.color import rgb2gray
                intensity_image = rgb2gray(self.main_window.original_data)
            else:
                intensity_image = self.main_window.original_data
        
        # Se não tiver original (o usuário carregou direto o label?), usamos apenas geometria
        
        # 3. Extração de Métricas usando Scikit-Image
        properties = ['label', 'area', 'equivalent_diameter_area', 'eccentricity']
        
        if intensity_image is not None:
            # Se temos topografia, podemos medir altura máxima e média da partícula
            if intensity_image.shape == data.shape:
                properties.extend(['max_intensity', 'mean_intensity'])
            else:
                print("Aviso: Tamanho da imagem original difere da máscara. Ignorando alturas.")

        # Calcula!
        try:
            props = measure.regionprops_table(
                label_image=data,
                intensity_image=intensity_image,
                properties=properties
            )
        except Exception as e:
            QMessageBox.critical(self.main_window, "Erro no Cálculo", str(e))
            return None

        # 4. Cria DataFrame Pandas e renomeia colunas para português
        df = pd.DataFrame(props)
        
        rename_map = {
            'label': 'ID',
            'area': 'Área (pixels)',
            'equivalent_diameter_area': 'Diâmetro (px)',
            'eccentricity': 'Excentricidade',
            'max_intensity': 'Altura Máx (Z)',
            'mean_intensity': 'Altura Média (Z)'
        }
        df.rename(columns=rename_map, inplace=True)

        # 5. Mostra a Tabela
        dialog = ResultsDialog(df, title="Métricas de Partículas")
        dialog.exec() # Bloqueia até fechar
        
        return None # Não altera a imagem
    
# --- PLUGIN 3: ANÁLISE DE COMPRIMENTO DE DNA (Esqueleto) ---
class DNALengthPlugin(AFMPlugin):
    @property
    def name(self):
        return "Comprimento de Fitas (DNA/Polímeros)"
    
    @property
    def category(self): return "Análise Quantitativa"

    def execute(self, data):
        """
        Calcula o comprimento de fitas baseando-se em uma imagem ESQUELETIZADA.
        Pede ao usuário o tamanho da varredura para converter pixels em nanômetros.
        """
        # 1. Validação: O dado deve ser uma Máscara Binária ou Inteira
        # (O esqueleto é composto de 0s e 1s/255s)
        unique_vals = len(np.unique(data))
        if unique_vals > 2:
            QMessageBox.warning(self.main_window, "Erro de Fluxo", 
                                "Este plugin requer uma imagem de ESQUELETO (Binária).\n\n"
                                "Passo a passo recomendado:\n"
                                "1. Segmentação -> Limiarização\n"
                                "2. Morfologia -> Esqueletização\n"
                                "3. Execute este plugin novamente.")
            return None

        # 2. Pergunta o tamanho físico da imagem (Calibração)
        # Imagens de AFM geralmente são quadradas (ex: 1um x 1um, 5um x 5um)
        scan_size_um, ok = QInputDialog.getDouble(
            self.main_window, 
            "Calibração Física", 
            "Qual o tamanho da varredura (Scan Size) em micrômetros (µm)?", 
            value=1.0, minValue=0.1, maxValue=100.0, decimals=2
        )
        
        if not ok:
            return None

        # 3. Calcula a resolução (nm por pixel)
        # Ex: 1 um = 1000 nm. Se a imagem tem 512 px, pixel_size = 1000/512 nm
        img_width_px = data.shape[1]
        pixel_size_nm = (scan_size_um * 1000.0) / img_width_px

        # 4. Identifica as fitas individuais (Labeling interno)
        # O dado é binário, precisamos rotular cada fita separadamente
        label_image = measure.label(data > 0)
        num_strands = label_image.max()

        if num_strands == 0:
            QMessageBox.warning(self.main_window, "Aviso", "Nenhuma fita encontrada.")
            return None

        # 5. Extrai propriedades
        props = measure.regionprops(label_image)
        
        results = []
        lengths_nm = []

        for prop in props:
            # Em um esqueleto, a área (contagem de pixels) é aprox. o comprimento
            # Correção estatística para diagonais: pixels diagonais valem sqrt(2). 
            # Para simplificar, usamos contagem direta ou fator 1.12 (comum em polímeros)
            # Aqui usaremos Contagem Direta * Tamanho do Pixel
            
            len_px = prop.area
            len_nm = len_px * pixel_size_nm
            
            lengths_nm.append(len_nm)
            
            results.append({
                'ID': prop.label,
                'Comprimento (px)': len_px,
                'Comprimento (nm)': round(len_nm, 2)
            })

        # 6. Estatísticas Globais
        avg_len = np.mean(lengths_nm)
        std_len = np.std(lengths_nm)
        min_len = np.min(lengths_nm)
        max_len = np.max(lengths_nm)

        # 7. Mostra Tabela Detalhada
        df = pd.DataFrame(results)
        dialog = ResultsDialog(df, title=f"Comprimento de DNA (N={num_strands})")
        dialog.show() # Usa show() para não bloquear o popup de resumo abaixo

        # 8. Popup de Resumo Estatístico
        summary_msg = (
            f"=== Resumo da Amostra ===\n"
            f"Total de Fitas: {num_strands}\n\n"
            f"Comprimento Médio: {avg_len:.2f} nm\n"
            f"Desvio Padrão: {std_len:.2f} nm\n"
            f"Mínimo: {min_len:.2f} nm\n"
            f"Máximo: {max_len:.2f} nm\n\n"
            f"Calibração usada: 1 pixel = {pixel_size_nm:.2f} nm"
        )
        QMessageBox.information(self.main_window, "Estatística de DNA", summary_msg)
        
        # Precisamos manter a referência do dialog para ele não fechar sozinho (garbage collection)
        self.main_window._results_dialog = dialog 
        
        return None