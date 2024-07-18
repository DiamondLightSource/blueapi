from services.generated.services.proto.worker_pb2_grpc import WorkerService


# todo complete this
class WorkerClient(WorkerService):
    def __init__(self) -> None:
        super().__init__()
