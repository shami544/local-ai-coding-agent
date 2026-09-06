import os
import sys
import ctypes
import customtkinter as ctk
from gui import CodingAgentApp


def enable_windows_dpi():
    """Enable crisp font rendering on high-DPI Windows displays."""
    if sys.platform == "win32":
        try:
            # Per-monitor DPI aware (Windows 8.1+)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                # System DPI aware (Windows Vista+)
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def main():
    enable_windows_dpi()

    root = ctk.CTk()
    app = CodingAgentApp(root)

    # Center window on screen
    root.update_idletasks()
    width = 1150
    height = 850
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")

    try:
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
