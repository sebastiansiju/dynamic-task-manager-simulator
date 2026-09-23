

import heapq
import itertools
import tkinter as tk
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from tkinter import messagebox, ttk
from typing import List, Optional, Tuple



# Scheduling engine (same design as Phase 1)


class ProcessState(Enum):
    NEW = "new"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"


@dataclass
class Process:
    pid: int
    name: str
    arrival_time: int
    burst_time: int
    priority: int = 0

    remaining_time: int = field(init=False)
    state: ProcessState = field(default=ProcessState.NEW, init=False)
    start_time: Optional[int] = field(default=None, init=False)
    completion_time: Optional[int] = field(default=None, init=False)
    waiting_time: int = field(default=0, init=False)

    def __post_init__(self):
        if self.burst_time <= 0:
            raise ValueError(f"burst_time must be a positive integer, got {self.burst_time!r}")
        if self.arrival_time < 0:
            raise ValueError(f"arrival_time must be >= 0, got {self.arrival_time!r}")
        self.remaining_time = self.burst_time

    @property
    def turnaround_time(self) -> Optional[int]:
        """Time from arrival to completion, or None while still running."""
        if self.completion_time is None:
            return None
        return self.completion_time - self.arrival_time


class Scheduler(ABC):
    """Shared simulation loop. Also records (pid, name, start, end) slices
    for every burst of CPU time, used to draw the Gantt chart."""

    name = "Base"

    def __init__(self, processes: List[Process]) -> None:
        self.incoming = sorted(processes, key=lambda p: p.arrival_time)
        self.completed: List[Process] = []
        self.timeline: List[Tuple[int, str, int, int]] = []  # pid, name, start, end
        self.time = 0

    @abstractmethod
    def _push(self, process: Process) -> None: ...

    @abstractmethod
    def _pop(self) -> Process: ...

    @abstractmethod
    def _has_ready(self) -> bool: ...

    @abstractmethod
    def _run_slice(self, process: Process) -> Optional[Process]:
        """Run one slice of `process`. Returns the process itself if it was
        preempted and still needs another turn, or None if it ran to
        completion."""
        ...

    def run(self) -> List[Process]:
        """Advance the simulation until every process has completed.

        Repeatedly admits any processes that have arrived by the current
        time into the ready structure, dispatches the next one via the
        subclass's `_push`/`_pop`/`_run_slice`, and fast-forwards the
        clock to the next arrival when nothing is ready to run. A process
        preempted mid-slice is requeued only after that slice's arrivals
        have been admitted, so it doesn't jump ahead of processes that
        were waiting for it to finish. Returns the completed processes.
        """
        pending = deque(self.incoming)
        requeue: Optional[Process] = None
        while pending or self._has_ready() or requeue is not None:
            while pending and pending[0].arrival_time <= self.time:
                p = pending.popleft()
                p.state = ProcessState.READY
                self._push(p)
            if requeue is not None:
                self._push(requeue)
                requeue = None
            if self._has_ready():
                p = self._pop()
                requeue = self._run_slice(p)
            else:
                self.time = pending[0].arrival_time
        return self.completed

    def _run_to_completion(self, process: Process) -> None:
        if process.start_time is None:
            process.start_time = self.time
            process.waiting_time = self.time - process.arrival_time
        process.state = ProcessState.RUNNING
        start = self.time
        self.time += process.remaining_time
        self.timeline.append((process.pid, process.name, start, self.time))
        process.remaining_time = 0
        process.completion_time = self.time
        process.state = ProcessState.COMPLETED
        self.completed.append(process)


class FCFSScheduler(Scheduler):
    """Runs ready processes strictly in arrival order, each to completion."""

    name = "First-Come-First-Served"

    def __init__(self, processes: List[Process]) -> None:
        super().__init__(processes)
        self._queue: deque[Process] = deque()

    def _push(self, process: Process) -> None: self._queue.append(process)
    def _pop(self) -> Process: return self._queue.popleft()
    def _has_ready(self) -> bool: return len(self._queue) > 0
    def _run_slice(self, process: Process) -> Optional[Process]:
        self._run_to_completion(process)
        return None


class SJFScheduler(Scheduler):
    """Non-preemptive: always picks the ready process with the shortest burst time."""

    name = "Shortest Job First"

    def __init__(self, processes: List[Process]) -> None:
        super().__init__(processes)
        self._counter = itertools.count()
        self._heap: list = []

    def _push(self, process: Process) -> None:
        heapq.heappush(self._heap, (process.burst_time, next(self._counter), process))

    def _pop(self) -> Process:
        _, _, process = heapq.heappop(self._heap)
        return process

    def _has_ready(self) -> bool: return len(self._heap) > 0
    def _run_slice(self, process: Process) -> Optional[Process]:
        self._run_to_completion(process)
        return None


