#!/usr/bin/env python3
import subprocess
import os
import re
import time
import threading
import queue
import tkinter as tk
from tkinter import messagebox, ttk

# --- LOGIC LAYER (BACKEND) ---
class DiskManager:
    """Handles all low-level OS operations. No GUI dependencies here."""
    
    def __init__(self):
        self.supported_fs = {
            "FAT32": "newfs_msdos -F 32 -L '{label}' {part}",
            "UFS":   "newfs -L '{label}' {part}",
            "exFAT": "mkexfatfs -n '{label}' {part}",
            "EXT4":  "mke2fs -t ext4 -L '{label}' {part}"
        }
        self.fs_mount_types = {
            "exfat": "mount.exfat",
            "msdosfs": "-t msdosfs",
            "fat": "-t msdosfs",
            "ext": "-t ext2fs",
            "ntfs": "-t ntfs"
        }

    def get_available_disks(self):
        """Returns safe-to-format disks with descriptions."""
        disks_info = []
        try:
            mount_res = subprocess.run("mount", shell=True, capture_output=True, text=True)
            root_devices = re.findall(r'/dev/(\w+)', mount_res.stdout)

            cmd_cam = "camcontrol devlist"
            res_cam = subprocess.run(cmd_cam, shell=True, capture_output=True, text=True)
            pattern = re.compile(r'<(.*?)>.*?\((da\d+),')
            
            for match in pattern.finditer(res_cam.stdout):
                description = match.group(1).strip()
                dev_name = match.group(2).strip()

                if not any(dev_name in rd for rd in root_devices):
                    disks_info.append({"dev": dev_name, "desc": description})
        except Exception as e:
            print(f"Discovery error: {e}")
        return disks_info

    def get_partition_path(self, disk_id):
        for suffix in ["p1", "s1", ""]:
            path = f"/dev/da{disk_id}{suffix}"
            if os.path.exists(path): return path
        return None

    def get_fs_type(self, path):
        res = subprocess.run(f"sudo fstyp {path}", shell=True, capture_output=True, text=True)
        return res.stdout.strip().lower()

    def get_mount_point(self, dev_name):
        try:
            res = subprocess.run("mount", shell=True, capture_output=True, text=True)
            for line in res.stdout.splitlines():
                if f"/dev/{dev_name}" in line:
                    return line.split(" on ")[1].split(" (")[0].strip()
        except: pass
        return None

    def get_mount_command(self, partition, target, fs_type):
        fs_type = fs_type.lower()
        for key, flag in self.fs_mount_types.items():
            if key in fs_type:
                if "exfat" in key: return f"sudo {flag} {partition} {target}"
                return f"sudo mount {flag} {partition} {target}"
        return f"sudo mount {partition} {target}"

    def format(self, disk_id, fs_label, fs_type, log_cb):
        dev = f"/dev/da{disk_id}"
        part = f"{dev}p1"
        try:
            log_cb(f"Preparing {dev}...")
            subprocess.run("sudo sysctl kern.geom.debugflags=16", shell=True)
            subprocess.run(f"sudo umount -f {dev}* 2>/dev/null", shell=True)
            subprocess.run(f"sudo gpart destroy -F {dev}", shell=True)
            subprocess.run(f"sudo gpart create -s gpt {dev}", shell=True)
            subprocess.run(f"sudo gpart add -t ms-basic-data {dev}", shell=True)
            
            cmd = self.supported_fs[fs_type].format(label=fs_label, part=part)
            log_cb(f"Formatting: {cmd}")
            res = subprocess.run(f"sudo {cmd}", shell=True, capture_output=True, text=True)
            
            if res.returncode == 0:
                subprocess.run(f"sudo true > {dev}", shell=True)
                subprocess.run(f"sudo gpart recover da{disk_id}", shell=True)
                time.sleep(1)
                return True, "Success"
            return False, res.stderr
        except Exception as e: return False, str(e)

