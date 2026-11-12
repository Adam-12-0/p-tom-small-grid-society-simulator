"""Two interactive Qt windows. The world and PSL rules stay in separate files."""
from __future__ import annotations

import threading


def display(run_steps, config_type, start_event_loop: bool = True):
    """Open a grid window and a synchronized count-over-time plot."""
    import pyqtgraph as pg
    from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

    pg.setConfigOption("background", "#0d1117")
    pg.setConfigOption("foreground", "#e6edf3")
    app = pg.mkQApp("Information flow")
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    for role, color in (("Window", "#161b22"), ("WindowText", "#e6edf3"),
                        ("Base", "#0d1117"), ("Text", "#e6edf3"),
                        ("Button", "#21262d"), ("ButtonText", "#e6edf3"),
                        ("Highlight", "#596a7c"), ("HighlightedText", "#ffffff")):
        palette.setColor(getattr(QtGui.QPalette.ColorRole, role), QtGui.QColor(color))
    app.setPalette(palette)

    class Bridge(QtCore.QObject):
        frame_ready = QtCore.pyqtSignal(int, object)
        run_finished = QtCore.pyqtSignal(int, str)

    bridge = Bridge()

    # This is a separate, large window. It shows the whole computed history.
    count_window = QtWidgets.QWidget()
    count_window.setWindowTitle("People informed over time")
    count_window.resize(650, 500)
    count_layout = QtWidgets.QVBoxLayout(count_window)
    count_label = QtWidgets.QLabel("Starting simulation...")
    count_label.setStyleSheet("font-size: 18px; font-weight: 600;")
    count_layout.addWidget(count_label)
    count_plot = pg.PlotWidget()
    count_layout.addWidget(count_plot)
    count_plot.setLabel("bottom", "Time step")
    count_plot.setLabel("left", "People informed")
    count_plot.showGrid(x=True, y=True, alpha=0.25)
    count_curve = count_plot.plot(pen=pg.mkPen("#ff4d5a", width=3))
    target_line = pg.InfiniteLine(angle=0, pen=pg.mkPen("#64748b", width=1,
                                  style=QtCore.Qt.PenStyle.DashLine))
    time_cursor = pg.InfiniteLine(angle=90, pen=pg.mkPen("#facc15", width=2))
    count_plot.addItem(target_line)
    count_plot.addItem(time_cursor)

    class Window(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Information flow | 25 × 25 grid")
            self.resize(650, 600)
            self.frames = []
            self.generation = 0
            self.cancel = threading.Event()
            self.finished = False
            self.paused = False

            layout = QtWidgets.QVBoxLayout(self)
            controls = QtWidgets.QHBoxLayout()
            controls.addWidget(QtWidgets.QLabel("Population (1–625):"))
            self.population_input = QtWidgets.QSpinBox()
            self.population_input.setRange(1, 625)
            self.population_input.setValue(40)
            self.population_input.setKeyboardTracking(False)
            controls.addWidget(self.population_input)
            self.restart_button = QtWidgets.QPushButton("Restart simulation")
            controls.addWidget(self.restart_button)
            controls.addStretch()
            layout.addLayout(controls)

            self.counter_label = QtWidgets.QLabel()
            self.counter_label.setStyleSheet("font-size: 18px; font-weight: 600;")
            layout.addWidget(self.counter_label)
            self.status_label = QtWidgets.QLabel("Starting...")
            layout.addWidget(self.status_label)
            layout.addWidget(QtWidgets.QLabel(
                '<span style="color:#ffffff">●</span> White: uninformed    '
                '<span style="color:#ff4d5a">●</span> Red: informed    □ Fixed source'))

            grid_row = QtWidgets.QHBoxLayout()
            grid_row.addStretch()
            grid = pg.PlotWidget()
            grid.setFixedSize(400, 400)
            grid_row.addWidget(grid)
            grid_row.addStretch()
            layout.addLayout(grid_row)
            grid.setAspectLocked(True)
            grid.setXRange(-0.5, 24.5, padding=0)
            grid.setYRange(-0.5, 24.5, padding=0)
            grid.setMouseEnabled(x=False, y=False)
            grid.hideButtons()
            grid.getAxis("bottom").setTicks([[(i, str(i) if i % 5 == 0 else "")
                                                for i in range(25)]])
            grid.getAxis("left").setTicks([[(i, str(i) if i % 5 == 0 else "")
                                              for i in range(25)]])
            grid.setLabel("bottom", "Grid column")
            grid.setLabel("left", "Grid row")
            for boundary in (i + 0.5 for i in range(24)):
                grid.addItem(pg.InfiniteLine(pos=boundary, angle=90,
                                             pen=pg.mkPen("#30363d", width=1)))
                grid.addItem(pg.InfiniteLine(pos=boundary, angle=0,
                                             pen=pg.mkPen("#30363d", width=1)))
            grid.addItem(pg.ScatterPlotItem(
                pos=[(12, 12)], symbol="s", size=24,
                brush=pg.mkBrush(0, 0, 0, 0), pen=pg.mkPen("#ffffff", width=2)))
            self.dots = pg.ScatterPlotItem(size=12, pen=pg.mkPen("#0d1117", width=0.6))
            grid.addItem(self.dots)

            timeline = QtWidgets.QHBoxLayout()
            self.play_button = QtWidgets.QPushButton("Pause")
            timeline.addWidget(self.play_button)
            timeline.addWidget(QtWidgets.QLabel("Time:"))
            self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            self.slider.setRange(0, 0)
            timeline.addWidget(self.slider, stretch=1)
            self.time_label = QtWidgets.QLabel("0")
            timeline.addWidget(self.time_label)
            layout.addLayout(timeline)

            self.timer = QtCore.QTimer(self)
            self.timer.setInterval(150)
            self.timer.timeout.connect(self.advance)
            self.slider.valueChanged.connect(self.render_frame)
            self.slider.sliderPressed.connect(self.pause)
            self.play_button.clicked.connect(self.toggle_play)
            self.restart_button.clicked.connect(self.restart)
            self.population_input.editingFinished.connect(self.population_edited)
            bridge.frame_ready.connect(self.receive_frame)
            bridge.run_finished.connect(self.finish_run)
            self.restart()

        def population_edited(self):
            if self.frames and len(self.frames[0].positions) != self.population_input.value():
                self.restart()

        def restart(self):
            self.cancel.set()
            self.cancel = threading.Event()
            cancel_event = self.cancel
            self.generation += 1
            generation = self.generation
            config = config_type(people=self.population_input.value())
            self.frames = []
            self.finished = False
            self.paused = False
            self.slider.setRange(0, 0)
            self.counter_label.setText(f"Population {config.people} | initializing source contacts")
            self.status_label.setText("Computing PSL steps...")
            self.dots.setData([])
            count_label.setText(f"Population {config.people} | waiting for time 0")
            count_curve.setData([], [])
            target_line.setPos(config.people)
            time_cursor.setPos(0)
            count_plot.setYRange(0, max(1, config.people), padding=0.05)
            count_plot.setXRange(0, 10, padding=0)
            self.play_button.setText("Pause")
            self.timer.start()

            def compute():
                try:
                    for frame in run_steps(config, engine="psl"):
                        if cancel_event.is_set() or generation != self.generation:
                            return
                        bridge.frame_ready.emit(generation, frame)
                    bridge.run_finished.emit(generation, "")
                except Exception as error:
                    bridge.run_finished.emit(generation, str(error))

            threading.Thread(target=compute, daemon=True).start()

        def receive_frame(self, generation, frame):
            if generation != self.generation:
                return
            self.frames.append(frame)
            self.slider.setMaximum(frame.step)
            count_curve.setData([f.step for f in self.frames],
                                [len(f.informed) for f in self.frames])
            count_plot.setXRange(0, max(10, frame.step), padding=0)
            if frame.step == 0:
                self.render_frame(0)
            if len(frame.informed) == len(frame.positions):
                self.status_label.setText(f"Goal reached at time {frame.step}.")

        def finish_run(self, generation, error):
            if generation != self.generation:
                return
            self.finished = True
            if error:
                self.status_label.setText(f"Simulation error: {error}")
                self.timer.stop()
            elif self.frames and len(self.frames[-1].informed) < len(self.frames[-1].positions):
                self.status_label.setText(f"Goal not reached by time {self.frames[-1].step}.")

        def render_frame(self, step):
            if not self.frames or step >= len(self.frames):
                return
            frame = self.frames[step]
            self.dots.setData([
                {"pos": point, "brush": pg.mkBrush("#ff4d5a" if i in frame.informed else "#ffffff")}
                for i, point in enumerate(frame.positions)
            ])
            self.counter_label.setText(
                f"Time {frame.step}  |  {len(frame.informed)} / {len(frame.positions)} informed"
            )
            self.time_label.setText(str(frame.step))
            time_cursor.setPos(frame.step)
            count_label.setText(
                f"Time {frame.step}: {len(frame.informed)} of {len(frame.positions)} informed"
            )

        def advance(self):
            if self.paused:
                return
            next_step = self.slider.value() + 1
            if next_step < len(self.frames):
                self.slider.setValue(next_step)
            elif self.finished:
                self.pause()

        def pause(self):
            self.paused = True
            self.play_button.setText("Play")

        def toggle_play(self):
            if not self.paused:
                self.pause()
                return
            if self.finished and self.frames and self.slider.value() == len(self.frames) - 1:
                self.slider.setValue(0)
            self.paused = False
            self.play_button.setText("Pause")
            self.timer.start()

        def closeEvent(self, event):
            self.cancel.set()
            count_window.close()
            super().closeEvent(event)

    window = Window()
    window.show()
    count_window.move(window.x() + window.width() + 20, window.y())
    count_window.show()
    if start_event_loop:
        app.exec()
    return app, window, count_window
