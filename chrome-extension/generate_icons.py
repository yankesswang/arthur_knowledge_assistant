#!/usr/bin/env python3
"""Generate PNG icons for the Chrome extension using only stdlib (no PIL needed)."""
import struct, zlib, os

def make_png(size):
    """Create a simple solid-color PNG with a mic emoji-inspired design."""
    # Colors
    bg = (124, 106, 247)       # accent purple
    mic = (255, 255, 255)      # white

    pixels = []
    cx, cy = size // 2, size // 2
    r_outer = size * 0.38
    r_inner = size * 0.18
    head_top = cy - size * 0.32
    head_bot = cy + size * 0.05
    body_w = size * 0.12

    for y in range(size):
        row = []
        for x in range(size):
            dx, dy = x - cx, y - cy
            # Rounded square background
            rr = size * 0.22
            in_bg = (x >= rr and x <= size - rr and y >= 0 and y <= size) or \
                    (y >= rr and y <= size - rr and x >= 0 and x <= size) or \
                    ((x - rr) ** 2 + (y - rr) ** 2 <= rr ** 2) or \
                    ((x - (size - rr)) ** 2 + (y - rr) ** 2 <= rr ** 2) or \
                    ((x - rr) ** 2 + (y - (size - rr)) ** 2 <= rr ** 2) or \
                    ((x - (size - rr)) ** 2 + (y - (size - rr)) ** 2 <= rr ** 2)
            in_bg = (rr <= x <= size - rr) or (rr <= y <= size - rr) or \
                    min(
                        (x - rr) ** 2 + (y - rr) ** 2,
                        (x - (size - rr)) ** 2 + (y - rr) ** 2,
                        (x - rr) ** 2 + (y - (size - rr)) ** 2,
                        (x - (size - rr)) ** 2 + (y - (size - rr)) ** 2
                    ) <= rr ** 2

            # Mic body (rounded rect)
            mic_on = (abs(x - cx) <= body_w and head_top <= y <= head_bot)
            # Mic head (semicircle top)
            mic_on = mic_on or (dx ** 2 + (y - head_top) ** 2 <= body_w ** 2 and y <= head_top)
            # Stand arc (bottom half of circle)
            arc_r = size * 0.26
            in_arc = abs(dx ** 2 + (y - head_bot) ** 2 - arc_r ** 2) < (size * 0.055) ** 2
            mic_on = mic_on or (in_arc and y >= head_bot and dy >= 0)
            # Stand base (vertical line)
            base_top = head_bot + arc_r
            mic_on = mic_on or (abs(x - cx) <= size * 0.04 and base_top <= y <= base_top + size * 0.1)
            # Stand foot (horizontal bar)
            mic_on = mic_on or (abs(x - cx) <= size * 0.18 and abs(y - (base_top + size * 0.1)) <= size * 0.04)

            if not in_bg:
                row += [0, 0, 0, 0]
            elif mic_on:
                row += list(mic) + [255]
            else:
                row += list(bg) + [255]
        pixels.append(bytes(row))

    return encode_png(size, size, pixels)

def encode_png(w, h, rows):
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    raw = b''.join(b'\x00' + r for r in rows)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 9))
    png += chunk(b'IEND', b'')
    return png

if __name__ == '__main__':
    out = os.path.join(os.path.dirname(__file__), 'icons')
    os.makedirs(out, exist_ok=True)
    for size in (16, 48, 128):
        path = os.path.join(out, f'icon{size}.png')
        with open(path, 'wb') as f:
            f.write(make_png(size))
        print(f'✅ {path}')
