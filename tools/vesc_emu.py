# -*- coding: utf-8 -*-
"""VESC 固件模拟器（带电机物理模型）

在没有实机的情况下，端到端测试 VESC Tool 的联机功能：连接、读写配置、电机参数检测、
占空比/电流/转速/制动控制、实时数据、终端。

与真实固件保持一致的关键点
  * 配置签名一律用【原版英文 XML】计算 —— 真固件的签名常量就是这么来的。汉化版写配置时
    如果签名不对，这里会像固件一样打印 "Could not set mcconf due to wrong signature"
    并且不回 ACK。
  * 写入配置后按硬件上限截断（本机 hwconf：相电流 ±80 A、绝对最大 90 A、电压 6~70 V）。
  * 转速环按固件公式：out = err*kp/20 + ∫err*ki/20，输出归一化后乘电流上限；
    目标转速低于 s_pid_min_erpm 时转速环不工作（电机不转）。
  * 保活：控制命令或 COMM_ALIVE 超过 appconf.timeout_msec 没来就停机，
    并按 timeout_brake_current 制动。
  * 急停：VESC Tool 的 STOP 按钮会发 COMM_MOTOR_ESTOP(毫秒)，固件在这段时间内忽略一切
    电机控制命令（mc_interface_ignore_input_both），这里同样处理。
  * 未实现的命令（如 COMM_GET_STATS）只记一条 unhandled 日志，不回包。
  * DETECT_APPLY_ALL_FOC：测 R/L → 开环转起来测磁链 → 检测传感器 → 按固件公式写回
    R/L/λ、i_max=√(P/R/1.5)（被硬件上限截断）、abs=1.5*i_max、KP=L*1000、KI=R*1000、
    观测器增益=1e3/λ² —— 然后【先主动推送 COMM_GET_MCCONF，再回结果码】。
  * 终端输出只用 ASCII：工具端按 Latin-1 解码 COMM_PRINT，中文会乱码。

模拟的电机（检测前工具并不知道这些值，检测后应当"测"出来）
  7 对极(14 极)，R=28.5 mΩ，L=21.6 µH，Lq-Ld=5.8 µH，λ=5.17 mWb，12S 电池 46.8 V

用法
  python vesc_emu.py <原版英文 config 目录> [--port 65102] [--fw 7.00] [--hw DIY_70_80]
                     [--log emu_log.jsonl] [--fast]

  在 VESC Tool 终端页可输入：
    emu_fault <none|uv|ov|drv|oc|flux>   让下一次检测以该故障失败
    emu_vin <电压>                       改电池电压
    emu_state                            打印电机状态
"""
import socket, struct, sys, os, math, threading, time, random, json, argparse
import xml.etree.ElementTree as ET

# ============================ 协议基础 ============================
CRC16_TAB = []
for _i in range(256):
    _c = _i << 8
    for _ in range(8):
        _c = ((_c << 1) ^ 0x1021) & 0xFFFF if _c & 0x8000 else (_c << 1) & 0xFFFF
    CRC16_TAB.append(_c)


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
    """写"""
    def u8(self, v):  self.append(int(v) & 0xFF); return self
    def i8(self, v):  self.append(int(v) & 0xFF); return self
    def u16(self, v): self += struct.pack('>H', int(v) & 0xFFFF); return self
    def i16(self, v): self += struct.pack('>h', max(-32768, min(32767, int(round(v))))); return self
    def u32(self, v): self += struct.pack('>I', int(v) & 0xFFFFFFFF); return self
    def i32(self, v): self += struct.pack('>i', max(-2**31, min(2**31 - 1, int(round(v))))); return self
    def d16(self, v, s): return self.i16(v * s)
    def d32(self, v, s): return self.i32(v * s)

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


class VR:
    """读"""
    def __init__(self, b):
        self.b, self.p = bytes(b), 0

    def left(self): return len(self.b) - self.p

    def _up(self, fmt, n):
        v = struct.unpack_from(fmt, self.b, self.p)[0]
        self.p += n
        return v

    def u8(self):  return self._up('>B', 1)
    def i8(self):  return self._up('>b', 1)
    def u16(self): return self._up('>H', 2)
    def i16(self): return self._up('>h', 2)
    def u32(self): return self._up('>I', 4)
    def i32(self): return self._up('>i', 4)
    def d16(self, s): return self.i16() / s
    def d32(self, s): return self.i32() / s

    def d32auto(self):
        res = self.u32()
        e = (res >> 23) & 0xFF
        sig_i = res & 0x7FFFFF
        neg = res & (1 << 31)
        sig = 0.0
        if e != 0 or sig_i != 0:
            sig = sig_i / (8388608.0 * 2.0) + 0.5
            e -= 126
        if neg:
            sig = -sig
        return math.ldexp(sig, e)

    def s(self):
        end = self.b.index(b'\x00', self.p)
        t = self.b[self.p:end].decode('utf-8', 'replace')
        self.p = end + 1
        return t


COMM = dict(FW_VERSION=0, GET_VALUES=4, SET_DUTY=5, SET_CURRENT=6, SET_CURRENT_BRAKE=7,
            SET_RPM=8, SET_POS=9, SET_HANDBRAKE=10, SET_MCCONF=13, GET_MCCONF=14,
            GET_MCCONF_DEFAULT=15, SET_APPCONF=16, GET_APPCONF=17, GET_APPCONF_DEFAULT=18,
            TERMINAL_CMD=20, PRINT=21, DETECT_MOTOR_PARAM=24, DETECT_MOTOR_R_L=25,
            DETECT_MOTOR_FLUX_LINKAGE=26, DETECT_ENCODER=27, DETECT_HALL_FOC=28, REBOOT=29,
            ALIVE=30, GET_DECODED_PPM=31, GET_DECODED_ADC=32, GET_DECODED_CHUK=33,
            GET_VALUES_SETUP=47, SET_MCCONF_TEMP=48, SET_MCCONF_TEMP_SETUP=49,
            GET_VALUES_SELECTIVE=50, GET_VALUES_SETUP_SELECTIVE=51,
            DETECT_MOTOR_FLUX_LINKAGE_OPENLOOP=57, DETECT_APPLY_ALL_FOC=58, PING_CAN=62,
            APP_DISABLE_OUTPUT=63, SET_CURRENT_REL=84, SET_BATTERY_CUT=86, MOTOR_ESTOP=159)
