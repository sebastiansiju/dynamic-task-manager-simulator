"""Unit tests for the scheduling engine in dynamic_task_manager.py.

These exercise only the non-GUI classes -- Process, ProcessState and the
Scheduler subclasses -- which are deliberately decoupled from Tkinter.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dynamic_task_manager import (  # noqa: E402
    FCFSScheduler,
    PriorityScheduler,
    Process,
    ProcessState,
    RoundRobinScheduler,
    SJFScheduler,
)


def build(spec):
    """spec: [(pid, name, arrival, burst, priority), ...]"""
    return [Process(pid=p, name=n, arrival_time=a, burst_time=b, priority=pr)
            for p, n, a, b, pr in spec]


def order_of(scheduler):
    """PIDs in the order they first got the CPU."""
    seen, out = set(), []
    for pid, _name, _start, _end in scheduler.timeline:
        if pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out


class ProcessTests(unittest.TestCase):
    def test_starts_new_with_full_remaining_time(self):
        p = Process(pid=1, name="A", arrival_time=0, burst_time=7)
        self.assertEqual(p.remaining_time, 7)
        self.assertIs(p.state, ProcessState.NEW)
        self.assertIsNone(p.start_time)
        self.assertIsNone(p.completion_time)

    def test_turnaround_is_none_until_completion(self):
        p = Process(pid=1, name="A", arrival_time=2, burst_time=5)
        self.assertIsNone(p.turnaround_time)
        p.completion_time = 11
        self.assertEqual(p.turnaround_time, 9)

    def test_default_priority_is_zero(self):
        self.assertEqual(Process(pid=1, name="A", arrival_time=0, burst_time=1).priority, 0)


class FCFSTests(unittest.TestCase):
    def test_runs_in_arrival_order(self):
        s = FCFSScheduler(build([
            (1, "A", 0, 4, 0), (2, "B", 1, 3, 0), (3, "C", 2, 2, 0),
        ]))
        s.run()
        self.assertEqual(order_of(s), [1, 2, 3])
        self.assertEqual(s.time, 9)

    def test_arrival_order_wins_over_shorter_jobs(self):
        s = FCFSScheduler(build([(1, "Long", 0, 10, 0), (2, "Short", 1, 1, 0)]))
        s.run()
        self.assertEqual(order_of(s), [1, 2])

    def test_idle_gap_advances_clock_to_next_arrival(self):
        s = FCFSScheduler(build([(1, "A", 0, 2, 0), (2, "B", 10, 3, 0)]))
        s.run()
        second = [t for t in s.timeline if t[0] == 2][0]
        self.assertEqual(second[2], 10, "clock should jump to the idle gap's end")
        self.assertEqual(s.time, 13)

    def test_waiting_and_turnaround_are_computed(self):
        s = FCFSScheduler(build([(1, "A", 0, 5, 0), (2, "B", 0, 3, 0)]))
        s.run()
        by_pid = {p.pid: p for p in s.completed}
        self.assertEqual(by_pid[1].waiting_time, 0)
        self.assertEqual(by_pid[1].turnaround_time, 5)
        self.assertEqual(by_pid[2].waiting_time, 5)
        self.assertEqual(by_pid[2].turnaround_time, 8)

    def test_every_process_completes(self):
        procs = build([(i, f"P{i}", i, 3, 0) for i in range(1, 6)])
        s = FCFSScheduler(procs)
        s.run()
        self.assertEqual(len(s.completed), 5)
        for p in s.completed:
            self.assertIs(p.state, ProcessState.COMPLETED)
            self.assertEqual(p.remaining_time, 0)


class SJFTests(unittest.TestCase):
    def test_shortest_burst_runs_first(self):
        # All three arrive at t=0, so all are queued before the first pick:
        # bursts 9/2/5 must run shortest-first as 2, 3, 1.
        s = SJFScheduler(build([
            (1, "Long", 0, 9, 0), (2, "Short", 0, 2, 0), (3, "Mid", 0, 5, 0),
        ]))
        s.run()
        self.assertEqual(order_of(s), [2, 3, 1])

    def test_queue_reorders_among_available_processes(self):
        s = SJFScheduler(build([
            (1, "First", 0, 2, 0), (2, "Long", 0, 8, 0), (3, "Tiny", 1, 1, 0),
        ]))
        s.run()
        self.assertEqual(order_of(s), [1, 3, 2])

    def test_equal_bursts_fall_back_to_insertion_order(self):
        """Without a tiebreaker the heap would try to compare Process objects."""
        s = SJFScheduler(build([(1, "A", 0, 4, 0), (2, "B", 0, 4, 0), (3, "C", 0, 4, 0)]))
        s.run()
        self.assertEqual(order_of(s), [1, 2, 3])


class PriorityTests(unittest.TestCase):
    def test_lower_number_runs_first(self):
        # All arrive at t=0, so priorities 9/1/5 must run as 2, 3, 1.
        s = PriorityScheduler(build([
            (1, "Low", 0, 3, 9), (2, "High", 0, 3, 1), (3, "Mid", 0, 3, 5),
        ]))
        s.run()
        self.assertEqual(order_of(s), [2, 3, 1])

    def test_equal_priorities_fall_back_to_insertion_order(self):
        s = PriorityScheduler(build([(1, "A", 0, 2, 4), (2, "B", 0, 2, 4)]))
        s.run()
        self.assertEqual(order_of(s), [1, 2])


class RoundRobinTests(unittest.TestCase):
    def test_no_slice_exceeds_the_quantum(self):
        s = RoundRobinScheduler(build([
            (1, "A", 0, 10, 0), (2, "B", 0, 7, 0), (3, "C", 0, 4, 0),
        ]), quantum=3)
        s.run()
        for _pid, _name, start, end in s.timeline:
            self.assertLessEqual(end - start, 3)

    def test_long_process_is_requeued_and_interleaved(self):
        s = RoundRobinScheduler(build([(1, "A", 0, 6, 0), (2, "B", 0, 6, 0)]), quantum=2)
        s.run()
        self.assertEqual([pid for pid, _n, _s, _e in s.timeline], [1, 2, 1, 2, 1, 2])

    def test_total_cpu_time_equals_total_burst(self):
        procs = build([(1, "A", 0, 10, 0), (2, "B", 1, 7, 0), (3, "C", 2, 4, 0)])
        total_burst = sum(p.burst_time for p in procs)
        s = RoundRobinScheduler(procs, quantum=3)
        s.run()
        self.assertEqual(sum(e - st for _p, _n, st, e in s.timeline), total_burst)

    def test_quantum_larger_than_every_burst_behaves_like_fcfs(self):
        spec = [(1, "A", 0, 2, 0), (2, "B", 1, 3, 0), (3, "C", 2, 1, 0)]
        rr = RoundRobinScheduler(build(spec), quantum=100)
        rr.run()
        fcfs = FCFSScheduler(build(spec))
        fcfs.run()
        self.assertEqual(order_of(rr), order_of(fcfs))
        self.assertEqual(rr.time, fcfs.time)

    def test_all_processes_complete(self):
        s = RoundRobinScheduler(build([(1, "A", 0, 5, 0), (2, "B", 3, 5, 0)]), quantum=2)
        s.run()
        self.assertEqual(len(s.completed), 2)
        for p in s.completed:
            self.assertEqual(p.remaining_time, 0)
            self.assertIsNotNone(p.completion_time)

    def test_arrival_during_a_slice_is_queued_ahead_of_the_preempted_process(self):
        """A process that arrives while another is mid-slice must get its
        turn as soon as that slice ends, not after the preempted process
        is allowed to run a second consecutive slice ahead of it."""
        s = RoundRobinScheduler(build([
            (1, "A", 0, 10, 0), (2, "B", 2, 3, 0),
        ]), quantum=3)
        s.run()
        self.assertEqual(order_of(s), [1, 2])
        self.assertEqual(s.timeline[0], (1, "A", 0, 3))
        self.assertEqual(s.timeline[1], (2, "B", 3, 6))

    def test_non_positive_quantum_is_rejected(self):
        """A quantum <= 0 would never shrink remaining_time to zero, hanging
        run() in an infinite requeue loop -- reject it up front instead."""
        procs = build([(1, "A", 0, 5, 0)])
        for bad_quantum in (0, -1):
            with self.subTest(quantum=bad_quantum):
                self.assertRaises(ValueError, RoundRobinScheduler, procs, quantum=bad_quantum)


class CrossSchedulerTests(unittest.TestCase):
    SPEC = [(1, "A", 0, 6, 2), (2, "B", 2, 4, 1), (3, "C", 4, 8, 3)]

    def schedulers(self):
        return [
            FCFSScheduler(build(self.SPEC)),
            SJFScheduler(build(self.SPEC)),
            PriorityScheduler(build(self.SPEC)),
            RoundRobinScheduler(build(self.SPEC), quantum=3),
        ]

    def test_makespan_matches_total_burst_when_there_are_no_idle_gaps(self):
        total = sum(b for _p, _n, _a, b, _pr in self.SPEC)
        for s in self.schedulers():
            with self.subTest(scheduler=s.name):
                s.run()
                self.assertEqual(s.time, total)

    def test_no_process_starts_before_it_arrives(self):
        for s in self.schedulers():
            with self.subTest(scheduler=s.name):
                s.run()
                arrivals = {p.pid: p.arrival_time for p in s.completed}
                for pid, _n, start, _e in s.timeline:
                    self.assertGreaterEqual(start, arrivals[pid])

    def test_timeline_slices_never_overlap(self):
        for s in self.schedulers():
            with self.subTest(scheduler=s.name):
                s.run()
                spans = sorted((st, e) for _p, _n, st, e in s.timeline)
                for (_, prev_end), (next_start, _) in zip(spans, spans[1:]):
                    self.assertLessEqual(prev_end, next_start)

    def test_completion_time_is_the_end_of_the_last_slice(self):
        for s in self.schedulers():
            with self.subTest(scheduler=s.name):
                s.run()
                last_end = {}
                for pid, _n, _st, end in s.timeline:
                    last_end[pid] = max(last_end.get(pid, 0), end)
                for p in s.completed:
                    self.assertEqual(p.completion_time, last_end[p.pid])

    def test_single_process_workload(self):
        for cls in (FCFSScheduler, SJFScheduler, PriorityScheduler):
            with self.subTest(scheduler=cls.name):
                s = cls(build([(1, "Solo", 0, 5, 0)]))
                s.run()
                self.assertEqual(s.time, 5)
                self.assertEqual(len(s.completed), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
