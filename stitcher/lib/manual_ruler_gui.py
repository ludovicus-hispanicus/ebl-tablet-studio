import tkinter as tk
from tkinter import messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import math


class ManualRulerDrawer:
    def __init__(self, image_path):
        self.image_path = image_path
        self.px_per_cm = None
        self.start_point = None
        self.end_point = None
        self.drawing = False
        
        self.root = tk.Toplevel()
        self.root.title("Manual Ruler Measurement - Draw 1 cm Line")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._load_and_display_image()
        self._create_instructions()
        self._create_buttons()
        
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        
        self.root.grab_set()
        
    def _load_and_display_image(self):
        self.original_image = cv2.imread(self.image_path)
        if self.original_image is None:
            raise ValueError(f"Could not load image: {self.image_path}")
        
        self.display_image = self.original_image.copy()
        
        max_width = 1200
        max_height = 800
        height, width = self.original_image.shape[:2]
        
        scale_w = max_width / width if width > max_width else 1.0
        scale_h = max_height / height if height > max_height else 1.0
        self.display_scale = min(scale_w, scale_h, 1.0)
        
        if self.display_scale < 1.0:
            new_width = int(width * self.display_scale)
            new_height = int(height * self.display_scale)
            self.display_image = cv2.resize(
                self.display_image, (new_width, new_height), 
                interpolation=cv2.INTER_AREA
            )
        
        self.canvas_width = self.display_image.shape[1]
        self.canvas_height = self.display_image.shape[0]
        
        self.canvas = tk.Canvas(
            self.root, 
            width=self.canvas_width, 
            height=self.canvas_height,
            cursor="crosshair"
        )
        self.canvas.pack(padx=10, pady=10)
        
        self._update_canvas()
        
    def _create_instructions(self):
        instruction_frame = tk.Frame(self.root)
        instruction_frame.pack(pady=5)
        
        instruction_text = "Draw a line representing exactly 1 cm on the ruler in the photograph"
        tk.Label(
            instruction_frame, 
            text=instruction_text,
            font=("Arial", 11, "bold")
        ).pack()
        
        self.status_label = tk.Label(
            instruction_frame,
            text="Click and drag to draw a line",
            font=("Arial", 9),
            fg="gray"
        )
        self.status_label.pack()
        
    def _create_buttons(self):
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        tk.Button(
            button_frame,
            text="Clear Line",
            command=self._clear_line,
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="Confirm",
            command=self._confirm,
            width=12,
            bg="#4CAF50",
            fg="white"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel,
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
    def _on_mouse_down(self, event):
        self.start_point = (event.x, event.y)
        self.end_point = (event.x, event.y)
        self.drawing = True
        
    def _on_mouse_drag(self, event):
        if self.drawing:
            self.end_point = (event.x, event.y)
            self._update_canvas()
            self._update_status()
            
    def _on_mouse_up(self, event):
        if self.drawing:
            self.end_point = (event.x, event.y)
            self.drawing = False
            self._update_canvas()
            self._update_status()
            
    def _update_canvas(self):
        temp_image = self.display_image.copy()
        
        if self.start_point and self.end_point:
            cv2.line(
                temp_image,
                self.start_point,
                self.end_point,
                (0, 255, 0),
                2
            )
            
            cv2.circle(temp_image, self.start_point, 4, (0, 0, 255), -1)
            cv2.circle(temp_image, self.end_point, 4, (0, 0, 255), -1)
        
        rgb_image = cv2.cvtColor(temp_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)
        self.photo = ImageTk.PhotoImage(pil_image)
        
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        
    def _update_status(self):
        if self.start_point and self.end_point:
            dx = self.end_point[0] - self.start_point[0]
            dy = self.end_point[1] - self.start_point[1]
            length_display = math.sqrt(dx*dx + dy*dy)
            length_original = length_display / self.display_scale
            
            direction = "horizontal" if abs(dx) > abs(dy) else "vertical"
            
            self.status_label.config(
                text=f"Line length: {length_original:.1f} px ({direction}) - "
                     f"This will represent 1 cm"
            )
        else:
            self.status_label.config(text="Click and drag to draw a line")
            
    def _clear_line(self):
        self.start_point = None
        self.end_point = None
        self._update_canvas()
        self._update_status()
        
    def _confirm(self):
        if not self.start_point or not self.end_point:
            messagebox.showwarning(
                "No Line Drawn",
                "Please draw a line representing 1 cm before confirming."
            )
            return
            
        dx = self.end_point[0] - self.start_point[0]
        dy = self.end_point[1] - self.start_point[1]
        length_display = math.sqrt(dx*dx + dy*dy)
        
        if length_display < 10:
            messagebox.showwarning(
                "Line Too Short",
                "The line is too short. Please draw a longer line for accurate measurement."
            )
            return
            
        length_original = length_display / self.display_scale
        
        self.px_per_cm = length_original
        
        print(f"Manual ruler measurement: {self.px_per_cm:.2f} px/cm")
        
        self.root.destroy()
        
    def _cancel(self):
        self.px_per_cm = None
        self.root.destroy()
        
    def _on_close(self):
        self._cancel()
        
    def get_result(self):
        self.root.wait_window()
        return self.px_per_cm


def get_manual_ruler_measurement(image_path):
    try:
        drawer = ManualRulerDrawer(image_path)
        px_per_cm = drawer.get_result()
        return px_per_cm
    except Exception as e:
        print(f"Error in manual ruler measurement: {e}")
        return None
