import os
import time

from pydantic import BaseModel, Field

from stembot.enums import TaskStatus

TASK_TIMEOUT_SECS = 60

class Task(BaseModel):
    """Represents a task to be executed by an agent."""
    touch_time:  float        = Field(default=0.0)
    expire_time: float | None = Field(default=0.0)
    every_secs:  int          = Field()
    pid:         int | None   = Field(default=None)
    call:        callable     = Field()
    status:      TaskStatus   = Field(default=TaskStatus.STOPPED)
    objuuid:     str | None   = Field(default=None)
    coluuid:     str | None   = Field(default=None)

    def run(self):
        self.status      = TaskStatus.RUNNING
        self.pid         = os.getpid()
        self.expire_time = time.time() + TASK_TIMEOUT_SECS

    def stop(self):
        self.status      = TaskStatus.STOPPED
        self.pid         = None
        self.expire_time = None

    def touch(self):
        self.touch_time = time.time() + self.every_secs
        if time.time() > self.expire_time:
            self.stop()
