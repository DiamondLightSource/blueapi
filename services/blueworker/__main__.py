from concurrent import futures

import grpc
from services.blueworker.service import ExtendedWorkerServiceServicer
from services.generated.services.proto.worker_pb2_grpc import (
    add_WorkerServiceServicer_to_server,
)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    add_WorkerServiceServicer_to_server(ExtendedWorkerServiceServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