class PriorityScheduler(Scheduler):
    """Non-preemptive: always picks the ready process with the lowest priority number."""

    name = "Priority"

    def __init__(self, processes: List[Process]) -> None:
        super().__init__(processes)
        self._counter = itertools.count()
        self._heap: list = []

    def _push(self, process: Process) -> None:
        heapq.heappush(self._heap, (process.priority, next(self._counter), process))

    def _pop(self) -> Process:
        _, _, process = heapq.heappop(self._heap)
        return process

    def _has_ready(self) -> bool: return len(self._heap) > 0
    def _run_slice(self, process: Process) -> Optional[Process]:
        self._run_to_completion(process)
        return None


DEFAULT_QUANTUM = 3


class RoundRobinScheduler(Scheduler):
    """Preemptive: each ready process gets at most `quantum` time units per turn
    before being requeued behind whatever else has since become ready."""

    name = "Round Robin"

    def __init__(self, processes: List[Process], quantum: int = DEFAULT_QUANTUM) -> None:
        if quantum <= 0:
            raise ValueError(f"quantum must be a positive integer, got {quantum!r}")
        super().__init__(processes)
        self.quantum = quantum
        self._queue: deque[Process] = deque()

    def _push(self, process: Process) -> None: self._queue.append(process)
    def _pop(self) -> Process: return self._queue.popleft()
    def _has_ready(self) -> bool: return len(self._queue) > 0

    def _run_slice(self, process: Process) -> Optional[Process]:
        if process.start_time is None:
            process.start_time = self.time
            process.waiting_time = self.time - process.arrival_time
        process.state = ProcessState.RUNNING

        slice_len = min(self.quantum, process.remaining_time)
        start = self.time
        self.time += slice_len
        self.timeline.append((process.pid, process.name, start, self.time))
        process.remaining_time -= slice_len

        if process.remaining_time <= 0:
            process.completion_time = self.time
            process.state = ProcessState.COMPLETED
            self.completed.append(process)
            return None

        process.state = ProcessState.READY
        return process


ALGORITHMS = {
    "First-Come-First-Served (FCFS)": FCFSScheduler,
    "Shortest Job First (SJF)": SJFScheduler,
    "Priority": PriorityScheduler,
    "Round Robin": RoundRobinScheduler,
}

# A small fixed palette so each PID keeps a consistent colour across runs
GANTT_COLORS = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52",
    "#8172B2", "#937860", "#DA8BC3", "#8C8C8C",
    "#CCB974", "#64B5CD",
]

# Gantt chart layout, in canvas pixels
GANTT_MIN_WIDTH = 600
GANTT_CANVAS_HEIGHT = 180
GANTT_MARGIN_LEFT = 50
GANTT_MARGIN_RIGHT = 20
GANTT_BAR_TOP = 30
GANTT_BAR_HEIGHT = 40
GANTT_AXIS_GAP = 20  # vertical gap between the bars and the time axis line
GANTT_MAX_AXIS_TICKS = 15
GANTT_MIN_LABEL_SLICE_WIDTH = 22  # slices narrower than this skip their text label


# ===========================================================================
# GUI
# ===========================================================================

