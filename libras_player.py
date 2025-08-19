import os
import sys
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QScrollArea, QGridLayout
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QTimer, Qt

print('Iniciando script libras_player.py')

def montar_glossario_e_alfabeto(pasta_base):
    glossario = {}
    alfabeto = {}
    for letra in os.listdir(pasta_base):
        pasta_letra = os.path.join(pasta_base, letra)
        if not os.path.isdir(pasta_letra):
            continue
        for nome_arquivo in os.listdir(pasta_letra):
            nome, ext = os.path.splitext(nome_arquivo)
            if ext.lower() != '.jpg':
                continue
            caminho = os.path.join(pasta_letra, nome_arquivo)
            if nome.upper() == letra.upper():
                alfabeto[letra.lower()] = caminho
            else:
                glossario[nome.lower()] = caminho
    return glossario, alfabeto

def limpar_segmento(texto):
    # Remove tags <c> e timestamps <00:00:00.000>
    texto = re.sub(r'<c>|</c>', '', texto)
    texto = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', texto)
    texto = re.sub(r'[^\w\s]', '', texto)  # Remove pontuação
    return texto.lower().split()

def parse_vtt(caminho):
    segmentos = []
    tempos = []
    with open(caminho, 'r', encoding='utf-8') as f:
        linhas = f.readlines()
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        if re.match(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}', linha):
            tempo_ini = linha.split('-->')[0].strip()
            tempo_ini_s = tempo_para_segundos(tempo_ini)
            texto = ''
            i += 1
            while i < len(linhas) and linhas[i].strip() and not re.match(r'\d{2}:\d{2}:\d{2}\.\d{3} -->', linhas[i]):
                texto += linhas[i].strip() + ' '
                i += 1
            segmentos.append(texto.strip())
            tempos.append(tempo_ini_s)
        else:
            i += 1
    return segmentos, tempos

def tempo_para_segundos(tempo):
    h, m, s = tempo.split(':')
    s, ms = s.split('.')
    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000

