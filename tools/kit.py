"""Test-client compatibility and native Qt 6 kit entry point."""
import json
import socket
from pathlib import Path


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



def main():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.native import execute
    execute('kit', sys.argv[1:])


if __name__ == '__main__':
    main()
