# -*- coding: utf-8 -*-
"""VESC 设备模拟器：用 VESC 的包协议在 TCP 上假装成一台电调。

用途是在没有真实硬件的情况下验证汉化版 VESC Tool 的联机功能，重点是验证
**配置签名**：这里的签名一律用原版英文 XML 计算（和固件端一致），如果汉化版能
正常读入配置而不是报 Invalid signature，就说明 enumNamesSig 那套修复是有效的。

用法: python vesc_sim.py <原版config目录> <端口> [固件主版本 次版本]
"""
import socket, struct, sys, os, math, threading, time
import xml.etree.ElementTree as ET

# ---------------- CRC ----------------
CRC16_TAB = []
for i in range(256):
    c = i << 8
    for _ in range(8):
        c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    CRC16_TAB.append(c)


def crc16(data):
    c = 0
    for b in data:
        c = ((c << 8) & 0xFFFF) ^ CRC16_TAB[((c >> 8) ^ b) & 0xFF]
    return c


def crc32c(data):
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return (~crc) & 0xFFFFFFFF


# ---------------- 打包 ----------------
def frame(payload):
    n = len(payload)
    if n <= 255:
        head = bytes([2, n])
    elif n <= 65535:
        head = bytes([3, n >> 8, n & 0xFF])
    else:
        head = bytes([4, (n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF])
    return head + payload + struct.pack('>H', crc16(payload)) + bytes([3])


class VB(bytearray):
    def u8(self, v):  self.append(v & 0xFF); return self
    def i8(self, v):  self.append(v & 0xFF); return self
    def u16(self, v): self += struct.pack('>H', v & 0xFFFF); return self
    def i16(self, v): self += struct.pack('>h', max(-32768, min(32767, int(v)))); return self
    def u32(self, v): self += struct.pack('>I', v & 0xFFFFFFFF); return self
    def i32(self, v): self += struct.pack('>i', max(-2**31, min(2**31 - 1, int(v)))); return self
    def d16(self, v, s): return self.i16(round(v * s))
    def d32(self, v, s): return self.i32(round(v * s))

    def d32auto(self, number):
        if abs(number) < 1.5e-38:
            number = 0.0
        fr, e = math.frexp(number)
        fr_abs = abs(fr)
        fr_s = 0
        if fr_abs >= 0.5:
            fr_s = int((struct.unpack('f', struct.pack('f', fr_abs))[0] - 0.5) * 2.0 * 8388608.0)
            e += 126
        res = ((e & 0xFF) << 23) | (fr_s & 0x7FFFFF)
        if fr < 0:
            res |= 1 << 31
        return self.u32(res)

    def s(self, txt):
        self += txt.encode('utf-8') + b'\x00'
        return self


# ---------------- 配置序列化 ----------------
CFG_T_DOUBLE, CFG_T_INT, CFG_T_QSTRING, CFG_T_ENUM, CFG_T_BOOL, CFG_T_BITFIELD = 1, 2, 3, 4, 5, 6
(TX_U8, TX_I8, TX_U16, TX_I16, TX_U32, TX_I32, TX_D16, TX_D32, TX_D32A) = range(1, 10)


class Conf:
    """从原版英文 XML 读出参数定义、默认值和序列化顺序"""

    def __init__(self, path):
        root = ET.parse(path).getroot()
        self.params, self.order = {}, []
        for sec in root:
            if sec.tag == 'Params':
                for p in sec:
                    self.params[p.tag] = p
            elif sec.tag == 'SerOrder':
                self.order = [e.text for e in sec]

    def signature(self):
        s = []
        for name in self.order:
            s.append(name)
            p = self.params.get(name)
            if p is not None:
                t = p.find('type')
                vtx = p.find('vTx')
                s.append(str(int(t.text)) if t is not None else '0')
                s.append(str(int(vtx.text)) if vtx is not None else '0')
                for e in p.findall('enumNames'):
                    s.append(e.text or '')
        return crc32c(''.join(s).encode('utf-8'))

    # 验证用：把几个参数改成一眼能认出来的特征值。界面上如果显示出这些数，
    # 就说明签名校验通过、配置被真正反序列化了。
    OVERRIDE = {'l_current_max': 123.45, 'l_in_current_max': 67.89,
                'si_battery_cells': 13, 'si_wheel_diameter': 0.155}

    def serialize(self):
        vb = VB()
        vb.u32(self.signature())
        for name in self.order:
            p = self.params.get(name)
            if p is None:
                continue
            t = int(p.findtext('type', '0'))
            vtx = int(p.findtext('vTx', '0'))
            if t == CFG_T_DOUBLE:
                val = float(self.OVERRIDE.get(name, p.findtext('valDouble', '0') or 0))
                scale = float(p.findtext('vTxDoubleScale', '1') or 1)
                if vtx == TX_D16:
                    vb.d16(val, scale)
                elif vtx == TX_D32:
                    vb.d32(val, scale)
                else:
                    vb.d32auto(val)
            elif t == CFG_T_INT:
                val = int(float(self.OVERRIDE.get(name, p.findtext('valInt', '0') or 0)))
                {TX_U8: vb.u8, TX_I8: vb.i8, TX_U16: vb.u16, TX_I16: vb.i16,
                 TX_U32: vb.u32, TX_I32: vb.i32}.get(vtx, vb.i32)(val)
            elif t == CFG_T_QSTRING:
                vb.s(p.findtext('valString', '') or '')
            else:
                vb.i8(int(float(p.findtext('valInt', '0') or 0)))
        return bytes(vb)


# ---------------- 服务端 ----------------
class Sim:
    def __init__(self, cfgdir, fw=(6, 6), hw='DIY_70_80'):
        self.mc = Conf(os.path.join(cfgdir, 'parameters_mcconf.xml'))
        self.app = Conf(os.path.join(cfgdir, 'parameters_appconf.xml'))
        self.fw, self.hw = fw, hw
        self.t0 = time.time()
        print('mcconf 签名 0x%08X (%d 项)  appconf 签名 0x%08X (%d 项)'
              % (self.mc.signature(), len(self.mc.order),
                 self.app.signature(), len(self.app.order)), flush=True)

    def fw_version(self):
        vb = VB().u8(0).i8(self.fw[0]).i8(self.fw[1]).s(self.hw)
        vb += bytes(range(0x11, 0x11 + 12))          # UUID
        vb.i8(0).i8(0).i8(0).i8(0).i8(1).i8(0).i8(0)  # paired/test/hwType/cfgNum/phaseFilters/qmlHw/qmlApp
        return bytes(vb)

    def values(self):
        t = time.time() - self.t0
        rpm = 3000 + 2000 * math.sin(t / 3.0)
        cur = 12.0 + 8.0 * math.sin(t / 2.0)
        vb = VB().u8(4)
        vb.d16(38.5 + 2 * math.sin(t / 5), 1e1)      # temp_mos
        vb.d16(42.0 + 3 * math.sin(t / 7), 1e1)      # temp_motor
        vb.d32(cur, 1e2)                             # current_motor
        vb.d32(cur * 0.4, 1e2)                       # current_in
        vb.d32(-1.5, 1e2).d32(cur, 1e2)              # id, iq
        vb.d16(0.42 + 0.1 * math.sin(t / 4), 1e3)    # duty
        vb.d32(rpm, 1e0)                             # rpm
        vb.d16(48.3, 1e1)                            # v_in
        vb.d32(1.234, 1e4).d32(0.221, 1e4)           # ah, ah_charged
        vb.d32(59.6, 1e4).d32(10.7, 1e4)             # wh, wh_charged
        vb.i32(int(t * 100)).i32(int(t * 100))       # tacho, tacho_abs
        vb.i8(0)                                     # fault
        vb.d32(123.456, 1e6)                         # position
        vb.u8(1)                                     # vesc_id
        vb.d16(37.1, 1e1).d16(38.2, 1e1).d16(36.9, 1e1)
        return bytes(vb)

    def handle(self, pid, body):
        if pid == 0:
            return self.fw_version()
        if pid == 4:
            return self.values()
        if pid in (14, 15):
            return bytes(VB().u8(pid)) + self.mc.serialize()
        if pid in (17, 18):
            return bytes(VB().u8(pid)) + self.app.serialize()
        if pid == 20:                                 # 终端命令
            cmd = body.decode('utf-8', 'replace').strip()
            return bytes(VB().u8(21).s('模拟器: 收到命令 "%s"\n' % cmd))
        return None


def serve(sim, port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', port))
    srv.listen(4)
    print('VESC 模拟器已监听 127.0.0.1:%d' % port, flush=True)
    while True:
        conn, addr = srv.accept()
        print('连接来自', addr, flush=True)
        threading.Thread(target=client, args=(sim, conn), daemon=True).start()


def client(sim, conn):
    buf = b''
    try:
        while True:
            d = conn.recv(4096)
            if not d:
                break
            buf += d
            while True:
                if not buf:
                    break
                st = buf[0]
                if st not in (2, 3, 4):
                    buf = buf[1:]
                    continue
                hl = st - 1
                if len(buf) < 1 + hl:
                    break
                n = int.from_bytes(buf[1:1 + hl], 'big')
                total = 1 + hl + n + 3
                if len(buf) < total:
                    break
                payload = buf[1 + hl:1 + hl + n]
                buf = buf[total:]
                if not payload:
                    continue
                rsp = sim.handle(payload[0], payload[1:])
                if rsp:
                    conn.sendall(frame(rsp))
                    if payload[0] in (0, 14, 17):
                        print('  -> 回复命令 %d，%d 字节' % (payload[0], len(rsp)), flush=True)
    except Exception as e:
        print('客户端断开:', e, flush=True)
    finally:
        conn.close()


if __name__ == '__main__':
    cfgdir, port = sys.argv[1], int(sys.argv[2])
    fw = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (6, 6)
    serve(Sim(cfgdir, fw), port)
