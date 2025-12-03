import pandas as pd
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, 
                                QTableWidgetItem, QPushButton, QFileDialog, QMessageBox)

class ResultsDialog(QDialog):
    def __init__(self, dataframe, title="Resultados da Análise"):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(800, 600)
        self.df = dataframe # Guarda o DataFrame do Pandas
        
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. Tabela
        self.table = QTableWidget()
        self.populate_table()
        layout.addWidget(self.table)

        # 2. Botão Exportar
        btn_export = QPushButton("Exportar para Excel/CSV")
        btn_export.clicked.connect(self.export_data)
        layout.addWidget(btn_export)

    def populate_table(self):
        """Preenche o QTableWidget com dados do Pandas DataFrame"""
        n_rows, n_cols = self.df.shape
        self.table.setRowCount(n_rows)
        self.table.setColumnCount(n_cols)
        self.table.setHorizontalHeaderLabels(self.df.columns.astype(str))

        for i in range(n_rows):
            for j in range(n_cols):
                # Converte dado para string
                val = self.df.iloc[i, j]
                # Formata floats para ficarem bonitos (4 casas)
                if isinstance(val, float):
                    text = f"{val:.4f}"
                else:
                    text = str(val)
                
                self.table.setItem(i, j, QTableWidgetItem(text))

    def export_data(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Dados", "", "CSV (*.csv);;Excel (*.xlsx)"
        )
        if file_path:
            try:
                if file_path.endswith('.csv'):
                    self.df.to_csv(file_path, index=False)
                elif file_path.endswith('.xlsx'):
                    self.df.to_excel(file_path, index=False)
                
                QMessageBox.information(self, "Sucesso", "Dados exportados com sucesso!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao salvar: {e}")