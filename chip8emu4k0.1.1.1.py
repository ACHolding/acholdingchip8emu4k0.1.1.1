import tkinter as tk
from tkinter import filedialog, messagebox
import random
import time

# ==========================================
# AC's Chip 8 Emulator 0.1.1
# Native Python Implementation (No mGBA)
# Theme: Black BG, Blue Text, Blue Hue Display
# ==========================================

class Chip8CPU:
    def __init__(self):
        self.memory = bytearray(4096)
        self.V = bytearray(16)          # V0-VF registers
        self.I = 0                      # Index register
        self.PC = 0x200                 # Program counter
        self.stack = []                 # Call stack
        self.delay_timer = 0
        self.sound_timer = 0
        self.display = bytearray(64 * 32)  # 64x32 pixels
        self.keys = bytearray(16)       # 16-key keypad
        self.draw_flag = False
        self.wait_for_key = None        # For 0xFx0A opcode
        self._load_fontset()

    def _load_fontset(self):
        # Standard Chip-8 4x5 font (0-F)
        font = [
            0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
            0x20, 0x60, 0x20, 0x20, 0x70,  # 1
            0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
            0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
            0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
            0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
            0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
            0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
            0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
            0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
            0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
            0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
            0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
            0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
            0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
            0xF0, 0x80, 0xF0, 0x80, 0x80,  # F
        ]
        self.memory[0:80] = bytearray(font)

    def load_rom(self, path):
        with open(path, 'rb') as f:
            rom = f.read()
        if len(rom) > 3584:
            raise ValueError("ROM too large for 4KB memory")
        # Clear program region so a shorter ROM cannot leave stale bytes behind.
        self.memory[0x200:0x200 + 3584] = b'\x00' * 3584
        self.memory[0x200:0x200 + len(rom)] = rom
        self.PC = 0x200
        self.V = bytearray(16)
        self.I = 0
        self.stack = []
        self.delay_timer = 0
        self.sound_timer = 0
        self.display = bytearray(64 * 32)
        self.keys = bytearray(16)
        self.wait_for_key = None
        self.draw_flag = True

    def key_press(self, key_index):
        if key_index < 0 or key_index > 15:
            return
        self.keys[key_index] = 1
        if self.wait_for_key is not None:
            self.V[self.wait_for_key] = key_index
            self.wait_for_key = None

    def key_release(self, key_index):
        if key_index < 0 or key_index > 15:
            return
        self.keys[key_index] = 0

    def cycle(self):
        if self.wait_for_key is not None:
            return

        if self.PC >= 0xFFF:
            return

        opcode = (self.memory[self.PC] << 8) | self.memory[self.PC + 1]
        self.PC += 2
        self._execute(opcode)

    def _execute(self, opcode):
        nnn = opcode & 0x0FFF
        n = opcode & 0x000F
        x = (opcode & 0x0F00) >> 8
        y = (opcode & 0x00F0) >> 4
        kk = opcode & 0x00FF

        match opcode & 0xF000:
            case 0x0000:
                match opcode:
                    case 0x00E0:
                        self.display = bytearray(64 * 32)
                        self.draw_flag = True
                    case 0x00EE:
                        if self.stack:
                            self.PC = self.stack.pop()
            case 0x1000:
                self.PC = nnn
            case 0x2000:
                self.stack.append(self.PC)
                self.PC = nnn
            case 0x3000:
                if self.V[x] == kk:
                    self.PC += 2
            case 0x4000:
                if self.V[x] != kk:
                    self.PC += 2
            case 0x5000:
                if self.V[x] == self.V[y]:
                    self.PC += 2
            case 0x6000:
                self.V[x] = kk
            case 0x7000:
                self.V[x] = (self.V[x] + kk) & 0xFF
            case 0x8000:
                match n:
                    case 0x0:
                        self.V[x] = self.V[y]
                    case 0x1:
                        self.V[x] |= self.V[y]
                    case 0x2:
                        self.V[x] &= self.V[y]
                    case 0x3:
                        self.V[x] ^= self.V[y]
                    case 0x4:
                        total = self.V[x] + self.V[y]
                        self.V[0xF] = 1 if total > 0xFF else 0
                        self.V[x] = total & 0xFF
                    case 0x5:
                        self.V[0xF] = 1 if self.V[x] >= self.V[y] else 0
                        self.V[x] = (self.V[x] - self.V[y]) & 0xFF
                    case 0x6:
                        # Modern CHIP-8: shift Vy, store in Vx
                        self.V[0xF] = self.V[y] & 1
                        self.V[x] = self.V[y] >> 1
                    case 0x7:
                        self.V[0xF] = 1 if self.V[y] >= self.V[x] else 0
                        self.V[x] = (self.V[y] - self.V[x]) & 0xFF
                    case 0xE:
                        # Modern CHIP-8: shift Vy, store in Vx
                        self.V[0xF] = (self.V[y] >> 7) & 1
                        self.V[x] = (self.V[y] << 1) & 0xFF
            case 0x9000:
                if self.V[x] != self.V[y]:
                    self.PC += 2
            case 0xA000:
                self.I = nnn
            case 0xB000:
                self.PC = (self.V[0] + nnn) & 0xFFF
            case 0xC000:
                self.V[x] = random.randint(0, 255) & kk
            case 0xD000:
                self.V[0xF] = 0
                for row in range(n):
                    sprite_byte = self.memory[(self.I + row) & 0xFFF]
                    for col in range(8):
                        if sprite_byte & (0x80 >> col):
                            px = (self.V[x] + col) % 64
                            py = (self.V[y] + row) % 32
                            idx = py * 64 + px
                            if self.display[idx]:
                                self.V[0xF] = 1
                            self.display[idx] ^= 1
                self.draw_flag = True
            case 0xE000:
                key = self.V[x] & 0x0F
                if kk == 0x9E and self.keys[key]:
                    self.PC += 2
                elif kk == 0xA1 and not self.keys[key]:
                    self.PC += 2
            case 0xF000:
                match kk:
                    case 0x07:
                        self.V[x] = self.delay_timer
                    case 0x0A:
                        self.wait_for_key = x
                    case 0x15:
                        self.delay_timer = self.V[x]
                    case 0x18:
                        self.sound_timer = self.V[x]
                    case 0x1E:
                        self.I = (self.I + self.V[x]) & 0xFFF
                    case 0x29:
                        self.I = self.V[x] * 5
                    case 0x33:
                        val = self.V[x]
                        self.memory[self.I] = val // 100
                        self.memory[(self.I + 1) & 0xFFF] = (val // 10) % 10
                        self.memory[(self.I + 2) & 0xFFF] = val % 10
                    case 0x55:
                        for i in range(x + 1):
                            self.memory[(self.I + i) & 0xFFF] = self.V[i]
                    case 0x65:
                        for i in range(x + 1):
                            self.V[i] = self.memory[(self.I + i) & 0xFFF]


class EmulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AC's Chip 8 Emulator 0.1.1")
        self.root.configure(bg="#000000")
        self.root.resizable(False, False)

        self.BLUE_TEXT = "#00AAFF"
        self.BLUE_HUE = "#0055CC"
        self.OFF_COLOR = "#000000"
        self.SCALE = 10

        self.cpu = Chip8CPU()

        self.canvas_width = 64 * self.SCALE
        self.canvas_height = 32 * self.SCALE
        self.canvas = tk.Canvas(
            root, width=self.canvas_width, height=self.canvas_height,
            bg="black", highlightthickness=0,
        )
        self.canvas.pack(pady=10)

        self.rects = []
        for y in range(32):
            for x in range(64):
                rect = self.canvas.create_rectangle(
                    x * self.SCALE, y * self.SCALE,
                    (x + 1) * self.SCALE, (y + 1) * self.SCALE,
                    fill=self.OFF_COLOR, width=0,
                )
                self.rects.append(rect)

        self.status_frame = tk.Frame(root, bg="black")
        self.status_frame.pack(fill="x", padx=10, pady=5)

        self.info_labels = {}
        for i in range(16):
            lbl = tk.Label(
                self.status_frame, text=f"V{i}: 0x00",
                fg=self.BLUE_TEXT, bg="black", font=("Consolas", 8),
            )
            lbl.grid(row=0, column=i, padx=2)
            self.info_labels[i] = lbl

        self.pc_lbl = tk.Label(
            self.status_frame, text="PC: 0x0200",
            fg=self.BLUE_TEXT, bg="black", font=("Consolas", 8),
        )
        self.pc_lbl.grid(row=1, column=0, columnspan=4, padx=5, pady=2, sticky="w")
        self.dt_lbl = tk.Label(
            self.status_frame, text="DT: 0",
            fg=self.BLUE_TEXT, bg="black", font=("Consolas", 8),
        )
        self.dt_lbl.grid(row=1, column=4, columnspan=4, padx=5, pady=2, sticky="w")
        self.st_lbl = tk.Label(
            self.status_frame, text="ST: 0",
            fg=self.BLUE_TEXT, bg="black", font=("Consolas", 8),
        )
        self.st_lbl.grid(row=1, column=8, columnspan=4, padx=5, pady=2, sticky="w")

        menubar = tk.Menu(
            root, bg="black", fg=self.BLUE_TEXT,
            activebackground=self.BLUE_HUE, activeforeground="white",
        )
        file_menu = tk.Menu(menubar, tearoff=0, bg="black", fg=self.BLUE_TEXT)
        file_menu.add_command(label="Load ROM...", command=self.load_rom)
        file_menu.add_command(label="Reset", command=self.reset_emulator)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        root.config(menu=menubar)

        self.key_map = {
            '1': 0x1, '2': 0x2, '3': 0x3, '4': 0x4,
            'q': 0x5, 'w': 0x6, 'e': 0x7, 'r': 0x8,
            'a': 0x9, 's': 0xA, 'd': 0xB, 'f': 0xC,
            'z': 0xD, 'x': 0xE, 'c': 0xF, 'v': 0x0,
        }
        self.bind_keys()

        self.running = False
        self.last_timer_tick = time.time()
        self.cycles_per_frame = 10

    def bind_keys(self):
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.root.focus_set()

    def on_key_press(self, event):
        key = event.keysym.lower()
        if key in self.key_map:
            self.cpu.key_press(self.key_map[key])
            return
        if event.char:
            key = event.char.lower()
            if key in self.key_map:
                self.cpu.key_press(self.key_map[key])

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in self.key_map:
            self.cpu.key_release(self.key_map[key])
            return
        if event.char:
            key = event.char.lower()
            if key in self.key_map:
                self.cpu.key_release(self.key_map[key])

    def load_rom(self):
        path = filedialog.askopenfilename(
            title="Select Chip-8 ROM",
            filetypes=[
                ("Chip-8 ROMs", "*.ch8"),
                ("Chip-8 ROMs", "*.rom"),
                ("Chip-8 ROMs", "*.bin"),
                ("All Files", "*.*"),
            ],
        )
        if path:
            try:
                self.cpu.load_rom(path)
                self.running = True
                self.last_timer_tick = time.time()
                self.cpu.draw_flag = True
                self.draw_display(force=True)
                self.update_status()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load ROM:\n{e}")

    def reset_emulator(self):
        self.cpu = Chip8CPU()
        self.running = False
        self.draw_display(force=True)
        self.update_status()

    def draw_display(self, force=False):
        if not force and not self.cpu.draw_flag:
            return
        self.cpu.draw_flag = False
        for i, pixel in enumerate(self.cpu.display):
            self.canvas.itemconfig(
                self.rects[i],
                fill=self.BLUE_HUE if pixel else self.OFF_COLOR,
            )

    def update_status(self):
        for i in range(16):
            self.info_labels[i].config(text=f"V{i}: 0x{self.cpu.V[i]:02X}")
        self.pc_lbl.config(text=f"PC: 0x{self.cpu.PC:04X}")
        self.dt_lbl.config(text=f"DT: {self.cpu.delay_timer}")
        self.st_lbl.config(text=f"ST: {self.cpu.sound_timer}")

    def tick(self):
        if self.running:
            now = time.time()
            if now - self.last_timer_tick >= 1 / 60:
                if self.cpu.delay_timer > 0:
                    self.cpu.delay_timer -= 1
                if self.cpu.sound_timer > 0:
                    self.cpu.sound_timer -= 1
                self.last_timer_tick = now

            for _ in range(self.cycles_per_frame):
                self.cpu.cycle()

            self.draw_display()
            self.update_status()

        self.root.after(16, self.tick)


if __name__ == "__main__":
    root = tk.Tk()
    app = EmulatorGUI(root)
    app.tick()
    root.mainloop()