COMM_NAME = {v: k for k, v in COMM.items()}

FAULT = dict(none=0, ov=1, uv=2, drv=3, oc=4)
FAULT_STR = {0: 'FAULT_CODE_NONE', 1: 'FAULT_CODE_OVER_VOLTAGE', 2: 'FAULT_CODE_UNDER_VOLTAGE',
             3: 'FAULT_CODE_DRV', 4: 'FAULT_CODE_ABS_OVER_CURRENT'}

# ============================ 配置 ============================
CFG_T_DOUBLE, CFG_T_INT, CFG_T_QSTRING, CFG_T_ENUM, CFG_T_BOOL, CFG_T_BITFIELD = 1, 2, 3, 4, 5, 6
(TX_U8, TX_I8, TX_U16, TX_I16, TX_U32, TX_I32, TX_D16, TX_D32, TX_D32A) = range(1, 10)


class Conf:
    """参数定义和签名来自原版英文 XML；数值保存在 self.v 里，可被 SET_*CONF 改写"""

    def __init__(self, path, overlay=None):
        root = ET.parse(path).getroot()
        self.params, self.order = {}, []
        for sec in root:
            if sec.tag == 'Params':
                for p in sec:
                    self.params[p.tag] = p
            elif sec.tag == 'SerOrder':
                self.order = [e.text for e in sec]
        self.overlay = overlay or {}
        self.v = self.defaults()
        self.sig = self._signature()

    def defaults(self):
        v = {}
        for name, p in self.params.items():
            t = int(p.findtext('type', '0'))
            if t == CFG_T_DOUBLE:
                v[name] = float(p.findtext('valDouble', '0') or 0)
            elif t == CFG_T_QSTRING:
                v[name] = p.findtext('valString', '') or ''
            else:
                v[name] = int(float(p.findtext('valInt', '0') or 0))
        v.update(self.overlay)
        return v

    def _signature(self):
        s = []
        for name in self.order:
            s.append(name)
            p = self.params.get(name)
            if p is not None:
                s.append(str(int(p.findtext('type', '0'))))
                s.append(str(int(p.findtext('vTx', '0'))))
                for e in p.findall('enumNames'):
                    s.append(e.text or '')
        return crc32c(''.join(s).encode('utf-8'))

    def _meta(self, name):
        p = self.params[name]
        return (int(p.findtext('type', '0')), int(p.findtext('vTx', '0')),
                float(p.findtext('vTxDoubleScale', '1') or 1))

    def serialize(self, vals=None):
        vals = vals or self.v
        vb = VB().u32(self.sig)
        for name in self.order:
            if name not in self.params:
                continue
            t, vtx, scale = self._meta(name)
            val = vals[name]
            if t == CFG_T_DOUBLE:
                if vtx == TX_D16:
                    vb.d16(val, scale)
                elif vtx == TX_D32:
                    vb.d32(val, scale)
                else:
                    vb.d32auto(val)
            elif t == CFG_T_INT:
                {TX_U8: vb.u8, TX_I8: vb.i8, TX_U16: vb.u16, TX_I16: vb.i16,
                 TX_U32: vb.u32, TX_I32: vb.i32}.get(vtx, vb.i32)(val)
            elif t == CFG_T_QSTRING:
                vb.s(val)
            else:
                vb.i8(val)
        return bytes(vb)

    def deserialize(self, data):
        """返回 (ok, 信息, 新值字典)。签名不对则不改任何值（与固件一致）"""
        r = VR(data)
        sig = r.u32()
        if sig != self.sig:
            return False, 'signature 0x%08X != expected 0x%08X' % (sig, self.sig), None
        new = dict(self.v)
        for name in self.order:
            if name not in self.params:
                continue
            t, vtx, scale = self._meta(name)
            if t == CFG_T_DOUBLE:
                if vtx == TX_D16:
                    new[name] = r.d16(scale)
                elif vtx == TX_D32:
                    new[name] = r.d32(scale)
                else:
                    new[name] = r.d32auto()
            elif t == CFG_T_INT:
                new[name] = {TX_U8: r.u8, TX_I8: r.i8, TX_U16: r.u16, TX_I16: r.i16,
                             TX_U32: r.u32, TX_I32: r.i32}.get(vtx, r.i32)()
            elif t == CFG_T_QSTRING:
                new[name] = r.s()
            else:
                new[name] = r.i8()
        return True, 'ok (%d bytes left)' % r.left(), new


# 本机 hw_diy_70_80.h 的 MCCONF_ 默认值（出厂配置 / "读取默认电机配置" 返回的就是它）
MC_OVERLAY = dict(l_min_vin=30.0, l_max_vin=57.0, motor_type=2, foc_f_zv=25000.0,
                  l_current_max=60.0, l_current_min=-60.0, l_abs_current_max=90.0,
                  l_in_current_max=60.0, l_in_current_min=-40.0)
# hwconf 的 HW_LIM_*：写入配置后按此截断（commands_apply_mcconf_hw_limits）
HW_LIM = dict(l_current_max=(-80.0, 80.0), l_current_min=(-80.0, 80.0),
              l_in_current_max=(-80.0, 80.0), l_in_current_min=(-80.0, 80.0),
              l_abs_current_max=(0.0, 90.0), l_min_vin=(6.0, 70.0), l_max_vin=(6.0, 70.0),
              l_temp_fet_start=(-40.0, 110.0), l_temp_fet_end=(-40.0, 110.0))


