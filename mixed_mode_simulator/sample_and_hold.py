from __future__ import annotations
import simpy
import itertools
import numpy as np
from events import *


class AnalogBuffer:

    def __init__(self, env: simpy.Environment, buffer_index: int, buffer_location: str, sample_length: float,
                 buffer_length: int, chain_delay: float,
                 debug: bool = False) -> AnalogBuffer:
        """
        Creates an analog buffer with a parameterizable number of individual memory units and sample lengths.
        This class can be used to create both the long tail buffers and initial ring buffers.

        :param buffer_index: unique index count of the buffer in its respective location.
        :param buffer_location: String either "ring" or "tail" to determine the location of this buffer object
        :param env: simpy environment
        :param buffer_length: number of chained S&H units
        :param sample_length: amount of time taken per sample unit
        :param chain_delay: parameterized delay associated with parasitics of chaining S&H units
        :param amux: Downstream Amux object that this is connected to, all buffers in one layer should share this object.
        :param debug: Boolean flag for printing debug messages, default = `False`

        """
        self.amux = None
        self.buffer_index = buffer_index
        self.buffer_location = buffer_location
        self.env = env
        self.sample_length = sample_length
        self.buffer_length = buffer_length
        self.chain_delay = chain_delay
        self.debug = debug
        self.downstream_events_processed = 0

    def set_amux(self, amux: 'AMUX'):
        self.amux = amux

    def sample_and_hold_unit(self, event: DownstreamEvent, unit_index):
        """
        A single memory unit delay simulation

        :param event: DownstreamEvent object that carries event information.
        :param unit_index: accounting variable, used to show where in the chain of S&H units is this located.
        :return: None
        """
        if self.debug:
            print(
                f'{self.env.now*1e6:.3f} us\tAt s&h unit {self.buffer_location}:{self.buffer_index}:{unit_index}, event {event.detection_event_info["event_number"]}, sample index '
                f'{event.event_info["sample_index"]} starting processing '
                f'at time {self.env.now}, amux is {self.amux}')

        yield self.env.timeout(self.sample_length)

        if self.debug:
            print(
                f'{self.env.now*1e6:.3f} us\tAt s&h unit {self.buffer_location}:{self.buffer_index}:{unit_index}, event {event.detection_event_info["event_number"]}, sample index'
                f'{event.event_info["sample_index"]} finished processing '
                f'at time {self.env.now}., amux is {self.amux}')

    def remove_from_buffer(self, event: DownstreamEvent, mux: 'AMUX'):
        """
        This processes the removal and chaining of an event from a buffer to the next analog multiplexer. The
        AMUX will deal with the decision to either drop or accept this event. This function always offloads the event
        and keeps count of number of events removed.

        :param event: DownstreamEvent object that carries event information.
        :param mux: Multiplexer object that is used to chain the event.
        :return: None
        """
        if self.debug:
            print(f"{self.env.now*1e6:.3f} us\tAt remove from buffer @ {self.buffer_location}:{self.buffer_index}")
        if mux is None:
            # event.event.fail(Exception(
            #     f"No downstream channels available at buffer located at {self.buffer_location}:{self.buffer_index}"))
            if self.debug:
                print(f"{self.env.now*1e6:.3f} us\tEvent failed, no downstream mux found!")

                print(f'Event {event.detection_event_info["event_number"]}, sample {event.event_info["sample_index"]} '
                      f'is out of the tail buffer')
            self.downstream_events_processed += 1

        else:
            yield self.env.process(mux.entry_point(self.buffer_index, event))

    def buffer_in(self, event: DownstreamEvent):
        """
        Creates an analog buffer by chaining sample and hold units.

        :param event: DownstreamEvent object that carries event information.
        :return: None
        """
        if self.debug:
            print(f"{self.env.now*1e6:.3f} us\tIn buffer {self.buffer_location}:{self.buffer_index}, amux is {self.amux}")
        for i in range(self.buffer_length):
            yield self.env.process(self.sample_and_hold_unit(event, i))
            yield self.env.timeout(self.chain_delay)  # Adding chaining delay overhead

        if self.debug:
            print(
                f"{self.env.now*1e6:.3f} us\tcall to remove from buf @ {self.buffer_location}:{self.buffer_index}, amux is {self.amux}")
        try:
            process_event = self.env.process(self.remove_from_buffer(event, self.amux))
            yield process_event
            if not process_event.ok:
                raise process_event.value  # Manually raise the exception if the process failed.
        except Exception as e:
            print(f"{self.env.now*1e6:.3f} us\tCaught failed event {e}, simulation continues")
