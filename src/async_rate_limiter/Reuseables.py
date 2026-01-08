from collections import deque
from typing import Generic, TypeVar

T = TypeVar("T")


# A simple fixed max size ring buffer implementation for storing elements.
class RingBuffer(Generic[T]):
    def __init__(self, size: int):
        self.size = size
        # to store tuples of (timestamp, weight)
        self.buffer: deque[T] = deque()

    """ Push an item to the ring buffer. If the buffer is full, the oldest item is removed. 
        param item: the item to push to the buffer.
        In case the buffer is full, the oldest item is removed to make space for the new item.
    """

    def push(self, item: T) -> None:
        if self.is_full():
            self.buffer.popleft()
        self.buffer.append(item)

    def pop(self) -> bool:
        if self.is_empty():
            return False
        else:
            self.buffer.popleft()
            return True

    def is_full(self) -> bool:
        return len(self.buffer) == self.size

    def is_empty(self) -> bool:
        return len(self.buffer) == 0

    def get_front(self) -> T:
        if self.is_empty():
            raise IndexError("RingBuffer is empty")
        return self.buffer[0]

    def __len__(self) -> int:
        return len(self.buffer)
