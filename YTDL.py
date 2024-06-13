from tkinter import messagebox, filedialog
from pytube import YouTube
from PIL import Image, ImageDraw, ImageOps
import win32clipboard as cb
import customtkinter as ctk
import urllib.request
import io
import asyncio
import ctypes
import re
import time
import threading
import sys
import os
import subprocess


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


ctk.set_appearance_mode("system")
ctk.set_default_color_theme(resource_path("./red_theme.json"))


class WebImage:
    def __init__(self, url):
        with urllib.request.urlopen(url) as u:
            raw_data = u.read()
        image = Image.open(io.BytesIO(raw_data))
        size = self.resize_to_max_percentage(image.width, image.height)
        image = self.round_corners(image, size)
        self.image = ctk.CTkImage(image, size=size)

    def get(self):
        return self.image

    @staticmethod
    def resize_to_max_percentage(width, height):
        window_width, window_height = 660 * 0.5, 500 * 0.5
        aspect_ratio = width / height

        if width > height:
            new_width = min(window_width, width * window_height / height)
            new_height = new_width / aspect_ratio
        else:
            new_height = min(window_height, height * window_width / width)
            new_width = new_height * aspect_ratio

        return int(new_width), int(new_height)

    @staticmethod
    def round_corners(image, size, radius=20):
        image = image.resize(size, Image.LANCZOS)

        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)

        draw.rounded_rectangle((0, 0) + size, radius=radius, fill=255)

        rounded_image = ImageOps.fit(image, mask.size, centering=(0.5, 0.5))
        rounded_image.putalpha(mask)

        return rounded_image


