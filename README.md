# Dynamic Task Manager Simulator

![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A desktop CPU process-scheduling simulator built with Python and Tkinter. Define a workload of processes, pick a scheduling algorithm, and see the resulting execution order as a colour-coded Gantt chart alongside per-process waiting and turnaround times.

Built for the **502IT** coursework as a demonstration of object-oriented design, abstract base classes, and classic queue/heap data structures.

## Features

- **Four scheduling algorithms** selectable at runtime, sharing one simulation engine.
- **Live Gantt chart** rendered on a Tkinter canvas — every CPU burst is drawn to scale on a time axis, with a stable colour per process across runs.
- **Per-process metrics table** showing arrival, burst, start, finish, waiting and turnaround time.
- **Summary statistics** — average waiting time, average turnaround time, and total makespan.
- **Workload editor** — add processes by hand, remove individual entries, clear the list, or load a built-in sample workload of six processes.
- **Configurable time quantum** for Round Robin, shown only when that algorithm is selected.
- **Zero dependencies** — Python standard library only.

## Implemented algorithms

| Algorithm | Data structure | Preemptive | Notes |
|---|---|---|---|
| First-Come-First-Served (FCFS) | `collections.deque` (FIFO) | No | Runs processes strictly in arrival order. |
| Shortest Job First (SJF) | `heapq` min-heap on burst time | No | Minimises average waiting time, but can starve long jobs. |
| Priority | `heapq` min-heap on priority | No | Lower number = higher priority. |
| Round Robin | `collections.deque` (circular) | Yes | Each process runs for at most one time quantum, then requeues. |

Both heap-based schedulers push an `itertools.count()` tiebreaker alongside the sort key, so processes with equal burst time or equal priority fall back to insertion order instead of raising a comparison error on the `Process` object.

## Architecture

The scheduling engine is fully decoupled from the GUI — every class below the `Scheduler` abstraction can be imported and tested without Tkinter.

```
Process (dataclass)         Encapsulates pid, arrival, burst, priority, and derived
                            state (remaining time, start/completion time, waiting time).
                            Exposes turnaround_time as a computed property.

ProcessState (Enum)         NEW -> READY -> RUNNING -> COMPLETED

Scheduler (ABC)             Owns the shared simulation loop: admits processes as the
                            clock reaches their arrival time, advances the clock, and
                            records a (pid, name, start, end) slice for every CPU burst.
                            Subclasses implement only _push / _pop / _has_ready / _run_slice.

  |- FCFSScheduler
  |- SJFScheduler
  |- PriorityScheduler
  +- RoundRobinScheduler

TaskManagerGUI (tk.Tk)      Workload editor, algorithm selector, results table,
                            and the Gantt chart renderer.
```

The base class also handles the idle case: when no process is ready but work remains pending, the clock jumps forward to the next arrival time rather than spinning.

## Running it

Requires Python 3.8+ with Tkinter (bundled with the standard Windows and macOS installers; on Debian/Ubuntu install `python3-tk`).

```bash
git clone https://github.com/sebastiansiju/dynamic-task-manager-simulator.git
```

```bash
cd dynamic-task-manager-simulator && python dynamic_task_manager.py
```

## Usage

1. Click **Load sample workload** for six ready-made processes, or fill in the *Add Process* form and click **Add**.
2. Choose an algorithm from the dropdown. If you pick **Round Robin**, a *Time quantum* field appears — the default is 3.
3. Click **▶ Run Simulation**.
4. Read the results: the summary line gives the averages, the table gives per-process figures, and the Gantt chart shows exactly when each process held the CPU.

Re-run with a different algorithm on the same workload to compare — Round Robin will typically show more, shorter slices than FCFS, and SJF will usually beat FCFS on average waiting time.

### Input rules

- Arrival time must be an integer `>= 0`.
- Burst time must be an integer `> 0`.
- Priority is any integer; **lower values mean higher priority**.
- Leaving the name blank auto-generates one (`Task1`, `Task2`, …).

## Sample workload

| PID | Name | Arrival | Burst | Priority |
|---|---|---|---|---|
| 1 | Compile | 0 | 8 | 3 |
| 2 | WebSrv | 1 | 4 | 1 |
| 3 | Backup | 2 | 9 | 4 |
| 4 | DBQuery | 3 | 5 | 2 |
| 5 | Render | 4 | 12 | 5 |
| 6 | Ping | 5 | 2 | 1 |

## Running the tests

The engine is decoupled from the GUI, so it is tested without a display:

```bash
python -m unittest discover -s tests -t . -v
```

28 tests cover the `Process` dataclass and its computed turnaround time,
including rejecting a non-positive burst time or a negative arrival time
(either would corrupt the simulation clock), each scheduler's ordering rule,
the heap tiebreakers that keep equal keys from comparing `Process` objects,
Round Robin's quantum slicing and requeueing (including rejecting a
non-positive quantum, which would otherwise hang the simulation loop, and
computing waiting_time as the total time spent ready across every
preemption, not just the wait before its first slice), and the idle-gap
clock jump. A cross-scheduler block asserts invariants that must
hold for all four: total CPU time equals total burst time, no process starts
before it arrives, timeline slices never overlap, and each completion time is
the end of that process's last slice.

## Project structure

```
dynamic-task-manager-simulator/
├── dynamic_task_manager.py         # Scheduling engine + Tkinter GUI
├── tests/
│   └── test_scheduling_engine.py   # unittest coverage for the schedulers
├── .github/workflows/tests.yml     # CI: runs the suite on every push
├── README.md
└── .gitignore
```

## License

MIT
