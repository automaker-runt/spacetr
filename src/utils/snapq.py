# snapq
import queue

class SnapshotQueue(queue.Queue):
    
    def snapshot(self):
        with self.mutex:
            return list(self.queue)
