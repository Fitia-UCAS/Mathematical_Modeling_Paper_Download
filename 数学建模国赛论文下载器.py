from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QFileDialog,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
)
from PySide6.QtUiTools import QUiLoader
import shutil
import requests
from lxml import etree
from PIL import Image, ImageFilter  # 添加ImageFilter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import webbrowser
from PySide6.QtCore import Signal, QObject


class mySignal(QObject):
    speed_of_progress_Refresh = Signal(int)
    button_enable = Signal(bool)
    info_tip = Signal(QWidget, str, str)


class paper_downloader:
    def __init__(self):
        self.ui = QUiLoader().load("download.ui")
        self.img_temp_folder = "图片"
        self.check_and_create_folder(self.img_temp_folder)
        self.folder_address = None
        self.ui.pushButton.clicked.connect(self.handleCalc)
        self.ui.pushButton_2.clicked.connect(self.fill_in_the_text_box)
        self.ui.progressBar.setRange(0, 100)
        self.ui.pushButton_3.clicked.connect(
            lambda: webbrowser.open(
                "https://dxs.moe.gov.cn/zx/hd/sxjm/sxjmlw/qkt_sxjm_lw_lwzs.shtml"
            )
        )
        self.ui.label_3.setOpenExternalLinks(True)
        self.workers = 1
        self.mySignal = mySignal()
        self.mySignal.speed_of_progress_Refresh.connect(self.ui.progressBar.setValue)
        self.mySignal.button_enable.connect(self.ui.pushButton.setEnabled)
        self.mySignal.info_tip.connect(QMessageBox.warning)

    def fill_in_the_text_box(self):
        self.ui.lineEdit_2.setText(self.select_folder())

    def handleCalc(self):
        url = self.ui.lineEdit.text()
        pdf_path = self.ui.lineEdit_2.text()
        if not url:
            self.mySignal.info_tip.emit(self.ui, "警告", "请输入下载链接")
        else:
            if not pdf_path:
                self.mySignal.info_tip.emit(self.ui, "警告", "请输入保存路径")
                return
            else:
                t = threading.Thread(target=self.down_, args=(url,))
                t.start()

    def get_imgs_thread(self, i, v):
        try:
            r = requests.get(v, timeout=10)
            r.raise_for_status()
            print(f"正在下载第{i}张图片,图片地址为{v}")
            img_path = f"{self.img_temp_folder}/{i}.png"
            with open(img_path, "wb") as f:
                f.write(r.content)
            # 图像锐化
            with Image.open(img_path) as img:
                sharpened_img = img.filter(ImageFilter.SHARPEN)
                sharpened_img.save(img_path)
        except requests.RequestException as e:
            print(f"下载图片失败: {e}")

    def down_(self, url):
        self.mySignal.button_enable.emit(False)
        txt_url, name = self.get_img_urls(url)
        for index, i in enumerate(txt_url):
            if not i.startswith("https"):
                txt_url[index] = "https://dxs.moe.gov.cn/" + i
        self.txt_url = txt_url
        completed_count = 0
        if self.ui.checkBox.isChecked():
            self.workers = self.ui.spinBox.value()
        else:
            self.workers = 1
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            print("workers:", self.workers)
            future = {
                executor.submit(self.get_imgs_thread, index, i): index
                for index, i in enumerate(txt_url)
            }
            for future_ in as_completed(future):
                try:
                    future_.result()
                except Exception as e:
                    self.mySignal.info_tip.emit(self.ui, "警告", f"任务出错: {e}")
                    print(f"任务出错: {e}")
                else:
                    completed_count += 1
                    print(f"已完成 {completed_count} 个任务")
                    self.mySignal.speed_of_progress_Refresh.emit(
                        int(completed_count / len(txt_url) * 99)
                    )

        folder_path = self.img_temp_folder
        folder_address = self.ui.lineEdit_2.text()
        output_path = os.path.join(folder_address, f"{name}.pdf")
        images = self.get_images(folder_path)
        print(f"正在生成{name}.pdf")
        self.images_to_pdf(images, output_path)
        self.delete_folder_contents(folder_path)
        self.ui.progressBar.setValue(100)
        self.mySignal.info_tip.emit(self.ui, "提示", "下载完成")
        self.mySignal.button_enable.emit(True)

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self.ui, "选择文件夹")
        print(folder_path)
        if folder_path:
            return folder_path
        else:
            return None

    def delete_folder_contents(self, folder_path):
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)

    def get_images(self, folder_path):
        imgs = []
        d = len(os.listdir(folder_path))
        for i in range(d):
            imgs.append(os.path.join(folder_path, f"{i}.png"))
        return imgs

    def images_to_pdf(self, images, output_path):
        c = canvas.Canvas(output_path, pagesize=letter)
        for image_path in images:
            with Image.open(image_path, mode="r") as image:
                width, height = image.size
                aspect_ratio = height / float(width)
                new_height = aspect_ratio * letter[0]
                c.setPageSize((letter[0], new_height))
                c.drawImage(image_path, 0, 0, letter[0], new_height)
                c.showPage()
        c.save()

    def get_img_urls(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
            "Referer": "https://www.google.com/",
            "Accept-Encoding": "gzip, deflate, br",
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"请求失败: {e}")
            return [], "未命名论文"

        html = etree.HTML(response.text)
        links = html.xpath('//div[@class="imgslide-wra"]/img/@src')
        name = html.xpath("//h1/text()") or html.xpath("//title/text()")

        if name:
            paper_name = name[0].strip()
        else:
            paper_name = "未命名论文"
            print("警告：未找到论文标题，使用默认名称。")

        return links, paper_name

    def check_and_create_folder(self, folder_name):
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            print(f"文件夹 '{folder_name}' 已创建。")
        else:
            print(f"文件夹 '{folder_name}' 已存在。")


if __name__ == "__main__":
    app = QApplication([])
    app.setWindowIcon(QIcon("f.ico"))
    paper_downloader = paper_downloader()
    paper_downloader.ui.show()
    app.exec()