# ============================ 电机模型 ============================
class Motor:
    PP = 7                 # 极对数（14 极）
    R = 0.0285             # Ω
    L = 21.6e-6            # H
    LDLQ = 5.8e-6          # H
    LAMBDA = 0.00517       # Wb
    J = 6.0e-4             # kg·m²
    B = 2.2e-4             # 粘滞摩擦 N·m·s
    TC = 0.015             # 库仑摩擦 N·m
    VBAT = 46.8            # 12S
    RBAT = 0.045           # 电池内阻

    def __init__(self):
        self.wm = 0.0
        self.iq = self.id = 0.0
        self.mode, self.cmd = 'off', 0.0
        self.i_term = 0.0
        self.temp_mos, self.temp_motor = 31.0, 29.5
        self.tacho = self.tacho_abs = 0.0
        self.ah = self.ahc = self.wh = self.whc = 0.0
        self.vbat = self.VBAT
        self.v_in, self.i_in, self.vq, self.vd = self.VBAT, 0.0, 0.0, 0.0
        self.fault, self.fault_until = 0, 0.0
        self.has_timeout = False
        self.pos = 0.0
        self.forced = None     # 检测期间：('still', iq显示) / ('spin', 目标ERPM, iq)

    @property
    def erpm(self):
        return self.wm * self.PP * 60.0 / (2 * math.pi)

    def step(self, dt, mc, now):
        we = self.wm * self.PP
        inv = -1.0 if mc.get('m_invert_direction', 0) else 1.0
        vmax_full = self.v_in / math.sqrt(3)
        vmax = vmax_full * 0.95
        imax = float(mc.get('l_current_max', 60.0))
        imin = float(mc.get('l_current_min', -60.0))

        if self.fault and now >= self.fault_until:
            self.fault = 0

        # ---------- 目标电流 ----------
        iq_cmd = 0.0
        if self.forced:
            kind = self.forced[0]
            if kind == 'still':
                iq_cmd = self.forced[1] * math.sin(now * 90.0)
            elif kind == 'spin':
                # 开环：强制转速，按设定斜率逼近目标
                target_wm = self.forced[1] * 2 * math.pi / 60.0 / self.PP
                rate = self.forced[3] * 2 * math.pi / 60.0 / self.PP
                dw = max(-rate * dt, min(rate * dt, target_wm - self.wm))
                self.wm += dw
                iq_cmd = self.forced[2]
        elif self.fault:
            iq_cmd = 0.0
        elif self.mode == 'current':
            iq_cmd = max(imin, min(imax, self.cmd * inv))
        elif self.mode == 'brake':
            if abs(self.erpm) > 60:
                iq_cmd = -math.copysign(min(abs(self.cmd), abs(imin)), self.wm)
        elif self.mode == 'handbrake':
            iq_cmd = max(-abs(self.cmd), min(abs(self.cmd), -we * 0.02))
        elif self.mode == 'duty':
            v_t = self.cmd * inv * vmax_full
            iq_cmd = max(imin, min(imax, (v_t - we * self.LAMBDA) / self.R))
        elif self.mode == 'rpm':
            target = self.cmd * inv
            if abs(target) < float(mc.get('s_pid_min_erpm', 900.0)):
                self.i_term = 0.0
                iq_cmd = 0.0
            else:
                err = target - self.erpm
                kp = float(mc.get('s_pid_kp', 0.004))
                ki = float(mc.get('s_pid_ki', 0.004))
                p_term = err * kp / 20.0
                self.i_term = max(-1.0, min(1.0, self.i_term + err * ki * dt / 20.0))
                out = max(-1.0, min(1.0, p_term + self.i_term))
                if not mc.get('s_pid_allow_braking', 1) and out * target < 0:
                    out = 0.0
                iq_cmd = out * imax if out > 0 else out * abs(imin)

        # 电压上限：|R*iq + we*λ| <= vmax
        lo = (-vmax - we * self.LAMBDA) / self.R
        hi = (vmax - we * self.LAMBDA) / self.R
        iq_cmd = max(lo, min(hi, iq_cmd))
        # 电池电流上限（近似）
        vq_est = self.R * iq_cmd + we * self.LAMBDA
        if self.v_in > 1 and abs(vq_est) > 0.1:
            iin_est = 1.5 * vq_est * iq_cmd / self.v_in
            iin_max = float(mc.get('l_in_current_max', 60.0))
            iin_min = float(mc.get('l_in_current_min', -40.0))
            if iin_est > iin_max:
                iq_cmd *= iin_max / iin_est
            elif iin_est < iin_min:
                iq_cmd *= iin_min / iin_est

        # 电流环（一阶，τ=L/R）
        self.iq += (iq_cmd - self.iq) * (1 - math.exp(-dt * self.R / self.L))

        # ---------- 机械 ----------
        if not (self.forced and self.forced[0] == 'spin'):
            torque = 1.5 * self.PP * self.LAMBDA * self.iq
            fric = self.B * self.wm
            if abs(self.wm) < 0.5 and abs(torque) <= self.TC:
                self.wm = 0.0
            else:
                fric += math.copysign(self.TC, self.wm if self.wm != 0 else torque)
                w_new = self.wm + (torque - fric) / self.J * dt
                if self.wm != 0 and (w_new * self.wm) < 0 and abs(torque) <= self.TC:
                    w_new = 0.0
                self.wm = w_new
        we = self.wm * self.PP

        # ---------- 电气量 ----------
        self.vq = self.R * self.iq + we * self.LAMBDA
        self.vd = -we * self.L * self.iq
        self.i_in = 1.5 * (self.vq * self.iq + self.vd * self.id) / max(self.v_in, 1.0)
        self.v_in = self.vbat - self.RBAT * self.i_in + random.uniform(-0.03, 0.03)

        # ---------- 累计量 ----------
        rev = we * dt / (2 * math.pi)
        self.tacho += rev * 6
        self.tacho_abs += abs(rev) * 6
        self.pos = (self.pos + math.degrees(self.wm * dt)) % 360.0
        if self.i_in >= 0:
            self.ah += self.i_in * dt / 3600
            self.wh += self.i_in * self.v_in * dt / 3600
        else:
            self.ahc += -self.i_in * dt / 3600
            self.whc += -self.i_in * self.v_in * dt / 3600
        self.temp_mos += ((31.0 + 0.004 * self.iq ** 2) - self.temp_mos) * dt / 60.0
        self.temp_motor += ((29.5 + 0.006 * self.iq ** 2) - self.temp_motor) * dt / 90.0

        # ---------- 保护 ----------
        if not self.forced and self.mode != 'off' and not self.fault:
            fault = 0
            if abs(self.iq) > float(mc.get('l_abs_current_max', 90.0)):
                fault = FAULT['oc']
            elif self.v_in < float(mc.get('l_min_vin', 30.0)):
                fault = FAULT['uv']
            elif self.v_in > float(mc.get('l_max_vin', 57.0)):
                fault = FAULT['ov']
            if fault:
                self.fault = fault
                self.fault_until = now + float(mc.get('m_fault_stop_time_ms', 500)) / 1000.0
                self.mode = 'off'
        return inv


