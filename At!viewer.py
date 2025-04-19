import sys
import os  
import glob
import requests
import tkinter as tk
from io import BytesIO
from tkinter import messagebox
import gspread
from bs4 import BeautifulSoup
from PIL import Image, UnidentifiedImageError
from oauth2client.service_account import ServiceAccountCredentials
import hashlib
from PyQt5 import QtGui
from PyQt5.QtWidgets import QLineEdit, QVBoxLayout, QApplication, QGridLayout, QMessageBox, QScrollArea, QMainWindow, QPushButton, QWidget, QHBoxLayout, QLabel, QSlider, QFileDialog, QStatusBar, QProgressBar
from PyQt5.QtCore import QPoint, Qt, QUrl, QSize, QPoint, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QPalette, QColor, QImage, QPainter, QPixmap
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from natsort import natsorted
from multiprocessing import cpu_count


# Get the path of the directory where the script is located
if getattr(sys, 'frozen', False):
    script_dir = sys._MEIPASS  # Executable version
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))  # .py version

# Get the absolute path to the JSON file
json_path = os.path.join(script_dir, 'Webtoonpass.json')

def verify_credentials(id, password):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Webtoonpass").sheet1
    data = sheet.get_all_records()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()

    for row in data:
        if row["ID"] == id and row["Pass"] == hashed_password:
            return True

    return False

def is_duplicate_login(id):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
    client = gspread.authorize(creds)
    duplicate_sheet = client.open("DuplicationId").sheet1
    duplicate_ids = duplicate_sheet.col_values(1)[1:]
    return id in duplicate_ids

def add_duplicate_login(id):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
    client = gspread.authorize(creds)
    duplicate_sheet = client.open("DuplicationId").sheet1
    duplicate_sheet.append_row([id])

def remove_duplicate_login(id):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
    client = gspread.authorize(creds)
    duplicate_sheet = client.open("DuplicationId").sheet1
    duplicate_ids = duplicate_sheet.col_values(1)[1:]

    if id in duplicate_ids:
        index = duplicate_ids.index(id) + 2
        duplicate_sheet.delete_rows(index)

class LoginThread(QThread):
    signal = pyqtSignal(str)

    def __init__(self, id, password):
        QThread.__init__(self)
        self.id = id
        self.password = password

    def run(self):
        if is_duplicate_login(self.id):
            self.signal.emit("duplicate")
        elif verify_credentials(self.id, self.password):
            self.signal.emit("success")
            add_duplicate_login(self.id)
        else:
            self.signal.emit("failure")

class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.initUI()

    def initUI(self):
        font = QFont("Arial", 10)


        self.close_button = QPushButton("X", self)
        self.close_button.setFixedSize(15, 15)
        self.close_button.clicked.connect(self.parent.close)

        layout = QGridLayout(self)
        layout.addWidget(self.close_button, 0, 1, 1, 1, Qt.AlignRight)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.setFixedHeight(30)
        self.setStyleSheet("background-color: gray; color: white;")


