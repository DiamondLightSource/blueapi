import asyncio

import grpc
from bluesky.run_engine import get_bluesky_event_loop
from services.blueworker.task_worker import TaskWorker
from services.generated.services.proto.worker_pb2_grpc import WorkerServiceServicer


class ExtendedWorkerServiceServicer(WorkerServiceServicer):
    def __init__(self):
        loop = get_bluesky_event_loop()
        asyncio.set_event_loop(loop)
        self.worker = TaskWorker()
        self.worker.run()
        super().__init__()

    def GetTasks(self, request, context):
        context.set_code(grpc.StatusCode.OK)
        return super().GetTasks(request, context)
