import sys
import time
from functools import partial
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from networkx.algorithms.bipartite import color

def button_pressed(button: QPushButton):
    button.setStyleSheet("QPushButton {background-color: lightblue}")

def button_cleaned(button: QPushButton):
    button.setStyleSheet("QPushButton {}")

def alarm_activated(button: QPushButton):
    button.setStyleSheet("QPushButton {background-color: red}")

def alarm_deactivated(button: QPushButton):
    button.setStyleSheet("QPushButton {}")

'''模拟界面'''
class Example(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    '''初始化UI'''
    def initUI(self):
        layout = QHBoxLayout()

        '''左右两部分'''
        grid_layout_right = QGridLayout()
        grid_layout_left = QGridLayout()

        '''左右两部分'''
        left_wg = QWidget()
        right_wg = QWidget()
        left_wg.setLayout(grid_layout_left)
        right_wg.setLayout(grid_layout_right)

        '''添加到主布局'''
        layout.addWidget(left_wg)
        layout.addWidget(right_wg)
        self.setLayout(layout)

        labels = [f'{i}' for i in range(1, 21)]
        positions = [(i, j) for j in range(2) for i in range(10)]
        up_labels = [f'▲ {i}' for i in range(1, 21)]
        down_labels = [f'▼ {i}' for i in range(1, 21)]

        '''右侧五个电梯按钮设置'''
        for i in range(5):
            j = 1
            for position, label in zip(positions, labels):
                if label == '':
                    continue
                self.button = QPushButton(label)
                self.button.setFont(QFont("Microsoft YaHei", 12))
                self.button.setObjectName("{}+{}".format(i + 1, j))
                self.button.clicked.connect(partial(set_goal, i + 1, j))  # 将按钮的点击事件绑定到 set_goal 函数
                j += 1
                self.button.setMaximumHeight(60)
                grid_layout_right.addWidget(self.button, position[0] + 2, position[1] + i * 3)

        '''电梯五个楼层显示显示'''
        for i in range(5):
            self.lcd = QLCDNumber()
            self.lcd.setObjectName('{}'.format(i + 1))
            grid_layout_right.addWidget(self.lcd, 0, 3 * i, 2, 2)

        '''电梯开关门状态显示'''
        for i in range(5):
            self.button = QPushButton()
            self.button.setObjectName("state{}".format(i + 1))
            self.button.setMinimumHeight(80)
            grid_layout_right.addWidget(self.button, 13, 3 * i, 1, 2)

        '''添加报警按钮'''
        for i in range(5):
            self.alarm_button = QPushButton("报警")
            self.alarm_button.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
            self.alarm_button.setObjectName("alarm{}".format(i + 1))
            self.alarm_button.setMinimumHeight(40)
            self.alarm_button.clicked.connect(partial(toggle_alarm, i + 1))
            grid_layout_right.addWidget(self.alarm_button, 14, 3 * i, 1, 2)

        '''楼层向上按钮'''
        j = 0
        for i in up_labels:
            self.button = QPushButton(i)
            self.button.setFont(QFont("Microsoft YaHei"))
            self.button.setObjectName("up{}".format(j + 1))
            self.button.setMinimumHeight(40)
            self.button.clicked.connect(partial(set_global_up, j + 1))
            grid_layout_left.addWidget(self.button, 20 - j, 0)
            j += 1

        '''楼层向下按钮'''
        j = 0
        for i in down_labels:
            self.button = QPushButton(i)
            self.button.setFont(QFont("Microsoft YaHei"))
            self.button.setObjectName("down{}".format(j + 1))
            self.button.setMinimumHeight(40)
            self.button.clicked.connect(partial(set_global_down, j + 1))
            grid_layout_left.addWidget(self.button, 20 - j, 1)
            j += 1

        self.move(10, 10)
        self.setWindowTitle('电梯模拟调度系统')
        self.show()

'''多线程操作'''
class WorkThread(QThread):
    trigger = pyqtSignal(int)

    def __init__(self, the_int):
        super(WorkThread, self).__init__()
        self.int = the_int
        self.trigger.connect(check)

    def run(self):
        while True:
            '''检查全局列表 should_sleep 中对应索引的值'''
            if should_pause[self.int - 1] == 1:
                ex.findChild(QPushButton, "state{}".format(self.int)).setText("<-- -->")  # 开门
                time.sleep(2)
                ex.findChild(QPushButton, "state{}".format(self.int)).setText("--> <--")  # 关门
                time.sleep(2)
                ex.findChild(QPushButton, "state{}".format(self.int)).setText("")  # 重置状态
                should_pause[self.int - 1] = 0

            # 仅当电梯未处于报警状态时才执行检查和移动
            if not alarm_state[self.int - 1]:
                self.trigger.emit(self.int)

            time.sleep(1)

'''分配电梯'''
class DispatcherThread(QThread):
    def run(self):
        while True:
            self.dispatch()
            time.sleep(1)

    def dispatch(self):
        unassigned = {f: d for f, (d, e) in floor_requests.items() if e is None}

        '''遍历所有未分配的楼层请求'''
        for flr, direction in unassigned.items():
            best = self.select_elevator(flr, direction)
            if best is not None:
                elevator_target[best].add(flr)  # 分配给最合适的电梯
                floor_requests[flr] = (direction, best)  # 更新分配信息

    def select_elevator(self, flr, direction):
        candidates = []
        '''state[]:电梯状态,0空闲,1向上,-1向下'''
        for i in range(5):
            # 只考虑未处于报警状态的电梯
            if not alarm_state[i]:
                if state[i] == 0:
                    candidates.append((abs(floor[i] - flr), i))  # 计算电梯与楼层之间的距离
                elif state[i] == direction:
                    if direction == 1 and floor[i] <= flr:
                        candidates.append((flr - floor[i], i))
                    elif direction == -1 and floor[i] >= flr:
                        candidates.append((floor[i] - flr, i))
        if candidates:
            return min(candidates)[1]  # 返回最优电梯
        return None

'''状态更新和请求处理逻辑'''
def check(the_int):
    idx = the_int - 1  # 从0开始

    # 如果电梯处于报警状态，不执行任何操作
    if alarm_state[idx]:
        return

    if pause[idx] == 1:
        current_floor = floor[idx]  # 当前楼层

        # 电梯运行（更新楼层）
        if state[idx] == -1:
            floor[idx] -= 1
        elif state[idx] == 1:
            floor[idx] += 1

        current_floor = floor[idx]  # 更新位置
        open_door = False

        # --- 处理电梯内请求 ---
        if current_floor in elevator_target[idx]:
            elevator_target[idx].discard(current_floor)
            open_door = True

        # --- 处理楼层请求 ---
        if current_floor in floor_requests:
            direction, assigned_elevator = floor_requests[current_floor]

            # 检查是否是分配的电梯，或者顺路经过（方向一致且顺路）
            is_assigned = (assigned_elevator == idx)
            is_passby = (
                assigned_elevator is None and
                direction == state[idx] and
                (
                    (state[idx] == 1 and floor[idx] <= current_floor) or
                    (state[idx] == -1 and floor[idx] >= current_floor)
                )
            )

            if is_assigned or is_passby:
                # 清除按钮
                if direction == 1:
                    button_cleaned(ex.findChild(QPushButton, f"up{current_floor}"))
                else:
                    button_cleaned(ex.findChild(QPushButton, f"down{current_floor}"))

                # 更新请求归属，防止其他电梯再响应
                floor_requests[current_floor] = (direction, idx)

                # 移除请求（已处理）
                del floor_requests[current_floor]

                open_door = True


        # --- 清除电梯内按钮 ---
        button_cleaned(ex.findChild(QPushButton, f"{the_int}+{current_floor}"))

        # --- 开门处理 ---
        if open_door:
            should_pause[idx] = 1

        # --- 状态更新 ---
        target = elevator_target[idx]
        if state[idx] == 1:  # 向上
            if not any(f > current_floor for f in target):
                if any(f < current_floor for f in target):
                    state[idx] = -1
                else:
                    state[idx] = 0
        elif state[idx] == -1:  # 向下
            if not any(f < current_floor for f in target):
                if any(f > current_floor for f in target):
                    state[idx] = 1
                else:
                    state[idx] = 0
        elif state[idx] == 0:  # 停止状态
            if target:
                nearest = min(target, key=lambda f: abs(f - current_floor))
                state[idx] = 1 if nearest > current_floor else -1

        # --- 显示楼层 ---
        ex.findChild(QLCDNumber, f"{the_int}").display(current_floor)

'''电梯内请求'''
def set_goal(elev, flr):
    # 检查电梯是否处于报警状态，如果是则不接受新请求
    if alarm_state[elev - 1]:
        return

    btn = ex.findChild(QPushButton, f"{elev}+{flr}")  # 查找"{电梯编号}+{楼层编号}"的按钮
    button_pressed(btn)
    elevator_target[elev - 1].add(flr)

'''楼层间向上请求'''
def set_global_up(flr):
    btn = ex.findChild(QPushButton, f"up{flr}")  # 查找"up+{楼层编号}"的按钮
    button_pressed(btn)
    '''添加请求，不分配电梯'''
    if flr not in floor_requests:
        floor_requests[flr] = (1, None)  # (方向, 分配的电梯索引)

'''楼层间向下请求'''
def set_global_down(flr):
    btn = ex.findChild(QPushButton, f"down{flr}")  # 查找"down+{楼层编号}"的按钮
    button_pressed(btn)
    '''添加请求，不分配电梯'''
    if flr not in floor_requests:
        floor_requests[flr] = (-1, None)  # (方向, 分配的电梯索引)

'''切换报警状态'''
def toggle_alarm(elev):
    idx = elev - 1
    alarm_button = ex.findChild(QPushButton, f"alarm{elev}")

    # 切换报警状态
    alarm_state[idx] = not alarm_state[idx]

    if alarm_state[idx]:
        # 激活报警 - 按钮变红，电梯停止工作
        alarm_activated(alarm_button)
        # 电梯状态信息显示报警信息
        ex.findChild(QPushButton, f"state{elev}").setText("⚠")

        # 清除该电梯的所有楼层请求
        # 1. 清除电梯内部按钮
        for floor_num in range(1, 21):
            button = ex.findChild(QPushButton, f"{elev}+{floor_num}")
            if button:
                button_cleaned(button)

        # 2. 清除电梯的目标集合
        elevator_target[idx].clear()

        # 3. 处理全局楼层请求中分配给该电梯的请求
        floors_to_reassign = []
        for flr, (direction, assigned_elevator) in floor_requests.items():
            if assigned_elevator == idx:
                floors_to_reassign.append(flr)

        # 将这些请求标记为未分配，以便重新分配给其他电梯
        for flr in floors_to_reassign:
            direction = floor_requests[flr][0]
            floor_requests[flr] = (direction, None)
    else:
        # 解除报警 - 按钮恢复正常，电梯恢复工作
        alarm_deactivated(alarm_button)
        # 清除电梯状态信息
        ex.findChild(QPushButton, f"state{elev}").setText("")

if __name__ == '__main__':

    elevator_target = [set() for _ in range(5)]
    floor_requests = {}  # 全局字典，存储了所有楼层请求的信息
    should_pause = [0, 0, 0, 0, 0]  # 控制每部电梯是否需要暂停
    state = [0, 0, 0, 0, 0]  # 存储每部电梯的运行状态
    pause = [1, 1, 1, 1, 1]  # 每部电梯是否处于暂停状态
    floor = [1, 1, 1, 1, 1]  # 存储每部电梯当前所在的楼层
    alarm_state = [False, False, False, False, False]  # 存储每部电梯的报警状态

    '''创建并启动工作线程'''
    threads = [WorkThread(i + 1) for i in range(5)]
    for t in threads:
        t.start()  # 启动工作线程

    '''创建并启动调度线程'''
    dispatcher = DispatcherThread()
    dispatcher.start()  # 启动调度线程

    '''启动程序'''
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())