class TaskManagerGUI(tk.Tk):
    """Tkinter front end: lets the user build a process list, pick a
    scheduling algorithm, run it against the engine above, and view the
    resulting wait/turnaround times and a Gantt chart of the timeline."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Dynamic Task Manager Simulator")
        self.geometry("980x680")
        self.minsize(880, 600)

        self._next_pid = 1
        self._build_layout()
        self._load_sample_processes()

    # ---------------------------------------------------------------- layout
    def _build_layout(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        left = ttk.Frame(root)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))

        right = ttk.Frame(root)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self._build_input_panel(left)
        self._build_results_panel(right)

    # ---- left panel: add processes + choose algorithm -----------------
    def _build_input_panel(self, parent):
        form = ttk.LabelFrame(parent, text="Add Process", padding=10)
        form.pack(fill="x")

        self.name_var = tk.StringVar()
        self.arrival_var = tk.StringVar(value="0")
        self.burst_var = tk.StringVar(value="5")
        self.priority_var = tk.StringVar(value="1")

        self._labeled_entry(form, "Name", self.name_var, 0)
        self._labeled_entry(form, "Arrival time", self.arrival_var, 1)
        self._labeled_entry(form, "Burst time", self.burst_var, 2)
        self._labeled_entry(form, "Priority (lower=higher)", self.priority_var, 3)

        btn_row = ttk.Frame(form)
        btn_row.grid(row=4, column=0, columnspan=2, pady=(8, 0), sticky="ew")
        ttk.Button(btn_row, text="Add", command=self._add_process).pack(side="left", expand=True, fill="x")
        ttk.Button(btn_row, text="Remove selected", command=self._remove_selected).pack(side="left", expand=True, fill="x", padx=(6, 0))

        ttk.Button(form, text="Load sample workload", command=self._load_sample_processes).grid(
            row=5, column=0, columnspan=2, pady=(8, 0), sticky="ew")
        ttk.Button(form, text="Clear all", command=self._clear_processes).grid(
            row=6, column=0, columnspan=2, pady=(4, 0), sticky="ew")

        list_frame = ttk.LabelFrame(parent, text="Processes", padding=10)
        list_frame.pack(fill="both", expand=True, pady=(10, 0))

        columns = ("pid", "name", "arrival", "burst", "priority")
        self.process_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        for col, label, width in [
            ("pid", "PID", 40), ("name", "Name", 90), ("arrival", "Arr", 45),
            ("burst", "Burst", 50), ("priority", "Prio", 45),
        ]:
            self.process_tree.heading(col, text=label)
            self.process_tree.column(col, width=width, anchor="center")
        self.process_tree.pack(fill="both", expand=True)

        algo_frame = ttk.LabelFrame(parent, text="Algorithm", padding=10)
        algo_frame.pack(fill="x", pady=(10, 0))

        self.algo_var = tk.StringVar(value=list(ALGORITHMS.keys())[0])
        algo_combo = ttk.Combobox(algo_frame, textvariable=self.algo_var, state="readonly",
                                   values=list(ALGORITHMS.keys()))
        algo_combo.pack(fill="x")
        algo_combo.bind("<<ComboboxSelected>>", self._on_algo_change)

        self.quantum_label = ttk.Label(algo_frame, text="Time quantum:")
        self.quantum_var = tk.StringVar(value=str(DEFAULT_QUANTUM))
        self.quantum_entry = ttk.Entry(algo_frame, textvariable=self.quantum_var, width=6)
        self._toggle_quantum_field()

        ttk.Button(parent, text="▶  Run Simulation", command=self._run_simulation).pack(
            fill="x", pady=(10, 0), ipady=4)

    def _labeled_entry(self, parent, label, var, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(parent, textvariable=var, width=14).grid(row=row, column=1, sticky="ew", pady=2, padx=(6, 0))
        parent.columnconfigure(1, weight=1)

    def _on_algo_change(self, _event=None):
        self._toggle_quantum_field()

    def _toggle_quantum_field(self):
        if self.algo_var.get() == "Round Robin":
            self.quantum_label.pack(anchor="w", pady=(6, 0))
            self.quantum_entry.pack(anchor="w")
        else:
            self.quantum_label.pack_forget()
            self.quantum_entry.pack_forget()

    # ---- right panel: results table + gantt chart ----------------------
    def _build_results_panel(self, parent):
        summary = ttk.LabelFrame(parent, text="Summary", padding=10)
        summary.grid(row=0, column=0, sticky="ew")
        self.summary_var = tk.StringVar(value="Add processes and click Run Simulation.")
        ttk.Label(summary, textvariable=self.summary_var, justify="left").pack(anchor="w")

        results_frame = ttk.LabelFrame(parent, text="Results", padding=10)
        results_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(1, weight=1)

        columns = ("pid", "name", "arrival", "burst", "priority", "start", "finish", "wait", "turnaround")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=8)
        headers = {
            "pid": "PID", "name": "Name", "arrival": "Arrival", "burst": "Burst",
            "priority": "Prio", "start": "Start", "finish": "Finish",
            "wait": "Wait", "turnaround": "Turnaround",
        }
        for col in columns:
            self.results_tree.heading(col, text=headers[col])
            self.results_tree.column(col, width=85, anchor="center")
        self.results_tree.grid(row=0, column=0, sticky="ew")

        gantt_frame = ttk.LabelFrame(parent, text="Gantt Chart", padding=10)
        gantt_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        parent.rowconfigure(2, weight=1)

        self.gantt_canvas = tk.Canvas(gantt_frame, background="white", height=GANTT_CANVAS_HEIGHT)
        self.gantt_canvas.pack(fill="both", expand=True)

    # ------------------------------------------------------------ actions
    def _add_process(self):
        name = self.name_var.get().strip() or f"Task{self._next_pid}"
        try:
            arrival = int(self.arrival_var.get())
            burst = int(self.burst_var.get())
            priority = int(self.priority_var.get())
            if burst <= 0 or arrival < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid input", "Arrival, burst and priority must be integers "
                                                    "(burst > 0, arrival >= 0).")
            return

        self.process_tree.insert("", "end", values=(self._next_pid, name, arrival, burst, priority))
        self._next_pid += 1
        self.name_var.set("")

    def _remove_selected(self):
        for item in self.process_tree.selection():
            self.process_tree.delete(item)

    def _clear_processes(self):
        for item in self.process_tree.get_children():
            self.process_tree.delete(item)
        self._next_pid = 1

    def _load_sample_processes(self):
        self._clear_processes()
        sample = [
            ("Compile", 0, 8, 3),
            ("WebSrv", 1, 4, 1),
            ("Backup", 2, 9, 4),
            ("DBQuery", 3, 5, 2),
            ("Render", 4, 12, 5),
            ("Ping", 5, 2, 1),
        ]
        for name, arrival, burst, priority in sample:
            self.process_tree.insert("", "end", values=(self._next_pid, name, arrival, burst, priority))
            self._next_pid += 1

    def _collect_processes(self) -> List[Process]:
        processes = []
        for item in self.process_tree.get_children():
            pid, name, arrival, burst, priority = self.process_tree.item(item, "values")
            processes.append(Process(pid=int(pid), name=name, arrival_time=int(arrival),
                                      burst_time=int(burst), priority=int(priority)))
        return processes

    def _run_simulation(self):
        processes = self._collect_processes()
        if not processes:
            messagebox.showwarning("No processes", "Add at least one process before running.")
            return

        algo_name = self.algo_var.get()
        scheduler_cls = ALGORITHMS[algo_name]

        if scheduler_cls is RoundRobinScheduler:
            try:
                quantum = int(self.quantum_var.get())
                if quantum <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid quantum", "Time quantum must be a positive integer.")
                return
            scheduler = RoundRobinScheduler(processes, quantum=quantum)
        else:
            scheduler = scheduler_cls(processes)

        scheduler.run()
        self._render_results(scheduler)

    # ------------------------------------------------------------ render
    def _render_results(self, scheduler: Scheduler):
        for row in self.results_tree.get_children():
            self.results_tree.delete(row)

        completed = sorted(scheduler.completed, key=lambda p: p.pid)
        total_wait = sum(p.waiting_time for p in completed)
        total_turn = sum(p.turnaround_time for p in completed)

        for p in completed:
            self.results_tree.insert("", "end", values=(
                p.pid, p.name, p.arrival_time, p.burst_time, p.priority,
                p.start_time, p.completion_time, p.waiting_time, p.turnaround_time,
            ))

        n = len(completed)
        avg_wait = total_wait / n if n else 0
        avg_turn = total_turn / n if n else 0
        self.summary_var.set(
            f"Algorithm: {scheduler.name}\n"
            f"Average waiting time: {avg_wait:.2f}      "
            f"Average turnaround time: {avg_turn:.2f}      "
            f"Makespan: {scheduler.time}"
        )

        self._draw_gantt(scheduler)

    def _draw_gantt(self, scheduler: Scheduler):
        canvas = self.gantt_canvas
        canvas.delete("all")
        canvas.update_idletasks()

        width = max(canvas.winfo_width(), GANTT_MIN_WIDTH)
        margin_left = GANTT_MARGIN_LEFT
        margin_right = GANTT_MARGIN_RIGHT
        bar_top = GANTT_BAR_TOP
        bar_height = GANTT_BAR_HEIGHT
        axis_y = bar_top + bar_height + GANTT_AXIS_GAP

        makespan = max(scheduler.time, 1)
        usable_width = width - margin_left - margin_right
        px_per_unit = usable_width / makespan

        pid_color = {}
        for pid, _name, _s, _e in scheduler.timeline:
            if pid not in pid_color:
                pid_color[pid] = GANTT_COLORS[(pid - 1) % len(GANTT_COLORS)]

        # time axis
        canvas.create_line(margin_left, axis_y, width - margin_right, axis_y, fill="#888")
        step = max(1, makespan // GANTT_MAX_AXIS_TICKS)
        t = 0
        while t <= makespan:
            x = margin_left + t * px_per_unit
            canvas.create_line(x, axis_y - 5, x, axis_y + 5, fill="#888")
            canvas.create_text(x, axis_y + 12, text=str(t), font=("TkDefaultFont", 8))
            t += step

        # execution slices
        for pid, name, start, end in scheduler.timeline:
            x1 = margin_left + start * px_per_unit
            x2 = margin_left + end * px_per_unit
            color = pid_color[pid]
            canvas.create_rectangle(x1, bar_top, x2, bar_top + bar_height,
                                     fill=color, outline="white")
            if x2 - x1 > GANTT_MIN_LABEL_SLICE_WIDTH:
                canvas.create_text((x1 + x2) / 2, bar_top + bar_height / 2,
                                    text=name, fill="white", font=("TkDefaultFont", 8, "bold"))

        canvas.create_text(margin_left, 12, anchor="w",
                            text="Execution timeline (each colour = one process, PID order)",
                            font=("TkDefaultFont", 9, "italic"))


def main():
    app = TaskManagerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()