class YouTubeDownloaderApp:
    def __init__(self):
        self.yt = None
        self.sizes = {}
        self.download_process = None
        self.start_time = None
        self.last_time = None
        self.window_width = 660
        self.window_height = 500
        self.download_directory = os.path.expanduser("~")

        self.root = ctk.CTk()
        self.root.title("YouTube Video Downloader")
        self.root.iconbitmap(resource_path("./icon.ico"))
        self.root.minsize(width=self.window_width, height=self.window_height)
        self.root.geometry(f"{self.window_width}x{self.window_height}")

        self.init_ui()

    def init_ui(self):
        self.frame_begin = ctk.CTkFrame(master=self.root)
        self.frame_begin.pack(pady=20, padx=60, fill="both", expand=True)

        main_label = ctk.CTkLabel(
            master=self.frame_begin, text="YTDL by Dimokat", font=("Roboto", 24)
        )
        main_label.pack(pady=12, padx=10)

        self.link_var = ctk.StringVar()
        self.link_var.trace_add("write", self.run_get)
        self.link_entry = ctk.CTkEntry(self.frame_begin, textvariable=self.link_var)
        self.link_entry.pack(pady=12, padx=10)

        paste_button = ctk.CTkButton(
            self.frame_begin, text="Paste", command=self.paste_from_clipboard
        )
        paste_button.pack(pady=12, padx=10)

        self.frame_searching = ctk.CTkFrame(master=self.root)
        status_title = ctk.CTkLabel(
            self.frame_searching, text="Getting info...", font=("Roboto", 24)
        )
        status_title.pack(pady=62, padx=10)

        self.frame_video_options = ctk.CTkFrame(master=self.root)
        return_button = ctk.CTkButton(
            self.frame_video_options,
            text="<",
            width=30,
            height=30,
            command=self.return_to_main_state,
        )
        return_button.place(x=10, y=12)

        self.video_thumbnail_label = ctk.CTkLabel(self.frame_video_options, text="")
        self.video_thumbnail_label.pack(pady=12, padx=10)

        self.video_title_label = ctk.CTkLabel(
            self.frame_video_options, text="", font=("Roboto", 20)
        )
        self.video_title_label.pack(pady=12, padx=10)

        self.size_label = ctk.CTkLabel(self.frame_video_options, text="")
        self.size_label.pack(padx=10)

        self.resolution_options_menu = ctk.CTkOptionMenu(
            self.frame_video_options, command=self.change_size_label
        )
        self.resolution_options_menu.pack(pady=12, padx=10)

        download_button = ctk.CTkButton(
            self.frame_video_options, text="Download", command=self.open_download_dialog
        )
        download_button.pack(pady=12, padx=10)

        self.frame_video_download = ctk.CTkFrame(master=self.root)
        cancel_button = ctk.CTkButton(
            self.frame_video_download,
            text="<",
            width=30,
            height=30,
            command=self.cancel_download,
        )
        cancel_button.place(x=10, y=12)

        self.video_thumbnail_label1 = ctk.CTkLabel(self.frame_video_download, text="")
        self.video_thumbnail_label1.pack(pady=12, padx=10)

        self.video_title_label1 = ctk.CTkLabel(
            self.frame_video_download, text="", font=("Roboto", 20)
        )
        self.video_title_label1.pack(pady=12, padx=10)

        self.progress_bar = ctk.CTkProgressBar(
            self.frame_video_download, orientation="horizontal", mode="determinate"
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=12, padx=10)

        self.progress_label = ctk.CTkLabel(self.frame_video_download, text="")
        self.progress_label.pack(padx=10)

        self.down_progress_label = ctk.CTkLabel(self.frame_video_download, text="")
        self.down_progress_label.pack(padx=10)

        self.speed_label = ctk.CTkLabel(self.frame_video_download, text="")
        self.speed_label.pack(padx=10)

        self.average_speed_label = ctk.CTkLabel(self.frame_video_download, text="")
        self.average_speed_label.pack(padx=10)

        self.eta_label = ctk.CTkLabel(self.frame_video_download, text="")
        self.eta_label.pack(pady=12, padx=10)

    def paste_from_clipboard(self):
        cb.OpenClipboard()
        data = cb.GetClipboardData()
        cb.CloseClipboard()
        self.link_entry.delete(0, ctk.END)
        self.link_entry.insert(0, data)

    def is_youtube_url(self, url: str) -> bool:
        try:
            youtube_regex = (
                r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/"
            )
            match = re.match(youtube_regex, url)
            return match is not None
        except:
            return False

    def run_get(self, *args):
        asyncio.run(self.get_info())

    def change_size_label(self, *args):
        res = self.resolution_options_menu.get()
        self.size_label.configure(True, text=f"{self.sizes[res][0]}MB")

    async def get_info(self):
        url = self.link_var.get()
        if self.is_youtube_url(url):
            self.frame_begin.pack_forget()
            self.frame_searching.pack(pady=20, padx=60, fill="both", expand=True)
            self.root.update()

            self.yt = YouTube(url, on_progress_callback=self.show_progress)
            self.frame_searching.pack_forget()

            url = self.yt.thumbnail_url
            img = WebImage(url).get()

            self.frame_video_options.pack(pady=20, padx=60, fill="both", expand=True)
            self.video_thumbnail_label.configure(image=img)
            self.video_title_label.configure(text=self.yt.title)
            self.video_thumbnail_label1.configure(image=img)
            self.video_title_label1.configure(text=self.yt.title)

            self.sizes = {}
            video_resolutions = []
            video_streams = self.yt.streams.filter(only_video=True)
            for stream in video_streams:
                if stream.resolution not in video_resolutions:
                    video_resolutions.append(stream.resolution)
                    self.sizes[stream.resolution] = [stream.filesize_mb, stream]

            audio_streams = self.yt.streams.filter(only_audio=True)
            audio_bitrates = []
            for stream in audio_streams:
                if stream.abr not in audio_bitrates:
                    audio_bitrates.append(stream.abr)
                    self.sizes[stream.abr] = [stream.filesize_mb, stream]

            if not self.sizes:
                messagebox.showwarning(
                    "Not found", "Not found any streams for this video"
                )
                self.return_to_main_state()
                return

            resolutions = sorted(video_resolutions, key=self.key) + sorted(
                audio_bitrates, key=self.key
            )
            self.resolution_options_menu.configure(
                require_redraw=True, values=resolutions
            )
            self.resolution_options_menu.set(resolutions[0])
            self.size_label.configure(True, text=f"{self.sizes[resolutions[0]][0]}MB")

    def key(self, res):
        return int(re.sub("\D", "", res))

    def show_progress(self, stream, chunk, bytes_remaining):
        if self.start_time is None:
            self.start_time = time.time()
        if self.last_time is None:
            self.last_time = time.time()
        timeout = time.time() - self.last_time
        if timeout == 0:
            timeout = 0.1
        elapsed_time = time.time() - self.start_time
        if elapsed_time == 0:
            elapsed_time = 0.1
        current = (stream.filesize - bytes_remaining) / stream.filesize
        percent = ("{0:.1f}").format(current * 100)
        total_size = stream.filesize_mb
        total_downloaded = (stream.filesize - bytes_remaining) / (1024 * 1024)
        current_speed = (len(chunk) / (1024)) / timeout
        average_speed = (total_downloaded / elapsed_time) * 1024
        remaining_time = (total_size - total_downloaded) / (average_speed / 1024)
        minutes, seconds = divmod(remaining_time, 60)
        eta = f"{int(minutes)}m {int(seconds)}s"
        self.last_time = time.time()

        self.progress_bar.set(current)
        self.progress_label.configure(text=f"{percent}%")
        self.down_progress_label.configure(
            text=f"{total_downloaded:.2f}/{total_size:.2f}MB"
        )
        self.speed_label.configure(text=f"Current Speed: {current_speed:.2f}KB/s")
        self.average_speed_label.configure(text=f"Avg Speed: {average_speed:.2f}KB/s")
        self.eta_label.configure(text=f"ETA: {eta}")

    def download_video(self, link, resolution):
        try:
            video_stream = self.sizes[resolution][1]
            if video_stream:
                filename = video_stream.default_filename
                path = os.path.join(self.download_directory, filename)
                path = os.path.normpath(path)
                video_stream.download(output_path=self.download_directory)
                if sys.platform == "win32":
                    subprocess.Popen(f'explorer /select,"{path}"')
                self.return_to_main_state()
            else:
                self.return_to_main_state()
                messagebox.showerror(
                    "Error", "No video stream found with the specified resolution."
                )
        except SystemExit:
            return
        except Exception as e:
            self.return_to_main_state()
            messagebox.showerror("Error", str(e))

    def start_download(self):
        res = self.resolution_options_menu.get()
        self.frame_video_options.pack_forget()
        self.frame_video_download.pack(pady=20, padx=60, fill="both", expand=True)
        self.download_process = threading.Thread(
            target=self.download_video, daemon=True, args=(None, res)
        )
        self.download_process.start()

    def open_download_dialog(self):
        self.download_directory = filedialog.askdirectory()
        if self.download_directory:
            self.start_download()

    def cancel_download(self):
        self.raise_exception_in_thread(self.download_process.ident, SystemExit)
        self.frame_video_download.pack_forget()
        self.frame_video_options.pack(pady=20, padx=60, fill="both", expand=True)

    def raise_exception_in_thread(self, thread_id, exception_type):
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_long(thread_id), ctypes.py_object(exception_type)
        )
        if res == 0:
            raise ValueError("Invalid thread ID")
        elif res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    def return_to_main_state(self):
        if self.is_frame_packed(self.frame_searching):
            self.frame_searching.pack_forget()
        if self.is_frame_packed(self.frame_video_options):
            self.frame_video_options.pack_forget()
        if self.is_frame_packed(self.frame_video_download):
            self.frame_video_download.pack_forget()
        self.frame_begin.pack(pady=20, padx=60, fill="both", expand=True)

        self.link_entry.delete(0, ctk.END)
        self.start_time = None
        self.last_time = None
        self.yt = None
        self.sizes = {}
        self.download_process = None

    def is_frame_packed(self, frame):
        return frame.winfo_manager() != ""


if __name__ == "__main__":
    app = YouTubeDownloaderApp()
    app.root.mainloop()