# --- PRESENTATION LAYER (GUI) ---
class GhostFormatGUI:
    def __init__(self, root, manager):
        self.root = root
        self.manager = manager
        self.log_queue = queue.Queue()
        self.root.title("GhostFormat")
        self.root.geometry("550x680")
        self._setup_ui()
        self.root.after(100, self._process_logs)

    def _setup_ui(self):
        style = ttk.Style()
        style.configure("TButton", font=("Segoe UI", 10))
        
        main = ttk.Frame(self.root, padding="20")
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="Select USB Drive:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.disk_cb = ttk.Combobox(main, state="readonly")
        self.disk_cb.pack(fill=tk.X, pady=5)
        self.disk_cb.bind("<<ComboboxSelected>>", lambda e: self._update_ui_state())
        
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_disks).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.mount_btn = ttk.Button(btn_frame, text="Mount", command=self.handle_mount)
        self.mount_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        ttk.Separator(main, orient='horizontal').pack(fill='x', pady=15)

        ttk.Label(main, text="Format Settings:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.fs_cb = ttk.Combobox(main, state="readonly", values=list(self.manager.supported_fs.keys()))
        self.fs_cb.set("FAT32")
        self.fs_cb.pack(fill=tk.X, pady=5)

        self.label_entry = ttk.Entry(main)
        self.label_entry.insert(0, "GHOST_USB")
        self.label_entry.pack(fill=tk.X, pady=5)

        self.progress = ttk.Progressbar(main, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=10)

        self.log_widget = tk.Text(main, height=12, bg="#1e1e1e", fg="#00ff00", font=("Courier New", 10))
        self.log_widget.pack(fill=tk.BOTH, expand=True)

        self.format_btn = ttk.Button(main, text="START FORMATTING", command=self.start_format)
        self.format_btn.pack(fill=tk.X, pady=(10, 2))
        ttk.Button(main, text="Safe Eject", command=self.eject).pack(fill=tk.X)

        self.refresh_disks()

    def _process_logs(self):
        try:
            while True:
                self.log_widget.insert(tk.END, f"> {self.log_queue.get_nowait()}\n")
                self.log_widget.see(tk.END)
        except queue.Empty: pass
        self.root.after(100, self._process_logs)

    def thread_log(self, msg): self.log_queue.put(msg)

    def _update_ui_state(self, busy=False):
        state = "disabled" if busy else "normal"
        self.format_btn.config(state=state)
        self.mount_btn.config(state=state)
        
        if not busy and self.disk_cb.get():
            dev = self.disk_cb.get().split(" ")[0]
            self.mount_btn.config(text="Open Folder" if self.manager.get_mount_point(dev) else "Mount & Open")

    def refresh_disks(self):
        data = self.manager.get_available_disks()
        self.disk_cb['values'] = [f"{d['dev']} - {d['desc']}" for d in data]
        if data: self.disk_cb.current(0)
        self._update_ui_state()

    def handle_mount(self):
        sel = self.disk_cb.get()
        if not sel: return
        disk_id = sel.split(" ")[0].replace("da", "")
        self.progress.start(10)
        self._update_ui_state(True)
        threading.Thread(target=self._mount_worker, args=(disk_id,), daemon=True).start()

    def _mount_worker(self, disk_id):
        user = os.environ.get("SUDO_USER", os.environ.get("USER"))
        path = self.manager.get_partition_path(disk_id)
        mount_point = self.manager.get_mount_point(f"da{disk_id}")
        
        if mount_point:
            subprocess.run(f"sudo -u {user} xdg-open {mount_point}", shell=True)
        elif path:
            fs = self.manager.get_fs_type(path)
            target = f"/media/da{disk_id}"
            subprocess.run(f"sudo mkdir -p {target} && sudo chown {user} {target}", shell=True)
            cmd = self.manager.get_mount_command(path, target, fs)
            if subprocess.run(cmd, shell=True).returncode == 0:
                subprocess.run(f"sudo -u {user} xdg-open {target}", shell=True)
        
        self.root.after(0, self._action_finished)

    def start_format(self):
        sel = self.disk_cb.get()
        if not sel or not messagebox.askyesno("Confirm", f"Format {sel}?\nALL DATA WILL BE ERASED!"): return
        self._update_ui_state(True)
        self.progress.start(10)
        threading.Thread(target=self._format_worker, args=(sel.split(" ")[0].replace("da", ""), self.label_entry.get(), self.fs_cb.get()), daemon=True).start()

    def _format_worker(self, d_id, lbl, fs):
        success, msg = self.manager.format(d_id, lbl, fs, self.thread_log)
        self.root.after(0, lambda: self._format_finished(success, msg))

    def _format_finished(self, success, msg):
        self._action_finished()
        if success: messagebox.showinfo("Success", "Drive formatted!")
        else: messagebox.showerror("Error", msg)

    def _action_finished(self):
        self.progress.stop()
        self._update_ui_state(False)
        self.refresh_disks()

    def eject(self):
        sel = self.disk_cb.get()
        if sel:
            dev = sel.split(" ")[0]
            subprocess.run(f"sudo umount -f /dev/{dev}* 2>/dev/null", shell=True)
            subprocess.run(f"sudo camcontrol eject {dev}", shell=True)
            self.refresh_disks()

if __name__ == "__main__":
    if os.getuid() != 0:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Privilege Error", "GhostFormat requires root privileges.\nPlease run with sudo.")
        sys.exit(1)
    
    root = tk.Tk()
    app = GhostFormatGUI(root, DiskManager())
    root.mainloop()