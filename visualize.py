"""Animate a finished grid-world run in a responsive PyQtGraph window."""
from __future__ import annotations

import argparse
from grid_world import Config, run


def show(history, size: int, interval_ms: int = 120):
    import pyqtgraph as pg
    from pyqtgraph.Qt import QtCore, QtWidgets

    app = pg.mkQApp("Grid information flow")
    window = QtWidgets.QWidget()
    window.setWindowTitle("Grid information flow")
    layout = QtWidgets.QVBoxLayout(window)
    label = QtWidgets.QLabel()
    layout.addWidget(label)
    canvas = pg.GraphicsLayoutWidget()
    layout.addWidget(canvas)
    grid = canvas.addPlot(row=0, col=0)
    grid.setAspectLocked(True)
    grid.setXRange(-0.5, size - 0.5, padding=0)
    grid.setYRange(-0.5, size - 0.5, padding=0)
    grid.showGrid(x=True, y=True, alpha=0.2)
    grid.setLabel("bottom", "x")
    grid.setLabel("left", "y")
    dots = pg.ScatterPlotItem(size=12, pen=None)
    grid.addItem(dots)
    progress = canvas.addPlot(row=1, col=0, title="Fraction informed")
    progress.setXRange(0, max(1, history[-1].step), padding=0)
    progress.setYRange(0, 1.05, padding=0)
    progress.setLabel("bottom", "Time step")
    curve = progress.plot(pen=pg.mkPen("#15803d", width=3))
    state = {"index": 0}

    def update():
        index = state["index"]
        frame = history[index]
        dots.setData([{"pos": p, "brush": pg.mkBrush("#15803d" if i in frame.informed else "#dc2626")}
                      for i, p in enumerate(frame.positions)])
        label.setText(f"Time: {frame.step}    Informed: {len(frame.informed)}/{len(frame.positions)}"
                      f" ({frame.fraction_informed:.0%})")
        curve.setData([f.step for f in history[:index+1]],
                      [f.fraction_informed for f in history[:index+1]])
        if index + 1 == len(history):
            timer.stop()
        else:
            state["index"] += 1

    timer = QtCore.QTimer(window)
    timer.timeout.connect(update)
    update()
    timer.start(interval_ms)
    window.resize(900, 800)
    window.show()
    return app, window, timer


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--people", type=int, default=40)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--interval-ms", type=int, default=120)
    args = parser.parse_args()
    config = Config(size=args.size, people=args.people, seed=args.seed)
    app, window, timer = show(run(config), config.size, args.interval_ms)
    app.exec()
