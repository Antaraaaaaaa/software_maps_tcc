import numpy as np
import pandas as pd
from scipy import ndimage
from skimage import filters, morphology, exposure, measure, util
from PySide6.QtWidgets import QMessageBox, QInputDialog
from core.plugin_interface import AFMPlugin
from ui.results_dialog import ResultsDialog

class DnaFullRoutinePlugin(AFMPlugin):
    def __init__(self):
        # Variáveis para controle do modo em lote
        self.is_batch = False
        self.batch_scan_size = None

    @property
    def name(self):
        return "Rotina: Pipeline Completo DNA (1-Click)"
    
    @property
    def category(self): return "Rotinas Automáticas"
    
    def setup_batch(self, parent_window):
        """
        Método opcional: Chamado pelo Gerenciador ANTES de iniciar o loop de lote.
        Serve para pedir parâmetros uma única vez.
        """
        scan_size_um, ok = QInputDialog.getDouble(
            parent_window, 
            "Configuração de Lote", 
            "Tamanho da Varredura (Scan Size) para TODAS as imagens (µm):", 
            value=2.0, minValue=0.1, maxValue=100.0, decimals=2
        )
        
        if ok:
            self.is_batch = True
            self.batch_scan_size = scan_size_um
            return True # Sucesso
        return False # Cancelou
    
    def teardown_batch(self):
        """Chamado ao final do lote para limpar estado"""
        self.is_batch = False
        self.batch_scan_size = None

    def execute(self, data):
        """
        Executa a sequência:
        1. Filtro da Mediana (Ruído)
        2. CLAHE (Realce de Contraste)
        3. Otsu (Binarização)
        4. Abertura (Limpeza)
        5. Esqueletização (Redução a linhas)
        6. Cálculo de Comprimento (Análise)
        """
        # 1. Configuração de Parâmetros
        if self.is_batch:
            # Modo Lote: Usa o valor configurado no setup
            scan_size_um = self.batch_scan_size
        else:
            # Modo Single: Pergunta agora (Validação inicial igual antes)
            # --- 0. VALIDAÇÃO INICIAL ---
            # O dado precisa ser Topografia (Float). Se for binário, não faz sentido rodar filtros.
            if np.issubdtype(data.dtype, np.integer) and len(np.unique(data)) <= 2:
                QMessageBox.warning(self.main_window, "Aviso", "A imagem parece já estar binarizada/segmentada.\nEsta rotina precisa da imagem de topografia original.")
                return None

            # --- 1. INPUT DO USUÁRIO (Única interação necessária) ---
            # Perguntamos o tamanho físico logo no começo para não interromper o cálculo depois
            scan_size_um, ok = QInputDialog.getDouble(
                self.main_window, 
                "Configuração da Rotina", 
                "Para calcular o comprimento, informe o Tamanho da Varredura (Scan Size) em µm:", 
                value=2.0, minValue=0.1, maxValue=100.0, decimals=2
            )
            if not ok: return None

            # Feedback na barra de status
            self.main_window.statusBar().showMessage("Executando Pipeline de DNA... Aguarde...", 0)

        try:
            # --- 2. FILTRAGEM (MEDIANA) ---
            # Remove ruído impulsivo (poeira)
            denoised = ndimage.median_filter(data, size=3)

            # --- 3. REALCE (CLAHE) ---
            # Normaliza para 0-1 para o CLAHE funcionar
            d_min, d_max = denoised.min(), denoised.max()
            norm_data = (denoised - d_min) / (d_max - d_min) if (d_max - d_min) > 0 else denoised
            
            enhanced = exposure.equalize_adapthist(norm_data, clip_limit=0.02)

            # --- 4. SEGMENTAÇÃO (OTSU) ---
            thresh = filters.threshold_otsu(enhanced)
            binary = enhanced > thresh

            # --- 5. MORFOLOGIA (ABERTURA) ---
            # Remove ruídos pequenos que sobraram após o Otsu
            selem = morphology.disk(1)
            cleaned = morphology.opening(binary, footprint=selem)

            # --- 6. ESQUELETIZAÇÃO ---
            skeleton = morphology.skeletonize(cleaned)

            # --- 7. EXTRAÇÃO DE MÉTRICAS (COMPRIMENTO) ---
            # Calcula resolução (nm/pixel)
            img_width_px = data.shape[1]
            pixel_size_nm = (scan_size_um * 1000.0) / img_width_px

            # Labeling nas fitas
            label_image = measure.label(skeleton)
            props = measure.regionprops(label_image)
            
            results = []
            for prop in props:
                len_nm = prop.area * pixel_size_nm
                results.append({
                    'ID': prop.label,
                    'Comprimento (nm)': round(len_nm, 2),
                    'Pixels': prop.area
                })

            # --- 8. APRESENTAÇÃO DOS RESULTADOS ---

            # Prepara o DataFrame
            df = pd.DataFrame(results) if results else pd.DataFrame()
            skeleton_img = util.img_as_ubyte(skeleton)

            # --- SAÍDA (DIFERENCIADA PARA LOTE VS SINGLE) ---
            
            if self.is_batch:
                # Em lote: Não mostra janelas, apenas RETORNA (Imagem, DataFrame)
                return (skeleton_img, df)
            
            else:
                # Em Single: Mostra GUI (Janelas e Popups)
                if not df.empty:

                    # Cálculos Estatísticos
                    avg_len = df['Comprimento (nm)'].mean()
                    std_len = df['Comprimento (nm)'].std()
                    count = len(df)
                    
                    # A) Adiciona linhas de resumo ao final do DataFrame (Tabela)
                    summary_rows = pd.DataFrame([
                        {'ID': '---', 'Comprimento (nm)': '', 'Pixels': ''}, # Linha vazia separadora
                        {'ID': 'MÉDIA', 'Comprimento (nm)': round(avg_len, 2), 'Pixels': '-'},
                        {'ID': 'DESVIO PADRÃO', 'Comprimento (nm)': round(std_len, 2), 'Pixels': '-'}
                    ])
                    df_show = pd.concat([df, summary_rows], ignore_index=True)

                    # B) Mostra Pop-up com a Média (Pedido do usuário)
                    msg_stats = (
                        f"Análise Concluída com Sucesso!\n\n"
                        f"Total de Fitas Medidas: {count}\n"
                        f"Comprimento Médio: {avg_len:.2f} nm\n"
                        f"Desvio Padrão: +/- {std_len:.2f} nm"
                    )
                    QMessageBox.information(self.main_window, "Resultado Estatístico", msg_stats)
                    
                    # C) Abre a janela de resultados com a tabela completa
                    dialog = ResultsDialog(df_show, title=f"Dados DNA (N={count})")
                    dialog.show()
                    self.main_window._pipeline_dialog = dialog

                    self.main_window.statusBar().showMessage(f"Média: {avg_len:.1f} nm.", 5000)

                # No modo single, mantemos o retorno antigo (apenas imagem para o canvas)
                return (skeleton_img, df)

        except Exception as e:
            if not self.is_batch:
                QMessageBox.critical(self.main_window, "Erro", f"Falha: {e}")
            else:
                print(f"Erro no lote: {e}") # Log para o console
                raise e # Relança para o Manager capturar
            return None