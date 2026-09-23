# -*- coding: utf-8 -*-
"""模拟器自测：不经过 VESC Tool，直接用协议验证模拟器行为。
用法: python emu_selftest.py <原版英文 res/config/7.00 目录>
"""
import sys, os, socket, struct, time, math, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vesc_emu as E

CFG = sys.argv[1]
PORT = 65199
emu = E.Emu(CFG, (7, 0), 'DIY_70_80', log=None, fast=True)
threading.Thread(target=E.serve, args=(emu, PORT), daemon=True).start()
time.sleep(0.5)

s = socket.create_connection(('127.0.0.1', PORT))
s.settimeout(5)
buf = b''


def send(p):
    s.sendall(E.frame(bytes(p)))


def recv(want=None, timeout=5.0):
    global buf
    end = time.time() + timeout
    while time.time() < end:
        while len(buf) >= 2:
            st = buf[0]; hl = st - 1
            n = int.from_bytes(buf[1:1 + hl], 'big')
            tot = 1 + hl + n + 3
            if len(buf) < tot:
                break
            pl = buf[1 + hl:1 + hl + n]; buf = buf[tot:]
            if want is None or pl[0] in want:
                return pl
        try:
            d = s.recv(65536)
            if d:
                buf += d
        except socket.timeout:
            pass
    return None


ok = []
def check(name, cond, info=''):
    ok.append(cond)
    print('%s  %s  %s' % ('PASS' if cond else 'FAIL', name, info))


# 1. d32auto 往返
vals = [0.0, 1.0, -1.0, 3.14159, 1e-6, 12345.678, -0.00517, 3.7e7]
rt = []
for v in vals:
    b = E.VB().d32auto(v)
    rt.append(E.VR(b).d32auto())
check('d32auto 往返', all(abs(a - b) <= 1e-6 * max(1, abs(a)) for a, b in zip(vals, rt)), rt)

# 2. 固件版本
send(E.VB().u8(0)); p = recv({0})
check('FW_VERSION', p is not None and p[1] == 7 and p[2] == 0, p[:14] if p else None)

# 3. 读配置 + 签名
send(E.VB().u8(14)); p = recv({14})
sig = struct.unpack('>I', p[1:5])[0]
check('GET_MCCONF 签名 = 7.00 原版 0x57AD8F53', sig == 0x57AD8F53, '0x%08X' % sig)
ok2, info, new = emu.mc.deserialize(p[1:])
check('GET_MCCONF 可被反序列化', ok2 and 'bytes left' in info, info)
check('出厂默认 l_current_max=60 (hwconf)', abs(new['l_current_max'] - 60) < 1e-3, new['l_current_max'])

# 4. 写配置：同样的字节写回 → ACK
send(E.VB().u8(13) + p[1:]); a = recv({13, 21})
check('SET_MCCONF 正确签名 → ACK', a is not None and a[0] == 13)

# 5. 写配置：改一个值 + 超过硬件上限 → 截断
v = dict(emu.mc.v); v['l_current_max'] = 100.0; v['s_pid_kp'] = 0.005
send(E.VB().u8(13) + emu.mc.serialize(v)); a = recv({13, 21})
check('SET_MCCONF 超限值被截断到 80A', a is not None and a[0] == 13 and abs(emu.mc.v['l_current_max'] - 80) < 1e-3,
      emu.mc.v['l_current_max'])
check('SET_MCCONF 其它值生效', abs(emu.mc.v['s_pid_kp'] - 0.005) < 1e-6, emu.mc.v['s_pid_kp'])
v['l_current_max'] = 60.0; v['s_pid_kp'] = 0.004
send(E.VB().u8(13) + emu.mc.serialize(v)); recv({13})

# 6. 写配置：错误签名 → 打印警告、不 ACK、值不变
bad = bytearray(E.VB().u8(13) + emu.mc.serialize(v)); bad[1] ^= 0xFF
send(bad); a = recv({13, 21})
check('SET_MCCONF 错误签名 → 警告且不 ACK', a is not None and a[0] == 21 and b'wrong signature' in a, a)

# 7. 转速控制 5000 ERPM + 保活
send(E.VB().u8(8).i32(5000))
t0 = time.time(); rpm = 0
while time.time() - t0 < 3.0:
    send(E.VB().u8(30)); time.sleep(0.2)
send(E.VB().u8(4)); p = recv({4})
r = E.VR(p[1:]); r.d16(10); r.d16(10); cm = r.d32(100); ci = r.d32(100); r.d32(100); r.d32(100); duty = r.d16(1000); rpm = r.d32(1)
check('SET_RPM 5000 → 3 s 后稳定在 5000±3%', abs(rpm - 5000) < 150, 'rpm=%.0f duty=%.3f Im=%.2fA Iin=%.2fA' % (rpm, duty, cm, ci))