class LoginWindow(QWidget):
    def __init__(self, app):  # QApplication 객체를 받는 생성자 추가
        super().__init__()
        self.app = app  # QApplication 객체 저장
        self.initUI()

    def initUI(self):
        self.login_successful = False

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setStyleSheet("background-color: darkgray;")

        self.layout = QVBoxLayout()

        # 타이틀 바를 생성하고 로그인 창의 맨 위에 추가합니다.
        self.title_bar = TitleBar(self)
        self.layout.addWidget(self.title_bar)

        font = QFont("Gothic", 25)

        self.label_login = QLabel("Login")
        self.label_login.setFont(font)
        self.label_login.setAlignment(Qt.AlignCenter)

        font = QFont("Gothic", 10)

        self.entry_id = QLineEdit()
        self.entry_id.setFixedSize(200, 30)
        self.entry_id.setPlaceholderText("ID")
        self.entry_id.setAlignment(Qt.AlignCenter)
        self.entry_id.setFont(font)
        self.entry_id.setStyleSheet("""
            background-color: white;
            border-radius: 5px;
            color: gray;
        """)

        self.entry_password = QLineEdit()
        self.entry_password.setFixedSize(200, 30)
        self.entry_password.setPlaceholderText("Password")
        self.entry_password.setAlignment(Qt.AlignCenter)
        self.entry_password.setEchoMode(QLineEdit.Password)
        self.entry_password.setFont(font)
        self.entry_password.setStyleSheet("""
            background-color: white;
            border-radius: 5px;
            color: gray;
        """)

        self.button_login = QPushButton("Login", self)
        self.button_login.clicked.connect(self.login)
        self.button_login.setStyleSheet("""
            QPushButton {
                background-color: rgba(70, 70, 70, 0.8);
                color: white;
                font-weight: bold;
                border: none;
                padding: 10px;
                text-align: center;
                border-radius: 10px;
            }
            QPushButton:pressed {
                background-color: rgba(100, 100, 100, 0.5);
            }
        """)

        self.layout.addWidget(self.label_login)
        self.layout.addSpacing(20)
        self.layout.addWidget(self.entry_id)
        self.layout.addWidget(self.entry_password)
        self.layout.addWidget(self.button_login)

        self.setLayout(self.layout)

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()

    def is_inputs_empty(self):
        return self.entry_id.text().strip() == "" or self.entry_password.text().strip() == ""

    def login(self):
        if self.is_inputs_empty():
            QMessageBox.warning(self, "Error", "Please enter ID and Password.")
            return

        self.button_login.setText("Logging in...")
        self.button_login.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 100, 100, 0.5);
                color: white;
                font-weight: bold;
                border: none;
                padding: 10px;
                text-align: center;
                border-radius: 10px;
            }
        """)

        id = self.entry_id.text()
        password = self.entry_password.text()

        self.thread = LoginThread(id, password)
        self.thread.signal.connect(self.handle_login)
        self.thread.start()

    def handle_login(self, result):
        if result == "duplicate":
            QMessageBox.warning(self, "Error", "Duplicate login detected")
        elif result == "success":
            self.login_successful = True
            self.hide()
            main(self.app)  # Pass QApplication instance to main
        else:
            QMessageBox.warning(self, "Error", "Invalid ID or Password")

        self.button_login.setText("Login")
        self.button_login.setStyleSheet("""
            QPushButton {
                background-color: rgba(70, 70, 70, 0.8);
                color: white;
                font-weight: bold;
                border: none;
                padding: 10px;
                text-align: center;
                border-radius: 10px;
            }
            QPushButton:pressed {
                background-color: rgba(100, 100, 100, 0.5);
            }
        """)

    def closeEvent(self, event):
        if self.login_successful:
            id = self.entry_id.text()
            remove_duplicate_login(id)
        else:
            QApplication.quit()
        event.accept()

class DownloadThread(QThread):
    progress_signal = pyqtSignal(str, int)

    def __init__(self, webtoon_id, webtoon_title, start_episode, end_episode, save_dir):
        super().__init__()
        self.webtoon_id = webtoon_id
        self.webtoon_title = webtoon_title
        self.start_episode = start_episode
        self.end_episode = end_episode
        self.save_dir = save_dir
        self.downloaded_episodes = []  # 다운로드된 에피소드 목록
        self.total_images = 0  # 전체 이미지 수
        self.downloaded_images = 0  # 다운로드된 이미지 수

    def run(self):
        session = requests.Session()  # 세션 사용하여 연결 유지
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }

        # 쓰레드 풀의 최대 크기를 시스템의 CPU 수의 절반으로 설정합니다.
        max_workers = cpu_count() // 2
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            episode_futures = []

            for episode in range(self.start_episode, self.end_episode + 1):
                episode_dir = os.path.join(self.save_dir, f"{self.webtoon_title}_{self.webtoon_id}")
                os.makedirs(episode_dir, exist_ok=True)

                # 파일이 이미 폴더에 존재하는지 확인합니다.
                if self.is_episode_downloaded(episode_dir, episode):
                    print(f"Episode {episode} already downloaded. Skipping...")
                    continue

                url = f"https://comic.naver.com/webtoon/detail?titleId={self.webtoon_id}&no={episode}"
                episode_future = executor.submit(self.download_episode, session, headers, episode, url, episode_dir)
                episode_futures.append(episode_future)

            # 모든 에피소드에 대한 다운로드가 완료될 때까지 대기합니다.
            for episode_future in concurrent.futures.as_completed(episode_futures):
                episode, downloaded_images = episode_future.result()
                if self.total_images == 0 or self.total_images * 100 == 0:
                    QMessageBox.warning(None, "Warning", "저장 할 수 없는 웹툰입니다.")
                    return  # 다운로드 시퀀스 중지
            
                if episode is not None:
                    self.downloaded_images += downloaded_images
                    progress_ratio = self.downloaded_images / self.total_images * 100
                    self.progress_signal.emit(f"Progress: {self.downloaded_images}/{self.total_images}  ({progress_ratio:.1f}%)", int(progress_ratio))

                if downloaded_images > 0:
                    self.downloaded_episodes.append(episode)

                        
        self.downloaded_episodes.sort()  # 다운로드 완료된 에피소드를 오름차순으로 정렬
        self.progress_signal.emit("다운로드 완료.", None)

    def is_episode_downloaded(self, episode_dir, episode):
        filename_pattern = f"{self.webtoon_title}_{self.webtoon_id}_{episode}_*.jpg"
        matching_files = glob.glob(os.path.join(episode_dir, filename_pattern))
        return len(matching_files) > 0
    
    def download_episode(self, session, headers, episode, url, episode_dir):
        response = session.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find('a', class_='title')
        if not title_tag:
            print(f"Invalid URL for episode {episode}. Skipping...")
            return episode, 0

        webtoon_title = title_tag.text.strip()
        
        img_tags = soup.select('img[src*="image-comic.pstatic.net/webtoon/"]')
        img_urls = [img['src'] for img in img_tags if "IMAG01" in img['src']]

        if not img_urls:
            print(f"No images found for episode {episode}. Skipping...")
            return episode, 0

        self.total_images += len(img_urls)  # 전체 이미지 수
        downloaded_images = 0  # 다운로드한 이미지 수

        for i, img_url in enumerate(img_urls):
            response = session.get(img_url, headers=headers)
            try:
                image = Image.open(BytesIO(response.content))
            except UnidentifiedImageError as e:
                print(f"Unidentified image at URL: {img_url}: {e}")
                continue

            filename = f"{webtoon_title}_{self.webtoon_id}_{episode}_{i + 1}.jpg"
            image.save(os.path.join(episode_dir, filename))

            downloaded_images += 1

        return episode, downloaded_images

class WebtoonViewer(QMainWindow):
    def __init__(self, login_window, alert_button):
        super().__init__()
        self.login_window = login_window
        self.alert_button = alert_button
        self.setWindowTitle("Webtoon Viewer")
        self.resize(1000, 800)
        self.opacity = 1.0

        self.webview = QWebEngineView()
        self.setWebEngineProfile()
        self.webview.load(QUrl("https://comic.naver.com/webtoon"))
        self.setCentralWidget(self.webview)
        self.webview.setContextMenuPolicy(Qt.NoContextMenu)

    def setWebEngineProfile(self):
        profile = QWebEngineProfile.defaultProfile()
        profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
        profile.setHttpCacheType(QWebEngineProfile.NoCache)
        page = QWebEnginePage(profile, self.webview)
        page.profile().downloadRequested.connect(self.handleDownloadRequested)
        page.loadFinished.connect(self.loadFinished)
        self.webview.setPage(page)

    def handleDownloadRequested(self, download):
        download.accept()

    def set_transparency(self, opacity):
        self.opacity = opacity / 100
        self.setWindowOpacity(self.opacity)

    def loadFinished(self, ok):
        if ok:
            url_info = self.webview.url().toString()
            webtoon_id, webtoon_title, episode_no = self.parse_webtoon_url(url_info)
            if webtoon_id and episode_no:  # 유효한 URL인 경우에만 설정
                self.alert_button.set_webtoon_info(webtoon_id, webtoon_title, episode_no)
            else:  # 유효하지 않은 URL인 경우 초기화
                self.alert_button.set_webtoon_info("", "", "")
                # 유효하지 않은 URL일 때 다운로드 버튼, 웹툰 제목, 웹툰 ID, 시작 에피소드, 종료 에피소드 칸 비활성화
                self.alert_button.save_images_button.setEnabled(False)
                self.alert_button.webtoon_title_label.setText("Webtoon 제목:")

    def resizeEvent(self, event):
        super().resizeEvent(event)

        # 창의 너비에 따라 줌 레벨을 조정합니다.
        zoom_factor = self.width() / 1300
        self.webview.setZoomFactor(zoom_factor)

    def parse_webtoon_url(self, url):
        if "titleId" in url and "no" in url:
            webtoon_id = url.split("titleId=")[1].split("&")[0]
            episode_no = url.split("no=")[1].split("&")[0]

            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('a', class_='title')
            webtoon_title = title_tag.text.strip() if title_tag else ""

            return webtoon_id, webtoon_title, episode_no

        return None, None, None  # 유효하지 않은 URL인 경우 None 반환

    def start_image_download(self, webtoon_id, webtoon_title, start_episode, end_episode):
        save_dir = QFileDialog.getExistingDirectory(self, "Save Images", "")
        if save_dir:
            self.download_thread = DownloadThread(webtoon_id, webtoon_title, start_episode, end_episode, save_dir)
            self.download_thread.progress_signal.connect(self.update_progress)
            self.download_thread.finished.connect(self.download_completed)
            self.download_thread.start()

    def update_progress(self, message, progress_ratio):
        print(message)
        self.alert_button.status_bar.showMessage(message)  # Status bar 업데이트

        if progress_ratio is not None:
            self.alert_button.progress_bar.setValue(progress_ratio)  # 진행률 업데이트

    def download_completed(self):
        print("Download completed.")
        self.alert_button.show_message_box(self.download_thread.downloaded_episodes)  # 다운로드 완료 메시지 박스 표시

    def closeEvent(self, event):
        self.alert_button.close()
        self.login_window.close()
        event.accept()

    def view_saved_webtoon(self, saved_webtoon_dir):
        images = glob.glob(os.path.join(saved_webtoon_dir, "*.jpg"))
        if not images:
            QMessageBox.warning(self, "Warning", "저장된 웹툰 이미지가 없습니다.")
            return

        self.saved_webtoon_viewer = QMainWindow()
        self.saved_webtoon_viewer.setWindowTitle("저장툰보기")
        self.saved_webtoon_viewer.resize(1000, 800)

        layout = QVBoxLayout()
        for image_path in images:
            image_label = QLabel()
            image = QImage(image_path)
            if not image.isNull():
                image_label.setPixmap(QPixmap.fromImage(image))
                layout.addWidget(image_label)

        widget = QWidget()
        widget.setLayout(layout)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(widget)
        self.saved_webtoon_viewer.setCentralWidget(scroll_area)
        self.saved_webtoon_viewer.show()



class AlertButton(QWidget):
    def __init__(self, webtoon_viewer):
        super().__init__()
        self.webtoon_viewer = webtoon_viewer
        self.setWindowTitle("앗!")
        self.resize(200, 150)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.draggable = False
        self.dragging_start_position = QPoint()

        self.toggle_transparency_button = QPushButton("투명 모드 전환", self)
        self.toggle_transparency_button.clicked.connect(self.toggle_transparency)

        self.opacity_label = QLabel("투명도:", self)
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self.set_opacity)

        self.webtoon_id_input = QLineEdit(self)  # Webtoon ID 입력란 추가
        self.webtoon_id_input.setValidator(QtGui.QIntValidator())  # 숫자만 입력 가능하도록 설정
        self.webtoon_id_input.returnPressed.connect(self.update_webtoon_title)  # ID 입력 후 엔터 이벤트 연결

        self.webtoon_title_label = QLabel("Webtoon 제목:", self)
        self.start_episode_input = QLineEdit(self)
        self.start_episode_input.setValidator(QtGui.QIntValidator())  # 숫자만 입력 가능하도록 설정
        self.end_episode_input = QLineEdit(self)
        self.end_episode_input.setValidator(QtGui.QIntValidator())  # 숫자만 입력 가능하도록 설정

        self.save_images_button = QPushButton("이미지 다운로드", self)
        self.save_images_button.clicked.connect(self.save_images)
        self.save_images_button.setEnabled(False)  # 초기에는 비활성화 상태로 설정

        self.status_bar = QStatusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)

        self.is_downloading = False  # 이미지 다운로드 중 여부

        self.home_button = QPushButton("홈으로", self)  # 홈으로 버튼 추가
        self.home_button.clicked.connect(self.go_to_home)  # 버튼 클릭 시 go_to_home

        self.view_saved_webtoon_button = QPushButton("저장툰보기", self)
        self.view_saved_webtoon_button.clicked.connect(self.view_saved_webtoon)

        layout = QVBoxLayout()
        layout.addWidget(self.toggle_transparency_button)
        layout.addWidget(self.opacity_label)
        layout.addWidget(self.opacity_slider)
        layout.addWidget(self.webtoon_title_label)
        layout.addWidget(QLabel("Webtoon ID:"))  # Webtoon ID 레이블 추가
        layout.addWidget(self.webtoon_id_input)  # Webtoon ID 입력란 추가
        layout.addWidget(QLabel("Start Episode:"))
        layout.addWidget(self.start_episode_input)
        layout.addWidget(QLabel("End Episode:"))
        layout.addWidget(self.end_episode_input)
        layout.addWidget(self.save_images_button)
        layout.addWidget(self.home_button)  # 레이아웃에 홈으로 버튼 추가
        layout.addStretch()
        layout.addWidget(self.view_saved_webtoon_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_bar)

        self.setLayout(layout)

    def go_to_home(self):
        self.webtoon_viewer.webview.load(QUrl("https://comic.naver.com/webtoon"))  # 웹툰뷰어 창에서 https://comic.naver.com/webtoon 페이지로 이동

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.draggable = True
            self.dragging_start_position = event.pos()

    def mouseMoveEvent(self, event):
        if self.draggable:
            self.move(self.pos() + event.pos() - self.dragging_start_position)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.draggable = False

    def toggle_transparency(self):
        if self.webtoon_viewer.isVisible():
            self.webtoon_viewer.set_transparency(100)
            self.toggle_transparency_button.setText("투명 모드 전환")
        else:
            opacity = self.opacity_slider.value()
            self.webtoon_viewer.set_transparency(opacity)
            self.toggle_transparency_button.setText("^^")

        self.webtoon_viewer.setVisible(not self.webtoon_viewer.isVisible())

    def set_opacity(self, opacity):
        if self.webtoon_viewer.isVisible():
            self.webtoon_viewer.set_transparency(opacity)

    def update_webtoon_title(self):
        webtoon_id = self.webtoon_id_input.text()  # 입력된 Webtoon ID 가져오기
        if webtoon_id:
            # Webtoon ID를 기반으로 제목 업데이트
            url = f"https://comic.naver.com/webtoon/detail?titleId={webtoon_id}&no=1"
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('a', class_='title')
            webtoon_title = title_tag.text.strip() if title_tag else ""
            self.webtoon_title_label.setText(f"Webtoon 제목: {webtoon_title}")

            if webtoon_title:
                self.save_images_button.setEnabled(True)  # Webtoon ID가 유효한 경우 이미지 다운로드 버튼 활성화

    def set_webtoon_info(self, webtoon_id, webtoon_title, episode_no):
        self.webtoon_title_label.setText(f"Webtoon 제목: {webtoon_title}")
        self.webtoon_id_input.setText(str(webtoon_id))  # Webtoon ID 입력란에 기본값으로 설정
        self.start_episode_input.setText(str(episode_no))
        self.end_episode_input.setText(str(episode_no))
        self.save_images_button.setEnabled(not self.is_downloading)  # 이미지 다운로드 중이 아닐 때만 버튼 활성화

    def save_images(self):
        webtoon_title = self.webtoon_title_label.text().split(":")[1].strip()
        webtoon_id = self.webtoon_id_input.text()  # Webtoon ID 입력값 사용
        start_episode = self.start_episode_input.text()
        end_episode = self.end_episode_input.text()

        if not webtoon_id or not start_episode or not end_episode:
            self.show_warning_message("Webtoon ID, Start Episode, End Episode 란을 모두 채우세요.")
            return

        start_episode = int(start_episode)
        end_episode = int(end_episode)

        if start_episode > end_episode:
            self.show_warning_message("시작 에피소드는 종료 에피소드보다 숫자가 작거나 같아야 합니다.")
            return

        self.is_downloading = True  # 이미지 다운로드 중 상태로 변경
        self.save_images_button.setEnabled(False)  # 이미지 다운로드 중일 때 버튼 비활성화
        self.webtoon_viewer.start_image_download(webtoon_id, webtoon_title, start_episode, end_episode)
        self.status_bar.showMessage("Download started...")  # Download 시작 메시지 표시

    def show_warning_message(self, message):
        QMessageBox.warning(self, "Warning", message)

    def show_message_box(self, downloaded_episodes):
        self.is_downloading = False  # 이미지 다운로드 완료 상태로 변경
        self.save_images_button.setEnabled(True)  # 이미지 다운로드 완료 후 버튼 활성화

        if downloaded_episodes:
            message = "다운로드 완료.\n다운로드된 에피소드: {}".format(", ".join(map(str, downloaded_episodes)))
            QMessageBox.information(self, "Download Completed", message)
        else:
            QMessageBox.warning(self, "Warning", "다운로드된 에피소드가 없습니다.")  # 다운로드된 에피소드 없음을 경고 메시지로 표시

    def closeEvent(self, event):
        self.webtoon_viewer.close()
        event.accept()


    def view_saved_webtoon(self):
        self.saved_webtoon_dir = QFileDialog.getExistingDirectory(self, "저장툰보기", "")
        if self.saved_webtoon_dir:
            # 저장된 폴더 내의 파일 이름에서 에피소드 번호 자동 추출
            image_files = glob.glob(os.path.join(self.saved_webtoon_dir, "*.jpg"))
            episode_numbers = set()

            for file in image_files:
                base = os.path.basename(file)
                parts = base.split("_")
                if len(parts) >= 4:
                    try:
                        episode_no = int(parts[2])
                        episode_numbers.add(episode_no)
                    except ValueError:
                        continue

            if episode_numbers:
                self.episode_number = min(episode_numbers)  # 첫 에피소드부터 시작
                self.load_and_show_episode()
            else:
                QMessageBox.warning(self, "Warning", "에피소드 정보를 찾을 수 없습니다.")


    def load_and_show_episode(self):
        episode_image_paths = natsorted(glob.glob(os.path.join(self.saved_webtoon_dir, f"*_*_{self.episode_number}_*.jpg")))
        
        if not episode_image_paths:
            if self.episode_number == 1:
                QMessageBox.warning(self, "Warning", "저장된 웹툰 이미지가 없습니다.")
            else:
                QMessageBox.information(self, "Information", "모든 에피소드를 로드했습니다.")
            return

        if not hasattr(self, 'saved_webtoon_viewer'):
            self.saved_webtoon_viewer = QMainWindow()
            self.saved_webtoon_viewer.setWindowTitle("저장툰보기")
            self.saved_webtoon_viewer.resize(800, 1000)
            self.layout = QVBoxLayout()
            self.layout.setSpacing(0)
            self.widget = QWidget()
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setWidget(self.widget)
            self.saved_webtoon_viewer.setCentralWidget(self.scroll_area)
            self.saved_webtoon_viewer.show()

        for image_path in episode_image_paths:
            image_label = QLabel()
            image = QImage(image_path)
            if not image.isNull():
                image_label.setPixmap(QPixmap.fromImage(image))
                image_label.setAlignment(Qt.AlignCenter)
                self.layout.addWidget(image_label)

        self.widget.setLayout(self.layout)
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())  # 스크롤바를 아래로 내려줌

        self.episode_number += 1  # 다음 에피소드 번호로 업데이트   



alert_button = None
webtoon_viewer = None

def main(app):  # 호출자로부터 QApplication 인스턴스를 받는 함수
    global alert_button, webtoon_viewer
    alert_button = AlertButton(None)
    webtoon_viewer = WebtoonViewer(window,alert_button)
    alert_button.webtoon_viewer = webtoon_viewer
    webtoon_viewer.show()
    alert_button.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoginWindow(app)  # QApplication 객체를 LoginWindow에 전달
    window.show()
    sys.exit(app.exec_())