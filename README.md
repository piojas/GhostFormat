# GhostFormat

A professional, lightweight GUI tool designed for **GhostBSD** and **FreeBSD** to safely format and manage USB drives. This tool solves common BSD-specific issues like "Device Busy" errors, GEOM structures not refreshing, and hybrid partition tables (e.g., Ventoy drives).

## 🚀 Key Features

* **Smart Device Discovery**: Automatically filters out system drives to prevent accidental data loss.
* **Multi-FS Support**: Format USB sticks to **FAT32, exFAT, EXT4,** or **UFS** with custom volume labels.
* **Advanced BSD Logic**: 
    * Handles `gpart` destruction and GPT creation automatically.
    * Forces GEOM "retaste" to ensure the system sees new partitions immediately.
    * Fixed mounting logic for **Ventoy** and MBR/GPT hybrid drives.
* **Real-time System Logs**: Built-in terminal emulator showing exact shell commands and system output.
* **Safe Operations**: Threaded backend ensures the UI never freezes during long formatting tasks.

## 🛠 Prerequisites

To run this tool, you need:
* **GhostBSD** or **FreeBSD** (Tested on 13.x/14.x)
* **Python 3.x**
* **Tkinter** (`pkg install python3 py39-tkinter`)
* **Root privileges** (Sudo access required for disk operations)

## 📦 Installation & Usage

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/piojas/GhostFormat.git
    cd GhostFormat
    ```

2.  **Install System Dependencies:**
    GhostFormat requires Python 3 and Tkinter. On GhostBSD/FreeBSD, run:
    ```bash
    sudo pkg install python3 py3x-tkinter
    ```
    *(Note: Replace `py3x` with your current Python version, e.g., `py39` or `py311`)*

3.  **Set Executable Permissions:**
    ```bash
    chmod +x ghostformat.py
    ```

4.  **Run the application:**
    The application requires root privileges for disk operations:
    ```bash
    sudo ./ghostformat.py
    ```

## 🏗 Architecture (SOLID Principles)

This project was built with maintainability and clean code in mind:
* **DiskManager (Logic Layer)**: Encapsulates all OS-level calls (gpart, mount, camcontrol). No GUI dependencies.
* **GhostFormatGUI (Presentation Layer)**: Handles user interaction, threading, and safe UI updates.
* **Thread-Safe Logging**: Uses `queue.Queue` to safely pass system messages from background workers to the main GUI thread.

## 🖥 Desktop Integration (Optional)

To add GhostFormat to your system menu, you can create a `.desktop` entry:
1. Copy `ghostformat.desktop` to `/usr/local/share/applications/`.
2. Update the `Exec` and `Icon` paths in the file to match your installation directory.

## ⚠️ Disclaimer

**WARNING:** Formatting a disk erases all data. While this tool includes safety filters to hide system drives, always double-check the device name (e.g., `da0`) before proceeding. Use at your own risk.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.