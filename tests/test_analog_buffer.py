import unittest
from mixed_mode_simulator import sample_and_hold
from mixed_mode_simulator import events
import simpy


class TestBuffer(unittest.TestCase):

    def setUp(self) -> None:
        self.env = simpy.Environment()
        self.buffer_length = 5
        self.test_buffer = sample_and_hold.AnalogBuffer(self.env, 0, "ring", 1, self.buffer_length, 0, debug=True)
        self.test_events = [events.DownstreamEvent(simpy.Event(self.env), {"event_number": 1, "scintillator": 1,
                                                                           "event_length": 1}, {"sample_index": i})
                            for i in range(10)]

    def test_single_event(self):
        self.env.process(self.test_buffer.buffer_in(self.test_events[0]))
        self.env.run()
        self.assertEqual(self.env.now, self.buffer_length)

    def multiple_event_helper(self, num_events):
        """
        Helper generator function for multi event test
        :return:
        """
        for i in range(num_events):
            self.env.process(self.test_buffer.buffer_in(self.test_events[i]))
            yield self.env.timeout(1)

    def test_multiple_events(self):
        self.env.process(self.multiple_event_helper(5))
        self.env.run()
        self.assertEqual(self.buffer_length + 4, self.env.now)


if __name__ == '__main__':
    unittest.main()