class LibrasPlayer(QWidget):
    def __init__(self, imagens_dir):
        print('Iniciando LibrasPlayer...')
        super().__init__()
        print('Janela QWidget criada')
        self.setWindowTitle('Libras Player')
        self.imagens_dir = imagens_dir
        print(f'Pasta imagens: {imagens_dir}')
        self.glossario, self.alfabeto = montar_glossario_e_alfabeto(imagens_dir)
        print(f'Glossario: {len(self.glossario)} palavras, Alfabeto: {len(self.alfabeto)} letras')
        self.segmentos = []
        self.tempos = []
        self.indice_segmento = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.proximo_segmento)
        self.init_ui()
        print('UI inicializada')
        self.resize(1280, 720)  # Tamanho padrão 1280x720

    def init_ui(self):
        print('Entrou em init_ui')
        layout = QVBoxLayout(self)
        # --- PARTE SUPERIOR: Campo de URL e botão para embed do YouTube ---
        from PyQt5.QtWidgets import QLineEdit
        try:
            from PyQt5.QtWebEngineWidgets import QWebEngineView
            self.webview = QWebEngineView()
            self.input_url = QLineEdit()
            self.input_url.setPlaceholderText('Cole a URL do vídeo do YouTube aqui')
            self.btn_embed = QPushButton('Visualizar YouTube')
            self.btn_embed.clicked.connect(self.embed_youtube)
            self.label_status_video = QLabel('')
            top_widget = QWidget()
            top_layout = QHBoxLayout(top_widget)
            top_layout.addWidget(self.input_url)
            top_layout.addWidget(self.btn_embed)
            top_layout.addWidget(self.label_status_video)
            layout.addWidget(top_widget)
            layout.addWidget(self.webview)
        except ImportError:
            self.webview = None
            self.input_url = QLineEdit()
            self.input_url.setPlaceholderText('PyQtWebEngine não disponível')
            self.label_status_video = QLabel('PyQtWebEngine não disponível')
            top_widget = QWidget()
            top_layout = QHBoxLayout(top_widget)
            top_layout.addWidget(self.input_url)
            top_layout.addWidget(self.label_status_video)
            layout.addWidget(top_widget)

        # --- PARTE INFERIOR: vídeo e legendas/imagens ---
        self.bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(self.bottom_widget)

        # Widget de vídeo (PyQt5.QtMultimediaWidgets)
        try:
            from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
            from PyQt5.QtMultimediaWidgets import QVideoWidget
            self.video_widget = QVideoWidget()
            self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
            self.player.setVideoOutput(self.video_widget)
            bottom_layout.addWidget(self.video_widget)
        except Exception as e:
            self.video_widget = QLabel('PyQt5.QtMultimedia não disponível')
            bottom_layout.addWidget(self.video_widget)
            self.player = None

        # Legenda limpa acima da box de imagens
        self.label_segmento = QLabel('Carregue uma transcrição (.vtt ou .srt)...')
        self.label_segmento.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        bottom_layout.addWidget(self.label_segmento)
        # Área de imagens com altura um pouco maior
        self.scroll_area = QScrollArea()
        self.scroll_area.setFixedHeight(150)
        self.scroll_widget = QWidget()
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(2)
        self.grid.setVerticalSpacing(2)
        self.scroll_widget.setLayout(self.grid)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        bottom_layout.addWidget(self.scroll_area)
        btn_layout = QHBoxLayout()
        self.btn_carregar = QPushButton('Carregar Transcrição')
        self.btn_carregar.clicked.connect(self.carregar_transcricao)
        btn_layout.addWidget(self.btn_carregar)
        self.btn_iniciar = QPushButton('Iniciar')
        self.btn_iniciar.clicked.connect(self.iniciar)
        btn_layout.addWidget(self.btn_iniciar)
        bottom_layout.addLayout(btn_layout)
        layout.addWidget(self.bottom_widget)
        print('Saiu do init_ui')



    def embed_youtube(self):
        if not self.webview:
            self.label_status_video.setText('QWebEngineView não disponível.')
            return
        url = self.input_url.text().strip()
        if not url:
            self.label_status_video.setText('Insira uma URL válida.')
            return
        import re
        match = re.search(r'(?:v=|youtu.be/)([\w-]+)', url)
        if not match:
            self.label_status_video.setText('URL inválida para embed.')
            return
        video_id = match.group(1)
        embed_url = f'https://www.youtube.com/embed/{video_id}'
        self.webview.setUrl(embed_url)

    def carregar_transcricao(self):
        print('Entrou em carregar_transcricao')
        caminho, _ = QFileDialog.getOpenFileName(self, 'Selecione a transcrição', '', 'Arquivos VTT/SRT (*.vtt *.srt)')
        print(f'Arquivo selecionado: {caminho}')
        if caminho:
            if caminho.endswith('.vtt'):
                self.segmentos, self.tempos = parse_vtt(caminho)
            else:
                self.segmentos, self.tempos = self.parse_srt(caminho)
            self.indice_segmento = 0
            self.label_segmento.setText('Transcrição carregada. Pronto para iniciar.')
        print('Saiu de carregar_transcricao')

    def parse_srt(self, caminho):
        segmentos = []
        tempos = []
        with open(caminho, 'r', encoding='utf-8') as f:
            linhas = f.readlines()
        i = 0
        while i < len(linhas):
            if re.match(r'\d+$', linhas[i].strip()):
                i += 1
                if i < len(linhas) and re.match(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', linhas[i]):
                    tempo_ini = linhas[i].split('-->')[0].strip().replace(',', '.')
                    tempo_ini_s = tempo_para_segundos(tempo_ini)
                    i += 1
                    texto = ''
                    while i < len(linhas) and linhas[i].strip() and not re.match(r'\d+$', linhas[i]):
                        texto += linhas[i].strip() + ' '
                        i += 1
                    segmentos.append(texto.strip())
                    tempos.append(tempo_ini_s)
            else:
                i += 1
        return segmentos, tempos

    def iniciar(self):
        print('Entrou em iniciar')
        if not self.segmentos:
            self.label_segmento.setText('Carregue uma transcrição primeiro!')
            print('Nenhuma transcrição carregada')
            return
        self.indice_segmento = 0
        self.proximo_segmento()
        self.timer.start(2000)  # 2 segundos por segmento
        print('Timer iniciado')

    def proximo_segmento(self):
        print(f'proximo_segmento: {self.indice_segmento}/{len(self.segmentos)}')
        if self.indice_segmento >= len(self.segmentos):
            self.timer.stop()
            self.label_segmento.setText('Fim da transcrição.')
            print('Fim da transcrição')
            return
        texto = self.segmentos[self.indice_segmento]
        texto_limpo = ' '.join(limpar_segmento(texto))
        self.label_segmento.setText(texto_limpo)
        palavras = limpar_segmento(texto)
        self.mostrar_imagens(palavras)
        self.indice_segmento += 1

    def mostrar_imagens(self, palavras):
        print(f'mostrar_imagens: {palavras}')
        # Limpa o grid
        for i in reversed(range(self.grid.count())):
            widget = self.grid.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        col = 0
        row = 0
        max_por_linha = 20  # Mais imagens por linha para ficarem mais coladas
        for palavra in palavras:
            if palavra in self.glossario:
                img_path = self.glossario[palavra]
                label = QLabel()
                pixmap = QPixmap(img_path)
                pixmap = pixmap.scaledToHeight(36)  # Imagem ainda menor
                label.setPixmap(pixmap)
                self.grid.addWidget(label, row, col)
                col += 1
                if col >= max_por_linha:
                    col = 0
                    row += 1
            else:
                for letra in palavra:
                    if letra in self.alfabeto:
                        img_path = self.alfabeto[letra]
                        label = QLabel()
                        pixmap = QPixmap(img_path)
                        pixmap = pixmap.scaledToHeight(36)
                        label.setPixmap(pixmap)
                        self.grid.addWidget(label, row, col)
                        col += 1
                        if col >= max_por_linha:
                            col = 0
                            row += 1
        print('Saiu de mostrar_imagens')

if __name__ == '__main__':
    print('Entrou no bloco principal')
    app = QApplication(sys.argv)
    pasta_imagens = os.path.join(os.path.dirname(__file__), 'imagens')
    print(f'Pasta imagens usada: {pasta_imagens}')
    player = LibrasPlayer(pasta_imagens)
    player.resize(900, 350)
    player.show()
    print('Janela show chamada, entrando no exec_')
    sys.exit(app.exec_())
