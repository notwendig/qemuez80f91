"""Live 7x5 matrix from QEMU's completed hardware-scan telemetry."""
import argparse
import json
import socket
from pathlib import Path
import tkinter as tk


class KitControls:
    """Short QMP requests; never share the ZDS debug connection."""
    def __init__(self, qmp_path):
        self.qmp_path = qmp_path
        self.pressed = 0

    def request(self, command, arguments=None):
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(1)
            connection.connect(str(self.qmp_path))
            with connection.makefile('rwb', buffering=0) as stream:
                json.loads(stream.readline())
                def call(name, args=None):
                    message = {'execute': name}
                    if args is not None:
                        message['arguments'] = args
                    stream.write(json.dumps(message).encode() + b'\n')
                    while True:
                        reply = json.loads(stream.readline())
                        if 'event' in reply:
                            continue
                        if 'error' in reply:
                            raise RuntimeError(reply['error']['desc'])
                        return reply['return']
                call('qmp_capabilities')
                if command == 'buttons':
                    children = call('qom-list', {'path': '/machine/unattached'})
                    memory = next(item['name'] for item in children
                                  if item['type'] == 'child<ez80f91-memory>')
                    return call('qom-set', {
                        'path': '/machine/unattached/' + memory,
                        'property': 'kit-buttons', 'value': arguments})
                return call(command, arguments)

    def button(self, bit, down):
        pressed = self.pressed | (1 << bit) if down else self.pressed & ~(1 << bit)
        if pressed != self.pressed:
            self.request('buttons', pressed)
            self.pressed = pressed

    def release(self):
        if self.pressed:
            self.request('buttons', 0)
            self.pressed = 0

    def reset(self):
        self.release()
        self.request('system_reset')


def panel(state_path, port, snapshot=None, qmp_path=None):
    root = tk.Tk()
    root.title(f'eZ80F91 Development Kit — {port}')
    root.resizable(False, False)
    canvas = tk.Canvas(root, width=420, height=690, bg='#102b25', highlightthickness=0)
    canvas.pack()
    canvas.create_rectangle(0, 0, 420, 690, fill='#102b25', outline='')
    canvas.create_text(24, 26, text='ZiLOG  eZ80F91', anchor='w',
                       fill='#f0cf69', font=('sans', 19, 'bold'))
    canvas.create_text(24, 55, text='DEVELOPMENT KIT  ·  7 × 5 LED MATRIX', anchor='w',
                       fill='#b3c7bd', font=('sans', 10))
    canvas.create_rectangle(71, 85, 349, 422, fill='#111619', outline='#486057', width=3)
    leds = []
    for row in range(7):
        for col in range(5):
            x, y = 106 + col * 52, 116 + row * 46
            glow = canvas.create_oval(x-19, y-19, x+19, y+19, fill='#181d20', outline='')
            dot = canvas.create_oval(x-13, y-13, x+13, y+13, fill='#392325', outline='#64302e')
            leds.append((glow, dot))
    status = canvas.create_text(24, 448, text='Warte auf Emulator …', anchor='w',
                                fill='#cfdfd5', font=('sans', 11))
    registers = canvas.create_text(24, 479, text='800000h  ANODE      —\n800001h  CATHODE    —',
                                   anchor='w', fill='#9eb7ac', font=('monospace', 10))
    signals = canvas.create_text(24, 528, text='MODEM RESET  —     TRIG1  —     TRIG2  —',
                                 anchor='w', fill='#b3c7bd', font=('sans', 9))
    controls = KitControls(qmp_path or state_path.with_suffix('.qmp'))
    canvas.create_text(24, 566, text='KIT-TASTER  ·  Gedrückthalten oder Tasten 1–3',
                       anchor='w', fill='#b3c7bd', font=('sans', 10))
    control_status = canvas.create_text(24, 667, text='SW1–3: offen', anchor='w',
                                        fill='#cfdfd5', font=('sans', 10))
    def action(callback, *args):
        try:
            callback(*args)
            canvas.itemconfigure(control_status, fill='#cfdfd5')
        except (OSError, ValueError, RuntimeError, StopIteration, KeyError) as error:
            canvas.itemconfigure(control_status, text='Emulator nicht erreichbar', fill='#ffb08b')
    for bit, label in enumerate(('SW1\nLinks · PB0', 'SW2\nMitte · PB1', 'SW3\nRechts · PB2')):
        button = tk.Button(root, text=label, bg='#29483f', fg='#f0cf69',
                           activebackground='#55775b', activeforeground='#ffffff',
                           font=('sans', 10), takefocus=False)
        canvas.create_window(72 + 112 * bit, 610, window=button, width=100, height=52)
        button.bind('<ButtonPress-1>', lambda event, i=bit: action(controls.button, i, True))
        root.bind(f'<KeyPress-{bit+1}>', lambda event, i=bit: action(controls.button, i, True))
        root.bind(f'<KeyRelease-{bit+1}>', lambda event, i=bit: action(controls.button, i, False))
    root.bind_all('<ButtonRelease-1>', lambda event: action(controls.release))
    root.bind('<FocusOut>', lambda event: action(controls.release))
    reset = tk.Button(root, text='SW4 Reset', command=lambda: action(controls.reset),
                      bg='#59362f', fg='#fff0d4', activebackground='#815044', takefocus=False)
    canvas.create_window(342, 664, window=reset, width=108, height=28)
    def close():
        action(controls.release)
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    last = None

    def refresh():
        nonlocal last
        try:
            data = json.loads(state_path.read_text())
            if data != last:
                mask = int(data['mask'], 16)
                if last is None or data['mask'] != last['mask']:
                    for i, (glow, dot) in enumerate(leds):
                        on = mask & (1 << i)
                        canvas.itemconfigure(glow, fill='#5e2723' if on else '#181d20')
                        canvas.itemconfigure(dot, fill='#ff5143' if on else '#392325',
                                             outline='#ffb08b' if on else '#64302e')
                canvas.itemconfigure(status, text='CS2 aktiv' if data['enabled'] else 'CS2 nicht freigegeben')
                a, c = data['anode'], data['cathode']
                canvas.itemconfigure(registers, text=f'800000h  ANODE      {a:02X}\n800001h  CATHODE    {c:02X}')
                canvas.itemconfigure(signals, text=f'MODEM RESET  {(c >> 5) & 1}     TRIG1  {(c >> 6) & 1}     TRIG2  {(c >> 7) & 1}')
                pressed = data.get('buttons', 0)
                names = [f'SW{i+1}' for i in range(3) if pressed & (1 << i)]
                canvas.itemconfigure(control_status,
                                     text=('Gedrückt: ' + ', '.join(names)) if names else 'SW1–3: offen')
                last = data
        except (OSError, ValueError, KeyError):
            canvas.itemconfigure(status, text='Warte auf Emulator …')
        root.after(20, refresh)

    refresh()
    if snapshot is not None:
        def save_preview():
            canvas.postscript(file=str(snapshot), colormode='color')
            root.destroy()
        root.after(200, save_preview)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state', type=Path)
    parser.add_argument('--port', type=int, default=4040)
    parser.add_argument('--qmp', type=Path, help='QMP-Socket des Emulators')
    parser.add_argument('--snapshot', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    panel(args.state, args.port, args.snapshot, args.qmp)


if __name__ == '__main__':
    main()
