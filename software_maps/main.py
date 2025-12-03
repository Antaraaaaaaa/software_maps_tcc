import sys
import os
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.plugin_manager import PluginManager

def main():
    # 1. Cria a aplicação Qt
    app = QApplication(sys.argv)

    # 2. Cria a janela principal
    window = MainWindow()
    window.show()

    # 3. Inicializa o PluginManager 
    # Descobre o caminho absoluto da pasta de plugins
    base_dir = os.path.dirname(os.path.abspath(__file__))
    plugins_dir = os.path.join(base_dir, "plugins")

    manager = PluginManager(window)
    manager.discover_and_load_plugins(plugins_dir)

    # 4. Executa o loop de eventos
    sys.exit(app.exec())

if __name__ == "__main__":
    main()