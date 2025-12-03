import os
import numpy as np
import pandas as pd
from skimage import io, util
import importlib.util
import inspect
import sys
from core.plugin_interface import AFMPlugin
from PySide6.QtWidgets import QMessageBox, QFileDialog, QProgressDialog
from PySide6.QtCore import Qt

class PluginManager:
    def __init__(self, main_window):
        """
        O Gerenciador precisa de uma referência à Janela Principal (main_window)
        para poder adicionar menus e passar os dados da imagem para os plugins.
        """
        self.main_window = main_window
        self.loaded_plugins = []

    def discover_and_load_plugins(self, plugins_dir):
        """
        Varre o diretório 'plugins', carrega cada arquivo .py e tenta encontrar
        classes que herdam de AFMPlugin.
        """
        if not os.path.isdir(plugins_dir):
            print(f"Diretório de plugins não encontrado: {plugins_dir}")
            return

        # Adiciona o diretório de plugins ao PATH do sistema para facilitar importações relativas
        sys.path.append(plugins_dir)

        for filename in os.listdir(plugins_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                self._load_plugin_file(plugins_dir, filename)

    def _load_plugin_file(self, plugin_dir, filename):
        module_name = filename[:-3]  # Remove o .py
        file_path = os.path.join(plugin_dir, filename)

        try:
            # 1. Cria a especificação do módulo (Metadados)
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            
            # 2. Cria o módulo a partir da especificação
            module = importlib.util.module_from_spec(spec)
            
            # 3. Executa o módulo (carrega o código na memória)
            spec.loader.exec_module(module)

            # 4. Procura por classes válidas dentro do módulo
            self._register_plugin_classes(module)

        except Exception as e:
            print(f"Erro ao carregar o plugin {filename}: {e}")

    def _register_plugin_classes(self, module):
        """
        Inspeciona o módulo em busca de classes que sejam filhas de AFMPlugin.
        """
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, AFMPlugin) and obj is not AFMPlugin:
                # Instancia a classe do plugin
                plugin_instance = obj()

                # --- INJEÇÃO DE DEPENDÊNCIA ---
                # Injetamos a main_window no plugin para ele acessar dados globais se precisar
                plugin_instance.main_window = self.main_window

                self.loaded_plugins.append(plugin_instance)
                
                print(f"Plugin Carregado: {plugin_instance.name}")

                # Adiciona ao menu da interface
                # Usamos lambda para capturar a instância correta no loop
                self.main_window.add_plugin_action(
                    plugin_instance.name, 
                    lambda checked, p=plugin_instance: self.run_plugin(p),
                    category=plugin_instance.category
                )

    # Substitua o método run_plugin por este:
    def run_plugin(self, plugin):
        """
        Executa o plugin. Decide se é na imagem atual ou na pasta toda.
        """
        # Verifica se é Modo em Lote
        if self.main_window.is_batch_mode():
            self._run_batch(plugin)
        else:
            self._run_single(plugin)
    
    def _run_single(self, plugin):
        """ 
        Execução isolada em uma única imagem
        
        Executa o plugin passando os dados atuais.
        Se o plugin retornar dados modificados, atualiza a interface.
        """

        # Pega os dados atuais da janela principal
        data = getattr(self.main_window, 'current_data', None)
        
        # Se não tiver imagem, avisa (exceto se o plugin não precisar de dados)
        if data is None:
            QMessageBox.warning(self.main_window, "Atenção", "Nenhuma imagem carregada.")
            print("Aviso: Nenhum dado carregado para processar.")
            return

        try:
            # Executa o plugin e captura o retorno
            result = plugin.execute(data)

            image_result = result

            # Se retornou tupla (img, df), pegamos só a imagem para mostrar na tela
            # (O plugin Single já mostrou a tabela na GUI dele)
            if isinstance(result, tuple):
                image_result = result[0]

            if image_result is not None:
                self.main_window.update_image_data(image_result)
                print(f"Plugin '{plugin.name}' aplicado.")

                # --- NOVO: Feedback Visual ---
                #QMessageBox.information(
                #    self.main_window,
                #    "Processamento Concluído",
                #    f"O método '{plugin.name}' foi aplicado com sucesso!\n\nA visualização foi atualizada."
                #)

        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Erro no Plugin",
                f"Ocorreu um erro ao executar '{plugin.name}':\n{str(e)}"
            )
            print(f"Erro detalhado: {e}")

    def _run_batch(self, plugin):
        """Execução em Lote (Batch Processing)"""
        current_folder = self.main_window.current_folder
        
        # 1. Validações
        if not current_folder:
            QMessageBox.warning(self.main_window, "Atenção", "Nenhuma pasta aberta para processar em lote.")
            return
        
        # 1.1. Configuração Prévia (SETUP)
        # Se o plugin tiver o método setup_batch, chama ele antes de começar
        if hasattr(plugin, 'setup_batch'):
            ok = plugin.setup_batch(self.main_window)
            if not ok: return # Cancelou no input

        # 2. Pede pasta de destino para não sobrescrever os originais
        output_dir = QFileDialog.getExistingDirectory(self.main_window, "Selecione a Pasta de Destino para Salvar")
        if not output_dir:
            if hasattr(plugin, 'teardown_batch'): plugin.teardown_batch()
            return

        # 3. Lista arquivos
        valid_extensions = ('.png', '.jpg', '.jpeg', '.tif', '.bmp')
        files = [f for f in os.listdir(current_folder) if f.lower().endswith(valid_extensions)]
        
        if not files:
            return

        # 4. Configura Barra de Progresso (UX importante para loops demorados)
        global_stats = []
        progress = QProgressDialog(f"Processando Lote...", "Cancelar", 0, len(files), self.main_window)
        progress.setWindowModality(Qt.WindowModal)
        
        count = 0
        errors = []

        # 5. Loop de Processamento
        for i, filename in enumerate(files):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            
            try:
                # Carrega
                input_path = os.path.join(current_folder, filename)

                # Usa o io.imread direto.
                raw_img = io.imread(input_path, as_gray=True)
                
                # Executa
                result = plugin.execute(raw_img)
                
                # Trata o retorno (Tupla ou Só Imagem)
                processed_img = result
                df_result = None

                # Processa
                processed_data = plugin.execute(raw_img)

                if isinstance(result, tuple):
                    processed_img = result[0]
                    df_result = result[1] # O DataFrame individual

                # Salva Imagem
                if processed_img is not None:
                    save_name = f"proc_{filename}"
                    base_name = os.path.splitext(filename)[0]
                    
                    # Salva IMG
                    io.imsave(os.path.join(output_dir, save_name), 
                                self._normalize_for_save(processed_img), check_contrast=False)
                    
                    # Salva CSV Individual e Calcula Global
                    if df_result is not None and not df_result.empty:
                        # Salva CSV individual
                        csv_name = f"dados_{base_name}.csv"
                        df_result.to_csv(os.path.join(output_dir, csv_name), index=False)
                        
                        # Acumula estatísticas
                        avg = df_result['Comprimento (nm)'].mean()
                        std = df_result['Comprimento (nm)'].std()
                        n = len(df_result)
                        
                        global_stats.append({
                            'Arquivo': filename,
                            'Média (nm)': round(avg, 2),
                            'Desvio Padrão (nm)': round(std, 2),
                            'N (Contagem)': n
                        })

                    count += 1

            except Exception as e:
                errors.append(f"{filename}: {e}")

        progress.setValue(len(files))

        # 6. Gera CSV Geral (Mestrado)
        if global_stats:
            df_global = pd.DataFrame(global_stats)
            
            # Adiciona uma linha final com a Média das Médias (Grande Média)
            grand_mean = df_global['Média (nm)'].mean()
            grand_std = df_global['Média (nm)'].std() # Variação entre imagens
            
            summary_row = pd.DataFrame([{
                'Arquivo': '--- RESUMO GERAL ---',
                'Média (nm)': round(grand_mean, 2),
                'Desvio Padrão (nm)': round(grand_std, 2),
                'N (Contagem)': df_global['N (Contagem)'].sum()
            }])
            
            df_global = pd.concat([df_global, summary_row], ignore_index=True)
            
            df_global.to_csv(os.path.join(output_dir, "_RESUMO_GLOBAL.csv"), index=False)

        # 7. Limpeza (Teardown)
        if hasattr(plugin, 'teardown_batch'):
            plugin.teardown_batch()

        # --- LÓGICA DE FLUXO CONTÍNUO ---
        if count > 0:
            # Usa o novo método dedicado para trocar a pasta
            self.main_window.change_working_directory(output_dir)

        # 6. Relatório Final
        msg = f"Processamento concluído!\n\nImagens processadas: {count}/{len(files)}"
        msg += "\n\nA pasta de trabalho foi atualizada para o diretório de saída."

        if global_stats:
            msg += "\n\nDados Estatísticos gerados (CSVs individuais e Resumo Global)."
        
        if errors:
            msg += f"\n\nErros ({len(errors)}):\n" + "\n".join(errors[:5])
            QMessageBox.warning(self.main_window, "Concluído com Erros", msg)
        else:
            QMessageBox.information(self.main_window, "Sucesso", msg)

    def _normalize_for_save(self, data):
        """
        Converte matriz float (com negativos) para uint8 (0-255) para salvar como PNG/JPG.
        """
        # Remove NaN/Inf
        data = np.nan_to_num(data)
        
        d_min = data.min()
        d_max = data.max()
        
        if d_max - d_min == 0:
            return data.astype(np.uint8)
            
        # Normaliza 0.0 a 1.0
        norm = (data - d_min) / (d_max - d_min)
        # Converte para 0-255
        return util.img_as_ubyte(norm)