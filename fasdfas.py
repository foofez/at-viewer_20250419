import tkinter as tk
from tkinter import ttk
import requests
from bs4 import BeautifulSoup

# URL
url = 'https://foofez.tistory.com/2'

# tkinter 애플리케이션 생성
app = tk.Tk()
app.title('Web Content Viewer')

# Text 위젯 생성
text_widget = tk.Text(app, wrap=tk.WORD)
text_widget.pack(fill='both', expand=True)

# URL에서 내용 가져와서 Text 위젯에 표시
def load_content():
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    ins_tag = soup.find('ins', {'class': 'adsbygoogle'})
    
    if ins_tag:
        content = str(ins_tag)
        text_widget.delete('1.0', tk.END)
        text_widget.insert('1.0', content)
    else:
        text_widget.delete('1.0', tk.END)
        text_widget.insert('1.0', 'Content not found.')

# 페이지 로드 버튼 생성
load_button = ttk.Button(app, text='Load Content', command=load_content)
load_button.pack()

app.mainloop()
