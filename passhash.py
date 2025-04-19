import hashlib
import tkinter as tk
from tkinter import messagebox
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

def verify_credentials(id):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Webtoonpass").sheet1
    data = sheet.get_all_records()

    for row in data:
        if row["ID"] == id:
            return False

    return True

def hash_password(password, algorithm='sha256'):
    hashed_password = hashlib.new(algorithm, password.encode()).hexdigest()
    return hashed_password

def hash_button_clicked():
    password = password_entry.get()
    hashed_password = hash_password(password)
    hash_text.delete(1.0, tk.END)  # Clear previous content
    hash_text.insert(tk.END, f"해시된 비밀번호:\n{hashed_password}")
    root.clipboard_clear()
    root.clipboard_append(hashed_password)

def register_user():
    id = id_entry.get()
    if not verify_credentials(id):
        messagebox.showerror("Error", "중복된 ID가 있습니다.")
    else:
        password = password_entry.get()
        hashed_password = hash_password(password)

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Webtoonpass").sheet1
        sheet.append_row([id, hashed_password, password])
        messagebox.showinfo("Success", "사용자 등록이 완료되었습니다.")

script_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(script_dir, 'atviewer-admin.json')

root = tk.Tk()
root.title("비밀번호 해시화")

# ID 입력창 추가
id_label = tk.Label(root, text="ID 입력:")
id_label.pack(pady=5)
id_entry = tk.Entry(root)
id_entry.pack(pady=5)

label = tk.Label(root, text="비밀번호 입력:")
label.pack(pady=5)
password_entry = tk.Entry(root)
password_entry.pack(pady=5)

hash_button = tk.Button(root, text="비밀번호 해시화", command=hash_button_clicked)
hash_button.pack(pady=10)

hash_text = tk.Text(root, wrap='word', height=2, font=('Helvetica', 12))
hash_text.pack(pady=5)

register_button = tk.Button(root, text="User 등록", command=register_user)
register_button.pack(pady=10)

root.mainloop()