# ============================ 模拟器 ============================
class Emu:
    def __init__(self, cfgdir, fw=(7, 0), hw='DIY_70_80', log=None, fast=False):
        self.mc = Conf(os.path.join(cfgdir, 'parameters_mcconf.xml'), MC_OVERLAY)
        self.app = Conf(os.path.join(cfgdir, 'parameters_appconf.xml'))
        self.fw, self.hw = fw, hw
        self.motor = Motor()
        self.lock = threading.RLock()
        self.conn = None
        self.send_lock = threading.Lock()
        self.last_ctrl = 0.0
        self.ignore_until = 0.0     # MOTOR_ESTOP：这段时间内忽略一切控制命令（固件 mc_interface_ignore_input_both）
        self.ignored_last = None
        self.t0 = time.time()
        self.detecting = False
        self.fault_inject = None
        self.speed = 0.5 if fast else 1.0
        self.logf = open(log, 'a', encoding='utf-8') if log else None
        self.faults_seen = []
        self.ev('start', fw='%d.%02d' % fw, hw=hw,
                mc_sig='0x%08X' % self.mc.sig, app_sig='0x%08X' % self.app.sig,
                mc_items=len(self.mc.order), app_items=len(self.app.order))
        threading.Thread(target=self._physics, daemon=True).start()

    # ---------- 日志 ----------
    def ev(self, kind, **kw):
        rec = dict(t=round(time.time() - self.t0, 3), ev=kind, **kw)
        line = json.dumps(rec, ensure_ascii=False)
        print(line, flush=True)
        if self.logf:
            self.logf.write(line + '\n')
            self.logf.flush()

    # ---------- 发送 ----------
    def send(self, payload):
        c = self.conn
        if c is None:
            return
        with self.send_lock:
            try:
                c.sendall(frame(bytes(payload)))
            except OSError:
                pass

    def printf(self, text):
        for line in text.split('\n'):
            self.send(VB().u8(COMM['PRINT']) + line.encode('latin-1', 'replace'))

    # ---------- 物理线程 ----------
    def _physics(self):
        last = time.time()
        tick = 0
        while True:
            time.sleep(0.001)
            now = time.time()
            dt = min(now - last, 0.01)
            last = now
            with self.lock:
                m = self.motor
                mc = self.mc.v
                # 保活超时
                if m.mode != 'off' and not m.forced:
                    tout = float(self.app.v.get('timeout_msec', 1000)) / 1000.0
                    if now - self.last_ctrl > tout:
                        bc = float(self.app.v.get('timeout_brake_current', 0.0))
                        prev = m.mode
                        m.mode, m.cmd = ('brake', bc) if bc > 0 else ('off', 0.0)
                        m.has_timeout = True
                        if prev != 'brake' or bc <= 0:
                            self.ev('timeout', after_ms=int(tout * 1000), then=m.mode,
                                    erpm=round(m.erpm))
                if m.mode == 'brake' and m.has_timeout and abs(m.erpm) < 60:
                    m.mode = 'off'
                prev_fault = m.fault
                m.step(dt, mc, now)
                if m.fault and not prev_fault:
                    self.faults_seen.append(m.fault)
                    self.ev('fault', code=FAULT_STR.get(m.fault, m.fault), v_in=round(m.v_in, 2),
                            iq=round(m.iq, 1))
            tick += 1

    def ctrl(self, mode, cmd):
        with self.lock:
            m = self.motor
            left = self.ignore_until - time.time()
            if left > 0:
                # 与固件一致：急停窗口内控制命令被丢弃，但保活计时照常刷新
                self.last_ctrl = time.time()
                if self.ignored_last != (mode, round(cmd, 4)):
                    self.ignored_last = (mode, round(cmd, 4))
                    self.ev('ctrl_ignored', mode=mode, cmd=round(cmd, 4), estop_left_ms=int(left * 1000))
                return
            if mode != m.mode or abs(cmd - m.cmd) > 1e-6:
                self.ev('ctrl', mode=mode, cmd=round(cmd, 4))
            if mode == 'rpm' and m.mode != 'rpm':
                m.i_term = 0.0
            m.mode, m.cmd = mode, cmd
            m.has_timeout = False
            self.last_ctrl = time.time()

    # ---------- 回包构造 ----------
    def fw_version(self):
        vb = VB().u8(COMM['FW_VERSION']).i8(self.fw[0]).i8(self.fw[1]).s(self.hw)
        vb += bytes(range(0x11, 0x11 + 12))
        vb.i8(0).i8(0).i8(0).i8(0).i8(1).i8(0).i8(0)
        return vb

    def _vals(self):
        m = self.motor
        inv = -1.0 if self.mc.v.get('m_invert_direction', 0) else 1.0
        duty = max(-1.0, min(1.0, m.vq / max(m.v_in / math.sqrt(3), 1.0)))
        return dict(temp_mos=m.temp_mos, temp_motor=m.temp_motor, current_motor=m.iq * inv,
                    current_in=m.i_in, id=m.id, iq=m.iq * inv, duty=duty * inv,
                    rpm=m.erpm * inv, v_in=m.v_in, ah=m.ah, ahc=m.ahc, wh=m.wh, whc=m.whc,
                    tacho=m.tacho * inv, tacho_abs=m.tacho_abs, fault=m.fault, pos=m.pos,
                    vd=m.vd, vq=m.vq, status=(1 if m.has_timeout else 0))

    def values(self, pid, mask=0xFFFFFFFF):
        with self.lock:
            v = self._vals()
        vb = VB().u8(pid)
        if pid == COMM['GET_VALUES_SELECTIVE']:
            vb.u32(mask)
        fields = [
            (0, lambda: vb.d16(v['temp_mos'], 1e1)), (1, lambda: vb.d16(v['temp_motor'], 1e1)),
            (2, lambda: vb.d32(v['current_motor'], 1e2)), (3, lambda: vb.d32(v['current_in'], 1e2)),
            (4, lambda: vb.d32(v['id'], 1e2)), (5, lambda: vb.d32(v['iq'], 1e2)),
            (6, lambda: vb.d16(v['duty'], 1e3)), (7, lambda: vb.d32(v['rpm'], 1e0)),
            (8, lambda: vb.d16(v['v_in'], 1e1)), (9, lambda: vb.d32(v['ah'], 1e4)),
            (10, lambda: vb.d32(v['ahc'], 1e4)), (11, lambda: vb.d32(v['wh'], 1e4)),
            (12, lambda: vb.d32(v['whc'], 1e4)), (13, lambda: vb.i32(v['tacho'])),
            (14, lambda: vb.i32(v['tacho_abs'])), (15, lambda: vb.i8(v['fault'])),
            (16, lambda: vb.d32(v['pos'], 1e6)),
            (17, lambda: vb.u8(self.app.v.get('controller_id', 0))),
            (18, lambda: (vb.d16(v['temp_mos'] + 0.4, 1e1), vb.d16(v['temp_mos'] - 0.3, 1e1),
                          vb.d16(v['temp_mos'] + 0.1, 1e1))),
            (19, lambda: vb.d32(v['vd'], 1e3)), (20, lambda: vb.d32(v['vq'], 1e3)),
            (21, lambda: vb.u8(v['status'])),
        ]
        for bit, fn in fields:
            if mask & (1 << bit):
                fn()
        return vb

    def values_setup(self, pid, mask=0xFFFFFFFF):
        with self.lock:
            v = self._vals()
            poles = max(2, int(self.mc.v.get('si_motor_poles', 14)))
            gear = float(self.mc.v.get('si_gear_ratio', 1.0)) or 1.0
            wheel = float(self.mc.v.get('si_wheel_diameter', 0.083))
            cells = max(1, int(self.mc.v.get('si_battery_cells', 12)))
        speed = v['rpm'] / (poles / 2) / gear / 60.0 * math.pi * wheel
        lvl = max(0.0, min(1.0, (v['v_in'] / cells - 3.0) / 1.2))
        vb = VB().u8(pid)
        if pid == COMM['GET_VALUES_SETUP_SELECTIVE']:
            vb.u32(mask)
        fields = [
            (0, lambda: vb.d16(v['temp_mos'], 1e1)), (1, lambda: vb.d16(v['temp_motor'], 1e1)),
            (2, lambda: vb.d32(v['current_motor'], 1e2)), (3, lambda: vb.d32(v['current_in'], 1e2)),
            (4, lambda: vb.d16(v['duty'], 1e3)), (5, lambda: vb.d32(v['rpm'], 1e0)),
            (6, lambda: vb.d32(speed, 1e3)), (7, lambda: vb.d16(v['v_in'], 1e1)),
            (8, lambda: vb.d16(lvl, 1e3)), (9, lambda: vb.d32(v['ah'], 1e4)),
            (10, lambda: vb.d32(v['ahc'], 1e4)), (11, lambda: vb.d32(v['wh'], 1e4)),
            (12, lambda: vb.d32(v['whc'], 1e4)),
            (13, lambda: vb.d32(v['tacho'] / 6 / (poles / 2) * math.pi * wheel, 1e3)),
            (14, lambda: vb.d32(v['tacho_abs'] / 6 / (poles / 2) * math.pi * wheel, 1e3)),
            (15, lambda: vb.d32(v['pos'], 1e6)), (16, lambda: vb.i8(v['fault'])),
            (17, lambda: vb.u8(self.app.v.get('controller_id', 0))), (18, lambda: vb.u8(1)),
            (19, lambda: vb.d32(cells * 3.7 * 10.0, 1e3)), (20, lambda: vb.u32(0)),
            (21, lambda: vb.u32(int((time.time() - self.t0) * 1000))),
        ]
        for bit, fn in fields:
            if mask & (1 << bit):
                fn()
        return vb

    # ---------- 配置写入 ----------
    def apply_hw_limits(self, vals):
        cut = []
        for k, (lo, hi) in HW_LIM.items():
            if k in vals:
                x = vals[k]
                y = max(lo, min(hi, x))
                if abs(y - x) > 1e-9:
                    cut.append('%s %.3f->%.3f' % (k, x, y))
                    vals[k] = y
        return cut

    def set_conf(self, which, body):
        conf = self.mc if which == 'mc' else self.app
        ok, info, new = conf.deserialize(body)
        if not ok:
            self.ev('set_%sconf' % which, ok=False, reason=info)
            self.printf('Warning: Could not set %sconf due to wrong signature' % which)
            return None
        cut = self.apply_hw_limits(new) if which == 'mc' else []
        changed = {k: (conf.v[k], new[k]) for k in new
                   if k in conf.v and conf.v[k] != new[k]
                   and not (isinstance(new[k], float) and abs(conf.v[k] - new[k]) < 1e-6 * max(1, abs(new[k])))}
        with self.lock:
            conf.v = new
        self.ev('set_%sconf' % which, ok=True, sig='0x%08X' % conf.sig, changed=len(changed),
                sample={k: [round(a, 6) if isinstance(a, float) else a,
                            round(b, 6) if isinstance(b, float) else b]
                        for k, (a, b) in list(changed.items())[:12]},
                truncated=cut)
        return VB().u8(COMM['SET_MCCONF'] if which == 'mc' else COMM['SET_APPCONF'])

    # ---------- 检测 ----------
    def _sleep(self, s):
        time.sleep(s * self.speed)

    def _forced(self, f):
        with self.lock:
            self.motor.forced = f

    def _measure(self):
        g = lambda x, rel: x * (1 + random.gauss(0, rel))
        return (g(Motor.R, 0.012), g(Motor.L * 1e6, 0.015),
                g(Motor.LDLQ * 1e6, 0.05), g(Motor.LAMBDA, 0.006))

    def _check_fault(self, stage):
        f = self.fault_inject
        if f and f != 'flux':
            self.fault_inject = None
            self._forced(None)
            code = FAULT[f]
            self.ev('detect_fault', stage=stage, fault=FAULT_STR[code])
            return -100 + code
        return None

    def detect_all_foc(self, body):
        r = VR(body)
        detect_can = r.u8()
        max_power_loss = r.d32(1e3)
        min_current_in, max_current_in = r.d32(1e3), r.d32(1e3)
        openloop_rpm, sl_erpm = r.d32(1e3), r.d32(1e3)
        self.ev('detect_all_foc_start', detect_can=detect_can, max_power_loss=max_power_loss,
                min_current_in=min_current_in, max_current_in=max_current_in,
                openloop_rpm=openloop_rpm, sl_erpm=sl_erpm)
        self.detecting = True
        res = None
        try:
            # 1) 测 R / L（电机不转，有高频电流声）
            self._forced(('still', 6.0))
            self._sleep(2.0)
            res = self._check_fault('R/L')
            if res is not None:
                return res
            R, Lu, LDu, lam = self._measure()
            i_max = min(math.sqrt(max_power_loss / R / 1.5), HW_LIM['l_current_max'][1])
            # 2) 开环转起来测磁链
            self._forced(('spin', 6500.0, i_max / 2.5, 1800.0))
            self._sleep(4.5)
            if self.fault_inject == 'flux':
                self.fault_inject = None
                self._forced(None)
                self.ev('detect_fault', stage='flux', fault='flux linkage detection failed')
                return -10
            # 3) 观测器闭环跑一会儿
            self._forced(('spin', 6500.0, i_max / 3.0, 1800.0))
            self._sleep(1.5)
            # 4) 停下，检测传感器（本电机无霍尔 → 无感）
            self._forced(None)
            with self.lock:
                self.motor.mode = 'off'
            self._sleep(3.0)
            self._forced(('still', i_max / 3.0 * 0.2))
            self._sleep(1.5)
            self._forced(None)
            # 5) 按固件逻辑写回配置
            with self.lock:
                c = self.mc.v
                abs_max = min(i_max * 1.5, HW_LIM['l_abs_current_max'][1])
                upd = dict(l_current_max=i_max, l_current_min=-i_max, l_abs_current_max=abs_max,
                           motor_type=2, foc_motor_r=R, foc_motor_l=Lu * 1e-6,
                           foc_motor_ld_lq_diff=LDu * 1e-6, foc_motor_flux_linkage=lam,
                           foc_current_kp=(Lu * 1e-6) * 1000.0, foc_current_ki=R * 1000.0,
                           foc_observer_gain=1e-3 / lam ** 2 * 1e6, foc_sensor_mode=0,
                           foc_temp_comp_base_temp=self.motor.temp_motor)
                if abs(min_current_in) > 0.001:
                    upd['l_in_current_min'] = min_current_in
                if abs(max_current_in) > 0.001:
                    upd['l_in_current_max'] = max_current_in
                if abs(openloop_rpm) > 0.001:
                    upd['foc_openloop_rpm'] = openloop_rpm
                if abs(sl_erpm) > 0.001:
                    upd['foc_sl_erpm'] = sl_erpm
                c.update({k: v for k, v in upd.items() if k in c})
            self.ev('detect_all_foc_done', result=0, sensors='sensorless',
                    R_mohm=round(R * 1e3, 2), L_uH=round(Lu, 2), LdLq_uH=round(LDu, 2),
                    lambda_mWb=round(lam * 1e3, 3), i_max=round(i_max, 2),
                    abs_max=round(abs_max, 2), kp=round(Lu * 1e-3, 5), ki=round(R * 1e3, 3),
                    observer_gain_x1M=round(1e-3 / lam ** 2, 3))
            # 固件：先主动推送新配置，再回结果
            self.send(VB().u8(COMM['GET_MCCONF']) + self.mc.serialize())
            return 0
        finally:
            self._forced(None)
            self.detecting = False

    def detect_rl(self):
        self.ev('detect_rl_start')
        self._forced(('still', 5.0))
        self._sleep(1.8)
        self._forced(None)
        f = self._check_fault('R/L')
        if f is not None:
            return VB().u8(COMM['DETECT_MOTOR_R_L']).d32(0, 1e6).d32(0, 1e3).d32(0, 1e3)
        R, Lu, LDu, lam = self._measure()
        self.ev('detect_rl_done', R_mohm=round(R * 1e3, 2), L_uH=round(Lu, 2), LdLq_uH=round(LDu, 2))
        return VB().u8(COMM['DETECT_MOTOR_R_L']).d32(R, 1e6).d32(Lu, 1e3).d32(LDu, 1e3)

    def detect_flux_openloop(self, body):
        r = VR(body)
        cur, erpm_s, low_duty = r.d32(1e3), r.d32(1e3), r.d32(1e3)
        res, ind = r.d32(1e6), r.d32(1e8)
        self.ev('detect_flux_start', current=cur, erpm_per_sec=erpm_s, duty=low_duty,
                r_mohm=round(res * 1e3, 3), l_uH=round(ind * 1e6, 3))
        target = low_duty * (Motor.VBAT / math.sqrt(3)) / Motor.LAMBDA * 60 / (2 * math.pi)
        rate = max(erpm_s, 500.0)
        self._forced(('spin', target, cur, rate))
        self._sleep(min(target / rate, 8.0) + 1.0)
        self._forced(None)
        with self.lock:
            self.motor.mode = 'off'
        if self.fault_inject == 'flux':
            self.fault_inject = None
            self.ev('detect_fault', stage='flux', fault='flux=0')
            return VB().u8(COMM['DETECT_MOTOR_FLUX_LINKAGE_OPENLOOP']).d32(0.0, 1e7)
        lam = self._measure()[3]
        self.ev('detect_flux_done', lambda_mWb=round(lam * 1e3, 3), peak_erpm=round(target))
        return VB().u8(COMM['DETECT_MOTOR_FLUX_LINKAGE_OPENLOOP']).d32(lam, 1e7)

    def detect_hall(self, body):
        cur = VR(body).d32(1e3)
        self.ev('detect_hall_start', current=cur)
        self._forced(('spin', 300.0, cur, 300.0))
        self._sleep(3.0)
        self._forced(None)
        with self.lock:
            self.motor.mode = 'off'
        self.ev('detect_hall_done', res=1, note='no hall sensors on emulated motor')
        vb = VB().u8(COMM['DETECT_HALL_FOC'])
        for _ in range(8):
            vb.u8(0xFF)
        return vb.u8(1)

    # ---------- 终端 ----------
    def terminal(self, cmd):
        a = cmd.strip().split()
        self.ev('terminal', cmd=cmd.strip())
        if not a:
            return
        c = a[0]
        m = self.motor
        if c == 'help':
            self.printf('Valid commands are:\n'
                        'help\n  Show this help\n'
                        'faults\n  Print all faults that have occurred since the last reboot\n'
                        'hw_status\n  Print hardware status\n'
                        'emu_fault [none|uv|ov|drv|oc|flux]\n  (emulator) fail the next detection\n'
                        'emu_vin [volts]\n  (emulator) set battery voltage\n'
                        'emu_state\n  (emulator) print motor state')
        elif c == 'faults':
            if not self.faults_seen:
                self.printf('No faults registered since startup\n')
            else:
                self.printf('\n'.join('Fault: %s' % FAULT_STR.get(f, f) for f in self.faults_seen))
        elif c == 'hw_status':
            self.printf('Firmware: %d.%02d\nHardware: %s\nInput voltage: %.2f V\n'
                        'Motor ERPM: %.1f\nMOSFET temp: %.1f C' %
                        (self.fw[0], self.fw[1], self.hw, m.v_in, m.erpm, m.temp_mos))
        elif c == 'emu_fault' and len(a) > 1:
            self.fault_inject = None if a[1] == 'none' else a[1]
            self.printf('emu: next detection fault = %s' % a[1])
        elif c == 'emu_vin' and len(a) > 1:
            with self.lock:
                m.vbat = float(a[1])
            self.printf('emu: battery voltage = %.2f V' % m.vbat)
        elif c == 'emu_state':
            self.printf('emu: mode=%s cmd=%.3f erpm=%.1f iq=%.2f vin=%.2f fault=%d timeout=%d' %
                        (m.mode, m.cmd, m.erpm, m.iq, m.v_in, m.fault, m.has_timeout))
        else:
            self.printf('Invalid command: %s\ntype help to list all available commands' % c)

    # ---------- 分发 ----------
    def handle(self, pid, body):
        C = COMM
        if pid == C['FW_VERSION']:
            return self.fw_version()
        if pid == C['GET_VALUES']:
            return self.values(pid)
        if pid == C['GET_VALUES_SELECTIVE']:
            return self.values(pid, VR(body).u32())
        if pid == C['GET_VALUES_SETUP']:
            return self.values_setup(pid)
        if pid == C['GET_VALUES_SETUP_SELECTIVE']:
            return self.values_setup(pid, VR(body).u32())
        if pid in (C['GET_MCCONF'], C['GET_MCCONF_DEFAULT']):
            vals = self.mc.v if pid == C['GET_MCCONF'] else self.mc.defaults()
            self.ev('get_mcconf', default=pid == C['GET_MCCONF_DEFAULT'])
            return VB().u8(pid) + self.mc.serialize(vals)
        if pid in (C['GET_APPCONF'], C['GET_APPCONF_DEFAULT']):
            vals = self.app.v if pid == C['GET_APPCONF'] else self.app.defaults()
            self.ev('get_appconf', default=pid == C['GET_APPCONF_DEFAULT'])
            return VB().u8(pid) + self.app.serialize(vals)
        if pid == C['SET_MCCONF']:
            return self.set_conf('mc', body)
        if pid == C['SET_APPCONF']:
            return self.set_conf('app', body)
        if pid in (C['SET_MCCONF_TEMP'], C['SET_MCCONF_TEMP_SETUP']):
            r = VR(body)
            store, fwd, ack = r.u8(), r.u8(), r.u8()
            self.ev('set_mcconf_temp', setup=pid == C['SET_MCCONF_TEMP_SETUP'], ack=ack)
            return VB().u8(pid) if ack else None
        if pid == C['SET_BATTERY_CUT']:
            r = VR(body)
            start, end = r.d32(1e3), r.d32(1e3)
            with self.lock:
                self.mc.v['l_battery_cut_start'] = start
                self.mc.v['l_battery_cut_end'] = end
            self.ev('set_battery_cut', start=start, end=end)
            return VB().u8(pid)
        if pid == C['MOTOR_ESTOP']:
            ms = VR(body).u16()
            with self.lock:
                self.motor.mode, self.motor.cmd = 'off', 0.0
                self.ignore_until = time.time() + ms / 1000.0
                self.ignored_last = None
            self.ev('estop', ignore_ms=ms)
            return None
        if pid == C['ALIVE']:
            with self.lock:
                self.last_ctrl = time.time()
            return None
        if pid == C['SET_DUTY']:
            self.ctrl('duty', VR(body).d32(1e5)); return None
        if pid == C['SET_CURRENT']:
            self.ctrl('current', VR(body).d32(1e3)); return None
        if pid == C['SET_CURRENT_REL']:
            self.ctrl('current', VR(body).d32(1e5) * float(self.mc.v.get('l_current_max', 60))); return None
        if pid == C['SET_CURRENT_BRAKE']:
            self.ctrl('brake', VR(body).d32(1e3)); return None
        if pid == C['SET_RPM']:
            self.ctrl('rpm', float(VR(body).i32())); return None
        if pid == C['SET_HANDBRAKE']:
            self.ctrl('handbrake', VR(body).d32(1e3)); return None
        if pid == C['SET_POS']:
            self.ev('ctrl', mode='pos', cmd=VR(body).d32(1e6), note='position mode not modelled')
            return None
        if pid == C['TERMINAL_CMD']:
            self.terminal(body.split(b'\x00')[0].decode('utf-8', 'replace'))
            return None
        if pid == C['PING_CAN']:
            return VB().u8(pid)
        if pid == C['GET_DECODED_PPM']:
            return VB().u8(pid).d32(0, 1e6).d32(0, 1e6)
        if pid == C['GET_DECODED_ADC']:
            return VB().u8(pid).d32(0, 1e6).d32(0, 1e6).d32(0, 1e6).d32(0, 1e6)
        if pid == C['GET_DECODED_CHUK']:
            return VB().u8(pid).d32(0, 1e6)
        if pid == C['APP_DISABLE_OUTPUT']:
            return None
        # 以下为耗时命令：在独立线程里跑，免得阻塞轮询
        if pid == C['DETECT_APPLY_ALL_FOC']:
            self._bg(lambda: VB().u8(pid).i16(self.detect_all_foc(body)))
            return None
        if pid == C['DETECT_MOTOR_R_L']:
            self._bg(self.detect_rl); return None
        if pid == C['DETECT_MOTOR_FLUX_LINKAGE_OPENLOOP']:
            self._bg(lambda: self.detect_flux_openloop(body)); return None
        if pid == C['DETECT_HALL_FOC']:
            self._bg(lambda: self.detect_hall(body)); return None
        if pid == C['REBOOT']:
            self.ev('reboot')
            threading.Thread(target=self._reboot, daemon=True).start()
            return None
        return 'unhandled'

    def _bg(self, fn):
        def run():
            rsp = fn()
            if rsp is not None:
                self.send(rsp)
        threading.Thread(target=run, daemon=True).start()

    def _reboot(self):
        time.sleep(0.3)
        c = self.conn
        if c:
            try:
                c.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def serve(emu, port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', port))
    srv.listen(4)
    emu.ev('listen', port=port)
    while True:
        conn, addr = srv.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        emu.conn = conn
        emu.ev('connect', peer='%s:%d' % addr)
        threading.Thread(target=client, args=(emu, conn), daemon=True).start()


def client(emu, conn):
    buf = b''
    unhandled = set()
    try:
        while True:
            d = conn.recv(4096)
            if not d:
                break
            buf += d
            while buf:
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
                crc_ok = struct.unpack('>H', buf[1 + hl + n:1 + hl + n + 2])[0] == crc16(payload)
                buf = buf[total:]
                if not payload or not crc_ok:
                    continue
                pid = payload[0]
                try:
                    rsp = emu.handle(pid, payload[1:])
                except Exception as e:
                    emu.ev('error', pid=pid, cmd=COMM_NAME.get(pid, pid), err=repr(e))
                    rsp = None
                if rsp == 'unhandled':
                    if pid not in unhandled:
                        unhandled.add(pid)
                        emu.ev('unhandled', pid=pid)
                elif rsp:
                    emu.send(rsp)
    except OSError as e:
        emu.ev('disconnect', reason=repr(e))
    finally:
        if emu.conn is conn:
            emu.conn = None
        with emu.lock:
            emu.motor.mode = 'off'
        emu.ev('disconnect', reason='closed')
        conn.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cfgdir')
    ap.add_argument('--port', type=int, default=65102)
    ap.add_argument('--fw', default='7.00')
    ap.add_argument('--hw', default='DIY_70_80')
    ap.add_argument('--log', default=None)
    ap.add_argument('--fast', action='store_true')
    a = ap.parse_args()
    major, minor = a.fw.split('.')
    serve(Emu(a.cfgdir, (int(major), int(minor)), a.hw, a.log, a.fast), a.port)
