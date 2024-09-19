import random
import string
import sys
import os
import tempfile
import time
import fitz  # PyMuPDF
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTextEdit, QProgressBar, QFileDialog, QLabel, 
                             QSplitter, QListWidget, QListWidgetItem, QGraphicsView, QGraphicsScene,
                             QMessageBox, QMenuBar, QMenu, QAction, QFontDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRectF
from PyQt5.QtGui import QPixmap, QImage, QPainter, QFont
import io
from PyQt5.QtWidgets import QStatusBar
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import json
import base64

import warnings
warnings.filterwarnings("ignore", message="file_cache is only supported with oauth2client<4.0.0")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_credentials(client_secret_file):
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

import contextlib

def process_image(service, image):
    try:
        logger.info("Processing image")
        mime = 'application/vnd.google-apps.document'
        file_metadata = {'name': 'temp_image.png', 'mimeType': mime}
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_filename = temp_file.name
            image.save(temp_filename, format='PNG')
        
        # Retry mechanism
        max_retries = 3
        for attempt in range(max_retries):
            try:
                media = MediaFileUpload(temp_filename, mimetype='image/png', resumable=True)
                file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                
                request = service.files().export_media(fileId=file['id'], mimeType='text/plain')
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                
                service.files().delete(fileId=file['id']).execute()
                
                # If successful, break the retry loop
                break
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise

    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return None
    finally:
        # Always try to remove the temporary file
        with contextlib.suppress(Exception):
            os.remove(temp_filename)
    
    return fh.getvalue().decode('utf-8')
    
def clean_text(text):
    cleaned = text.replace(' )', ')').replace('( ', '(').replace('.', '. ').replace(',', ', ')
    cleaned = ' '.join(cleaned.split())
    return cleaned

class OCRWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str, int)

    def __init__(self, pdf_doc, page_num, client_secret_file):
        super().__init__()
        self.pdf_doc = pdf_doc
        self.page_num = page_num
        self.client_secret_file = client_secret_file

    def run(self):
        try:
            creds = get_credentials(self.client_secret_file)
            service = build('drive', 'v3', credentials=creds)

            page = self.pdf_doc.load_page(self.page_num)
            pix = page.get_pixmap()
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)

            text_content = process_image(service, img)
            if text_content:
                result = clean_text(text_content)
                self.finished.emit(result, self.page_num)
            else:
                self.finished.emit("OCR process failed. Check the logs for more information.", self.page_num)
        except Exception as e:
            self.finished.emit(f"An error occurred: {str(e)}", self.page_num)

        # Simulate progress
        for i in range(101):
            self.progress.emit(i)
            self.msleep(50)

class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.scale(1, 1)

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            factor = 1.25
        else:
            factor = 0.8
        self.scale(factor, factor)

class EditableTextEdit(QTextEdit):
    def __init__(self, ocr_app, parent=None):
        super().__init__(parent)
        self.ocr_app = ocr_app
        self.textChanged.connect(self.on_text_changed)

    def on_text_changed(self):
        self.ocr_app.save_current_text()

class OCRApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ocr_results = {}
        self.full_ocr_in_progress = False
        self.total_pages = 0
        self.current_page = 0
        self.pdf_content = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('OCR - rexmi.in')
        self.setGeometry(100, 100, 1200, 800)

        self.create_menu_bar()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        layout = QVBoxLayout()
        main_widget.setLayout(layout)

        # Create a splitter for three sections
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left side (Page numbers)
        self.page_list = QListWidget()
        self.page_list.itemClicked.connect(self.display_page)

        # Middle (PDF Preview)
        middle_widget = QWidget()
        middle_layout = QVBoxLayout()
        middle_widget.setLayout(middle_layout)

        self.graphics_view = ZoomableGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)

        middle_layout.addWidget(self.graphics_view)

        # Right side (Extracted text)
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        self.extracted_text = EditableTextEdit(self, right_widget)
        self.extracted_text.setPlaceholderText("Extracted text will appear here")

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        right_layout.addWidget(self.extracted_text)
        right_layout.addWidget(self.progress_bar)

        # Add widgets to splitter
        splitter.addWidget(self.page_list)
        splitter.addWidget(middle_widget)
        splitter.addWidget(right_widget)

        # Set initial sizes for widgets
        splitter.setSizes([200, 500, 500])

        # Add status bar for project information
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.update_status_bar()

    def create_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')

        new_action = QAction('New', self)
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)

        open_action = QAction('Open', self)
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)

        save_project_action = QAction('Save Project', self)
        save_project_action.triggered.connect(self.save_project)
        file_menu.addAction(save_project_action)

        save_as_action = QAction('Save As', self)
        save_as_action.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_action)

        # Operations menu
        operations_menu = menubar.addMenu('Operations')

        full_ocr_action = QAction('Full OCR', self)
        full_ocr_action.triggered.connect(self.full_ocr)
        operations_menu.addAction(full_ocr_action)

        current_page_ocr_action = QAction('Current Page OCR', self)
        current_page_ocr_action.triggered.connect(self.current_page_ocr)
        operations_menu.addAction(current_page_ocr_action)

        save_results_action = QAction('Save Results', self)
        save_results_action.triggered.connect(self.save_results)
        operations_menu.addAction(save_results_action)

        # Font menu
        font_menu = menubar.addMenu('Font')

        increase_font_action = QAction('Increase Font Size', self)
        increase_font_action.triggered.connect(self.increase_font_size)
        font_menu.addAction(increase_font_action)

        decrease_font_action = QAction('Decrease Font Size', self)
        decrease_font_action.triggered.connect(self.decrease_font_size)
        font_menu.addAction(decrease_font_action)

        choose_font_action = QAction('Choose Font', self)
        choose_font_action.triggered.connect(self.choose_font)
        font_menu.addAction(choose_font_action)

        # Developer Information menu
        dev_menu = menubar.addMenu('Developer Info')

        dev_info_action = QAction('About Developer', self)
        dev_info_action.triggered.connect(self.show_dev_info)
        dev_menu.addAction(dev_info_action)

    def show_dev_info(self):
        QMessageBox.information(self, "Developer Information", 
                                "Developer: Sujith S\n"
                                "GitHub: https://github.com/sujithrex")

    def update_status_bar(self):
        project_info = "OCR Application | "
        if hasattr(self, 'pdf_doc'):
            project_info += f"PDF Pages: {len(self.pdf_doc)} | "
        if hasattr(self, 'current_project_path'):
            project_info += f"Project: {os.path.basename(self.current_project_path)}"
        else:
            project_info += "No project loaded"
        self.statusBar.showMessage(project_info)

    def new_project(self):
        self.ocr_results.clear()
        self.current_page = 0
        self.pdf_content = None
        self.page_list.clear()
        self.graphics_scene.clear()
        self.extracted_text.clear()
        self.open_file()

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.pdf_doc = fitz.open(file_path)
            
            # Create a new PDF with an empty first page
            new_pdf = fitz.open()
            new_pdf.new_page(width=self.pdf_doc[0].rect.width, height=self.pdf_doc[0].rect.height)
            
            # Add the pages from the opened PDF
            new_pdf.insert_pdf(self.pdf_doc)
            
            # Replace the old PDF with the new one
            self.pdf_doc = new_pdf
            
            with open(file_path, 'rb') as file:
                self.pdf_content = base64.b64encode(file.read()).decode('utf-8')
            self.update_page_list()
            self.initialize_first_page()
            self.update_status_bar()

    def update_page_list(self):
        self.page_list.clear()
        self.page_list.addItem(QListWidgetItem("Initial Page"))
        for i in range(1, len(self.pdf_doc)):
            item = QListWidgetItem(f"Page {i}")
            self.page_list.addItem(item)

    def save_current_text(self):
        if hasattr(self, 'pdf_doc') and self.current_page is not None:
            current_text = self.extracted_text.toPlainText()
            self.ocr_results[str(self.current_page)] = current_text

    def display_page(self, index):
        self.save_current_text()  # Save the current page's text before switching

        if isinstance(index, QListWidgetItem):
            index = self.page_list.row(index)
        
        self.current_page = index
        page = self.pdf_doc.load_page(index)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(img)

        self.graphics_scene.clear()
        self.graphics_scene.addPixmap(pixmap)
        self.graphics_view.setSceneRect(QRectF(pixmap.rect()))
        self.graphics_view.fitInView(self.graphics_scene.sceneRect(), Qt.KeepAspectRatio)
        
        if str(index) in self.ocr_results:
            self.extracted_text.setPlainText(self.ocr_results[str(index)])
            logger.info(f"Text found for page {index}")
        else:
            self.extracted_text.setPlainText("")
            logger.warning(f"No text found for page {index}")

    def initialize_first_page(self):
        if self.pdf_doc and len(self.pdf_doc) > 0:
            self.current_page = 0
            self.display_page(0)
            self.save_current_text()  # Ensure the first page's text is saved

    def current_page_ocr(self):
        self.run_ocr(self.current_page)

    def full_ocr(self):
        self.ocr_results.clear()
        self.current_page = 0
        self.full_ocr_in_progress = True
        self.total_pages = len(self.pdf_doc)
        self.run_ocr(self.current_page)

    def run_ocr(self, page_num):
        client_secret_file = 'client_secret.json'  # Update this path

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.worker = OCRWorker(self.pdf_doc, page_num, client_secret_file)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.display_result)
        self.worker.start()

    def update_progress(self, value):
        if self.full_ocr_in_progress:
            overall_progress = (self.current_page * 100 + value) // self.total_pages
            self.progress_bar.setValue(overall_progress)
        else:
            self.progress_bar.setValue(value)

    def display_result(self, result, page_num):
        self.ocr_results[str(page_num)] = result
        if page_num == self.current_page:
            self.extracted_text.setPlainText(result)
        self.save_current_text()  # Save the OCR result immediately

        if self.full_ocr_in_progress:
            if page_num < self.total_pages - 1:
                self.current_page = page_num + 1
                self.display_page(self.current_page)
                self.run_ocr(self.current_page)
            else:
                self.full_ocr_in_progress = False
                self.progress_bar.setVisible(False)
                QMessageBox.information(self, "OCR Complete", "Full OCR process has been completed.")
        else:
            self.progress_bar.setVisible(False)

    def save_project(self):
        if not hasattr(self, 'pdf_doc') or not self.pdf_content:
            QMessageBox.warning(self, "Warning", "No project to save. Please open a PDF first.")
            return

        if hasattr(self, 'current_project_path'):
            self._save_project_to_file(self.current_project_path)
        else:
            self.save_project_as()

    def save_project_as(self):
        if not hasattr(self, 'pdf_doc') or not self.pdf_content:
            QMessageBox.warning(self, "Warning", "No project to save. Please open a PDF first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "REXMI Files (*.rexmi)")
        if file_path:
            if not file_path.endswith('.rexmi'):
                file_path += '.rexmi'
            self._save_project_to_file(file_path)
            self.current_project_path = file_path

    def _save_project_to_file(self, file_path):
        self.save_current_text()  # Save the current text before saving the project
        
        project_data = {
            'pdf_content': self.pdf_content,
            'ocr_results': self.ocr_results
        }
        
        with open(file_path, 'w') as f:
            json.dump(project_data, f)
        
        QMessageBox.information(self, "Success", f"Project saved successfully to {file_path}")

    def open_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "REXMI Files (*.rexmi)")
        if file_path:
            self._load_project_from_file(file_path)

    def _load_project_from_file(self, file_path):
        with open(file_path, 'r') as f:
            project_data = json.load(f)
        
        pdf_content = project_data['pdf_content']
        pdf_bytes = base64.b64decode(pdf_content)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            temp_pdf.write(pdf_bytes)
            temp_pdf_path = temp_pdf.name
        
        self.pdf_doc = fitz.open(temp_pdf_path)
        
        # Create a new PDF with an empty first page
        new_pdf = fitz.open()
        new_pdf.new_page(width=self.pdf_doc[0].rect.width, height=self.pdf_doc[0].rect.height)
        
        # Add the pages from the loaded PDF
        new_pdf.insert_pdf(self.pdf_doc)
        
        # Replace the old PDF with the new one
        self.pdf_doc = new_pdf

        self.pdf_content = pdf_content
        self.ocr_results = project_data['ocr_results']
        
        self.update_page_list()
        self.display_page(0)  # Display the empty page first
        
        self.current_project_path = file_path
        QMessageBox.information(self, "Success", f"Project loaded successfully from {file_path}")
        self.update_status_bar()

    def save_results(self):
        if not self.ocr_results:
            QMessageBox.warning(self, "Warning", "No results to save. Please perform OCR first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Results", "", "Text Files (*.txt)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                for page in sorted(self.ocr_results.keys(), key=int):
                    f.write(self.ocr_results[page])
                    f.write(' ')  # Add a space between pages instead of a line break

            QMessageBox.information(self, "Success", f"Results saved successfully to {file_path}")

    def increase_font_size(self):
        font = self.extracted_text.font()
        font.setPointSize(font.pointSize() + 1)
        self.extracted_text.setFont(font)

    def decrease_font_size(self):
        font = self.extracted_text.font()
        if font.pointSize() > 1:
            font.setPointSize(font.pointSize() - 1)
            self.extracted_text.setFont(font)

    def choose_font(self):
        current_font = self.extracted_text.font()
        font, ok = QFontDialog.getFont(current_font, self)
        if ok:
            self.extracted_text.setFont(font)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont("Arial", 9))  # Set a default font
    ex = OCRApp()
    ex.show()
    sys.exit(app.exec_())