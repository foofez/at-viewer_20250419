import sys
import os
import glob
import requests
from io import BytesIO
from bs4 import BeautifulSoup
from PIL import Image, UnidentifiedImageError
from PyQt5 import QtGui
from PyQt5.QtWidgets import QLineEdit, QVBoxLayout, QApplication, QGridLayout, QMessageBox, QScrollArea, QMainWindow, QPushButton, QWidget, QHBoxLayout, QLabel, QSlider, QFileDialog, QStatusBar, QProgressBar
from PyQt5.QtCore import QPoint, Qt, QUrl, QSize, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from natsort import natsorted
from multiprocessing import cpu_count

class DownloadThread(QThread):
    progress_signal = pyqtSignal(str, int)

    def __init__(self, webtoon_id, webtoon_title, start_episode, end_episode, save_dir):
        super().__init__()
        self.webtoon_id = webtoon_id
        self.webtoon_title = webtoon_title
        self.start_episode = start_episode
        self.end_episode = end_episode
        self.save_dir = save_dir
        self.downloaded_episodes = []
        self.total_images = 0
        self.downloaded_images = 0

    def run(self):
        session = requests.Session()
        headers = {"User-Agent": "Mozilla/5.0"}
        max_workers = cpu_count() // 2

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            episode_futures = []
            for episode in range(self.start_episode, self.end_episode + 1):
                episode_dir = os.path.join(self.save_dir, f"{self.webtoon_title}_{self.webtoon_id}")
                os.makedirs(episode_dir, exist_ok=True)
                if self.is_episode_downloaded(episode_dir, episode):
                    continue
                url = f"https://comic.naver.com/webtoon/detail?titleId={self.webtoon_id}&no={episode}"
                episode_future = executor.submit(self.download_episode, session, headers, episode, url, episode_dir)
                episode_futures.append(episode_future)

            for episode_future in concurrent.futures.as_completed(episode_futures):
                episode, downloaded_images = episode_future.result()
                if self.total_images == 0:
                    QMessageBox.warning(None, "Warning", "저장 할 수 없는 웹툰입니다.")
                    return
                if episode is not None:
                    self.downloaded_images += downloaded_images
                    progress_ratio = self.downloaded_images / self.total_images * 100
                    self.progress_signal.emit(f"Progress: {self.downloaded_images}/{self.total_images}  ({progress_ratio:.1f}%)", int(progress_ratio))
                if downloaded_images > 0:
                    self.downloaded_episodes.append(episode)
        self.downloaded_episodes.sort()
        self.progress_signal.emit("다운로드 완료.", None)

    def is_episode_downloaded(self, episode_dir, episode):
        filename_pattern = f"{self.webtoon_title}_{self.webtoon_id}_{episode}_*.jpg"
        return len(glob.glob(os.path.join(episode_dir, filename_pattern))) > 0

    def download_episode(self, session, headers, episode, url, episode_dir):
        response = session.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find('a', class_='title')
        if not title_tag:
            return episode, 0
        webtoon_title = title_tag.text.strip()
        img_tags = soup.select('img[src*="image-comic.pstatic.net/webtoon/"]')
        img_urls = [img['src'] for img in img_tags if "IMAG01" in img['src']]
        if not img_urls:
            return episode, 0
        self.total_images += len(img_urls)
        downloaded_images = 0
        for i, img_url in enumerate(img_urls):
            response = session.get(img_url, headers=headers)
            try:
                image = Image.open(BytesIO(response.content))
            except UnidentifiedImageError:
                continue
            filename = f"{webtoon_title}_{self.webtoon_id}_{episode}_{i + 1}.jpg"
            image.save(os.path.join(episode_dir, filename))
            downloaded_images += 1
        return episode, downloaded_images