# 8. 停止保活 → 超时停机
time.sleep(1.5)
send(E.VB().u8(4)); p = recv({4})
r = E.VR(p[1:]); [r.d16(10) for _ in range(2)]; [r.d32(100) for _ in range(4)]; r.d16(1000); rpm2 = r.d32(1)
check('停发保活 1.5 s → 超时停机、转速下降', rpm2 < rpm * 0.8 and emu.motor.mode == 'off', 'rpm=%.0f mode=%s' % (rpm2, emu.motor.mode))

# 9. 低于 s_pid_min_erpm 的目标 → 不转
time.sleep(4)
send(E.VB().u8(8).i32(500)); time.sleep(1.5); send(E.VB().u8(30))
check('目标 500 ERPM (< s_pid_min_erpm 900) → 不转', abs(emu.motor.erpm) < 50, '%.1f' % emu.motor.erpm)
send(E.VB().u8(6).d32(0, 1e3))

# 10. 一键检测
send(E.VB().u8(58).u8(0).d32(250, 1e3).d32(-40, 1e3).d32(60, 1e3).d32(1500, 1e3).d32(4000, 1e3))
seen_rpm = 0; t0 = time.time(); got_conf = got_res = None
while time.time() - t0 < 20 and got_res is None:
    send(E.VB().u8(4))
    p = recv({4, 14, 58}, timeout=1)
    if p is None:
        continue
    if p[0] == 4:
        r = E.VR(p[1:]); [r.d16(10) for _ in range(2)]; [r.d32(100) for _ in range(4)]; r.d16(1000)
        seen_rpm = max(seen_rpm, r.d32(1))
    elif p[0] == 14:
        got_conf = p
    elif p[0] == 58:
        got_res = struct.unpack('>h', p[1:3])[0]
    time.sleep(0.1)
check('检测过程中电机转起来', seen_rpm > 3000, 'peak %.0f ERPM' % seen_rpm)
check('检测：先推送新配置 再回结果码 0', got_conf is not None and got_res == 0, got_res)
_, _, nc = emu.mc.deserialize(got_conf[1:])
exp_imax = min(math.sqrt(250 / E.Motor.R / 1.5), 80)
check('检测出 R ≈ 28.5 mΩ', abs(nc['foc_motor_r'] * 1e3 - 28.5) < 1.5, '%.2f mΩ' % (nc['foc_motor_r'] * 1e3))
check('检测出 L ≈ 21.6 µH', abs(nc['foc_motor_l'] * 1e6 - 21.6) < 1.5, '%.2f µH' % (nc['foc_motor_l'] * 1e6))
check('检测出 λ ≈ 5.17 mWb', abs(nc['foc_motor_flux_linkage'] * 1e3 - 5.17) < 0.2, '%.3f mWb' % (nc['foc_motor_flux_linkage'] * 1e3))
check('电流上限 = √(P/R/1.5) 截断到 80', abs(nc['l_current_max'] - exp_imax) < 3, '%.2f A (期望≈%.2f)' % (nc['l_current_max'], exp_imax))
check('观测器增益 = 1e3/λ²', abs(nc['foc_observer_gain'] - 1e3 / nc['foc_motor_flux_linkage'] ** 2) < 1e3, '%.3e' % nc['foc_observer_gain'])
check('传感器模式 = 无感', nc['foc_sensor_mode'] == 0)
check('电池电流上限按向导参数写入', abs(nc['l_in_current_max'] - 60) < 1e-3 and abs(nc['l_in_current_min'] + 40) < 1e-3)

# 11. 注入故障 → 检测失败
emu.fault_inject = 'uv'
send(E.VB().u8(58).u8(0).d32(250, 1e3).d32(0, 1e3).d32(0, 1e3).d32(0, 1e3).d32(0, 1e3))
p = recv({58}, timeout=10)
check('注入欠压 → 检测结果码 -98', p is not None and struct.unpack('>h', p[1:3])[0] == -98,
      struct.unpack('>h', p[1:3])[0] if p else None)

# 12. 终端
send(E.VB().u8(20).s('hw_status')); p = recv({21})
check('终端 hw_status 有回应（ASCII）', p is not None and b'Firmware: 7.00' in p, p)

# 13. STOP 按钮的急停：COMM_MOTOR_ESTOP 期间忽略控制命令，到时后恢复
emu.fault_inject = None
send(E.VB().u8(8).i32(3000)); time.sleep(0.6)
running = emu.motor.mode == 'rpm'
send(E.VB().u8(159).u16(800))
send(E.VB().u8(8).i32(3000)); time.sleep(0.3)
blocked = emu.motor.mode == 'off'
time.sleep(0.7)
send(E.VB().u8(8).i32(3000)); time.sleep(0.2)
resumed = emu.motor.mode == 'rpm'
send(E.VB().u8(6).i32(0))
check('急停 800 ms：期间 SET_RPM 被忽略，到时后恢复响应', running and blocked and resumed,
      'running=%s blocked=%s resumed=%s' % (running, blocked, resumed))

print('\n合计 %d/%d 通过' % (sum(ok), len(ok)))
