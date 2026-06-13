import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import socket
import threading
import json
import os
import struct
import time
from datetime import datetime

# --- Settings & Constants ---
PORT = 6000  # Application Port
BUFFER_SIZE = 4096
DB_FILE = "history.json"
DOWNLOAD_DIR = "downloads"

# Modern Color Palette
COLOR_BG = "#f0f2f5"        # Main Background
COLOR_SIDEBAR = "#2c3e50"   # Sidebar
COLOR_BTN = "#2980b9"       # Buttons
COLOR_BTN_HOVER = "#3498db" # Button Hover
COLOR_TEXT_LIGHT = "#ecf0f1"
COLOR_TEXT_DARK = "#2c3e50"

# Authorized Users
USERS = {
    "sara": "1234",
    "emma": "1234",
    "mike": "1234"
}

# Ensure download directory exists
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# --- Data Management (JSON) ---
class DataManager:
    @staticmethod
    def load_data():
        if not os.path.exists(DB_FILE):
            return {"sent": [], "received": []}
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"sent": [], "received": []}

    @staticmethod
    def save_entry(section, entry):
        data = DataManager.load_data()
        # Initialize key if missing
        if section not in data:
            data[section] = []
        data[section].append(entry)
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

# --- P2P Networking Class ---
class P2PNetwork:
    def __init__(self, update_callback):
        self.update_callback = update_callback  # Function to update UI
        self.running = True
        
        # Start server in a separate thread
        server_thread = threading.Thread(target=self.start_server, daemon=True)
        server_thread.start()

    def start_server(self):
        """Listen on port for incoming messages"""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("0.0.0.0", PORT))
            s.listen(5)
            print(f"Server listening on port {PORT}")
            
            while self.running:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        except Exception as e:
            print(f"Server Error: {e}")

    def handle_client(self, conn, addr):
        """Process incoming message"""
        try:
            # 1. Read header length (4 bytes)
            header_len_data = conn.recv(4)
            if not header_len_data: return
            header_len = struct.unpack("!I", header_len_data)[0]
            
            # 2. Read JSON header
            header_data = conn.recv(header_len)
            header = json.loads(header_data.decode("utf-8"))
            
            sender = header.get("sender", "Unknown")
            msg_type = header.get("type", "text")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

            if msg_type == "text":
                content = header.get("content", "")
                entry = {
                    "from": sender,
                    "ip": addr[0],
                    "content": content,
                    "type": "text",
                    "time": timestamp
                }
                DataManager.save_entry("received", entry)
                self.update_callback("New text message received!")

            elif msg_type == "file":
                filename = header.get("filename", "unknown_file")
                filesize = header.get("filesize", 0)
                
                # Unique filename to prevent overwrite
                save_path = os.path.join(DOWNLOAD_DIR, f"{int(time.time())}_{filename}")
                
                # Receive file content
                received = 0
                with open(save_path, "wb") as f:
                    while received < filesize:
                        chunk = conn.recv(min(BUFFER_SIZE, filesize - received))
                        if not chunk: break
                        f.write(chunk)
                        received += len(chunk)
                
                entry = {
                    "from": sender,
                    "ip": addr[0],
                    "content": f"File: {filename}",
                    "path": save_path,
                    "type": "file",
                    "time": timestamp
                }
                DataManager.save_entry("received", entry)
                self.update_callback(f"File received: {filename}")

        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            conn.close()

    def send_packet(self, target_ip, sender_name, content, file_path=None):
        """Send message or file"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)  # Connection timeout
            s.connect((target_ip, PORT))
            
            msg_type = "file" if file_path else "text"
            filesize = os.path.getsize(file_path) if file_path else 0
            filename = os.path.basename(file_path) if file_path else ""

            # Build Header
            header = {
                "sender": sender_name,
                "type": msg_type,
                "content": content,
                "filename": filename,
                "filesize": filesize
            }
            
            header_json = json.dumps(header).encode("utf-8")
            header_len = struct.pack("!I", len(header_json))
            
            # Send Header Length + Header
            s.sendall(header_len + header_json)
            
            # Send file content if applicable
            if file_path:
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(BUFFER_SIZE)
                        if not chunk: break
                        s.sendall(chunk)

            s.close()
            return True, "Sent successfully."
        except Exception as e:
            return False, str(e)

# --- GUI Application ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("P2P Automation System")
        self.geometry("900x600")
        self.configure(bg=COLOR_BG)
        self.current_user = None
        
        # Fonts
        self.font_main = ("Segoe UI", 11)
        self.font_bold = ("Segoe UI", 12, "bold")
        self.font_header = ("Segoe UI", 16, "bold")

        self.show_login()

    def clear_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

    # --- Login Screen ---
    def show_login(self):
        self.clear_screen()
        
        frame = tk.Frame(self, bg="white", padx=40, pady=40, relief="raised", bd=1)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(frame, text="Login", font=self.font_header, bg="white", fg=COLOR_SIDEBAR).pack(pady=20)

        tk.Label(frame, text="Username:", font=self.font_main, bg="white").pack(anchor="w")
        user_entry = ttk.Entry(frame, font=self.font_main, width=25)
        user_entry.pack(pady=5)

        tk.Label(frame, text="Password:", font=self.font_main, bg="white").pack(anchor="w")
        pass_entry = ttk.Entry(frame, font=self.font_main, width=25, show="●")
        pass_entry.pack(pady=5)

        def attempt_login():
            u = user_entry.get()
            p = pass_entry.get()
            if u in USERS and USERS[u] == p:
                self.current_user = u
                self.network = P2PNetwork(self.on_notification)
                self.show_dashboard()
            else:
                messagebox.showerror("Error", "Invalid username or password")

        tk.Button(frame, text="Login", command=attempt_login, bg=COLOR_BTN, fg="white", 
                  font=self.font_bold, width=20, relief="flat").pack(pady=20)

    # --- Notifications ---
    def on_notification(self, msg):
        self.after(0, lambda: messagebox.showinfo("New Message", msg))

    # --- Main Dashboard ---
    def show_dashboard(self):
        self.clear_screen()

        # Sidebar
        sidebar = tk.Frame(self, bg=COLOR_SIDEBAR, width=200)
        sidebar.pack(side="left", fill="y")
        
        # Sidebar Header
        tk.Label(sidebar, text=f"User:\n{self.current_user}", bg=COLOR_SIDEBAR, fg="white", 
                 font=self.font_bold, pady=20).pack()

        # Sidebar Buttons
        btn_style = {"bg": COLOR_SIDEBAR, "fg": "white", "font": self.font_main, "relief": "flat", "bd": 0, "activebackground": COLOR_BTN, "pady": 10, "anchor": "w", "padx": 20}
        
        tk.Button(sidebar, text="✉ Send Message", command=self.page_send, **btn_style).pack(fill="x")
        tk.Button(sidebar, text="📥 Inbox", command=lambda: self.page_history("received"), **btn_style).pack(fill="x")
        tk.Button(sidebar, text="📤 Sent Items", command=lambda: self.page_history("sent"), **btn_style).pack(fill="x")
        tk.Button(sidebar, text="Log Out", command=self.show_login, **btn_style).pack(side="bottom", fill="x")

        # Content Area
        self.content_frame = tk.Frame(self, bg=COLOR_BG)
        self.content_frame.pack(side="right", expand=True, fill="both", padx=20, pady=20)
        
        self.page_send()  # Default page

    # --- Send Page ---
    def page_send(self):
        for w in self.content_frame.winfo_children(): w.destroy()

        tk.Label(self.content_frame, text="Send Message / File", font=self.font_header, bg=COLOR_BG, fg=COLOR_TEXT_DARK).pack(anchor="nw", pady=(0, 20))

        form_frame = tk.Frame(self.content_frame, bg="white", padx=20, pady=20)
        form_frame.pack(fill="x")

        # Fields
        tk.Label(form_frame, text="Receiver IP Address:", bg="white", font=self.font_main).pack(anchor="w")
        ent_ip = ttk.Entry(form_frame, font=self.font_main)
        ent_ip.pack(fill="x", pady=5)

        tk.Label(form_frame, text="Message:", bg="white", font=self.font_main).pack(anchor="w")
        txt_msg = tk.Text(form_frame, height=5, font=self.font_main, bg="#fafafa", bd=1)
        txt_msg.pack(fill="x", pady=5)

        # File Selection
        self.selected_file = None
        lbl_file = tk.Label(form_frame, text="No file selected", bg="white", fg="gray")
        lbl_file.pack(pady=5)

        def select_file():
            path = filedialog.askopenfilename()
            if path:
                self.selected_file = path
                lbl_file.config(text=f"File: {os.path.basename(path)}", fg="green")

        tk.Button(form_frame, text="📎 Attach File", command=select_file).pack(pady=5)

        # Send Button Logic
        def do_send():
            ip = ent_ip.get()
            msg = txt_msg.get("1.0", "end").strip()

            if not ip:
                messagebox.showwarning("Warning", "Please enter receiver IP.")
                return

            # Send packet
            success, status = self.network.send_packet(ip, self.current_user, msg, self.selected_file)
            
            if success:
                # Save to history
                entry = {
                    "to": "Unknown User", # Name removed from input, so just a placeholder
                    "to_ip": ip,
                    "content": msg + (f" [File: {os.path.basename(self.selected_file)}]" if self.selected_file else ""),
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                DataManager.save_entry("sent", entry)
                messagebox.showinfo("Success", "Message sent successfully.")
                
                # Clear form
                txt_msg.delete("1.0", "end")
                self.selected_file = None
                lbl_file.config(text="No file selected", fg="gray")
            else:
                messagebox.showerror("Error", f"Failed to send:\n{status}")

        tk.Button(form_frame, text="Send", bg=COLOR_BTN, fg="white", font=self.font_bold, 
                  command=do_send, padx=20, pady=5).pack(pady=15)

    # --- History Page (Sent/Received) ---
    def page_history(self, section):
        for w in self.content_frame.winfo_children(): w.destroy()
        
        title = "Sent Messages" if section == "sent" else "Inbox"
        tk.Label(self.content_frame, text=title, font=self.font_header, bg=COLOR_BG, fg=COLOR_TEXT_DARK).pack(anchor="nw", pady=(0, 20))

        # Scrollable List Container
        list_frame = tk.Frame(self.content_frame)
        list_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        canvas = tk.Canvas(list_frame, bg=COLOR_BG, yscrollcommand=scrollbar.set, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=canvas.yview)

        inner_frame = tk.Frame(canvas, bg=COLOR_BG)
        canvas.create_window((0, 0), window=inner_frame, anchor="nw", width=600)

        # Load Data
        data = DataManager.load_data().get(section, [])
        
        if not data:
            tk.Label(inner_frame, text="No messages found.", bg=COLOR_BG).pack(pady=20)

        # Display Cards (Newest first)
        for item in reversed(data):
            card = tk.Frame(inner_frame, bg="white", padx=15, pady=10, relief="flat")
            card.pack(fill="x", pady=5, padx=5)

            # Card Header
            if section == "sent":
                # Only showing IP since Name input was removed
                header_txt = f"To: {item.get('to_ip')} | {item.get('time')}"
                icon = "📤"
            else:
                header_txt = f"From: {item.get('from')} ({item.get('ip')}) | {item.get('time')}"
                icon = "📥"

            tk.Label(card, text=f"{icon} {header_txt}", font=("Segoe UI", 9, "bold"), fg="gray", bg="white").pack(anchor="nw")
            
            # Message Content
            content = item.get("content", "")
            tk.Label(card, text=content, font=("Segoe UI", 11), bg="white", justify="left", wraplength=500).pack(anchor="nw", pady=5)
            
            # File Button
            if "path" in item and os.path.exists(item["path"]):
                path = item["path"]
                def open_file(p=path):
                    try:
                        os.startfile(p)
                    except:
                        messagebox.showinfo("File Path", f"File saved at:\n{p}")
                
                tk.Button(card, text="📂 Open File", command=open_file, font=("Segoe UI", 9), bg="#eee").pack(anchor="nw")

        inner_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))


if __name__ == "__main__":
    app = App()
    app.mainloop()
