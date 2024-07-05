import queue
import socket, sys
import threading
import numpy as np
import time


class FrameGenerator:
    def __init__(self, shape):
        template = np.zeros((20, 5, 3), dtype=np.uint8)
        template[:, :] = [50, 50, 50]
        template[1:-1, 1:-1] = np.linspace(70, 0, template.shape[0]-2, dtype=np.uint8)[:, None, None]
        template[1:-1, 1:-1] = template[1:-1, 1:-1] // (4, 4, 1)
        template[0, 0] = template[0, -1] = template[-1, 0] = template[-1, -1] = [10, 10, 10]
        template[0, 1:-1] = 100

        times = np.random.randint(1, 1000, size=100)
        x = np.random.randint(0, shape[1]-template.shape[1], size=100)

        data = np.zeros((1000 + shape[0] + 10, shape[1], 3), dtype=np.uint8)
        for i in range(100):
            data[
                times[i]:times[i] + template.shape[0], 
                x[i]:x[i] + template.shape[1]
            ] = template
        self.data = ((2.0 * data / 255)**2) * 255

    def iter_frames(self):
        i = 0
        while True:
            fi = int(np.floor(i))
            v1 = self.data[fi:fi+shape[0]]
            v2 = self.data[fi+1:fi+shape[0]+1]
            s = i - fi
            view = interpolate_frames(v1, v2, s)

            # view[:] = 0
            # view[30:40, ::16, :] = 100
            i = (i + 0.2) % 999
            yield view[::-1].tobytes()
            time.sleep(0.01)



# class FrameGenerator:
#     def __init__(self, shape):
#         self.shape = shape

#     def iter_frames(self):
#         frame = np.zeros(np.prod(self.shape) * 3, dtype=np.uint8)
#         for i in range(0, len(frame), 3):
#             frame[i:i+3] = 50
#             time.sleep(0.01)
#             yield frame


def interpolate_frames(frame1, frame2, s, gamma=0.5):    
    interp = frame1 * (1 - s)**gamma + frame2 * s**gamma
    return np.clip(interp, 0, 255).astype('uint8')


# class FrameGenerator:
#     """For testing gamma"""
#     def __init__(self, shape):
#         self.shape = shape

#     def iter_frames(self):
#         xvals = np.abs(np.linspace(-1, 1, 100))
#         frame1 = np.zeros(self.shape + (3,), dtype=np.uint8)
#         frame2 = frame1.copy()
#         frame1[::2, :, :] = 100
#         frame2[1::2, :, :] = 100
#         while True:
#             for x in xvals:
#                 yield interpolate_frames(frame1, frame2, x)
#                 time.sleep(0.01)


class FrameSender:
    def __init__(self, host, port, udp=False):
        
        self.host = host
        self.port = port
        self.udp = udp

        self.next_frame = None
        self.stop = False

        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        if self.udp:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, data[0].nbytes + 10)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))

        last_frame = None
        while not self.stop:
            frame = self.next_frame
            if frame is last_frame:
                time.sleep(0.003)
                continue
            last_frame = frame

            if self.udp:
                frame = frame.tobytes()
                sent = 0
                max_size = 65507
                while sent < len(frame):
                    sock.sendto(frame[sent:sent+max_size], (self.host, self.port))
                    sent += max_size
            else:
                sock.sendall(frame)

        sock.close()

    def send_frame(self, frame):
        self.next_frame = frame

    def close(self):
        self.stop = True


if __name__ == '__main__':

    host, port = sys.argv[1], int(sys.argv[2])
    shape = (64, 512)

    fg = FrameGenerator(shape)
    fs = FrameSender(host, port, udp=True)
    for frame in fg.iter_frames():
        fs.send_frame(frame)

    fs.close()
