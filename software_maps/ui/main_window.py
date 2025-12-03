import os
import numpy as np
from skimage import io, color, util 
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                                QListWidget, QFileDialog, QDockWidget, QMessageBox, QStatusBar)
from PySide6.QtGui import QAction, QActionGroup
from ui.image_canvas import ImageCanvas
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MAPS - Modular AFM Processing Software")
        self.resize(1200, 800)

        # --- DADOS DA APLICAÇÃO ---
        # Esta variável guarda a matriz da imagem atual para os plugins usarem
        self.current_data = None
        self.original_data = None 
        self.current_folder = ""

        # VISUALIZAÇÃO (Novo Padrão: Cinza)
        self.current_cmap = 'gray'

        self.submenus = {} # Guarda referências aos menus criados (ex: "Segmentação" -> QMenu)

        # --- SETUP DA UI ---
        self._setup_ui()
        self._setup_menus()

    def _setup_ui(self):
        """Configura o layout principal: Lista na Esquerda, Gráfico no Centro"""
        
        # 1. Painel Lateral (Lista de Arquivos)
        self.file_list = QListWidget()
        self.file_list.clicked.connect(self.on_file_clicked)
        
        # Usamos um DockWidget para que o painel seja "acoplável" (pode esconder/mostrar)
        self.dock_files = QDockWidget("Navegador de Arquivos", self)
        self.dock_files.setWidget(self.file_list)
        self.dock_files.setAllowedAreas(Qt.AllDockWidgetAreas) # Compatibilidade
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_files) # 0x1 é LeftDockWidgetArea no Qt

        # 2. Área Central (Gráfico)
        self.canvas = ImageCanvas(self)
        self.setCentralWidget(self.canvas)

        # 3. Adiciona explicitamente a barra de status
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Pronto. Carregue uma imagem para começar.")

    def _setup_menus(self):
        main_menu = self.menuBar()

        # Menu Arquivo
        file_menu = main_menu.addMenu("Arquivo")
        
        action_open_file = QAction("Abrir Imagem Única...", self)
        action_open_file.triggered.connect(self.open_single_file)
        file_menu.addAction(action_open_file)

        action_open_folder = QAction("Abrir Pasta...", self)
        action_open_folder.triggered.connect(self.open_folder)
        file_menu.addAction(action_open_folder)

        # --- SALVAR ---
        file_menu.addSeparator()
        action_save = QAction("Salvar Imagem Atual Como...", self)
        action_save.setShortcut("Ctrl+S")  # Atalho de teclado padrão
        action_save.triggered.connect(self.save_current_image)
        file_menu.addAction(action_save)

        action_close = QAction("Fechar Imagem/Pasta", self)
        action_close.triggered.connect(self.close_current_image)
        file_menu.addAction(action_close)

        file_menu.addSeparator()
        
        action_exit = QAction("Sair", self)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        # --- MENU: EDITAR ---
        edit_menu = main_menu.addMenu("Editar")
        
        self.action_restore = QAction("Restaurar Imagem Original", self)
        self.action_restore.setShortcut("Ctrl+R") # Atalho prático
        self.action_restore.setStatusTip("Descarta todas as alterações e volta para a imagem bruta")
        self.action_restore.triggered.connect(self.restore_original_image)

        self.action_restore.setEnabled(False)  # Desabilita inicialmente
        edit_menu.addAction(self.action_restore)

        # --- MENU: EXIBIR ---
        view_menu = main_menu.addMenu("Exibir")

        # Grupo de Ações (Mutuamente Exclusivas)
        self.view_group = QActionGroup(self)

        # Opção 1: Apenas Processada (Padrão)
        self.action_view_processed = QAction("Apenas Processada", self, checkable=True)
        self.action_view_processed.setChecked(True) # Começa marcada
        self.action_view_processed.triggered.connect(self.update_view)
        self.view_group.addAction(self.action_view_processed)
        view_menu.addAction(self.action_view_processed)

        # Opção 2: Apenas Original
        self.action_view_original = QAction("Apenas Original", self, checkable=True)
        self.action_view_original.triggered.connect(self.update_view)
        self.view_group.addAction(self.action_view_original)
        view_menu.addAction(self.action_view_original)

        # Opção 3: Lado a Lado
        self.action_view_side_by_side = QAction("Lado a Lado (Comparação)", self, checkable=True)
        self.action_view_side_by_side.triggered.connect(self.update_view)
        self.view_group.addAction(self.action_view_side_by_side)
        view_menu.addAction(self.action_view_side_by_side)

        view_menu.addSeparator()

        # --- SUBMENU: MAPA DE CORES ---
        cmap_menu = view_menu.addMenu("Mapa de Cores")
        self.cmap_group = QActionGroup(self)

        # Opção 1: Escala de Cinza (Padrão)
        action_gray = QAction("Escala de Cinza (Padrão)", self, checkable=True)
        action_gray.setChecked(True)
        action_gray.triggered.connect(lambda: self.set_colormap('gray'))
        self.cmap_group.addAction(action_gray)
        cmap_menu.addAction(action_gray)

        # Opção 2: AFM Hot (Térmico)
        action_afm = QAction("AFM Hot (Térmico)", self, checkable=True)
        action_afm.triggered.connect(lambda: self.set_colormap('afmhot'))
        self.cmap_group.addAction(action_afm)
        cmap_menu.addAction(action_afm)

        # Opção 3: Viridis (Científico Moderno)
        action_viridis = QAction("Viridis (Contraste Alto)", self, checkable=True)
        action_viridis.triggered.connect(lambda: self.set_colormap('viridis'))
        self.cmap_group.addAction(action_viridis)
        cmap_menu.addAction(action_viridis)
        
        # Opção 4: Plasma (Alto Contraste)
        action_plasma = QAction("Plasma", self, checkable=True)
        action_plasma.triggered.connect(lambda: self.set_colormap('plasma'))
        self.cmap_group.addAction(action_plasma)
        cmap_menu.addAction(action_plasma)

        # --- SPECTRAL (Para Segmentação) ---
        # nipy_spectral é excelente para separar classes discretas (labels)
        self.action_spectral = QAction("Spectral (Segmentação)", self, checkable=True)
        self.action_spectral.triggered.connect(lambda: self.set_colormap('nipy_spectral'))
        self.cmap_group.addAction(self.action_spectral)
        cmap_menu.addAction(self.action_spectral)
        # -----------------------------------

        view_menu.addSeparator()

        # 2. Opção para Mostrar/Esconder o Painel de Arquivos (lateral)
        # O toggleViewAction() cria uma ação automática que:
        # - Mostra o nome do dock ("Navegador de Arquivos")
        # - Fica com um 'check' se ele estiver visível
        # - Mostra/Esconde o dock quando clicada
        view_menu.addAction(self.dock_files.toggleViewAction())

        # --- MENU: FERRAMENTAS ---
        tools_menu = main_menu.addMenu("Ferramentas")

        # Opção de Modo em Lote (Checkable)
        self.action_batch_mode = QAction("Ativar Processamento em Lote", self, checkable=True)
        self.action_batch_mode.setStatusTip("Se marcado, aplica o plugin em todas as imagens da pasta atual")

        # Começa desabilitado (cinza) porque não tem pasta aberta
        self.action_batch_mode.setEnabled(False)

        tools_menu.addAction(self.action_batch_mode)

        # Menu Plugins (vazio, será populado pelo PluginManager)
        self.plugins_menu = main_menu.addMenu("Plugins")

    # --- LÓGICA DE ARQUIVOS ---

    def open_single_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Abrir Imagem", "", "Imagens (*.png *.jpg *.tif *.bmp)")
        if file_name:
            # 1. Limpa o contexto de pasta anterior (se houver)
            self.current_folder = "" 
            self.file_list.clear()
            
            # 2. Bloqueia o Modo Batch (Regra de Negócio)
            self.action_batch_mode.setChecked(False) # Desmarca
            self.action_batch_mode.setEnabled(False) # Desabilita visualmente

            # 3. Processa a imagem selecionada
            self.process_image(file_name)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if folder:
            self.current_folder = folder
            self.populate_file_list()

            # Libera o Modo Batch, pois agora temos uma pasta
            self.action_batch_mode.setEnabled(True) 
            # Opcional: Resetar para False ao trocar de pasta para evitar acidentes
            self.action_batch_mode.setChecked(False)

    def populate_file_list(self):
        """Lê a pasta e adiciona arquivos de imagem na lista lateral"""
        self.file_list.clear()
        valid_extensions = ('.png', '.jpg', '.jpeg', '.tif', '.bmp')
        
        try:
            files = sorted([f for f in os.listdir(self.current_folder) 
                            if f.lower().endswith(valid_extensions)])
            
            for f in files:
                self.file_list.addItem(f)
                
            if not files:
                QMessageBox.warning(self, "Aviso", "Nenhuma imagem encontrada nesta pasta.")
                
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao ler pasta: {e}")

    def save_current_image(self):
        """Salva a imagem processada atual em disco"""
        if self.current_data is None:
            QMessageBox.warning(self, "Aviso", "Não há imagem para salvar.")
            return

        # 1. Abre diálogo para escolher onde salvar
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Salvar Imagem", 
            "", 
            "PNG (*.png);;JPEG (*.jpg);;TIFF (*.tif)"
        )

        if file_path:
            try:
                # 2. Normalização (Float -> Uint8)
                # Necessário porque dados de AFM podem ser negativos ou floats pequenos
                data = np.nan_to_num(self.current_data)
                d_min, d_max = data.min(), data.max()
                
                if d_max - d_min == 0:
                    norm_data = data.astype(np.uint8)
                else:
                    # Normaliza para 0.0 - 1.0 e converte para 0 - 255
                    norm_data = (data - d_min) / (d_max - d_min)
                    norm_data = util.img_as_ubyte(norm_data)

                # 3. Salva
                io.imsave(file_path, norm_data, check_contrast=False)
                QMessageBox.information(self, "Sucesso", f"Imagem salva em:\n{file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Erro ao Salvar", str(e))

    # Novo método para trocar a cor
    def set_colormap(self, cmap_name):
        self.current_cmap = cmap_name
        self.update_view()  # Força o redesenho imediato

    def restore_original_image(self):
        """Descarta alterações e volta para o estado inicial da imagem carregada"""
        if self.original_data is None:
            return

        reply = QMessageBox.question(
            self, 
            "Confirmar Restauração", 
            "Tem certeza que deseja descartar todas as alterações?\nIsso voltará para a imagem bruta.",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 1. Recria a matriz de trabalho a partir do backup (original_data)
                # Precisamos converter de novo porque o original pode ser RGB (visual),
                # mas o current_data precisa ser float/gray (científico).
                if self.original_data.ndim == 3:
                    # Se o original for RGB, converte para cinza
                    work_img = color.rgb2gray(self.original_data)
                else:
                    work_img = self.original_data

                # 2. Garante Float (física)
                self.current_data = util.img_as_float(work_img)

                # 3. Reseta visualização para o padrão (Cinza ou a cor atual)
                # Opcional: Se quiser forçar cinza ao resetar, descomente a linha abaixo:
                self.set_colormap('gray') 
                
                # Se estiver marcado "Spectral" (segmentação), desmarca, pois voltamos para topografia
                if hasattr(self, 'action_spectral'):
                    self.action_spectral.setChecked(False)

                self.update_view()
                self.statusBar().showMessage("Imagem restaurada para o original.", 3000)

            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao restaurar imagem: {e}")

    def on_file_clicked(self):
        """Chamado quando o usuário clica em um item da lista"""
        if not self.current_folder:
            return
            
        item = self.file_list.currentItem()
        if item:
            full_path = os.path.join(self.current_folder, item.text())
            self.process_image(full_path)

    def process_image(self, file_path):
        """Lê a imagem, converte para escala de cinza e plota"""
        try:
            # 1. Lê a imagem usando scikit-image
            raw_image = io.imread(file_path)

            # 2. Guarda o original (para visualização)
            # Se for RGBA (tem transparência), converte para RGB para não quebrar o plot
            if raw_image.ndim == 3 and raw_image.shape[2] == 4:
                self.original_data = color.rgba2rgb(raw_image)
            else:
                self.original_data = raw_image

            # 3. Garante que é escala de cinza (2D)
            # Se tiver 3 dimensões (RGB), converte. Se tiver 4 (RGBA), descarta Alpha e converte.
            if raw_image.ndim == 3:
                if raw_image.shape[2] == 4: # RGBA
                    raw_image = color.rgba2rgb(raw_image)
                image_gray = color.rgb2gray(raw_image)
            else:
                image_gray = raw_image

            # 4. Normaliza ou mantém os dados (depende do formato)
            self.current_data = util.img_as_float(image_gray)

            # Habilita o botão de restaurar
            self.action_restore.setEnabled(True)
            
            if self.original_data is not None:
                # Apenas para visualização consistente
                pass

            # 5. Atualiza a tela (respeitando a escolha do usuário no menu)
            self.update_view()
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar a imagem:\n{e}")

    def update_view(self):
        """Decide qual modo de visualização usar com base no menu selecionado"""
        if self.current_data is None:
            return

        # 1. Modo Lado a Lado
        if self.action_view_side_by_side.isChecked():
            # Se a imagem original não existir (ex: carregou direto um numpy array), usa a current como original
            orig = self.original_data if self.original_data is not None else self.current_data

            self.canvas.plot_comparison(orig, self.current_data, cmap_processed=self.current_cmap)

        # 2. Modo Apenas Original
        elif self.action_view_original.isChecked():
            if self.original_data is not None:
                # cmap='gray' funciona se for 2D, se for RGB o matplotlib ignora
                self.canvas.plot_image(self.original_data, cmap='gray', title="Imagem Original")
            else:
                # Fallback se não tiver original salvo
                self.canvas.plot_image(self.current_data, title="Original não disponível")

        # 3. Modo Processada (Padrão)
        else:
            self.canvas.plot_image(self.current_data, cmap=self.current_cmap, title="Topografia (Processada)")

    def close_current_image(self):
        """Reseta a aplicação para o estado inicial (vazio)"""
        
        # 1. Limpa os dados da memória
        self.current_data = None
        self.original_data = None
        self.current_folder = ""

        # 2. Limpa a interface lateral
        self.file_list.clear()

        # 3. Reseta o gráfico para a mensagem de texto
        self.canvas.show_empty_message()

        # Desabilita o botão de restaurar
        self.action_restore.setEnabled(False)

        # 4. Reseta e Bloqueia o Modo Batch
        self.action_batch_mode.setChecked(False)
        self.action_batch_mode.setEnabled(False)

        # 5. (Opcional) Feedback visual na barra de status
        self.statusBar().showMessage("Área de trabalho limpa.", 3000)

    def change_working_directory(self, new_folder):
        """
        Muda a pasta ativa programaticamente (usado pelo modo Batch).
        Limpa a imagem atual, mas carrega a lista de arquivos da nova pasta.
        """
        # 1. Reseta a visualização central (limpa dados antigos)
        self.current_data = None
        self.original_data = None
        self.canvas.show_empty_message()

        # 2. Atualiza o caminho da pasta
        self.current_folder = new_folder

        # 3. Atualiza a lista lateral
        self.populate_file_list()

        # 4. Feedback visual
        self.statusBar().showMessage(f"Diretório alterado para: {new_folder}", 5000)

    # Adicione este método auxiliar para o PluginManager consultar
    def is_batch_mode(self):
        return self.action_batch_mode.isChecked()

    # --- INTERFACE PARA PLUGINS ---
    
    def add_plugin_action(self, plugin_name, callback, category="Geral"):
        """Adiciona o plugin ao menu correto (criando submenus se necessário)"""
        
        # 1. Define onde adicionar (Raiz ou Submenu)
        target_menu = self.plugins_menu
        
        if category:
            # Se o submenu ainda não existe, cria
            if category not in self.submenus:
                self.submenus[category] = target_menu.addMenu(category)
            
            # Define o alvo como o submenu
            target_menu = self.submenus[category]

        # 2. Cria e adiciona a ação
        action = QAction(plugin_name, self)
        action.triggered.connect(callback)
        target_menu.addAction(action)

    def update_image_data(self, new_data):
        """Método chamado pelos plugins para atualizar a imagem na tela"""
        if new_data is not None:
            # 1. Atualiza a "memória" da imagem processadaclear
            self.current_data = new_data

            # 1. Verifica se é INTEIRO (Candidato a Segmentação)
            if np.issubdtype(new_data.dtype, np.integer) or new_data.dtype == bool:
                
                unique_vals = len(np.unique(new_data))

                # Caso A: Binário (0 e 1/255) -> Cinza
                if unique_vals <= 2:
                    self.set_colormap('gray')
                    if hasattr(self, 'action_spectral'): self.action_spectral.setChecked(False)
                    self.statusBar().showMessage("Máscara Binária detectada.", 4000)

                # Caso B: Mapa de Rótulos (Labeling) -> Spectral
                else: 
                    self.set_colormap('nipy_spectral')
                    if hasattr(self, 'action_spectral'): self.action_spectral.setChecked(True)
                    self.statusBar().showMessage(f"Segmentação detectada: {unique_vals} objetos (Spectral).", 4000)

            # 2. Se for FLOAT (Topografia real) -> Mantém cor do usuário
            else:
                self.statusBar().showMessage("Imagem processada atualizada.", 3000)
            
            self.update_view()