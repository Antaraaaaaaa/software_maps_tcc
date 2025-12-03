import os
import numpy as np
import pandas as pd
from skimage import io, util
from skimage.transform import resize
from PySide6.QtWidgets import QMessageBox, QFileDialog, QProgressDialog
from PySide6.QtCore import Qt
from core.plugin_interface import AFMPlugin
from ui.results_dialog import ResultsDialog

class SegmentationValidationPlugin(AFMPlugin):
    @property
    def name(self):
        return "Validação: Comparar com Ground Truth (IoU, Dice...)"

    @property
    def category(self):
        return "Validação e Testes"

    def execute(self, data):
        """
        Compara imagens de uma pasta de Predição contra uma pasta de Ground Truth (CVAT).
        Gera métricas de classificação pixel a pixel.
        """
        # 1. Seleção de Pastas
        # Pasta A: O que seu software gerou (Predição)
        pred_dir = QFileDialog.getExistingDirectory(
            self.main_window, "Selecione a Pasta das Predições (Seu Software)"
        )
        if not pred_dir: return None

        # Pasta B: O que você fez no CVAT (Ground Truth)
        gt_dir = QFileDialog.getExistingDirectory(
            self.main_window, "Selecione a Pasta do Ground Truth (CVAT/Manual)"
        )
        if not gt_dir: return None

        # 2. Listar e Casar Arquivos
        # Assume-se que os arquivos tenham nomes similares ou iguais
        pred_files = sorted([f for f in os.listdir(pred_dir) if f.endswith(('.png', '.jpg', '.tif', '.bmp'))])
        gt_files = sorted([f for f in os.listdir(gt_dir) if f.endswith(('.png', '.jpg', '.tif', '.bmp'))])

        if not pred_files or not gt_files:
            QMessageBox.warning(self.main_window, "Erro", "Pastas vazias ou sem imagens.")
            return None

        # 3. Preparação
        results = []
        progress = QProgressDialog("Validando Imagens...", "Cancelar", 0, len(pred_files), self.main_window)
        progress.setWindowModality(Qt.WindowModal)

        # 4. Loop de Validação
        matched_count = 0
        
        for p_name in pred_files:
            if progress.wasCanceled(): break
            
            # Tenta achar o arquivo correspondente no Ground Truth
            # Lógica de match: Verifica se o nome do GT está contido no nome da Predição ou vice-versa
            # Ex: "amostra1.png" (GT) e "proc_amostra1.png" (Pred)
            gt_name = next((g for g in gt_files if p_name in g or g in p_name), None)
            
            if gt_name:
                try:
                    # Carrega as imagens
                    path_pred = os.path.join(pred_dir, p_name)
                    path_gt = os.path.join(gt_dir, gt_name)

                    # Lê e força binário (Booleano)
                    # as_gray=True garante que leia 2D.
                    raw_pred = io.imread(path_pred, as_gray=True)
                    raw_gt = io.imread(path_gt, as_gray=True)

                    if raw_pred.shape != raw_gt.shape:
                        # Redimensiona o GT para ficar igual à Predição
                        # order=0: Vizinho Mais Próximo (Mantém 0 e 1 puros, sem criar cinza no meio)
                        # anti_aliasing=False: Crucial para máscaras binárias
                        raw_gt = resize(raw_gt, raw_pred.shape, order=0, preserve_range=True, anti_aliasing=False)

                    # Binariza (Garante True/False)
                    img_pred = raw_pred > 0
                    img_gt = raw_gt > 0
                    
                    # --- CÁLCULO DAS MÉTRICAS ---
                    # Flatten para vetor 1D facilita contas
                    y_pred = img_pred.flatten()
                    y_true = img_gt.flatten()

                    # Matriz de Confusão Pixel a Pixel
                    # TP: True e Predito True
                    tp = np.sum(np.logical_and(y_pred == 1, y_true == 1))
                    # TN: False e Predito False
                    tn = np.sum(np.logical_and(y_pred == 0, y_true == 0))
                    # FP: False mas Predito True (Ruído/Excesso)
                    fp = np.sum(np.logical_and(y_pred == 1, y_true == 0))
                    # FN: True mas Predito False (Perdeu parte do DNA)
                    fn = np.sum(np.logical_and(y_pred == 0, y_true == 1))

                    # Evita divisão por zero
                    smooth = 1e-6

                    # Fórmulas Clássicas
                    precision = tp / (tp + fp + smooth)
                    recall = tp / (tp + fn + smooth)
                    f1 = 2 * (precision * recall) / (precision + recall + smooth)
                    iou = tp / (tp + fp + fn + smooth)
                    dice = 2 * tp / (2 * tp + fp + fn + smooth)

                    results.append({
                        'Arquivo': p_name,
                        'IoU': round(iou, 4),
                        'Dice': round(dice, 4),
                        'Precision': round(precision, 4),
                        'Recall': round(recall, 4),
                        'F1-Score': round(f1, 4),
                        'TP': tp, 'FP': fp, 'FN': fn
                    })
                    
                    matched_count += 1
                    progress.setValue(matched_count)

                except Exception as e:
                    print(f"Erro ao processar {p_name}: {e}")

        progress.setValue(len(pred_files))

        # 5. Exibição dos Resultados
        if results:
            df = pd.DataFrame(results)
            
            # Média Global das Métricas
            means = df.mean(numeric_only=True)
            summary_row = pd.DataFrame([{
                'Arquivo': '--- MÉDIA GLOBAL ---',
                'IoU': round(means['IoU'], 4),
                'Dice': round(means['Dice'], 4),
                'Precision': round(means['Precision'], 4),
                'Recall': round(means['Recall'], 4),
                'F1-Score': round(means['F1-Score'], 4),
                'TP': '-', 'FP': '-', 'FN': '-'
            }])
            
            df_final = pd.concat([df, summary_row], ignore_index=True)

            msg = (f"Validação Concluída!\n"
                    f"Imagens Comparadas: {matched_count}\n\n"
                    f"Média IoU: {means['IoU']:.4f}\n"
                    f"Média Dice: {means['Dice']:.4f}\n"
                    f"Média F1-Score: {means['F1-Score']:.4f}")
            
            QMessageBox.information(self.main_window, "Relatório de Validação", msg)
            
            dialog = ResultsDialog(df_final, title="Métricas de Validação (Ground Truth vs Software)")
            dialog.show()
            self.main_window._val_dialog = dialog
        else:
            QMessageBox.warning(self.main_window, "Aviso", "Nenhuma correspondência de arquivos encontrada entre as pastas.")
            
        return None