class WebtoonViewer(QMainWindow):
    def __init__(self, alert_button):
        super().__init__()
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
            if webtoon_id and episode_no:
                self.alert_button.set_webtoon_info(webtoon_id, webtoon_title, episode_no)
            else:
                self.alert_button.set_webtoon_info("", "", "")
                self.alert_button.save_images_button.setEnabled(False)
                self.alert_button.webtoon_title_label.setText("Webtoon 제목:")

    def resizeEvent(self, event):
        super().resizeEvent(event)
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
        return None, None, None

    def start_image_download(self, webtoon_id, webtoon_title, start_episode, end_episode):
        save_dir = QFileDialog.getExistingDirectory(self, "Save Images", "")
        if save_dir:
            self.download_thread = DownloadThread(webtoon_id, webtoon_title, start_episode, end_episode, save_dir)
            self.download_thread.progress_signal.connect(self.update_progress)
            self.download_thread.finished.connect(self.download_completed)
            self.download_thread.start()

    def update_progress(self, message, progress_ratio):
        print(message)
        self.alert_button.status_bar.showMessage(message)
        if progress_ratio is not None:
            self.alert_button.progress_bar.setValue(progress_ratio)

    def download_completed(self):
        print("Download completed.")
        self.alert_button.show_message_box(self.download_thread.downloaded_episodes)

    def closeEvent(self, event):
        self.alert_button.close()
        event.accept()

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
        self.webtoon_id_input = QLineEdit(self)
        self.webtoon_id_input.setValidator(QtGui.QIntValidator())
        self.webtoon_id_input.returnPressed.connect(self.update_webtoon_title)
        self.webtoon_title_label = QLabel("Webtoon 제목:", self)
        self.start_episode_input = QLineEdit(self)
        self.start_episode_input.setValidator(QtGui.QIntValidator())
        self.end_episode_input = QLineEdit(self)
        self.end_episode_input.setValidator(QtGui.QIntValidator())
        self.save_images_button = QPushButton("이미지 다운로드", self)
        self.save_images_button.clicked.connect(self.save_images)
        self.save_images_button.setEnabled(False)
        self.status_bar = QStatusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.home_button = QPushButton("홈으로", self)
        self.home_button.clicked.connect(self.go_to_home)
        self.view_saved_webtoon_button = QPushButton("저장된 웹툰 보기", self)
        self.view_saved_webtoon_button.clicked.connect(self.view_saved_webtoon)

        layout = QVBoxLayout()
        layout.addWidget(self.toggle_transparency_button)
        layout.addWidget(self.opacity_label)
        layout.addWidget(self.opacity_slider)
        layout.addWidget(self.webtoon_title_label)
        layout.addWidget(QLabel("Webtoon ID:"))
        layout.addWidget(self.webtoon_id_input)
        layout.addWidget(QLabel("Start Episode:"))
        layout.addWidget(self.start_episode_input)
        layout.addWidget(QLabel("End Episode:"))
        layout.addWidget(self.end_episode_input)
        layout.addWidget(self.save_images_button)
        layout.addWidget(self.home_button)
        layout.addWidget(self.view_saved_webtoon_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_bar)
        self.setLayout(layout)

    def view_saved_webtoon(self):
        folder = QFileDialog.getExistingDirectory(self, "저장된 웹툰 폴더 선택")
        if not folder:
            return

        webtoon_dirs = [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]
        if not webtoon_dirs:
            QMessageBox.warning(self, "경고", "해당 경로에 저장된 웹툰이 없습니다.")
            return

        self.webtoon_list_window = QMainWindow(self)
        self.webtoon_list_window.setWindowTitle("저장된 웹툰 목록")
        self.webtoon_list_window.resize(1000, 800)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QGridLayout(container)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

        for dirname in sorted(webtoon_dirs):
            if "_" not in dirname:
                continue
            title_parts = dirname.rsplit("_", 1)
            if len(title_parts) != 2 or not title_parts[1].isdigit():
                continue

            title = title_parts[0]
            title_id = title_parts[1]
            path = os.path.join(folder, dirname)
            meta_url = f"https://comic.naver.com/webtoon/list?titleId={title_id}"

            try:
                res = requests.get(meta_url, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(res.text, 'html.parser')
                image_url = soup.find("meta", {"property": "og:image"})["content"]
                description = soup.find("meta", {"property": "og:description"})["content"]
            except:
                image_url = ""
                description = "설명을 가져올 수 없습니다."

            card = QWidget()
            card_layout = QHBoxLayout()

            thumb_label = QLabel()
            if image_url:
                try:
                    thumb_data = requests.get(image_url).content
                    pixmap = QPixmap()
                    pixmap.loadFromData(thumb_data)
                    thumb_label.setPixmap(pixmap.scaled(120, 160, Qt.KeepAspectRatio))
                except:
                    thumb_label.setText("썸네일 오류")
            else:
                thumb_label.setText("썸네일 없음")

            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setFixedWidth(400)

            btn_layout = QVBoxLayout()
            start_btn = QPushButton("처음부터 보기")
            resume_btn = QPushButton("이어서 보기")
            delete_btn = QPushButton("웹툰 삭제")

            def make_start_func(p=path, tid=title_id, t=title):
                return lambda: self.start_webtoon_from(p, t, tid, 1)

            def make_resume_func(p=path, tid=title_id, t=title):
                def resume():
                    progress_file = os.path.join(p, "last_read.txt")
                    episode = 1
                    if os.path.exists(progress_file):
                        with open(progress_file, "r") as f:
                            try:
                                episode = int(f.read().strip())
                            except:
                                episode = 1
                    self.start_webtoon_from(p, t, tid, episode)
                return resume

            def make_delete_func(p=path, w=card):
                def delete():
                    confirm = QMessageBox.question(self, "삭제 확인", f"{title} 웹툰을 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
                    if confirm == QMessageBox.Yes:
                        import shutil
                        shutil.rmtree(p)
                        layout.removeWidget(w)
                        w.setParent(None)
                return delete

            start_btn.clicked.connect(make_start_func())
            resume_btn.clicked.connect(make_resume_func())
            delete_btn.clicked.connect(make_delete_func())

            btn_layout.addWidget(start_btn)
            btn_layout.addWidget(resume_btn)
            btn_layout.addWidget(delete_btn)

            card_layout.addWidget(thumb_label)
            card_layout.addWidget(desc_label)
            card_layout.addLayout(btn_layout)
            card.setLayout(card_layout)

            row = layout.rowCount()
            layout.addWidget(card, row, 0, 1, 1)

        container.setLayout(layout)
        scroll.setWidget(container)
        self.webtoon_list_window.setCentralWidget(scroll)
        self.webtoon_list_window.show()

    def start_webtoon_from(self, folder, title, title_id, start_episode):
        # 기존 뷰어 닫기
        if hasattr(self, 'saved_webtoon_viewer') and self.saved_webtoon_viewer:
            self.saved_webtoon_viewer.close()

        # 뷰어 초기화
        self.saved_webtoon_viewer = QMainWindow()
        self.saved_webtoon_viewer.setWindowTitle(f"{title} - 웹툰 뷰어")
        self.saved_webtoon_viewer.resize(800, 1000)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_container = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_container)
        self.scroll_layout.setSpacing(0)
        self.scroll_area.setWidget(self.scroll_container)

        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.saved_webtoon_viewer.setCentralWidget(self.scroll_area)

        self.viewer_folder = folder
        self.viewer_title = title
        self.viewer_title_id = title_id
        self.viewer_current_episode = start_episode

        self.load_viewer_episode(self.viewer_current_episode)
        self.saved_webtoon_viewer.show()

    def load_viewer_episode(self, episode):
        image_paths = natsorted(glob.glob(os.path.join(self.viewer_folder, f"*_{episode}_*.jpg")))
        if not image_paths:
            QMessageBox.information(self, "정보", f"{episode}화 이미지를 찾을 수 없습니다.")
            return

        for img_path in image_paths:
            img = QImage(img_path)
            if img.isNull():
                continue
            label = QLabel()
            label.setPixmap(QPixmap.fromImage(img))
            label.setAlignment(Qt.AlignCenter)
            self.scroll_layout.addWidget(label)

        self.viewer_current_episode = episode
        # 이어보기 저장
        progress_file = os.path.join(self.viewer_folder, "last_read.txt")
        try:
            with open(progress_file, "w") as f:
                f.write(str(episode))
        except:
            print("[경고] 이어보기 저장 실패")

    def on_scroll(self):
        if hasattr(self, 'download_thread') and self.download_thread.isRunning():
            return  # 중복 다운로드 방지
        scroll_bar = self.scroll_area.verticalScrollBar()
        max_scroll = scroll_bar.maximum()
        current_scroll = scroll_bar.value()

        if current_scroll == max_scroll:
            next_ep = self.viewer_current_episode + 1
            episode_images = glob.glob(os.path.join(self.viewer_folder, f"*_{next_ep}_*.jpg"))
            if episode_images:
                self.load_viewer_episode(next_ep)
            else:
                # 자동 다운로드 시도
                download_dir = self.viewer_folder
                webtoon_id = self.viewer_title_id
                webtoon_title = self.viewer_title

                download_thread = DownloadThread(webtoon_id, webtoon_title, next_ep, next_ep, download_dir)
                self.download_thread = DownloadThread(webtoon_id, webtoon_title, next_ep, next_ep, download_dir)
                self.download_thread.progress_signal.connect(self.status_bar.showMessage)
                self.download_thread.finished.connect(lambda: self.after_auto_download(next_ep))
                self.download_thread.start()
                return  # 다운로드 완료 후 후처리에서 다음 회차 로드 시도

                # 다시 확인 후 로드 또는 메시지
                episode_images = glob.glob(os.path.join(self.viewer_folder, f"*_{next_ep}_*.jpg"))
                if episode_images:
                    self.load_viewer_episode(next_ep)
                else:
                    pass  # 이후 다운로드 실패 시 처리

        elif current_scroll == 0:
            prev_ep = self.viewer_current_episode - 1
            if prev_ep < 1:
                QMessageBox.information(self, "정보", "이전 에피소드가 없습니다.")
                return
            episode_images = glob.glob(os.path.join(self.viewer_folder, f"*_{prev_ep}_*.jpg"))
            if episode_images:
                for img_path in reversed(natsorted(episode_images)):
                    img = QImage(img_path)
                    if img.isNull():
                        continue
                    label = QLabel()
                    label.setPixmap(QPixmap.fromImage(img))
                    label.setAlignment(Qt.AlignCenter)
                    self.scroll_layout.insertWidget(0, label)
                self.viewer_current_episode = prev_ep
                scroll_bar.setValue(scroll_bar.minimum() + 1)
            else:
                QMessageBox.information(self, "정보", "이전 에피소드가 없습니다.")
                return
            episode_images = glob.glob(os.path.join(self.viewer_folder, f"*_{prev_ep}_*.jpg"))
            if episode_images:
                for img_path in reversed(natsorted(episode_images)):
                    img = QImage(img_path)
                    if img.isNull():
                        continue
                    label = QLabel()
                    label.setPixmap(QPixmap.fromImage(img))
                    label.setAlignment(Qt.AlignCenter)
                    self.scroll_layout.insertWidget(0, label)
                self.viewer_current_episode = prev_ep
                scroll_bar.setValue(scroll_bar.minimum() + 1)
            else:
                QMessageBox.information(self, "정보", "이전 에피소드가 없습니다.")

    def after_auto_download(self, episode):
        episode_images = glob.glob(os.path.join(self.viewer_folder, f"*_{episode}_*.jpg"))
        if episode_images:
            self.load_viewer_episode(episode)
        else:
            QMessageBox.information(self, "정보", "다음 회차가 없습니다.")

    def go_to_home(self):
        self.webtoon_viewer.webview.load(QUrl("https://comic.naver.com/webtoon"))

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
        webtoon_id = self.webtoon_id_input.text()
        if webtoon_id:
            url = f"https://comic.naver.com/webtoon/detail?titleId={webtoon_id}&no=1"
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('a', class_='title')
            webtoon_title = title_tag.text.strip() if title_tag else ""
            self.webtoon_title_label.setText(f"Webtoon 제목: {webtoon_title}")
            if webtoon_title:
                self.save_images_button.setEnabled(True)

    def set_webtoon_info(self, webtoon_id, webtoon_title, episode_no):
        self.webtoon_title_label.setText(f"Webtoon 제목: {webtoon_title}")
        self.webtoon_id_input.setText(str(webtoon_id))
        self.start_episode_input.setText(str(episode_no))
        self.end_episode_input.setText(str(episode_no))
        self.save_images_button.setEnabled(True)

    def save_images(self):
        webtoon_title = self.webtoon_title_label.text().split(":")[1].strip()
        webtoon_id = self.webtoon_id_input.text()
        start_episode = self.start_episode_input.text()
        end_episode = self.end_episode_input.text()
        if not webtoon_id or not start_episode or not end_episode:
            QMessageBox.warning(self, "Warning", "Webtoon ID, Start Episode, End Episode 란을 모두 채우세요.")
            return
        start_episode = int(start_episode)
        end_episode = int(end_episode)
        if start_episode > end_episode:
            QMessageBox.warning(self, "Warning", "시작 에피소드는 종료 에피소드보다 숫자가 작거나 같아야 합니다.")
            return
        self.save_images_button.setEnabled(False)
        self.webtoon_viewer.start_image_download(webtoon_id, webtoon_title, start_episode, end_episode)
        self.status_bar.showMessage("Download started...")

    def show_message_box(self, downloaded_episodes):
        self.save_images_button.setEnabled(True)
        if downloaded_episodes:
            message = "다운로드 완료.\n다운로드된 에피소드: {}".format(", ".join(map(str, downloaded_episodes)))
            QMessageBox.information(self, "Download Completed", message)
        else:
            QMessageBox.warning(self, "Warning", "다운로드된 에피소드가 없습니다.")

    def closeEvent(self, event):
        self.webtoon_viewer.close()
        event.accept()

def main():
    app = QApplication(sys.argv)
    alert_button = AlertButton(None)
    webtoon_viewer = WebtoonViewer(alert_button)
    alert_button.webtoon_viewer = webtoon_viewer
    webtoon_viewer.show()
    alert_button.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
